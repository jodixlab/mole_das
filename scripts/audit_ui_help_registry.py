from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
REGISTRY_PATH = ROOT / "config" / "mole_ui_help_registry_v1.json"
CODE_PATHS = [
    ROOT / "MOLE_code" / "mole_code_das_2026_01_21_v10_0_22_ARCADE_RELEASE.py",
    ROOT / "MOLE_code" / "mole_daq_runner_2026_02_03_v10_0_24_ARCADE_RELEASE.py",
]
HELP_ID_RE = re.compile(r'help_mgr\.bind\([^,\n]+,\s*"([^"]+)"\)')


def _load_registry() -> dict[str, dict]:
    payload = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    entries = payload.get("entries")
    return entries if isinstance(entries, dict) else {}


def _collect_bound_ids() -> set[str]:
    bound: set[str] = set()
    for path in CODE_PATHS:
        text = path.read_text(encoding="utf-8")
        for match in HELP_ID_RE.finditer(text):
            bound.add(match.group(1).strip())
    return bound


def main() -> int:
    registry = _load_registry()
    registry_ids = set(registry.keys())
    bound_ids = _collect_bound_ids()

    missing_registry = sorted(bound_ids - registry_ids)
    unbound_registry = sorted(registry_ids - bound_ids)
    missing_doc_refs = sorted(
        help_id
        for help_id, entry in registry.items()
        if not isinstance(entry, dict) or not isinstance(entry.get("doc_refs"), list) or not entry.get("doc_refs")
    )

    payload = {
        "registry_path": str(REGISTRY_PATH),
        "bound_id_count": len(bound_ids),
        "registry_id_count": len(registry_ids),
        "missing_registry_entries": missing_registry,
        "unbound_registry_entries": unbound_registry,
        "entries_missing_doc_refs": missing_doc_refs,
        "status": "PASS" if not missing_registry and not missing_doc_refs else "FAIL",
    }
    print(json.dumps(payload, indent=2))
    return 1 if payload["status"] != "PASS" else 0


if __name__ == "__main__":
    raise SystemExit(main())
