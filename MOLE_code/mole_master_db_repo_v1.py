"""MOLE Master DB Repository (v1)

This module provides a small, dependency-free repository wrapper around the
MOLE master SQLite database.

It is intentionally lightweight and designed to be imported dynamically by the
Session Setup Wizard (Catalog Governance + Source Details picklists).

Key goals:
  - Self-initializing schema (via ensure_schema)
  - Deterministic, portable paths
  - Simple governance operations (pending queue, synonyms, merges, audit log)

Schema version target: v3 (matches mole_db_schema_v1.sql)
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import datetime
import json
import re
import sqlite3


def _now_iso() -> str:
    return datetime.datetime.now().isoformat(timespec="seconds")


_WS_RE = re.compile(r"\s+")


def _norm_text(s: Any) -> str:
    """Normalize text for matching and uniqueness."""
    if s is None:
        return ""
    t = str(s).strip()
    if not t:
        return ""
    t = _WS_RE.sub(" ", t)
    return t.lower()


def _is_suspicious_token(s: str) -> bool:
    """Heuristic for make/model strings that should route to the pending queue."""
    t = _norm_text(s)
    if not t:
        return True
    bad = {
        "unknown",
        "unk",
        "n/a",
        "na",
        "none",
        "tbd",
        "pending",
        "?",
        "-",
        "--",
    }
    if t in bad:
        return True
    if len(t) < 2:
        return True
    # Pure punctuation or repeated placeholders
    if all(ch in "-_/\\. ?" for ch in t):
        return True
    return False


@dataclass
class MoleDBConfig:
    db_path: Path


class MoleMasterDB:
    """Repository wrapper around the master catalog DB."""

    def __init__(self, cfg: MoleDBConfig):
        self.cfg = cfg
        self.db_path = Path(cfg.db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self.con = sqlite3.connect(str(self.db_path))
        self.con.row_factory = sqlite3.Row

        try:
            self.con.execute("PRAGMA foreign_keys=ON")
        except Exception:
            pass

        # Safe defaults (do not fail if not supported)
        for pragma in (
            "PRAGMA journal_mode=WAL",
            "PRAGMA synchronous=NORMAL",
            "PRAGMA temp_store=MEMORY",
            "PRAGMA busy_timeout=5000",
        ):
            try:
                self.con.execute(pragma)
            except Exception:
                pass

    # ----------------------- schema / audit -----------------------

    def ensure_schema(self, schema_sql: str, target_version: int = 3) -> Dict[str, Any]:
        """Apply schema DDL (idempotent) and stamp migration version."""
        try:
            if schema_sql and str(schema_sql).strip():
                self.con.executescript(schema_sql)
            else:
                # Minimal fallback: create migration marker so downstream calls behave.
                self.con.execute(
                    "CREATE TABLE IF NOT EXISTS meta_schema_migrations (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)"
                )

            # Stamp the target version (idempotent)
            self.con.execute(
                "INSERT OR IGNORE INTO meta_schema_migrations(version, applied_at) VALUES (?, ?)",
                (int(target_version), _now_iso()),
            )
            self.con.commit()
            return {"status": "OK", "version": int(target_version)}
        except Exception as e:
            try:
                self.con.commit()
            except Exception:
                pass
            return {"status": "ERROR", "error": str(e)}

    def audit_log(
        self,
        action: str,
        subject_type: str | None = None,
        subject_id: int | None = None,
        actor: str = "system",
        details: Any | None = None,
    ) -> None:
        try:
            d = None
            if details is not None:
                try:
                    d = json.dumps(details, ensure_ascii=False)
                except Exception:
                    d = str(details)
            self.con.execute(
                "INSERT INTO catalog_audit_log(created_at, actor, action, subject_type, subject_id, details_json) VALUES (?,?,?,?,?,?)",
                (_now_iso(), str(actor or "system"), str(action or ""), subject_type, subject_id, d),
            )
            self.con.commit()
        except Exception:
            # audit must never crash the app
            try:
                self.con.commit()
            except Exception:
                pass

    def list_audit_log(self, limit: int = 250) -> List[Dict[str, Any]]:
        try:
            cur = self.con.cursor()
            cur.execute(
                "SELECT audit_id, created_at, actor, action, subject_type, subject_id, details_json "
                "FROM catalog_audit_log ORDER BY audit_id DESC LIMIT ?",
                (int(limit),),
            )
            out: List[Dict[str, Any]] = []
            for r in cur.fetchall() or []:
                d = dict(r)
                # attempt to decode JSON
                try:
                    if d.get("details_json"):
                        d["details"] = json.loads(d.get("details_json"))
                except Exception:
                    pass
                out.append(d)
            return out
        except Exception:
            return []

    # ----------------------- counts -----------------------

    def catalog_counts(self) -> Dict[str, int]:
        cur = self.con.cursor()
        mapping = {
            "manufacturers": "catalog_manufacturer",
            "models": "catalog_model",
            "variants": "catalog_variant",
            "instances": "catalog_instance",
            "pending": "catalog_pending",
            "synonyms": "catalog_synonym",
        }
        out: Dict[str, int] = {}
        for k, tbl in mapping.items():
            try:
                cur.execute(f"SELECT COUNT(*) FROM {tbl}")
                out[k] = int(cur.fetchone()[0])
            except Exception:
                out[k] = 0
        return out

    # ----------------------- manufacturers -----------------------

    def _manufacturer_id_by_name(self, name: str) -> Optional[int]:
        """Resolve a manufacturer name via canonical match first, then synonyms."""
        nn = _norm_text(name)
        if not nn:
            return None
        cur = self.con.cursor()
        try:
            cur.execute("SELECT manufacturer_id FROM catalog_manufacturer WHERE name_norm=?", (nn,))
            row = cur.fetchone()
            if row:
                return int(row[0])
        except Exception:
            pass

        # synonyms
        try:
            cur.execute(
                "SELECT canonical_manufacturer_id FROM catalog_synonym "
                "WHERE synonym_type='MANUFACTURER' AND synonym_norm=?",
                (nn,),
            )
            row = cur.fetchone()
            if row and row[0] is not None:
                return int(row[0])
        except Exception:
            pass
        return None

    def _upsert_manufacturer(self, name: str) -> Optional[int]:
        name = str(name or "").strip()
        nn = _norm_text(name)
        if not nn:
            return None
        mid = self._manufacturer_id_by_name(name)
        if mid:
            # touch updated_at
            try:
                self.con.execute("UPDATE catalog_manufacturer SET updated_at=? WHERE manufacturer_id=?", (_now_iso(), int(mid)))
                self.con.commit()
            except Exception:
                pass
            return int(mid)

        try:
            self.con.execute(
                "INSERT INTO catalog_manufacturer(name, name_norm, created_at, updated_at) VALUES (?,?,?,?)",
                (name, nn, _now_iso(), _now_iso()),
            )
            self.con.commit()
            return int(self.con.execute("SELECT last_insert_rowid()").fetchone()[0])
        except Exception:
            try:
                self.con.commit()
            except Exception:
                pass
            # race-safe retry
            try:
                return self._manufacturer_id_by_name(name)
            except Exception:
                return None

    def list_manufacturers_full(self, limit: int = 2000) -> List[Dict[str, Any]]:
        try:
            cur = self.con.cursor()
            cur.execute(
                "SELECT manufacturer_id, name, created_at, updated_at FROM catalog_manufacturer "
                "ORDER BY name COLLATE NOCASE ASC LIMIT ?",
                (int(limit),),
            )
            return [dict(r) for r in (cur.fetchall() or [])]
        except Exception:
            return []

    def suggest_manufacturers(self, prefix: str = "", limit: int = 200) -> List[str]:
        p = _norm_text(prefix)
        like = p + "%" if p else "%"
        out: List[str] = []
        cur = self.con.cursor()

        # canonical
        try:
            cur.execute(
                "SELECT name FROM catalog_manufacturer WHERE name_norm LIKE ? ORDER BY name COLLATE NOCASE ASC LIMIT ?",
                (like, int(limit)),
            )
            for (n,) in cur.fetchall() or []:
                if n and n not in out:
                    out.append(str(n))
        except Exception:
            pass

        # synonyms -> canonical
        try:
            cur.execute(
                "SELECT m.name FROM catalog_synonym s "
                "JOIN catalog_manufacturer m ON m.manufacturer_id = s.canonical_manufacturer_id "
                "WHERE s.synonym_type='MANUFACTURER' AND s.synonym_norm LIKE ? "
                "ORDER BY m.name COLLATE NOCASE ASC LIMIT ?",
                (like, int(limit)),
            )
            for (n,) in cur.fetchall() or []:
                if n and n not in out:
                    out.append(str(n))
        except Exception:
            pass

        return out[: int(limit)]

    # ----------------------- models -----------------------

    def _model_id(self, manufacturer_id: int, source_category: str, model_number: str) -> Optional[int]:
        mn = _norm_text(model_number)
        if not mn:
            return None
        cur = self.con.cursor()
        try:
            cur.execute(
                "SELECT model_id FROM catalog_model WHERE manufacturer_id=? AND source_category=? AND model_norm=?",
                (int(manufacturer_id), str(source_category or "Other"), mn),
            )
            row = cur.fetchone()
            if row:
                return int(row[0])
        except Exception:
            pass
        return None

    def list_models_full(
        self,
        source_category: Optional[str] = None,
        manufacturer_id: Optional[int] = None,
        limit: int = 500,
    ) -> List[Dict[str, Any]]:
        try:
            cur = self.con.cursor()
            sql = (
                "SELECT m.model_id, m.manufacturer_id, m.source_category, m.model_number, "
                "m.engine_cycle, m.engine_cyl_count, m.duty_value, m.duty_unit, "
                "m.usage_count, m.created_at, m.updated_at, mf.name AS manufacturer "
                "FROM catalog_model m "
                "JOIN catalog_manufacturer mf ON mf.manufacturer_id = m.manufacturer_id "
                "WHERE 1=1"
            )
            params: List[Any] = []
            if source_category:
                sql += " AND m.source_category=?"
                params.append(str(source_category))
            if manufacturer_id:
                sql += " AND m.manufacturer_id=?"
                params.append(int(manufacturer_id))
            sql += " ORDER BY m.usage_count DESC, m.model_number COLLATE NOCASE ASC LIMIT ?"
            params.append(int(limit))
            cur.execute(sql, tuple(params))
            return [dict(r) for r in (cur.fetchall() or [])]
        except Exception:
            return []

    def get_model(self, source_category: str, manufacturer: str, model_number: str) -> Optional[Dict[str, Any]]:
        cat = str(source_category or "Other").strip() or "Other"
        mfr = str(manufacturer or "").strip()
        mdl = str(model_number or "").strip()
        if not mfr or not mdl:
            return None
        mfr_id = self._manufacturer_id_by_name(mfr)
        if not mfr_id:
            return None
        try:
            cur = self.con.cursor()
            cur.execute(
                "SELECT m.model_id, m.manufacturer_id, m.source_category, m.model_number, "
                "m.engine_cycle, m.engine_cyl_count, m.duty_value, m.duty_unit, "
                "m.usage_count, m.created_at, m.updated_at, mf.name AS manufacturer "
                "FROM catalog_model m "
                "JOIN catalog_manufacturer mf ON mf.manufacturer_id = m.manufacturer_id "
                "WHERE m.manufacturer_id=? AND m.source_category=? AND m.model_norm=?",
                (int(mfr_id), cat, _norm_text(mdl)),
            )
            row = cur.fetchone()
            return dict(row) if row else None
        except Exception:
            return None

    def suggest_models(self, source_category: str, manufacturer: str, prefix: str = "", limit: int = 200) -> List[str]:
        mfr_id = self._manufacturer_id_by_name(manufacturer)
        if not mfr_id:
            return []
        p = _norm_text(prefix)
        like = p + "%" if p else "%"
        out: List[str] = []
        cur = self.con.cursor()

        try:
            cur.execute(
                "SELECT model_number FROM catalog_model "
                "WHERE manufacturer_id=? AND source_category=? AND model_norm LIKE ? "
                "ORDER BY usage_count DESC, model_number COLLATE NOCASE ASC LIMIT ?",
                (int(mfr_id), str(source_category or "Other"), like, int(limit)),
            )
            for (n,) in cur.fetchall() or []:
                if n and n not in out:
                    out.append(str(n))
        except Exception:
            pass

        # model synonyms
        try:
            cur.execute(
                "SELECT m.model_number FROM catalog_synonym s "
                "JOIN catalog_model m ON m.model_id = s.canonical_model_id "
                "WHERE s.synonym_type='MODEL' AND s.synonym_norm LIKE ? AND m.manufacturer_id=? AND m.source_category=? "
                "ORDER BY m.usage_count DESC, m.model_number COLLATE NOCASE ASC LIMIT ?",
                (like, int(mfr_id), str(source_category or "Other"), int(limit)),
            )
            for (n,) in cur.fetchall() or []:
                if n and n not in out:
                    out.append(str(n))
        except Exception:
            pass

        return out[: int(limit)]

    # ----------------------- pending -----------------------

    def _insert_pending(
        self,
        source_category: str,
        manufacturer: str,
        model_number: str,
        reason: str,
        details: Any | None = None,
    ) -> int:
        try:
            det = None
            if details is not None:
                try:
                    det = json.dumps(details, ensure_ascii=False)
                except Exception:
                    det = str(details)
            self.con.execute(
                "INSERT INTO catalog_pending(source_category, manufacturer, manufacturer_norm, model_number, model_norm, reason, details_json, created_at) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (
                    str(source_category or "Other"),
                    str(manufacturer or "").strip() or None,
                    _norm_text(manufacturer),
                    str(model_number or "").strip() or None,
                    _norm_text(model_number),
                    str(reason or ""),
                    det,
                    _now_iso(),
                ),
            )
            self.con.commit()
            pid = int(self.con.execute("SELECT last_insert_rowid()").fetchone()[0])
            self.audit_log("PENDING_INSERT", subject_type="PENDING", subject_id=pid, details={"reason": reason})
            return pid
        except Exception:
            try:
                self.con.commit()
            except Exception:
                pass
            return -1

    def list_pending(
        self,
        limit: int = 300,
        source_category: Optional[str] = None,
        search: str = "",
        text: str = "",
    ) -> List[Dict[str, Any]]:
        try:
            cur = self.con.cursor()
            sql = (
                "SELECT pending_id, source_category, manufacturer, model_number, reason, created_at "
                "FROM catalog_pending WHERE 1=1"
            )
            params: List[Any] = []
            if source_category:
                sql += " AND source_category=?"
                params.append(str(source_category))
            s = (search or text or "").strip()
            if s:
                like = "%" + s + "%"
                sql += " AND (manufacturer LIKE ? OR model_number LIKE ? OR reason LIKE ?)"
                params += [like, like, like]
            sql += " ORDER BY pending_id DESC LIMIT ?"
            params.append(int(limit))
            cur.execute(sql, tuple(params))
            return [dict(r) for r in (cur.fetchall() or [])]
        except Exception:
            return []

    def get_pending(self, pending_id: int) -> Optional[Dict[str, Any]]:
        try:
            cur = self.con.cursor()
            cur.execute("SELECT * FROM catalog_pending WHERE pending_id=?", (int(pending_id),))
            row = cur.fetchone()
            return dict(row) if row else None
        except Exception:
            return None

    def approve_pending(self, pending_id: int) -> Dict[str, Any]:
        p = self.get_pending(int(pending_id))
        if not p:
            return {"status": "MISSING"}

        cat = str(p.get("source_category") or "Other")
        mfr = str(p.get("manufacturer") or "").strip()
        mdl = str(p.get("model_number") or "").strip()

        # Approval forces canonical insertion.
        mfr_id = self._upsert_manufacturer(mfr)
        if not mfr_id:
            return {"status": "ERROR", "error": "manufacturer missing"}

        model_id = self._model_id(int(mfr_id), cat, mdl)
        now = _now_iso()
        if model_id:
            try:
                self.con.execute(
                    "UPDATE catalog_model SET usage_count=usage_count+1, updated_at=? WHERE model_id=?",
                    (now, int(model_id)),
                )
            except Exception:
                pass
        else:
            try:
                self.con.execute(
                    "INSERT INTO catalog_model(manufacturer_id, source_category, model_number, model_norm, usage_count, created_at, updated_at) "
                    "VALUES (?,?,?,?,?,?,?)",
                    (int(mfr_id), cat, mdl, _norm_text(mdl), 1, now, now),
                )
                model_id = int(self.con.execute("SELECT last_insert_rowid()").fetchone()[0])
            except Exception:
                model_id = self._model_id(int(mfr_id), cat, mdl)

        try:
            self.con.execute("DELETE FROM catalog_pending WHERE pending_id=?", (int(pending_id),))
            self.con.commit()
        except Exception:
            try:
                self.con.commit()
            except Exception:
                pass

        self.audit_log("PENDING_APPROVE", subject_type="PENDING", subject_id=int(pending_id), details={"model_id": model_id})
        return {"status": "APPROVED", "manufacturer_id": mfr_id, "model_id": model_id}

    def resolve_pending_to_model(
        self,
        pending_id: int,
        model_id: int,
        add_mfr_synonym: bool = True,
        add_model_synonym: bool = True,
    ) -> Dict[str, Any]:
        p = self.get_pending(int(pending_id))
        if not p:
            return {"status": "MISSING"}

        # Add synonyms so future matches resolve automatically
        try:
            if add_mfr_synonym and p.get("manufacturer"):
                # resolve manufacturer for the model
                cur = self.con.cursor()
                cur.execute("SELECT manufacturer_id FROM catalog_model WHERE model_id=?", (int(model_id),))
                r = cur.fetchone()
                if r and r[0] is not None:
                    self.add_manufacturer_synonym(str(p.get("manufacturer")), int(r[0]))
        except Exception:
            pass

        try:
            if add_model_synonym and p.get("model_number"):
                self.add_model_synonym(str(p.get("model_number")), int(model_id))
        except Exception:
            pass

        try:
            self.con.execute("DELETE FROM catalog_pending WHERE pending_id=?", (int(pending_id),))
            self.con.commit()
        except Exception:
            try:
                self.con.commit()
            except Exception:
                pass

        self.audit_log("PENDING_RESOLVE", subject_type="PENDING", subject_id=int(pending_id), details={"model_id": int(model_id)})
        return {"status": "RESOLVED"}

    def reject_pending(self, pending_id: int, reason: str = "") -> Dict[str, Any]:
        try:
            self.con.execute("DELETE FROM catalog_pending WHERE pending_id=?", (int(pending_id),))
            self.con.commit()
            self.audit_log("PENDING_REJECT", subject_type="PENDING", subject_id=int(pending_id), details={"reason": reason})
            return {"status": "REJECTED"}
        except Exception as e:
            try:
                self.con.commit()
            except Exception:
                pass
            return {"status": "ERROR", "error": str(e)}

    # ----------------------- learning / instances -----------------------

    def learn_make_model(
        self,
        source_category: str,
        manufacturer: str,
        model_number: str,
        engine_cycle: Optional[str] = None,
        engine_cyl_count: Optional[int] = None,
        duty_value: Optional[float] = None,
        duty_unit: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Upsert make/model into canonical tables.

        If strings look suspicious, route to pending queue instead.
        """
        cat = str(source_category or "Other")
        mfr = str(manufacturer or "").strip()
        mdl = str(model_number or "").strip()

        if not mfr or not mdl:
            return {"status": "SKIP"}

        if _is_suspicious_token(mfr) or _is_suspicious_token(mdl):
            pid = self._insert_pending(cat, mfr, mdl, reason="SUSPICIOUS", details={"engine_cycle": engine_cycle, "engine_cyl_count": engine_cyl_count})
            return {"status": "PENDING", "pending_id": pid}

        mfr_id = self._upsert_manufacturer(mfr)
        if not mfr_id:
            return {"status": "ERROR", "error": "manufacturer invalid"}

        now = _now_iso()
        model_id = self._model_id(int(mfr_id), cat, mdl)
        if model_id:
            # update usage + enrichment (best-effort)
            try:
                self.con.execute(
                    "UPDATE catalog_model SET usage_count=usage_count+1, updated_at=? WHERE model_id=?",
                    (now, int(model_id)),
                )
            except Exception:
                pass
            try:
                # fill enrichment fields if empty
                cur = self.con.cursor()
                cur.execute(
                    "SELECT engine_cycle, engine_cyl_count, duty_value, duty_unit FROM catalog_model WHERE model_id=?",
                    (int(model_id),),
                )
                row = cur.fetchone()
                if row:
                    updates: List[str] = []
                    params: List[Any] = []
                    if engine_cycle and (row[0] in (None, "")):
                        updates.append("engine_cycle=?")
                        params.append(str(engine_cycle))
                    if engine_cyl_count is not None and (row[1] is None):
                        updates.append("engine_cyl_count=?")
                        params.append(int(engine_cyl_count))
                    if duty_value is not None and (row[2] is None):
                        updates.append("duty_value=?")
                        params.append(float(duty_value))
                    if duty_unit and (row[3] in (None, "")):
                        updates.append("duty_unit=?")
                        params.append(str(duty_unit))
                    if updates:
                        params.extend([now, int(model_id)])
                        self.con.execute(
                            "UPDATE catalog_model SET " + ", ".join(updates) + ", updated_at=? WHERE model_id=?",
                            tuple(params),
                        )
            except Exception:
                pass

            try:
                self.con.commit()
            except Exception:
                pass

            return {"status": "EXISTS", "manufacturer_id": int(mfr_id), "model_id": int(model_id)}

        # insert
        try:
            self.con.execute(
                "INSERT INTO catalog_model(manufacturer_id, source_category, model_number, model_norm, engine_cycle, engine_cyl_count, duty_value, duty_unit, usage_count, created_at, updated_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (
                    int(mfr_id),
                    cat,
                    mdl,
                    _norm_text(mdl),
                    (str(engine_cycle) if engine_cycle else None),
                    (int(engine_cyl_count) if engine_cyl_count is not None else None),
                    (float(duty_value) if duty_value is not None else None),
                    (str(duty_unit) if duty_unit else None),
                    1,
                    now,
                    now,
                ),
            )
            model_id = int(self.con.execute("SELECT last_insert_rowid()").fetchone()[0])
            self.con.commit()
            self.audit_log("MODEL_INSERT", subject_type="MODEL", subject_id=int(model_id), details={"manufacturer": mfr, "model_number": mdl, "category": cat})
            return {"status": "INSERTED", "manufacturer_id": int(mfr_id), "model_id": int(model_id)}
        except Exception as e:
            try:
                self.con.commit()
            except Exception:
                pass
            return {"status": "ERROR", "error": str(e)}

    def upsert_instance(
        self,
        source_category: str,
        manufacturer: str,
        model_number: str,
        serial_number: str,
        asset_tag: Optional[str] = None,
        site_id: Optional[str] = None,
        location_id: Optional[str] = None,
        manufacture_date: Optional[str] = None,
        install_date: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        cat = str(source_category or "Other")
        mfr = str(manufacturer or "").strip()
        mdl = str(model_number or "").strip()
        ser = str(serial_number or "").strip()
        if not ser:
            return {"status": "SKIP"}

        # Ensure make/model exists
        lm = self.learn_make_model(cat, mfr, mdl)
        if str(lm.get("status")) not in ("INSERTED", "EXISTS"):
            return {"status": "PENDING" if lm.get("status") == "PENDING" else "ERROR"}

        mfr_id = self._manufacturer_id_by_name(mfr) or lm.get("manufacturer_id")
        model_id = lm.get("model_id")
        if not (mfr_id and model_id):
            return {"status": "ERROR"}

        now = _now_iso()
        ser_norm = _norm_text(ser)
        asset_norm = _norm_text(asset_tag) if asset_tag else None

        cur = self.con.cursor()
        try:
            cur.execute(
                "SELECT instance_id FROM catalog_instance WHERE source_category=? AND serial_norm=?",
                (cat, ser_norm),
            )
            row = cur.fetchone()
            if row:
                iid = int(row[0])
                self.con.execute(
                    "UPDATE catalog_instance SET model_id=?, manufacturer_id=?, serial_number=?, asset_tag=?, asset_norm=?, site_id=?, location_id=?, usage_count=usage_count+1, updated_at=? "
                    "WHERE instance_id=?",
                    (
                        int(model_id),
                        int(mfr_id),
                        ser,
                        (asset_tag if asset_tag else None),
                        asset_norm,
                        (site_id if site_id else None),
                        (location_id if location_id else None),
                        now,
                        iid,
                    ),
                )
                if manufacture_date is not None:
                    self.set_instance_attr(iid, "manufacture_date", manufacture_date, value_type="TEXT")
                if install_date is not None:
                    self.set_instance_attr(iid, "install_date", install_date, value_type="TEXT")
                if notes is not None:
                    self.set_instance_attr(iid, "notes", notes, value_type="TEXT")
                self.con.commit()
                return {"status": "UPDATED", "instance_id": iid}
        except Exception:
            pass

        try:
            self.con.execute(
                "INSERT INTO catalog_instance(model_id, source_category, manufacturer_id, serial_number, serial_norm, asset_tag, asset_norm, site_id, location_id, usage_count, created_at, updated_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    int(model_id),
                    cat,
                    int(mfr_id),
                    ser,
                    ser_norm,
                    (asset_tag if asset_tag else None),
                    asset_norm,
                    (site_id if site_id else None),
                    (location_id if location_id else None),
                    1,
                    now,
                    now,
                ),
            )
            iid = int(self.con.execute("SELECT last_insert_rowid()") .fetchone()[0])
            if manufacture_date is not None:
                self.set_instance_attr(iid, "manufacture_date", manufacture_date, value_type="TEXT")
            if install_date is not None:
                self.set_instance_attr(iid, "install_date", install_date, value_type="TEXT")
            if notes is not None:
                self.set_instance_attr(iid, "notes", notes, value_type="TEXT")
            self.con.commit()
            self.audit_log("INSTANCE_INSERT", subject_type="INSTANCE", subject_id=iid, details={"category": cat, "serial": ser})
            return {"status": "INSERTED", "instance_id": iid}
        except Exception as e:
            try:
                self.con.commit()
            except Exception:
                pass
            return {"status": "ERROR", "error": str(e)}

    def _ensure_instance_attr_table(self) -> None:
        try:
            self.con.execute(
                "CREATE TABLE IF NOT EXISTS catalog_instance_attr ("
                "instance_id INTEGER NOT NULL, "
                "attr_key TEXT NOT NULL, "
                "attr_value TEXT, "
                "value_type TEXT NOT NULL DEFAULT 'TEXT', "
                "updated_at TEXT NOT NULL, "
                "PRIMARY KEY(instance_id, attr_key), "
                "FOREIGN KEY(instance_id) REFERENCES catalog_instance(instance_id) ON DELETE CASCADE)"
            )
            self.con.execute(
                "CREATE INDEX IF NOT EXISTS idx_catalog_instance_attr_inst ON catalog_instance_attr(instance_id)"
            )
            self.con.commit()
        except Exception:
            try:
                self.con.commit()
            except Exception:
                pass

    def _coerce_attr_value(self, value: Any, value_type: str) -> Any:
        vt = str(value_type or "TEXT").strip().upper()
        if value is None:
            return None
        if vt == "INT":
            try:
                return int(float(value))
            except Exception:
                return value
        if vt == "REAL":
            try:
                return float(value)
            except Exception:
                return value
        if vt == "BOOL":
            try:
                return str(value).strip().lower() in ("1", "true", "yes", "y", "on")
            except Exception:
                return value
        if vt == "JSON":
            try:
                return json.loads(str(value))
            except Exception:
                return value
        return value

    def _instance_attrs(self, instance_id: int) -> Dict[str, Any]:
        self._ensure_instance_attr_table()
        try:
            cur = self.con.cursor()
            cur.execute(
                "SELECT attr_key, attr_value, value_type FROM catalog_instance_attr WHERE instance_id=? ORDER BY attr_key COLLATE NOCASE ASC",
                (int(instance_id),),
            )
            out: Dict[str, Any] = {}
            for row in cur.fetchall() or []:
                key = str(row[0] or "").strip()
                if not key:
                    continue
                out[key] = self._coerce_attr_value(row[1], str(row[2] or "TEXT"))
            return out
        except Exception:
            return {}

    def set_instance_attr(self, instance_id: int, attr_key: str, attr_value: Any, value_type: str = "TEXT") -> Dict[str, Any]:
        self._ensure_instance_attr_table()
        key = str(attr_key or "").strip()
        if not key:
            return {"status": "SKIP"}
        try:
            iid = int(instance_id)
        except Exception:
            return {"status": "ERROR", "error": "invalid instance_id"}
        try:
            val = None if attr_value is None else str(attr_value).strip()
            if val in (None, ""):
                self.con.execute(
                    "DELETE FROM catalog_instance_attr WHERE instance_id=? AND attr_key=?",
                    (iid, key),
                )
            else:
                now = _now_iso()
                self.con.execute(
                    "INSERT INTO catalog_instance_attr(instance_id, attr_key, attr_value, value_type, updated_at) "
                    "VALUES (?,?,?,?,?) "
                    "ON CONFLICT(instance_id, attr_key) DO UPDATE SET "
                    "attr_value=excluded.attr_value, value_type=excluded.value_type, updated_at=excluded.updated_at",
                    (iid, key, val, str(value_type or "TEXT").strip().upper() or "TEXT", now),
                )
            self.con.execute("UPDATE catalog_instance SET updated_at=? WHERE instance_id=?", (_now_iso(), iid))
            self.con.commit()
            return {"status": "OK"}
        except Exception as e:
            try:
                self.con.commit()
            except Exception:
                pass
            return {"status": "ERROR", "error": str(e)}

    def get_instance(self, instance_id: int) -> Optional[Dict[str, Any]]:
        self._ensure_instance_attr_table()
        try:
            cur = self.con.cursor()
            cur.execute(
                "SELECT i.instance_id, i.model_id, i.source_category, i.manufacturer_id, "
                "i.serial_number, i.asset_tag, i.site_id, i.location_id, i.usage_count, i.created_at, i.updated_at, "
                "m.model_number, m.engine_cycle, m.engine_cyl_count, m.duty_value, m.duty_unit, "
                "mf.name AS manufacturer "
                "FROM catalog_instance i "
                "JOIN catalog_model m ON m.model_id = i.model_id "
                "JOIN catalog_manufacturer mf ON mf.manufacturer_id = i.manufacturer_id "
                "WHERE i.instance_id=?",
                (int(instance_id),),
            )
            row = cur.fetchone()
            if not row:
                return None
            out = dict(row)
            attrs = self._instance_attrs(int(instance_id))
            if out.get("engine_cycle") is not None:
                attrs.setdefault("engine_cycle", out.get("engine_cycle"))
            if out.get("engine_cyl_count") is not None:
                attrs.setdefault("engine_cyl_count", out.get("engine_cyl_count"))
            if out.get("duty_value") is not None:
                attrs.setdefault("duty_value", out.get("duty_value"))
            if out.get("duty_unit"):
                attrs.setdefault("duty_unit", out.get("duty_unit"))
            out["attrs"] = attrs
            out["manufacture_date"] = attrs.get("manufacture_date")
            out["install_date"] = attrs.get("install_date")
            out["notes"] = attrs.get("notes")
            return out
        except Exception:
            return None

    def list_instances(
        self,
        limit: int = 250,
        source_category: Optional[str] = None,
        manufacturer: Optional[str] = None,
        model_number: Optional[str] = None,
        serial: Optional[str] = None,
        asset_tag: Optional[str] = None,
        site_id: Optional[str] = None,
        location_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        try:
            cur = self.con.cursor()
            sql = (
                "SELECT i.instance_id, i.source_category, mf.name AS manufacturer, m.model_number, "
                "i.serial_number, i.asset_tag, i.site_id, i.location_id, i.updated_at "
                "FROM catalog_instance i "
                "JOIN catalog_model m ON m.model_id = i.model_id "
                "JOIN catalog_manufacturer mf ON mf.manufacturer_id = i.manufacturer_id "
                "WHERE 1=1"
            )
            params: List[Any] = []
            if source_category:
                sql += " AND i.source_category=?"
                params.append(str(source_category))
            if manufacturer:
                sql += " AND mf.name LIKE ?"
                params.append(f"%{str(manufacturer).strip()}%")
            if model_number:
                sql += " AND m.model_number LIKE ?"
                params.append(f"%{str(model_number).strip()}%")
            if serial:
                sql += " AND i.serial_number LIKE ?"
                params.append(f"%{str(serial).strip()}%")
            if asset_tag:
                sql += " AND COALESCE(i.asset_tag,'') LIKE ?"
                params.append(f"%{str(asset_tag).strip()}%")
            if site_id:
                sql += " AND COALESCE(i.site_id,'') LIKE ?"
                params.append(f"%{str(site_id).strip()}%")
            if location_id:
                sql += " AND COALESCE(i.location_id,'') LIKE ?"
                params.append(f"%{str(location_id).strip()}%")
            sql += " ORDER BY i.updated_at DESC, i.instance_id DESC LIMIT ?"
            params.append(int(limit))
            cur.execute(sql, tuple(params))
            return [dict(r) for r in (cur.fetchall() or [])]
        except Exception:
            return []

    def update_instance_base(
        self,
        instance_id: int,
        site_id: Optional[str] = None,
        location_id: Optional[str] = None,
        asset_tag: Optional[str] = None,
        manufacture_date: Optional[str] = None,
        install_date: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        try:
            iid = int(instance_id)
        except Exception:
            return {"status": "ERROR", "error": "invalid instance_id"}

        asset_norm = _norm_text(asset_tag) if asset_tag else None
        try:
            self.con.execute(
                "UPDATE catalog_instance SET asset_tag=?, asset_norm=?, site_id=?, location_id=?, updated_at=? WHERE instance_id=?",
                (
                    asset_tag if asset_tag else None,
                    asset_norm,
                    site_id if site_id else None,
                    location_id if location_id else None,
                    _now_iso(),
                    iid,
                ),
            )
            if manufacture_date is not None:
                self.set_instance_attr(iid, "manufacture_date", manufacture_date, value_type="TEXT")
            if install_date is not None:
                self.set_instance_attr(iid, "install_date", install_date, value_type="TEXT")
            if notes is not None:
                self.set_instance_attr(iid, "notes", notes, value_type="TEXT")
            self.con.commit()
            return {"status": "OK", "instance_id": iid}
        except Exception as e:
            try:
                self.con.commit()
            except Exception:
                pass
            return {"status": "ERROR", "error": str(e)}

    def list_model_variants(self, model_id: int, limit: int = 250) -> List[Dict[str, Any]]:
        try:
            cur = self.con.cursor()
            cur.execute(
                "SELECT engine_cycle, engine_cyl_count, duty_value, duty_unit FROM catalog_model WHERE model_id=?",
                (int(model_id),),
            )
            model_row = cur.fetchone()
            model_defaults = {
                "engine_cycle": (model_row[0] if model_row else None),
                "engine_cyl_count": (model_row[1] if model_row else None),
                "duty_value": (model_row[2] if model_row else None),
                "duty_unit": (model_row[3] if model_row else None),
                "fuel_family": None,
            }
            cur.execute(
                "SELECT variant_id, model_id, variant_name, created_at, updated_at "
                "FROM catalog_variant WHERE model_id=? ORDER BY variant_name COLLATE NOCASE ASC LIMIT ?",
                (int(model_id), int(limit)),
            )
            out: List[Dict[str, Any]] = []
            for row in cur.fetchall() or []:
                d = dict(row)
                d.update(model_defaults)
                out.append(d)
            return out
        except Exception:
            return []

    # ----------------------- synonyms -----------------------

    def list_synonyms(self, synonym_type: Optional[str] = None, limit: int = 500) -> List[Dict[str, Any]]:
        try:
            cur = self.con.cursor()
            sql = (
                "SELECT s.synonym_id, s.synonym_type, s.synonym, s.canonical_manufacturer_id, s.canonical_model_id, s.created_at "
                "FROM catalog_synonym s WHERE 1=1"
            )
            params: List[Any] = []
            if synonym_type:
                sql += " AND s.synonym_type=?"
                params.append(str(synonym_type))
            sql += " ORDER BY s.synonym_type ASC, s.synonym COLLATE NOCASE ASC LIMIT ?"
            params.append(int(limit))
            cur.execute(sql, tuple(params))
            rows = cur.fetchall() or []

            out: List[Dict[str, Any]] = []
            for r in rows:
                d = dict(r)
                canon_id = d.get("canonical_manufacturer_id") or d.get("canonical_model_id")
                d["canonical_id"] = canon_id

                canon_name = ""
                try:
                    if d.get("synonym_type") == "MANUFACTURER" and d.get("canonical_manufacturer_id"):
                        cur2 = self.con.cursor()
                        cur2.execute(
                            "SELECT name FROM catalog_manufacturer WHERE manufacturer_id=?",
                            (int(d.get("canonical_manufacturer_id")),),
                        )
                        rr = cur2.fetchone()
                        canon_name = str(rr[0]) if rr and rr[0] is not None else ""
                    elif d.get("synonym_type") == "MODEL" and d.get("canonical_model_id"):
                        cur2 = self.con.cursor()
                        cur2.execute(
                            "SELECT m.model_number, mf.name FROM catalog_model m JOIN catalog_manufacturer mf ON mf.manufacturer_id=m.manufacturer_id WHERE m.model_id=?",
                            (int(d.get("canonical_model_id")),),
                        )
                        rr = cur2.fetchone()
                        if rr:
                            canon_name = f"{rr[1]} | {rr[0]}" if rr[1] else str(rr[0])
                except Exception:
                    canon_name = ""

                d["canonical_name"] = canon_name
                out.append(d)
            return out
        except Exception:
            return []

    def add_manufacturer_synonym(self, synonym: str, manufacturer_id: int) -> Dict[str, Any]:
        syn = str(synonym or "").strip()
        sn = _norm_text(syn)
        if not sn:
            return {"status": "SKIP"}
        try:
            now = _now_iso()
            self.con.execute(
                "INSERT INTO catalog_synonym(synonym_type, synonym, synonym_norm, canonical_manufacturer_id, canonical_model_id, created_at, updated_at) "
                "VALUES ('MANUFACTURER', ?, ?, ?, NULL, ?, ?) "
                "ON CONFLICT(synonym_type, synonym_norm) DO UPDATE SET synonym=excluded.synonym, canonical_manufacturer_id=excluded.canonical_manufacturer_id, updated_at=excluded.updated_at",
                (syn, sn, int(manufacturer_id), now, now),
            )
            self.con.commit()
            self.audit_log("SYNONYM_UPSERT", subject_type="MANUFACTURER", subject_id=int(manufacturer_id), details={"synonym": syn})
            return {"status": "OK"}
        except Exception as e:
            try:
                self.con.commit()
            except Exception:
                pass
            return {"status": "ERROR", "error": str(e)}

    def add_model_synonym(self, synonym: str, model_id: int) -> Dict[str, Any]:
        syn = str(synonym or "").strip()
        sn = _norm_text(syn)
        if not sn:
            return {"status": "SKIP"}
        try:
            now = _now_iso()
            self.con.execute(
                "INSERT INTO catalog_synonym(synonym_type, synonym, synonym_norm, canonical_manufacturer_id, canonical_model_id, created_at, updated_at) "
                "VALUES ('MODEL', ?, ?, NULL, ?, ?, ?) "
                "ON CONFLICT(synonym_type, synonym_norm) DO UPDATE SET synonym=excluded.synonym, canonical_model_id=excluded.canonical_model_id, updated_at=excluded.updated_at",
                (syn, sn, int(model_id), now, now),
            )
            self.con.commit()
            self.audit_log("SYNONYM_UPSERT", subject_type="MODEL", subject_id=int(model_id), details={"synonym": syn})
            return {"status": "OK"}
        except Exception as e:
            try:
                self.con.commit()
            except Exception:
                pass
            return {"status": "ERROR", "error": str(e)}

    def delete_synonym(self, synonym_id: int) -> Dict[str, Any]:
        try:
            self.con.execute("DELETE FROM catalog_synonym WHERE synonym_id=?", (int(synonym_id),))
            self.con.commit()
            self.audit_log("SYNONYM_DELETE", subject_type="SYNONYM", subject_id=int(synonym_id))
            return {"status": "OK"}
        except Exception as e:
            try:
                self.con.commit()
            except Exception:
                pass
            return {"status": "ERROR", "error": str(e)}

    # ----------------------- merges -----------------------

    def merge_manufacturers(self, canonical_manufacturer_id: int, merge_manufacturer_id: int, add_synonym: bool = True) -> Dict[str, Any]:
        """Merge manufacturer B into manufacturer A."""
        a = int(canonical_manufacturer_id)
        b = int(merge_manufacturer_id)
        if a == b:
            return {"status": "SKIP"}

        cur = self.con.cursor()
        try:
            cur.execute("SELECT name FROM catalog_manufacturer WHERE manufacturer_id=?", (b,))
            row = cur.fetchone()
            b_name = str(row[0]) if row and row[0] is not None else ""
        except Exception:
            b_name = ""

        try:
            # Move models: if collisions occur, fold usage_count into existing and delete duplicate.
            cur.execute("SELECT model_id, source_category, model_norm, usage_count FROM catalog_model WHERE manufacturer_id=?", (b,))
            rows = cur.fetchall() or []
            for r in rows:
                mid = int(r[0])
                cat = str(r[1])
                mn = str(r[2])
                uc = int(r[3] or 0)

                cur.execute(
                    "SELECT model_id, usage_count FROM catalog_model WHERE manufacturer_id=? AND source_category=? AND model_norm=?",
                    (a, cat, mn),
                )
                ex = cur.fetchone()
                if ex:
                    keep_id = int(ex[0])
                    keep_uc = int(ex[1] or 0)
                    # move instances
                    self.con.execute("UPDATE catalog_instance SET model_id=? WHERE model_id=?", (keep_id, mid))
                    # accumulate usage
                    self.con.execute("UPDATE catalog_model SET usage_count=? WHERE model_id=?", (keep_uc + uc, keep_id))
                    # delete duplicate model
                    self.con.execute("DELETE FROM catalog_model WHERE model_id=?", (mid,))
                else:
                    self.con.execute("UPDATE catalog_model SET manufacturer_id=? WHERE model_id=?", (a, mid))

            # Add synonym for merged manufacturer name
            if add_synonym and b_name:
                try:
                    self.add_manufacturer_synonym(b_name, a)
                except Exception:
                    pass

            # Delete merged manufacturer
            self.con.execute("DELETE FROM catalog_manufacturer WHERE manufacturer_id=?", (b,))
            self.con.commit()
            self.audit_log("MERGE_MANUFACTURER", subject_type="MANUFACTURER", subject_id=a, details={"merged_id": b, "merged_name": b_name})
            return {"status": "OK"}
        except Exception as e:
            try:
                self.con.commit()
            except Exception:
                pass
            return {"status": "ERROR", "error": str(e)}

    def merge_models(self, canonical_model_id: int, merge_model_id: int, add_synonym: bool = True) -> Dict[str, Any]:
        a = int(canonical_model_id)
        b = int(merge_model_id)
        if a == b:
            return {"status": "SKIP"}

        cur = self.con.cursor()
        try:
            cur.execute("SELECT model_number FROM catalog_model WHERE model_id=?", (b,))
            row = cur.fetchone()
            b_name = str(row[0]) if row and row[0] is not None else ""
        except Exception:
            b_name = ""

        try:
            # move instances
            self.con.execute("UPDATE catalog_instance SET model_id=? WHERE model_id=?", (a, b))

            # accumulate usage
            cur.execute("SELECT usage_count FROM catalog_model WHERE model_id=?", (a,))
            a_uc = int((cur.fetchone() or [0])[0] or 0)
            cur.execute("SELECT usage_count FROM catalog_model WHERE model_id=?", (b,))
            b_uc = int((cur.fetchone() or [0])[0] or 0)
            self.con.execute("UPDATE catalog_model SET usage_count=? WHERE model_id=?", (a_uc + b_uc, a))

            if add_synonym and b_name:
                try:
                    self.add_model_synonym(b_name, a)
                except Exception:
                    pass

            self.con.execute("DELETE FROM catalog_model WHERE model_id=?", (b,))
            self.con.commit()
            self.audit_log("MERGE_MODEL", subject_type="MODEL", subject_id=a, details={"merged_id": b, "merged_name": b_name})
            return {"status": "OK"}
        except Exception as e:
            try:
                self.con.commit()
            except Exception:
                pass
            return {"status": "ERROR", "error": str(e)}


__all__ = ["MoleDBConfig", "MoleMasterDB"]
