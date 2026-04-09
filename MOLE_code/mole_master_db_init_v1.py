"""Initialize / repair the MOLE master SQLite DB.

Usage:
  python mole_master_db_init_v1.py
  python mole_master_db_init_v1.py /path/to/mole_master.sqlite

If no path is provided, the script initializes the runtime default:
  ../mole_das_data/db/mole_master.sqlite  (relative to this file)

This script is safe to re-run; it uses CREATE TABLE IF NOT EXISTS.
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path
import datetime


def _now_iso() -> str:
    return datetime.datetime.now().isoformat(timespec="seconds")


def _default_db_path(base_dir: Path) -> Path:
    # MOLE_code/ -> ../mole_das_data/db/mole_master.sqlite
    return (base_dir / ".." / "mole_das_data" / "db" / "mole_master.sqlite").resolve()


def main() -> int:
    base_dir = Path(__file__).resolve().parent

    # Path resolution: CLI arg > env var > default
    import sys

    db_path: Path
    if len(sys.argv) >= 2 and sys.argv[1].strip():
        db_path = Path(sys.argv[1]).expanduser().resolve()
    else:
        envp = os.environ.get("MOLE_MASTER_DB", "").strip()
        db_path = Path(envp).expanduser().resolve() if envp else _default_db_path(base_dir)

    db_path.parent.mkdir(parents=True, exist_ok=True)

    schema_file = base_dir / "mole_db_schema_v1.sql"
    if not schema_file.exists():
        print(f"ERROR: schema file not found: {schema_file}")
        return 2

    schema_sql = schema_file.read_text(encoding="utf-8", errors="ignore")

    print(f"Initializing master DB: {db_path}")
    con = sqlite3.connect(str(db_path))
    try:
        con.execute("PRAGMA foreign_keys=ON;")
        try:
            con.execute("PRAGMA journal_mode=WAL;")
            con.execute("PRAGMA synchronous=NORMAL;")
            con.execute("PRAGMA busy_timeout=5000;")
        except Exception:
            pass

        con.executescript(schema_sql)

        # Record schema version marker (v3)
        try:
            con.execute(
                "INSERT OR REPLACE INTO meta_schema_migrations(version, applied_at) VALUES (?, ?)",
                (3, _now_iso()),
            )
        except Exception:
            pass

        con.commit()

        # Summary
        cur = con.cursor()
        tables = [
            "catalog_manufacturer",
            "catalog_model",
            "catalog_variant",
            "catalog_instance",
            "catalog_pending",
            "catalog_synonym",
            "catalog_audit_log",
            "qaqc_cal_event",
        ]
        print("\nTables:")
        for t in tables:
            try:
                cur.execute(f"SELECT COUNT(*) FROM {t}")
                n = cur.fetchone()[0]
            except Exception:
                n = "(missing)"
            print(f"  - {t}: {n}")

        print("\nOK")
        return 0
    finally:
        try:
            con.close()
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
