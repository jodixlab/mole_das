from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from mole_ftir_validation_v1 import build_validation_package, normalize_config, write_validation_exports


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

    def test_write_validation_exports_preserves_snapshot_and_exclusion_fields(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            payload = {
                "status": "Available",
                "overall_status": "PASS",
                "source": "LOCKED_REVIEW_SNAPSHOT",
                "review_locked": True,
                "review_lock_by": "peer_scientist",
                "review_lock_iso": "2026-04-10T18:05:00Z",
                "review_snapshot": {
                    "json_path": str(root / "locked.json"),
                    "windows_csv_path": str(root / "locked_windows.csv"),
                    "method301_csv_path": str(root / "locked_method301.csv"),
                    "snapshot_iso": "2026-04-10T18:05:00Z",
                    "snapshot_by": "peer_scientist",
                    "source": "LOCK_REVIEW",
                },
                "signoff": {
                    "decision": "ACCEPTED",
                    "basis": "FORMAL_METHOD_301_PASS",
                    "by": "peer_scientist",
                    "role": "Peer Scientist",
                    "iso": "2026-04-10T18:15:00Z",
                    "note": "Accepted for formal Method 301 reporting.",
                },
                "aligned_rows": [
                    {
                        "run_no": 1,
                        "label": "Run 1",
                        "window_start_iso": "2026-04-10T12:00:00Z",
                        "window_end_iso": "2026-04-10T12:20:00Z",
                        "analyte": "NO",
                        "row_key": "1|NO|2026-04-10T12:00:00Z|2026-04-10T12:20:00Z",
                        "mole_count": 4,
                        "ftir_count": 4,
                        "mole_avg": 10.0,
                        "ftir_avg": 9.5,
                        "difference": 0.5,
                        "paired": True,
                        "status": "PAIRED",
                        "excluded": True,
                        "exclusion_reason": "startup stabilization",
                        "reviewer": "peer_scientist",
                        "updated_iso": "2026-04-10T18:00:00Z",
                    }
                ],
                "method301": [
                    {
                        "analyte": "NO",
                        "mode": "METHOD_301_FORMAL",
                        "paired_window_count": 5,
                        "excluded_window_count": 1,
                        "mole_mean": 10.0,
                        "ftir_mean": 9.5,
                        "mean_difference": 0.5,
                        "relative_bias_pct": 5.263157,
                        "correction_factor": 0.95,
                        "difference_sd": 0.1,
                        "t_statistic": 1.0,
                        "t_critical_95_two_sided": 2.571,
                        "candidate_variance": 0.01,
                        "validated_variance": 0.02,
                        "f_statistic": 2.0,
                        "f_critical_95": 4.28,
                        "bias_status": "PASS",
                        "precision_status": "PASS",
                        "overall_status": "PASS",
                        "note": "frozen",
                    }
                ],
            }

            out = write_validation_exports(
                payload,
                json_path=root / "locked.json",
                windows_csv_path=root / "locked_windows.csv",
                method301_csv_path=root / "locked_method301.csv",
            )

            self.assertTrue(Path(out["json_path"]).exists())
            self.assertTrue(Path(out["windows_csv_path"]).exists())
            self.assertTrue(Path(out["method301_csv_path"]).exists())
            snapshot = json.loads((root / "locked.json").read_text(encoding="utf-8"))
            self.assertEqual(snapshot.get("source"), "LOCKED_REVIEW_SNAPSHOT")
            self.assertTrue(snapshot.get("review_locked"))
            self.assertEqual((snapshot.get("review_snapshot") or {}).get("snapshot_by"), "peer_scientist")
            self.assertEqual((snapshot.get("signoff") or {}).get("decision"), "ACCEPTED")
            self.assertEqual((snapshot.get("signoff") or {}).get("basis"), "FORMAL_METHOD_301_PASS")
            windows_csv = (root / "locked_windows.csv").read_text(encoding="utf-8")
            self.assertIn("startup stabilization", windows_csv)
            method_csv = (root / "locked_method301.csv").read_text(encoding="utf-8")
            self.assertIn("excluded_window_count", method_csv)


if __name__ == "__main__":
    unittest.main()
