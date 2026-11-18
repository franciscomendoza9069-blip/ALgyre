PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS auth(
    id INTEGER PRIMARY KEY CHECK(id=1),
    salt TEXT NOT NULL,
    password_hash TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS company(
    id INTEGER PRIMARY KEY CHECK(id=1),
    name TEXT NOT NULL,
    country TEXT NOT NULL DEFAULT '',
    boundary TEXT NOT NULL DEFAULT '',
    exclusions TEXT NOT NULL DEFAULT '',
    year INTEGER NOT NULL DEFAULT 2026,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS facilities(
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    country TEXT NOT NULL,
    ownership TEXT NOT NULL CHECK(ownership IN ('owned','rented')),
    categories TEXT NOT NULL,
    archived INTEGER NOT NULL DEFAULT 0 CHECK(archived IN (0,1)),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS factors(
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    category TEXT NOT NULL CHECK(category IN ('electricity','gas','diesel','petrol','refrigerant','heat','cooling','purchased_goods','upstream_transport','waste','business_travel','commuting','water')),
    country TEXT NOT NULL,
    year INTEGER NOT NULL CHECK(year BETWEEN 2000 AND 2100),
    unit TEXT NOT NULL CHECK(unit IN ('kWh','L','kg','m3','unit','tkm','pkm','km','night')),
    value TEXT NOT NULL,
    source TEXT NOT NULL,
    version TEXT NOT NULL,
    license TEXT NOT NULL,
    validated INTEGER NOT NULL CHECK(validated=1),
    method TEXT NOT NULL DEFAULT 'location',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS documents(
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    hash TEXT NOT NULL UNIQUE,
    content BLOB NOT NULL,
    text TEXT NOT NULL,
    extracted TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS consumptions(
    id TEXT PRIMARY KEY,
    facility_id TEXT NOT NULL REFERENCES facilities(id) ON DELETE RESTRICT,
    document_id TEXT REFERENCES documents(id) ON DELETE RESTRICT,
    category TEXT NOT NULL CHECK(category IN ('electricity','gas','diesel','petrol','refrigerant','heat','cooling','purchased_goods','upstream_transport','waste','business_travel','commuting','water')),
    quantity TEXT NOT NULL,
    unit TEXT NOT NULL CHECK(unit IN ('kWh','MWh','L','kg','m3','t','unit','tkm','pkm','km','night')),
    start TEXT NOT NULL,
    end TEXT NOT NULL,
    supplier TEXT NOT NULL DEFAULT '',
    reference TEXT NOT NULL DEFAULT '',
    factor_id TEXT REFERENCES factors(id) ON DELETE RESTRICT,
    note TEXT NOT NULL DEFAULT '',
    estimated INTEGER NOT NULL DEFAULT 0 CHECK(estimated IN (0,1)),
    revision INTEGER NOT NULL DEFAULT 1 CHECK(revision>0),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    CHECK(end>=start)
);
CREATE TABLE IF NOT EXISTS calculations(
    id TEXT PRIMARY KEY,
    consumption_id TEXT NOT NULL REFERENCES consumptions(id) ON DELETE RESTRICT,
    revision INTEGER NOT NULL,
    factor_id TEXT NOT NULL REFERENCES factors(id) ON DELETE RESTRICT,
    normalized_quantity TEXT NOT NULL,
    kg_co2e TEXT NOT NULL,
    engine TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(consumption_id,revision,factor_id)
);
CREATE TABLE IF NOT EXISTS events(
    id TEXT PRIMARY KEY,
    entity TEXT NOT NULL,
    record_id TEXT NOT NULL,
    action TEXT NOT NULL,
    before_json TEXT,
    after_json TEXT,
    reason TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS reports(
    id TEXT PRIMARY KEY,
    year INTEGER NOT NULL,
    name TEXT NOT NULL,
    snapshot TEXT NOT NULL,
    fingerprint TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_consumptions_facility_dates ON consumptions(
    facility_id,
    start,
    end
);
CREATE INDEX IF NOT EXISTS ix_consumptions_document ON consumptions(
    document_id
);
CREATE INDEX IF NOT EXISTS ix_consumptions_factor ON consumptions(
    factor_id
);
CREATE INDEX IF NOT EXISTS ix_factors_match ON factors(
    category,
    country,
    year,
    unit
);
CREATE INDEX IF NOT EXISTS ix_calculations_consumption ON calculations(
    consumption_id
);
CREATE INDEX IF NOT EXISTS ix_calculations_factor ON calculations(
    factor_id
);
CREATE INDEX IF NOT EXISTS ix_events_date ON events(
    created_at
);
CREATE INDEX IF NOT EXISTS ix_reports_year ON reports(
    year
);
