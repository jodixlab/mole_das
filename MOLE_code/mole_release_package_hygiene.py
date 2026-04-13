from __future__ import annotations

import argparse
import json
import re
import zipfile
from pathlib import Path
from typing import Dict, List, Sequence


_BANNED_ENTRY_PATTERNS: Sequence[tuple[re.Pattern[str], str]] = (
    (re.compile(r"(^|/)(?:\.git|\.vs|__pycache__)(/|$)"), "workspace metadata"),
    (re.compile(r"(^|/)MOLE_code/\.venv_stale[^/]*/"), "stale virtualenv"),
    (re.compile(r"\.sqlite-(?:wal|shm)$"), "sqlite sidecar"),
    (re.compile(r"(^|/)mole_das_data/logs(/|$)"), "runtime logs"),
    (re.compile(r"(^|/)\.github(/|$)"), "ci metadata"),
    (re.compile(r"(^|/)scripts(/|$)"), "release-only scripts"),
    (re.compile(r"(^|/)RUN_CLEAN_RELEASE_WORKFLOW\.bat$"), "release-only workflow launcher"),
    (re.compile(r"(^|/)BUILD_WHEELHOUSE\.bat$"), "release-only wheelhouse builder"),
)

_TEXT_EXTS = {".json", ".md", ".txt", ".csv", ".py", ".bat", ".ps1"}
_TEXT_SCAN_PREFIXES = (
    "config/",
    "mole_das_data/configs/",
    "MOLE_code/",
)
_TEXT_SCAN_NAMES = {
    "mole_config.json",
    "mole_config_training.json",
    "PORTABLE_PACKAGE_NOTES.txt",
    "README.md",
    "README_FIRST.txt",
}
_TEXT_SKIP_PREFIXES = (
    "MOLE_code/.venv/",
)
_ABS_PATH_PATTERNS: Sequence[tuple[re.Pattern[str], str]] = (
    (re.compile(r"[A-Za-z]:\\Users\\"), "absolute user-profile path"),
    (re.compile(r"[A-Za-z]:\\codex_environ\\"), "absolute codex runtime path"),
    (re.compile(r"OneDrive\\mole_das_development_shared"), "onedrive repo path"),
)


def _entry_text_should_scan(name: str) -> bool:
    if any(name.startswith(prefix) for prefix in _TEXT_SKIP_PREFIXES):
        return False
    if name in _TEXT_SCAN_NAMES:
        return True
    if any(name.startswith(prefix) for prefix in _TEXT_SCAN_PREFIXES):
        return Path(name).suffix.lower() in _TEXT_EXTS
    return False


def audit_release_zip(zip_path: Path) -> Dict[str, object]:
    banned_entries: List[Dict[str, str]] = []
    absolute_hits: List[Dict[str, str]] = []
    entry_count = 0

    with zipfile.ZipFile(zip_path, "r") as zf:
        for info in zf.infolist():
            name = info.filename.replace("\\", "/")
            entry_count += 1

            for pattern, reason in _BANNED_ENTRY_PATTERNS:
                if pattern.search(name):
                    banned_entries.append({"path": name, "reason": reason})
                    break

            if not _entry_text_should_scan(name):
                continue
            try:
                raw = zf.read(info)
            except OSError as exc:
                absolute_hits.append({
                    "path": name,
                    "reason": f"read_error:{type(exc).__name__}",
                    "match": str(exc),
                })
                continue
            text = raw.decode("utf-8", errors="ignore")
            for pattern, reason in _ABS_PATH_PATTERNS:
                match = pattern.search(text)
                if not match:
                    continue
                excerpt = text[max(0, match.start() - 40): match.end() + 120].replace("\r", " ").replace("\n", " ")
                absolute_hits.append({
                    "path": name,
                    "reason": reason,
                    "match": excerpt[:240],
                })
                break

    status = "PASS" if (not banned_entries and not absolute_hits) else "FAIL"
    return {
        "schema": "mole_release_package_hygiene_v1",
        "zip_path": str(zip_path),
        "entry_count": entry_count,
        "banned_entry_count": len(banned_entries),
        "absolute_path_hit_count": len(absolute_hits),
        "banned_entries": banned_entries,
        "absolute_path_hits": absolute_hits,
        "status": status,
    }


def format_hygiene_report(report: Dict[str, object]) -> str:
    lines: List[str] = []
    lines.append("MOLE-DAS Release Package Hygiene")
    lines.append("=" * 33)
    lines.append(f"Status: {report.get('status')}")
    lines.append(f"ZIP:    {report.get('zip_path')}")
    lines.append(f"Entries: {report.get('entry_count')}")
    lines.append(f"Banned entries: {report.get('banned_entry_count')}")
    lines.append(f"Absolute path hits: {report.get('absolute_path_hit_count')}")
    if report.get("banned_entries"):
        lines.append("")
        lines.append("Banned entries")
        lines.append("--------------")
        for item in report.get("banned_entries") or []:
            lines.append(f"- {item.get('path')} :: {item.get('reason')}")
    if report.get("absolute_path_hits"):
        lines.append("")
        lines.append("Absolute path hits")
        lines.append("------------------")
        for item in report.get("absolute_path_hits") or []:
            lines.append(f"- {item.get('path')} :: {item.get('reason')} :: {item.get('match')}")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--zip", required=True, help="Release ZIP to audit.")
    ap.add_argument("--json-out", default=None, help="Optional JSON report output.")
    ap.add_argument("--txt-out", default=None, help="Optional text report output.")
    args = ap.parse_args()

    report = audit_release_zip(Path(args.zip).resolve())
    text = format_hygiene_report(report)
    print(text)

    if args.json_out:
        Path(args.json_out).write_text(json.dumps(report, indent=2), encoding="utf-8")
    if args.txt_out:
        Path(args.txt_out).write_text(text, encoding="utf-8")
    return 0 if report.get("status") == "PASS" else 3


if __name__ == "__main__":
    raise SystemExit(main())
