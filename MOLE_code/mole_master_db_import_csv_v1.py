"""MOLE Master DB CSV Importer — v1

Imports make/model (and optional instance) rows into the master catalog DB.

CSV format
----------
See:
  mole_das_data/configs/catalog_import_template.csv

Columns
-------
source_category,manufacturer,model_number,engine_cycle,engine_cyl_count,duty_value,duty_unit,serial_number,asset_tag,site_id,location_id

Rules
-----
- manufacturer + model_number are required to create a model.
- serial_number is optional; if present, an inventory instance is upserted.
- All inserts are idempotent (duplicates ignored / upserted).

Usage (Windows)
---------------
  python MOLE_code/mole_master_db_import_csv_v1.py --csv mole_das_data/configs/catalog_import_template.csv

"""

from __future__ import annotations

import argparse
import csv
import datetime
import sqlite3
from pathlib import Path


def now_iso() -> str:
    return datetime.datetime.now().isoformat(timespec="seconds")


def norm_text(s: str) -> str:
    return " ".join((s or "").strip().lower().split())


def ensure_schema(db_path: Path, schema_path: Path) -> None:
    con = sqlite3.connect(str(db_path))
    try:
        con.execute("PRAGMA foreign_keys=ON")
        con.executescript(schema_path.read_text(encoding="utf-8"))
        try:
            con.execute("INSERT OR IGNORE INTO meta_schema_migrations(version, applied_at) VALUES (?,?)", (1, now_iso()))
        except Exception:
            pass
        con.commit()
    finally:
        con.close()


def upsert_manufacturer(con: sqlite3.Connection, name: str) -> int:
    nm = (name or "").strip()
    if not nm:
        return 0
    nn = norm_text(nm)
    now = now_iso()
    cur = con.cursor()
    cur.execute("SELECT manufacturer_id FROM catalog_manufacturer WHERE name_norm=?", (nn,))
    row = cur.fetchone()
    if row:
        return int(row[0])
    con.execute(
        "INSERT INTO catalog_manufacturer(name, name_norm, created_at, updated_at) VALUES (?,?,?,?)",
        (nm, nn, now, now),
    )
    return int(con.execute("SELECT last_insert_rowid()").fetchone()[0])


def upsert_model(
    con: sqlite3.Connection,
    manufacturer_id: int,
    source_category: str,
    model_number: str,
    engine_cycle: str | None,
    engine_cyl_count: int | None,
    duty_value: float | None,
    duty_unit: str | None,
) -> int:
    cat = (source_category or "Other").strip() or "Other"
    mnum = (model_number or "").strip()
    if not mnum:
        return 0
    mn = norm_text(mnum)
    now = now_iso()
    cur = con.cursor()
    cur.execute(
        """SELECT model_id FROM catalog_model
           WHERE manufacturer_id=? AND source_category=? AND model_norm=?""",
        (int(manufacturer_id), cat, mn),
    )
    row = cur.fetchone()
    if row:
        return int(row[0])
    con.execute(
        """INSERT INTO catalog_model(
               manufacturer_id, source_category, model_number, model_norm,
               engine_cycle, engine_cyl_count, duty_value, duty_unit,
               usage_count, created_at, updated_at
           ) VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (
            int(manufacturer_id),
            cat,
            mnum,
            mn,
            (engine_cycle if engine_cycle else None),
            (int(engine_cyl_count) if engine_cyl_count is not None else None),
            (float(duty_value) if duty_value is not None else None),
            (str(duty_unit) if duty_unit else None),
            0,
            now,
            now,
        ),
    )
    return int(con.execute("SELECT last_insert_rowid()").fetchone()[0])


def upsert_instance(
    con: sqlite3.Connection,
    model_id: int,
    manufacturer_id: int,
    source_category: str,
    serial_number: str,
    asset_tag: str | None,
    site_id: str | None,
    location_id: str | None,
) -> int:
    cat = (source_category or "Other").strip() or "Other"
    ser = (serial_number or "").strip()
    if not ser:
        return 0
    ser_norm = norm_text(ser)
    asset = (asset_tag or "").strip() or None
    asset_norm = norm_text(asset) if asset else None
    now = now_iso()

    cur = con.cursor()
    cur.execute(
        "SELECT instance_id FROM catalog_instance WHERE source_category=? AND serial_norm=?",
        (cat, ser_norm),
    )
    row = cur.fetchone()
    if row:
        iid = int(row[0])
        con.execute(
            """UPDATE catalog_instance
               SET model_id=?, manufacturer_id=?, serial_number=?, asset_tag=?, asset_norm=?,
                   site_id=?, location_id=?, usage_count=usage_count+1, updated_at=?
               WHERE instance_id=?""",
            (
                int(model_id),
                int(manufacturer_id),
                ser,
                asset,
                asset_norm,
                site_id,
                location_id,
                now,
                iid,
            ),
        )
        return iid

    con.execute(
        """INSERT INTO catalog_instance(
               model_id, source_category, manufacturer_id,
               serial_number, serial_norm, asset_tag, asset_norm,
               site_id, location_id, usage_count, created_at, updated_at
           ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            int(model_id),
            cat,
            int(manufacturer_id),
            ser,
            ser_norm,
            asset,
            asset_norm,
            site_id,
            location_id,
            1,
            now,
            now,
        ),
    )
    return int(con.execute("SELECT last_insert_rowid()").fetchone()[0])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="", help="Path to mole_master.sqlite (default: ../mole_das_data/db/mole_master.sqlite)")
    ap.add_argument("--schema", default="", help="Path to schema SQL (default: mole_db_schema_v1.sql next to this script)")
    ap.add_argument("--csv", required=True, help="CSV file to import")
    args = ap.parse_args()

    script_dir = Path(__file__).resolve().parent
    root = script_dir.parent
    db_path = Path(args.db).expanduser().resolve() if args.db else (root / "mole_das_data" / "db" / "mole_master.sqlite").resolve()
    schema_path = Path(args.schema).expanduser().resolve() if args.schema else (script_dir / "mole_db_schema_v1.sql").resolve()
    csv_path = Path(args.csv).expanduser().resolve()

    if not schema_path.exists():
        print(f"ERROR: schema not found: {schema_path}")
        return 2
    if not csv_path.exists():
        print(f"ERROR: csv not found: {csv_path}")
        return 2

    db_path.parent.mkdir(parents=True, exist_ok=True)
    ensure_schema(db_path, schema_path)

    con = sqlite3.connect(str(db_path))
    try:
        con.execute("PRAGMA foreign_keys=ON")
        cur = con.cursor()

        n_rows = 0
        n_models = 0
        n_instances = 0

        with csv_path.open("r", newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                n_rows += 1
                cat = (row.get("source_category") or "Other").strip() or "Other"
                mfr = (row.get("manufacturer") or "").strip()
                mdl = (row.get("model_number") or "").strip()
                if not (mfr and mdl):
                    continue
                cyc = (row.get("engine_cycle") or "").strip() or None
                cyl = (row.get("engine_cyl_count") or "").strip()
                cyl_i = int(float(cyl)) if cyl else None
                dv = (row.get("duty_value") or "").strip()
                dv_f = float(dv) if dv else None
                du = (row.get("duty_unit") or "").strip() or None
                ser = (row.get("serial_number") or "").strip()
                asset = (row.get("asset_tag") or "").strip() or None
                site_id = (row.get("site_id") or "").strip() or None
                loc_id = (row.get("location_id") or "").strip() or None

                mid = upsert_manufacturer(con, mfr)
                model_id = upsert_model(con, mid, cat, mdl, cyc, cyl_i, dv_f, du)
                if model_id:
                    n_models += 1
                if ser:
                    iid = upsert_instance(con, model_id, mid, cat, ser, asset, site_id, loc_id)
                    if iid:
                        n_instances += 1

        con.commit()

        # Basic counts
        def count(tbl: str) -> int:
            try:
                cur.execute(f"SELECT COUNT(*) FROM {tbl}")
                return int(cur.fetchone()[0])
            except Exception:
                return -1

        print("Imported rows:", n_rows)
        print("Upsert attempts:", "models=", n_models, "instances=", n_instances)
        print("DB counts:")
        for t in ["catalog_manufacturer", "catalog_model", "catalog_instance", "catalog_pending", "catalog_synonym"]:
            print(f"  {t}: {count(t)}")
        print("DB:", db_path)
        return 0
    finally:
        try:
            con.close()
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
