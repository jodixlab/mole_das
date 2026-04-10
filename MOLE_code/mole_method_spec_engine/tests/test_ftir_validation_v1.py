from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from mole_ftir_validation_v1 import build_validation_package, normalize_config


class FtirValidationTests(unittest.TestCase):
    def test_formal_validation_passes_for_six_paired_windows(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            ftir_csv = root / "ftir.csv"
            raw_samples = root / "raw_samples.jsonl"

            base = datetime(2026, 4, 10, 12, 0, 0, tzinfo=timezone.utc)
            ftir_lines = ["timestamp,NO"]
            raw_lines = []
            actual_runs = []

            for idx in range(6):
                start = base + timedelta(minutes=idx * 25)
                end = start + timedelta(minutes=20)
                actual_runs.append({
                    "run_no": idx + 1,
                    "start_ts_iso": start.isoformat().replace("+00:00", "Z"),
                    "end_ts_iso": end.isoformat().replace("+00:00", "Z"),
                })
                for step in range(4):
                    ts = start + timedelta(minutes=(step * 5) + 1)
                    value = 50.0 + idx + (step * 0.25)
                    ts_iso = ts.isoformat().replace("+00:00", "Z")
                    ftir_lines.append(f"{ts_iso},{value}")
                    raw_lines.append(json.dumps({
                        "ts_utc": ts_iso,
                        "channel_id": "NO",
                        "value_eng": value,
                        "quality_flags": {"comm_ok": True, "decode_ok": True},
                    }))

            ftir_csv.write_text("\n".join(ftir_lines) + "\n", encoding="utf-8")
            raw_samples.write_text("\n".join(raw_lines) + "\n", encoding="utf-8")

            cfg = normalize_config({
                "enabled": True,
                "validation_mode": "METHOD_301_FORMAL",
                "ftir_file_path": str(ftir_csv),
                "ftir_timestamp_column": "timestamp",
                "ftir_delimiter": "CSV",
                "analytes": ["NO"],
            })
            payload = build_validation_package(
                cfg,
                run_aggregation={"actual_runs": actual_runs},
                raw_samples_path=raw_samples,
            )

            self.assertEqual(payload.get("status"), "Available")
            self.assertEqual(payload.get("overall_status"), "PASS")
            self.assertEqual(payload.get("paired_window_count"), 6)
            self.assertEqual(len(payload.get("method301") or []), 1)
            row = (payload.get("method301") or [])[0]
            self.assertEqual(row.get("analyte"), "NO")
            self.assertEqual(row.get("bias_status"), "PASS")
            self.assertEqual(row.get("precision_status"), "PASS")
            self.assertEqual(row.get("overall_status"), "PASS")

    def test_missing_raw_samples_yields_gap_without_fake_stats(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            ftir_csv = root / "ftir.csv"
            ftir_csv.write_text("timestamp,NO\n2026-04-10T12:00:00Z,10\n", encoding="utf-8")
            cfg = normalize_config({
                "enabled": True,
                "validation_mode": "METHOD_301_INFORMED_COMPARISON",
                "ftir_file_path": str(ftir_csv),
                "ftir_timestamp_column": "timestamp",
                "analytes": ["NO"],
            })
            payload = build_validation_package(
                cfg,
                run_aggregation={"actual_runs": []},
                raw_samples_path=root / "missing_raw_samples.jsonl",
            )
            self.assertEqual(payload.get("status"), "Gap")
            self.assertEqual(payload.get("paired_window_count"), 0)
            self.assertEqual(payload.get("method301"), [])

    def test_excluded_window_is_removed_from_method301_counts_and_reported(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            ftir_csv = root / "ftir.csv"
            raw_samples = root / "raw_samples.jsonl"

            base = datetime(2026, 4, 10, 12, 0, 0, tzinfo=timezone.utc)
            ftir_lines = ["timestamp,NO"]
            raw_lines = []
            actual_runs = []

            for idx in range(6):
                start = base + timedelta(minutes=idx * 25)
                end = start + timedelta(minutes=20)
                actual_runs.append({
                    "run_no": idx + 1,
                    "start_ts_iso": start.isoformat().replace("+00:00", "Z"),
                    "end_ts_iso": end.isoformat().replace("+00:00", "Z"),
                })
                for step in range(4):
                    ts = start + timedelta(minutes=(step * 5) + 1)
                    value = 60.0 + idx
                    ts_iso = ts.isoformat().replace("+00:00", "Z")
                    ftir_lines.append(f"{ts_iso},{value}")
                    raw_lines.append(json.dumps({
                        "ts_utc": ts_iso,
                        "channel_id": "NO",
                        "value_eng": value,
                        "quality_flags": {"comm_ok": True, "decode_ok": True},
                    }))

            ftir_csv.write_text("\n".join(ftir_lines) + "\n", encoding="utf-8")
            raw_samples.write_text("\n".join(raw_lines) + "\n", encoding="utf-8")

            excluded_key = "1|NO|2026-04-10T12:00:00Z|2026-04-10T12:20:00Z"
            cfg = normalize_config({
                "enabled": True,
                "validation_mode": "METHOD_301_FORMAL",
                "ftir_file_path": str(ftir_csv),
                "ftir_timestamp_column": "timestamp",
                "ftir_delimiter": "CSV",
                "analytes": ["NO"],
                "review_notes": "Reviewer excluded first window.",
                "reviewer": "peer_scientist",
                "review_locked": True,
                "review_lock_by": "peer_scientist",
                "review_lock_iso": "2026-04-10T18:05:00Z",
                "exclusions": {
                    excluded_key: {
                        "reason": "startup stabilization",
                        "reviewer": "peer_scientist",
                        "updated_iso": "2026-04-10T18:00:00Z",
                    }
                },
            })
            payload = build_validation_package(
                cfg,
                run_aggregation={"actual_runs": actual_runs},
                raw_samples_path=raw_samples,
            )

            self.assertEqual(payload.get("excluded_count"), 1)
            self.assertEqual(len(payload.get("excluded_rows") or []), 1)
            self.assertEqual((payload.get("excluded_rows") or [])[0].get("reason"), "startup stabilization")
            self.assertEqual(payload.get("review_notes"), "Reviewer excluded first window.")
            self.assertTrue(payload.get("review_locked"))
            self.assertEqual(payload.get("review_lock_by"), "peer_scientist")
            row = (payload.get("method301") or [])[0]
            self.assertEqual(row.get("paired_window_count"), 5)
            self.assertEqual(row.get("excluded_window_count"), 1)
            self.assertEqual(row.get("overall_status"), "INSUFFICIENT_FORMAL_WINDOWS")


if __name__ == "__main__":
    unittest.main()
