-- MOLE Master DB schema (v3)
-- Portable SQLite catalog for make/model, instances, QA/QC events, and governance.

PRAGMA foreign_keys=ON;

BEGIN;

-- Schema migration marker
CREATE TABLE IF NOT EXISTS meta_schema_migrations (
    version     INTEGER PRIMARY KEY,
    applied_at  TEXT NOT NULL
);

-- Canonical manufacturers
CREATE TABLE IF NOT EXISTS catalog_manufacturer (
    manufacturer_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL,
    name_norm       TEXT NOT NULL UNIQUE,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);

-- Canonical models
CREATE TABLE IF NOT EXISTS catalog_model (
    model_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    manufacturer_id  INTEGER NOT NULL,
    source_category  TEXT NOT NULL,
    model_number     TEXT NOT NULL,
    model_norm       TEXT NOT NULL,

    -- optional enrichment fields (engine-focused)
    engine_cycle     TEXT,
    engine_cyl_count INTEGER,
    duty_value       REAL,
    duty_unit        TEXT,

    usage_count      INTEGER NOT NULL DEFAULT 0,
    created_at       TEXT NOT NULL,
    updated_at       TEXT NOT NULL,

    UNIQUE(manufacturer_id, source_category, model_norm),
    FOREIGN KEY(manufacturer_id) REFERENCES catalog_manufacturer(manufacturer_id) ON DELETE CASCADE
);

-- Optional: variants (future expansion; kept light for governance counts)
CREATE TABLE IF NOT EXISTS catalog_variant (
    variant_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    model_id      INTEGER NOT NULL,
    variant_name  TEXT NOT NULL,
    variant_norm  TEXT NOT NULL,
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL,

    UNIQUE(model_id, variant_norm),
    FOREIGN KEY(model_id) REFERENCES catalog_model(model_id) ON DELETE CASCADE
);

-- Concrete asset instances (serialized equipment)
CREATE TABLE IF NOT EXISTS catalog_instance (
    instance_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    model_id        INTEGER NOT NULL,
    source_category TEXT NOT NULL,
    manufacturer_id INTEGER NOT NULL,

    serial_number   TEXT NOT NULL,
    serial_norm     TEXT NOT NULL,
    asset_tag       TEXT,
    asset_norm      TEXT,

    site_id         TEXT,
    location_id     TEXT,

    usage_count     INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL,

    UNIQUE(source_category, serial_norm),
    FOREIGN KEY(model_id) REFERENCES catalog_model(model_id) ON DELETE CASCADE,
    FOREIGN KEY(manufacturer_id) REFERENCES catalog_manufacturer(manufacturer_id) ON DELETE CASCADE
);

-- Optional serialized instance attributes (engine cycle, duty, dates, notes, fuel hints, etc.)
CREATE TABLE IF NOT EXISTS catalog_instance_attr (
    instance_id  INTEGER NOT NULL,
    attr_key     TEXT NOT NULL,
    attr_value   TEXT,
    value_type   TEXT NOT NULL DEFAULT 'TEXT',
    updated_at   TEXT NOT NULL,

    PRIMARY KEY(instance_id, attr_key),
    FOREIGN KEY(instance_id) REFERENCES catalog_instance(instance_id) ON DELETE CASCADE
);

-- Pending / quarantine (governance review)
CREATE TABLE IF NOT EXISTS catalog_pending (
    pending_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    source_category   TEXT NOT NULL,
    manufacturer      TEXT,
    manufacturer_norm TEXT,
    model_number      TEXT,
    model_norm        TEXT,
    reason            TEXT,
    details_json      TEXT,
    created_at        TEXT NOT NULL
);

-- Synonyms: alias -> canonical mapping
CREATE TABLE IF NOT EXISTS catalog_synonym (
    synonym_id              INTEGER PRIMARY KEY AUTOINCREMENT,
    synonym_type            TEXT NOT NULL, -- MANUFACTURER | MODEL
    synonym                 TEXT NOT NULL,
    synonym_norm            TEXT NOT NULL,
    canonical_manufacturer_id INTEGER,
    canonical_model_id      INTEGER,
    created_at              TEXT NOT NULL,
    updated_at              TEXT NOT NULL,

    UNIQUE(synonym_type, synonym_norm),
    FOREIGN KEY(canonical_manufacturer_id) REFERENCES catalog_manufacturer(manufacturer_id) ON DELETE CASCADE,
    FOREIGN KEY(canonical_model_id) REFERENCES catalog_model(model_id) ON DELETE CASCADE
);

-- Audit trail (governance actions)
CREATE TABLE IF NOT EXISTS catalog_audit_log (
    audit_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at   TEXT NOT NULL,
    actor        TEXT NOT NULL,
    action       TEXT NOT NULL,
    subject_type TEXT,
    subject_id   INTEGER,
    details_json TEXT
);

-- QA/QC calibration events (wizard trending viewer reads this table)
CREATE TABLE IF NOT EXISTS qaqc_cal_event (
    event_id                         INTEGER PRIMARY KEY AUTOINCREMENT,
    event_iso                        TEXT NOT NULL,
    run_id                           TEXT,
    phase                            TEXT,
    pollutant                         TEXT,
    event_type                       TEXT,

    meas                             REAL,
    target                           REAL,
    recovery_pct                     REAL,

    drift_abs                        REAL,
    drift_recovery_pct               REAL,
    drift_rate_abs_per_hr            REAL,
    drift_rate_recovery_pct_per_hr   REAL,
    combined_drift_ratio             REAL,

    health                           TEXT,

    manufacturer                     TEXT,
    model_number                     TEXT,
    serial_number                    TEXT,

    site_id                          TEXT,
    location_id                      TEXT,
    source_category                  TEXT
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_catalog_model_cat_mfr ON catalog_model(source_category, manufacturer_id);
CREATE INDEX IF NOT EXISTS idx_catalog_instance_mfr ON catalog_instance(manufacturer_id);
CREATE INDEX IF NOT EXISTS idx_catalog_instance_serial ON catalog_instance(serial_norm);
CREATE INDEX IF NOT EXISTS idx_catalog_instance_attr_inst ON catalog_instance_attr(instance_id);
CREATE INDEX IF NOT EXISTS idx_pending_cat ON catalog_pending(source_category);
CREATE INDEX IF NOT EXISTS idx_synonym_norm ON catalog_synonym(synonym_type, synonym_norm);
CREATE INDEX IF NOT EXISTS idx_qaqc_event_iso ON qaqc_cal_event(event_iso);

COMMIT;
