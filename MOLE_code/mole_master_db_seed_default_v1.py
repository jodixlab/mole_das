"""MOLE Master DB Seed (Default Catalog) — v1

Purpose
-------
Seeds the master catalog DB (mole_master.sqlite) with a starter make/model dataset
covering all MOLE source categories (Engine, Turbine, Boiler, etc.). This ensures
that Manufacturer/Model dropdowns and Catalog Governance screens are populated
out-of-the-box.

Usage (Windows)
--------------
  python mole_master_db_seed_default_v1.py
  python mole_master_db_seed_default_v1.py --wipe
  python mole_master_db_seed_default_v1.py --db ../mole_das_data/db/mole_master.sqlite

Notes
-----
- This is a starter dataset, not an authoritative OEM registry.
- You can extend the catalog via Catalog Governance UI (Pending Queue -> Approve) or
  by importing your own CSV using your internal tooling.
"""

from __future__ import annotations

import argparse
import datetime
import re
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_WS_RE = re.compile(r"\s+")


def now_iso() -> str:
    return datetime.datetime.now().isoformat(timespec="seconds")


def norm_text(s: Any) -> str:
    if s is None:
        return ""
    t = str(s).strip()
    if not t:
        return ""
    t = _WS_RE.sub(" ", t)
    return t.lower()


def apply_schema(con: sqlite3.Connection, schema_sql: str) -> None:
    con.executescript(schema_sql)
    try:
        con.execute(
            "INSERT OR IGNORE INTO meta_schema_migrations(version, applied_at) VALUES (?,?)",
            (1, now_iso()),
        )
    except Exception:
        pass
    con.commit()


def upsert_manufacturer(con: sqlite3.Connection, name: str) -> int:
    name = str(name or "").strip()
    if not name:
        raise ValueError("manufacturer name is empty")
    n = norm_text(name)
    cur = con.cursor()
    cur.execute("SELECT manufacturer_id FROM catalog_manufacturer WHERE name_norm=?", (n,))
    row = cur.fetchone()
    if row:
        return int(row[0])
    ts = now_iso()
    cur.execute(
        "INSERT INTO catalog_manufacturer(name, name_norm, created_at, updated_at) VALUES (?,?,?,?)",
        (name, n, ts, ts),
    )
    con.commit()
    return int(cur.execute("SELECT last_insert_rowid()").fetchone()[0])


def upsert_model(
    con: sqlite3.Connection,
    manufacturer_id: int,
    source_category: str,
    model_number: str,
    engine_cycle: Optional[str] = None,
    engine_cyl_count: Optional[int] = None,
    duty_value: Optional[float] = None,
    duty_unit: Optional[str] = None,
) -> int:
    cat = str(source_category or "Other").strip() or "Other"
    mdl = str(model_number or "").strip()
    if not mdl:
        raise ValueError("model_number is empty")
    mn = norm_text(mdl)
    cur = con.cursor()
    cur.execute(
        "SELECT model_id FROM catalog_model WHERE manufacturer_id=? AND source_category=? AND model_norm=?",
        (int(manufacturer_id), cat, mn),
    )
    row = cur.fetchone()
    if row:
        return int(row[0])
    ts = now_iso()
    cur.execute(
        """
        INSERT INTO catalog_model(
          manufacturer_id, source_category,
          model_number, model_norm,
          engine_cycle, engine_cyl_count,
          duty_value, duty_unit,
          usage_count, created_at, updated_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            int(manufacturer_id),
            cat,
            mdl,
            mn,
            (str(engine_cycle) if engine_cycle else None),
            (int(engine_cyl_count) if engine_cyl_count is not None else None),
            (float(duty_value) if duty_value is not None else None),
            (str(duty_unit) if duty_unit else None),
            0,
            ts,
            ts,
        ),
    )
    con.commit()
    return int(cur.execute("SELECT last_insert_rowid()").fetchone()[0])


def insert_synonym(
    con: sqlite3.Connection,
    synonym_type: str,
    synonym: str,
    canonical_manufacturer_id: Optional[int] = None,
    canonical_model_id: Optional[int] = None,
) -> None:
    ts = now_iso()
    con.execute(
        """
        INSERT OR IGNORE INTO catalog_synonym(
          synonym_type, synonym, synonym_norm,
          canonical_manufacturer_id, canonical_model_id,
          created_at, updated_at
        ) VALUES (?,?,?,?,?,?,?)
        """,
        (
            str(synonym_type),
            str(synonym),
            norm_text(synonym),
            int(canonical_manufacturer_id) if canonical_manufacturer_id is not None else None,
            int(canonical_model_id) if canonical_model_id is not None else None,
            ts,
            ts,
        ),
    )
    con.commit()


def upsert_instance(
    con: sqlite3.Connection,
    model_id: int,
    source_category: str,
    manufacturer_id: int,
    serial_number: str,
    asset_tag: Optional[str] = None,
    site_id: Optional[str] = None,
    location_id: Optional[str] = None,
) -> int:
    cat = str(source_category or "Other").strip() or "Other"
    ser = str(serial_number or "").strip()
    if not ser:
        raise ValueError("serial_number is empty")
    sn = norm_text(ser)
    an = norm_text(asset_tag) if asset_tag else None
    cur = con.cursor()
    cur.execute(
        "SELECT instance_id FROM catalog_instance WHERE source_category=? AND serial_norm=?",
        (cat, sn),
    )
    row = cur.fetchone()
    if row:
        return int(row[0])
    ts = now_iso()
    cur.execute(
        """
        INSERT INTO catalog_instance(
          model_id, source_category, manufacturer_id,
          serial_number, serial_norm,
          asset_tag, asset_norm,
          site_id, location_id,
          usage_count, created_at, updated_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            int(model_id),
            cat,
            int(manufacturer_id),
            ser,
            sn,
            (asset_tag if asset_tag else None),
            an,
            (site_id if site_id else None),
            (location_id if location_id else None),
            0,
            ts,
            ts,
        ),
    )
    con.commit()
    return int(cur.execute("SELECT last_insert_rowid()").fetchone()[0])


def default_seed_models() -> List[Tuple[str, str, str, Optional[str], Optional[int]]]:
    """(category, manufacturer, model_number, engine_cycle, engine_cyl_count)"""
    models: List[Tuple[str, str, str, Optional[str], Optional[int]]] = []

    # Engine
    models += [
        ("Engine", "Caterpillar", "G3516", "4_CYL", 16),
        ("Engine", "Caterpillar", "G3520", "4_CYL", 20),
        ("Engine", "Caterpillar", "G3606", "4_CYL", 6),
        ("Engine", "Cummins", "QSK19-G", "4_CYL", 6),
        ("Engine", "Cummins", "QSK60-G", "4_CYL", 16),
        ("Engine", "Waukesha", "VHP7044", "4_CYL", 12),
        ("Engine", "Waukesha", "VHP9390", "4_CYL", 18),
        ("Engine", "Jenbacher", "J320", "4_CYL", 20),
        ("Engine", "Jenbacher", "J620", "4_CYL", 20),
        ("Engine", "MTU", "16V4000", "4_CYL", 16),
        ("Engine", "Deutz", "TCG2020 V16", "4_CYL", 16),
        ("Engine", "Perkins", "4016-61TRG3", "4_CYL", 16),
        ("Engine", "MAN", "E3262LE212", "4_CYL", 12),
        ("Engine", "Detroit Diesel", "Series 60", "4_CYL", 6),
    ]

    # Turbine
    models += [
        ("Turbine", "Solar Turbines", "Taurus 70", None, None),
        ("Turbine", "Solar Turbines", "Mars 100", None, None),
        ("Turbine", "Solar Turbines", "Titan 130", None, None),
        ("Turbine", "GE", "LM2500", None, None),
        ("Turbine", "GE", "LM6000", None, None),
        ("Turbine", "Siemens", "SGT-400", None, None),
        ("Turbine", "Siemens", "SGT-800", None, None),
        ("Turbine", "Rolls-Royce", "RB211", None, None),
        ("Turbine", "Kawasaki", "GPB15", None, None),
        ("Turbine", "Pratt & Whitney", "FT8", None, None),
    ]

    # Boiler
    models += [
        ("Boiler", "Cleaver-Brooks", "CB-700", None, None),
        ("Boiler", "Cleaver-Brooks", "CBEX", None, None),
        ("Boiler", "Hurst", "Series 250", None, None),
        ("Boiler", "Miura", "EX", None, None),
        ("Boiler", "Fulton", "VMP", None, None),
        ("Boiler", "Superior", "Mohican", None, None),
    ]

    # Heater
    models += [
        ("Heater", "Zeeco", "Line Heater", None, None),
        ("Heater", "John Zink", "Process Heater", None, None),
        ("Heater", "Eclipse", "ThermJet", None, None),
        ("Heater", "Maxon", "OvenPak", None, None),
        ("Heater", "Honeywell", "Max Burner", None, None),
    ]

    # Flare
    models += [
        ("Flare", "John Zink", "Sonic Tip", None, None),
        ("Flare", "Zeeco", "Enclosed Flare", None, None),
        ("Flare", "Callidus", "Pressure Assisted", None, None),
        ("Flare", "Honeywell UOP", "Smokeless Flare", None, None),
        ("Flare", "Flare Industries", "Ground Flare", None, None),
    ]

    # Tank Vent
    models += [
        ("Tank Vent", "Protectoseal", "830 Series", None, None),
        ("Tank Vent", "Enardo", "E2000", None, None),
        ("Tank Vent", "Groth", "1400 Series", None, None),
        ("Tank Vent", "Shand & Jurs", "940 Series", None, None),
    ]

    # Process Vent
    models += [
        ("Process Vent", "Emerson", "PSV", None, None),
        ("Process Vent", "Fisher", "289", None, None),
        ("Process Vent", "Leslie", "430", None, None),
        ("Process Vent", "ValvTechnologies", "Isolation Valve", None, None),
    ]

    # Fugitive / Component
    models += [
        ("Fugitive / Component", "Swagelok", "V Series", None, None),
        ("Fugitive / Component", "Parker", "Ball Valve", None, None),
        ("Fugitive / Component", "Cameron", "Gate Valve", None, None),
        ("Fugitive / Component", "Masoneilan", "Control Valve", None, None),
        ("Fugitive / Component", "Flowserve", "Pump Seal", None, None),
    ]

    # Other
    models += [("Other", "Generic", "Generic", None, None)]

    return models


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="", help="Path to master DB (mole_master.sqlite)")
    ap.add_argument("--wipe", action="store_true", help="Delete existing DB and recreate schema")
    ap.add_argument("--no-instances", action="store_true", help="Seed only make/model tables")
    args = ap.parse_args()

    base_dir = Path(__file__).resolve().parent
    root = base_dir.parent

    db_path = Path(args.db).expanduser() if args.db else (root / "mole_das_data" / "db" / "mole_master.sqlite")
    db_path = db_path.resolve()

    schema_path = base_dir / "mole_db_schema_v1.sql"
    if not schema_path.exists():
        print(f"ERROR: schema file not found: {schema_path}")
        return 2

    if args.wipe and db_path.exists():
        try:
            db_path.unlink()
        except Exception as e:
            print(f"ERROR: unable to delete {db_path}: {e}")
            return 2

    db_path.parent.mkdir(parents=True, exist_ok=True)

    con = sqlite3.connect(str(db_path))
    try:
        apply_schema(con, schema_path.read_text(encoding="utf-8"))

        # Seed dataset
        models = default_seed_models()

        # Manufacturer cache
        mfr_id: Dict[str, int] = {}
        model_id_cache: Dict[Tuple[str, str, str], int] = {}

        for cat, mfr, mdl, cyc, cyl in models:
            mid = mfr_id.get(mfr)
            if not mid:
                mid = upsert_manufacturer(con, mfr)
                mfr_id[mfr] = mid

            model_id = upsert_model(con, mid, cat, mdl, engine_cycle=cyc, engine_cyl_count=cyl)
            model_id_cache[(cat, mfr, mdl)] = model_id

        # Common synonyms
        if "Caterpillar" in mfr_id:
            insert_synonym(con, "MANUFACTURER", "CAT", canonical_manufacturer_id=mfr_id["Caterpillar"])
            insert_synonym(con, "MANUFACTURER", "CATERPILLAR INC", canonical_manufacturer_id=mfr_id["Caterpillar"])
        if "GE" in mfr_id:
            insert_synonym(con, "MANUFACTURER", "GENERAL ELECTRIC", canonical_manufacturer_id=mfr_id["GE"])

        # Demo instances (optional)
        if not args.no_instances:
            i = 1
            for (cat, mfr, mdl), mid in model_id_cache.items():
                serial = f"DEMO-{cat[:3].upper()}-{mfr[:3].upper()}-{i:04d}"
                asset = f"A-{i:04d}"
                upsert_instance(
                    con,
                    model_id=int(mid),
                    source_category=cat,
                    manufacturer_id=int(mfr_id[mfr]),
                    serial_number=serial,
                    asset_tag=asset,
                    site_id="DEMO_SITE",
                    location_id="DEMO_LOC",
                )
                i += 1

        # Summary
        cur = con.cursor()
        for t in ["catalog_manufacturer", "catalog_model", "catalog_instance", "catalog_synonym", "catalog_pending", "qaqc_cal_event"]:
            try:
                cur.execute(f"SELECT COUNT(*) FROM {t}")
                print(f"{t}: {cur.fetchone()[0]}")
            except Exception:
                print(f"{t}: (missing)")

        print(f"\nOK: seeded master DB: {db_path}")
        return 0
    finally:
        con.close()


if __name__ == "__main__":
    raise SystemExit(main())
