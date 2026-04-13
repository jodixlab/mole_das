from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from mole_ftir_validation_v1 import build_validation_package, load_ftir_records, normalize_config, write_validation_exports


class FtirValidationTests(unittest.TestCase):
    def test_live_execution_metadata_flows_into_comparison_sets(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            ftir_csv = root / "ftir.csv"
            raw_samples = root / "raw_samples.jsonl"
            base = datetime(2026, 4, 10, 12, 0, 0, tzinfo=timezone.utc)
            ftir_csv.write_text(
                "\n".join([
                    "timestamp,NO",
                    "2026-04-10T12:01:00Z,10.0",
                    "2026-04-10T12:06:00Z,10.5",
                ]) + "\n",
                encoding="utf-8",
            )
            raw_samples.write_text(
                "\n".join([
                    json.dumps({
                        "ts_utc": "2026-04-10T12:01:00Z",
                        "channel_id": "NO",
                        "value_eng": 10.0,
                        "quality_flags": {"comm_ok": True, "decode_ok": True},
                    }),
                    json.dumps({
                        "ts_utc": "2026-04-10T12:06:00Z",
                        "channel_id": "NO",
                        "value_eng": 10.5,
                        "quality_flags": {"comm_ok": True, "decode_ok": True},
                    }),
                ]) + "\n",
                encoding="utf-8",
            )
            cfg = normalize_config({
                "enabled": True,
                "validation_mode": "METHOD_301_INFORMED_COMPARISON",
                "ftir_file_path": str(ftir_csv),
                "ftir_timestamp_column": "timestamp",
                "analytes": ["NO"],
                "execution": {
                    "enabled": True,
                    "profile": "SESSION_RUNS",
                    "comparison_set_policy": "RUN_EQUALS_SET",
                    "purge_minutes_required": 5.0,
                    "require_purge_event": True,
                    "require_bias_event": True,
                    "purge_due_after_run_no": None,
                    "bias_due_after_run_no": 1,
                    "live_review_status": "BIAS_DUE",
                },
            })
            payload = build_validation_package(
                cfg,
                run_aggregation={"actual_runs": [{
                    "run_no": 7,
                    "start_ts_iso": "2026-04-10T12:00:00Z",
                    "end_ts_iso": "2026-04-10T12:20:00Z",
                    "comparison_set_no": 7,
                    "comparison_set_key": "RUN_SET_07",
                    "source": "LIVE_SESSION_RUNS",
                    "label": "Run 7",
                    "execution_profile": "SESSION_RUNS",
                    "comparison_set_policy": "RUN_EQUALS_SET",
                    "target_run_minutes": 20.0,
                    "purge_minutes_required": 5.0,
                    "purge_required": True,
                    "bias_required": True,
                    "cadence_status": "BIAS_DUE",
                    "cadence_note": "Bias logging is due after Run 7.",
                    "review_live_status": "BIAS_DUE",
                }]},
                raw_samples_path=raw_samples,
            )
            comparison_sets = payload.get("comparison_sets") or []
            self.assertEqual(len(comparison_sets), 1)
            self.assertEqual(comparison_sets[0].get("set_no"), 7)
            self.assertEqual(comparison_sets[0].get("set_key"), "RUN_SET_07")
            self.assertEqual(comparison_sets[0].get("comparison_set_policy"), "RUN_EQUALS_SET")
            self.assertEqual(comparison_sets[0].get("cadence_status"), "BIAS_DUE")
            execution = payload.get("execution") or {}
            self.assertTrue(execution.get("enabled"))
            self.assertEqual(execution.get("profile"), "SESSION_RUNS")
            self.assertEqual(execution.get("comparison_set_count"), 1)
            self.assertEqual(execution.get("completed_run_count"), 1)
            self.assertEqual(execution.get("bias_due_after_run_no"), 1)
            self.assertEqual(execution.get("status"), "BIAS_DUE")

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
            self.assertEqual(len(payload.get("comparison_sets") or []), 6)
            self.assertEqual(payload.get("comparison_set_count"), 6)
            self.assertEqual(payload.get("included_comparison_set_count"), 6)
            self.assertEqual(payload.get("excluded_comparison_set_count"), 0)
            self.assertEqual(payload.get("acceptance_basis"), "FORMAL_METHOD_301")
            self.assertEqual(payload.get("acceptance_recommended_decision"), "ACCEPTED")
            delta_trace = payload.get("delta_trace") or {}
            self.assertEqual((delta_trace.get("counts") or {}).get("comparison_set_count"), 6)
            self.assertEqual(
                [row.get("stage") for row in (delta_trace.get("stages") or []) if isinstance(row, dict)],
                ["IMPORTED", "ALIGNED", "EXCLUDED", "FROZEN"],
            )
            first_set = (payload.get("comparison_sets") or [])[0]
            self.assertEqual(first_set.get("inclusion_status"), "INCLUDED")
            self.assertEqual(first_set.get("formal_basis"), "FORMAL_COMPARISON_SET")
            self.assertEqual(len(payload.get("method301") or []), 1)
            row = (payload.get("method301") or [])[0]
            self.assertEqual(row.get("analyte"), "NO")
            self.assertEqual(row.get("comparison_set_count"), 6)
            self.assertEqual(row.get("included_comparison_set_count"), 6)
            self.assertEqual(row.get("excluded_comparison_set_count"), 0)
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
            comparison_sets = payload.get("comparison_sets") or []
            self.assertEqual(len(comparison_sets), 6)
            self.assertEqual(payload.get("comparison_set_count"), 6)
            self.assertEqual(payload.get("included_comparison_set_count"), 5)
            self.assertEqual(payload.get("excluded_comparison_set_count"), 1)
            self.assertEqual(payload.get("acceptance_basis"), "METHOD_301_INFORMED_COMPARISON")
            self.assertEqual(payload.get("acceptance_recommended_decision"), "ACCEPTED")
            self.assertEqual(comparison_sets[0].get("inclusion_status"), "EXCLUDED")
            self.assertEqual(comparison_sets[0].get("excluded_row_count"), 1)
            row = (payload.get("method301") or [])[0]
            self.assertEqual(row.get("comparison_set_count"), 6)
            self.assertEqual(row.get("included_comparison_set_count"), 5)
            self.assertEqual(row.get("excluded_comparison_set_count"), 1)
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
                        "delta_trace_json_path": str(root / "locked_delta_trace.json"),
                        "delta_trace_csv_path": str(root / "locked_delta_trace.csv"),
                    },
                "signoff": {
                    "decision": "ACCEPTED",
                    "basis": "FORMAL_METHOD_301",
                    "by": "peer_scientist",
                    "role": "Peer Scientist",
                    "iso": "2026-04-10T18:15:00Z",
                    "note": "Accepted for formal Method 301 reporting.",
                },
                "aligned_rows": [
                    {
                        "comparison_set_no": 1,
                        "comparison_set_key": "1|2026-04-10T12:00:00Z|2026-04-10T12:20:00Z",
                        "comparison_set_status": "EXCLUDED",
                        "comparison_set_basis": "FORMAL_COMPARISON_SET",
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
                "comparison_sets": [
                    {
                        "set_no": 1,
                        "set_key": "1|2026-04-10T12:00:00Z|2026-04-10T12:20:00Z",
                        "run_no": 1,
                        "label": "Run 1",
                        "window_start_iso": "2026-04-10T12:00:00Z",
                        "window_end_iso": "2026-04-10T12:20:00Z",
                        "source": "ACTUAL_RUNS",
                        "validation_mode": "METHOD_301_FORMAL",
                        "review_state": "SIGNED_OFF",
                        "analytes": ["NO"],
                        "paired_analytes": [],
                        "excluded_analytes": ["NO"],
                        "row_count": 1,
                        "paired_row_count": 1,
                        "included_row_count": 0,
                        "included_paired_row_count": 0,
                        "excluded_row_count": 1,
                        "error_row_count": 0,
                        "warning_row_count": 0,
                        "inclusion_status": "EXCLUDED",
                        "formal_basis": "NO_COMPARISON_BASIS",
                        "note": "1 excluded analyte row(s)",
                    }
                ],
                "method301": [
                    {
                        "analyte": "NO",
                        "mode": "METHOD_301_FORMAL",
                        "comparison_set_count": 1,
                        "included_comparison_set_count": 0,
                        "excluded_comparison_set_count": 1,
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
                delta_trace_json_path=root / "locked_delta_trace.json",
                delta_trace_csv_path=root / "locked_delta_trace.csv",
            )

            self.assertTrue(Path(out["json_path"]).exists())
            self.assertTrue(Path(out["windows_csv_path"]).exists())
            self.assertTrue(Path(out["method301_csv_path"]).exists())
            self.assertTrue(Path(out["delta_trace_json_path"]).exists())
            self.assertTrue(Path(out["delta_trace_csv_path"]).exists())
            snapshot = json.loads((root / "locked.json").read_text(encoding="utf-8"))
            self.assertEqual(snapshot.get("source"), "LOCKED_REVIEW_SNAPSHOT")
            self.assertTrue(snapshot.get("review_locked"))
            self.assertEqual((snapshot.get("review_snapshot") or {}).get("snapshot_by"), "peer_scientist")
            self.assertEqual((snapshot.get("review_snapshot") or {}).get("delta_trace_json_path"), str(root / "locked_delta_trace.json"))
            self.assertEqual((snapshot.get("signoff") or {}).get("decision"), "ACCEPTED")
            self.assertEqual((snapshot.get("signoff") or {}).get("basis"), "FORMAL_METHOD_301")
            self.assertEqual((snapshot.get("delta_trace") or {}).get("contract_version"), "ftir_delta_trace_v1")
            windows_csv = (root / "locked_windows.csv").read_text(encoding="utf-8")
            self.assertIn("comparison_set_status", windows_csv)
            self.assertIn("startup stabilization", windows_csv)
            method_csv = (root / "locked_method301.csv").read_text(encoding="utf-8")
            self.assertIn("comparison_set_count", method_csv)
            self.assertIn("excluded_window_count", method_csv)
            delta_json = json.loads((root / "locked_delta_trace.json").read_text(encoding="utf-8"))
            self.assertEqual(delta_json.get("contract_version"), "ftir_delta_trace_v1")
            delta_csv = (root / "locked_delta_trace.csv").read_text(encoding="utf-8")
            self.assertIn("IMPORTED_TO_ALIGNED", delta_csv)
            self.assertIn("ALIGNED_TO_EXCLUDED", delta_csv)

    def test_legacy_signoff_basis_normalizes_to_new_acceptance_basis(self) -> None:
        cfg = normalize_config({
            "enabled": True,
            "signoff": {
                "decision": "ACCEPTED",
                "basis": "FORMAL_METHOD_301_PASS",
                "by": "peer_scientist",
            },
        })
        signoff = cfg.get("signoff") or {}
        self.assertEqual(signoff.get("decision"), "ACCEPTED")
        self.assertEqual(signoff.get("basis"), "FORMAL_METHOD_301")

    def test_qa_preview_autodetects_columns_and_flags_large_time_offset(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            ftir_csv = root / "ftir.csv"
            raw_samples = root / "raw_samples.jsonl"

            base = datetime(2026, 4, 10, 12, 0, 0, tzinfo=timezone.utc)
            ftir_lines = ["sample_time,NO_ppm"]
            raw_lines = []
            actual_runs = [{
                "run_no": 1,
                "start_ts_iso": base.isoformat().replace("+00:00", "Z"),
                "end_ts_iso": (base + timedelta(minutes=20)).isoformat().replace("+00:00", "Z"),
            }]

            for step in range(4):
                mole_ts = base + timedelta(minutes=(step * 5) + 1)
                ftir_ts = mole_ts + timedelta(seconds=90)
                value = 25.0 + step
                ftir_lines.append(f"{ftir_ts.isoformat().replace('+00:00', 'Z')},{value}")
                raw_lines.append(json.dumps({
                    "ts_utc": mole_ts.isoformat().replace("+00:00", "Z"),
                    "channel_id": "NO",
                    "value_eng": value,
                    "quality_flags": {"comm_ok": True, "decode_ok": True},
                }))

            ftir_csv.write_text("\n".join(ftir_lines) + "\n", encoding="utf-8")
            raw_samples.write_text("\n".join(raw_lines) + "\n", encoding="utf-8")

            cfg = normalize_config({
                "enabled": True,
                "validation_mode": "METHOD_301_INFORMED_COMPARISON",
                "ftir_file_path": str(ftir_csv),
                "analytes": ["NO"],
            })
            payload = build_validation_package(
                cfg,
                run_aggregation={"actual_runs": actual_runs},
                raw_samples_path=raw_samples,
            )

            ftir_summary = payload.get("ftir_source") or {}
            qa = payload.get("qa") or {}
            self.assertEqual(ftir_summary.get("timestamp_column"), "sample_time")
            self.assertEqual((ftir_summary.get("autodetected_columns_used") or {}).get("NO"), "NO_ppm")
            self.assertFalse(bool(qa.get("lock_ready")))
            self.assertFalse(bool(qa.get("signoff_ready")))
            self.assertTrue(any("failed alignment QA" in str(item) for item in list(qa.get("blocking_issues") or [])))
            row = (payload.get("aligned_rows") or [])[0]
            self.assertEqual(row.get("comparison_set_no"), 1)
            self.assertEqual(row.get("qa_status"), "ERROR")
            self.assertTrue("HIGH_TIME_OFFSET" in list(row.get("qa_flags") or []))

    def test_mks_vendor_profile_parses_record_date_time_and_unit_headers(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            ftir_csv = root / "mks.csv"
            ftir_csv.write_text(
                "\n".join([
                    "Record Date,Record Time,NO (ppm),CO2 (%)",
                    "04/10/2026,12:00:05,11.5,2.5",
                    "04/10/2026,12:05:05,11.8,2.6",
                ]) + "\n",
                encoding="utf-8",
            )
            cfg = normalize_config({
                "enabled": True,
                "ftir_vendor_profile": "MKS_MULTIGAS_CSV",
                "ftir_file_path": str(ftir_csv),
                "analytes": ["NO", "CO2"],
            })
            loaded = load_ftir_records(cfg)
            summary = loaded.get("summary") or {}
            rows = loaded.get("rows") or []
            self.assertEqual(summary.get("vendor_profile_used"), "MKS_MULTIGAS_CSV")
            self.assertEqual(summary.get("timestamp_column"), "Record Date+Record Time")
            self.assertEqual((summary.get("effective_column_map") or {}).get("NO"), "NO (ppm)")
            self.assertEqual((summary.get("effective_column_map") or {}).get("CO2"), "CO2 (%)")
            self.assertEqual(len(rows), 2)
            self.assertEqual((rows[0].get("values") or {}).get("NO"), 11.5)

    def test_thermofisher_max_profile_parses_datestamp_and_timestamp(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            ftir_csv = root / "thermo_max.csv"
            ftir_csv.write_text(
                "\n".join([
                    "DateStamp,TimeStampUTC,NOX ppm,O2 %",
                    "2026-04-10,12:00:05,21.5,5.1",
                    "2026-04-10,12:05:05,21.7,5.0",
                ]) + "\n",
                encoding="utf-8",
            )
            cfg = normalize_config({
                "enabled": True,
                "ftir_vendor_profile": "THERMOFISHER_MAX_CSV",
                "ftir_file_path": str(ftir_csv),
                "analytes": ["NOX", "O2"],
            })
            loaded = load_ftir_records(cfg)
            summary = loaded.get("summary") or {}
            rows = loaded.get("rows") or []
            self.assertEqual(summary.get("vendor_profile_used"), "THERMOFISHER_MAX_CSV")
            self.assertEqual(summary.get("timestamp_column"), "DateStamp+TimeStampUTC")
            self.assertEqual((summary.get("effective_column_map") or {}).get("NOX"), "NOX ppm")
            self.assertEqual((summary.get("effective_column_map") or {}).get("O2"), "O2 %")
            self.assertEqual(len(rows), 2)
            self.assertEqual((rows[1].get("values") or {}).get("O2"), 5.0)


if __name__ == "__main__":
    unittest.main()
