-- SmartLocker Edge - SQLite Schema
-- Local database for offline-first operation
-- WAL mode enabled for crash safety

PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

-- ============================================================
-- CONFIGURATION (synced from cloud)
-- ============================================================

CREATE TABLE IF NOT EXISTS product (
    product_id TEXT PRIMARY KEY,
    ppg_code TEXT UNIQUE,
    name TEXT NOT NULL,
    product_type TEXT NOT NULL,  -- 'base_paint', 'hardener', 'thinner', 'primer'
    density_g_per_ml REAL DEFAULT 1.0,
    pot_life_minutes INTEGER,
    hazard_class TEXT DEFAULT '',
    can_sizes_ml TEXT DEFAULT '[]',       -- JSON array
    can_tare_weight_g TEXT DEFAULT '{}',  -- JSON object {size_ml: tare_grams}
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS mixing_recipe (
    recipe_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    base_product_id TEXT REFERENCES product(product_id),
    hardener_product_id TEXT REFERENCES product(product_id),
    ratio_base REAL NOT NULL,
    ratio_hardener REAL NOT NULL,
    tolerance_pct REAL DEFAULT 5.0,
    thinner_pct_brush REAL DEFAULT 5.0,
    thinner_pct_roller REAL DEFAULT 5.0,
    thinner_pct_spray REAL DEFAULT 10.0,
    recommended_thinner_id TEXT REFERENCES product(product_id),
    pot_life_minutes INTEGER DEFAULT 480,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS maintenance_chart (
    chart_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    vessel_type TEXT,
    area_type TEXT,
    iso_category TEXT,
    layers TEXT DEFAULT '[]',  -- JSON array of layer definitions
    version INTEGER DEFAULT 1,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS config (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- LOCAL STATE
-- ============================================================

CREATE TABLE IF NOT EXISTS shelf (
    shelf_id TEXT PRIMARY KEY,
    position INTEGER NOT NULL,
    weight_channel TEXT NOT NULL,
    tare_weight_g REAL DEFAULT 0,
    max_weight_g REAL DEFAULT 50000
);

CREATE TABLE IF NOT EXISTS slot (
    slot_id TEXT PRIMARY KEY,
    shelf_id TEXT REFERENCES shelf(shelf_id),
    position INTEGER NOT NULL,
    rfid_reader_id TEXT NOT NULL,
    led_index INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS slot_state (
    slot_id TEXT PRIMARY KEY REFERENCES slot(slot_id),
    status TEXT DEFAULT 'empty',
    current_tag_id TEXT,
    current_product_id TEXT,
    weight_when_placed_g REAL DEFAULT 0,
    weight_current_g REAL DEFAULT 0,
    last_change_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS weight_snapshot (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    shelf_id TEXT NOT NULL,
    channel TEXT NOT NULL,
    grams REAL DEFAULT 0,
    raw_value INTEGER DEFAULT 0,
    stable INTEGER DEFAULT 0,
    source TEXT DEFAULT 'periodic',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_weight_snapshot_shelf_time
ON weight_snapshot(shelf_id, created_at DESC);

CREATE TABLE IF NOT EXISTS rfid_tag (
    tag_uid TEXT PRIMARY KEY,
    product_id TEXT REFERENCES product(product_id),
    batch_number TEXT,
    can_size_ml INTEGER,
    weight_full_g REAL,
    weight_current_g REAL,
    color TEXT DEFAULT '',
    assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- EVENT LOG (append-only, tamper-evident)
-- ============================================================

CREATE TABLE IF NOT EXISTS event_log (
    event_id TEXT PRIMARY KEY,
    sequence_num INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    timestamp REAL NOT NULL,
    device_id TEXT NOT NULL,
    shelf_id TEXT DEFAULT '',
    slot_id TEXT DEFAULT '',
    tag_id TEXT DEFAULT '',
    session_id TEXT DEFAULT '',
    user_name TEXT DEFAULT '',
    data_json TEXT DEFAULT '{}',
    confirmation TEXT DEFAULT 'unconfirmed',
    synced INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_event_log_type ON event_log(event_type);
CREATE INDEX IF NOT EXISTS idx_event_log_timestamp ON event_log(timestamp);
CREATE INDEX IF NOT EXISTS idx_event_log_synced ON event_log(synced);
CREATE INDEX IF NOT EXISTS idx_event_log_session ON event_log(session_id);

-- ============================================================
-- MIXING SESSIONS
-- ============================================================

CREATE TABLE IF NOT EXISTS mixing_session (
    session_id TEXT PRIMARY KEY,
    recipe_id TEXT REFERENCES mixing_recipe(recipe_id),
    job_id TEXT,
    user_name TEXT DEFAULT '',
    started_at REAL,
    completed_at REAL,
    base_product_id TEXT,
    base_tag_id TEXT,
    base_weight_target_g REAL DEFAULT 0,
    base_weight_actual_g REAL DEFAULT 0,
    hardener_product_id TEXT,
    hardener_tag_id TEXT,
    hardener_weight_target_g REAL DEFAULT 0,
    hardener_weight_actual_g REAL DEFAULT 0,
    thinner_product_id TEXT,
    thinner_weight_g REAL DEFAULT 0,
    ratio_achieved REAL DEFAULT 0,
    ratio_in_spec INTEGER DEFAULT 0,
    override_reason TEXT DEFAULT '',
    application_method TEXT DEFAULT 'brush',
    pot_life_started_at REAL DEFAULT 0,
    pot_life_expires_at REAL DEFAULT 0,
    status TEXT DEFAULT 'in_progress',
    confirmation TEXT DEFAULT 'confirmed'
);

-- ============================================================
-- CONSUMPTION EVENTS
-- ============================================================

CREATE TABLE IF NOT EXISTS consumption_event (
    event_id TEXT PRIMARY KEY,
    device_id TEXT,
    tag_uid TEXT,
    product_id TEXT,
    session_id TEXT,
    job_id TEXT,
    weight_before_g REAL,
    weight_after_g REAL,
    estimated_usage_g REAL,
    confirmed INTEGER DEFAULT 0,
    timestamp REAL
);

-- ============================================================
-- SYNC QUEUE
-- ============================================================

CREATE TABLE IF NOT EXISTS sync_queue (
    queue_id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    created_at REAL NOT NULL,
    retry_count INTEGER DEFAULT 0,
    next_retry_at REAL DEFAULT 0,
    status TEXT DEFAULT 'pending'  -- 'pending', 'sending', 'acked', 'failed'
);

CREATE INDEX IF NOT EXISTS idx_sync_queue_status ON sync_queue(status);

CREATE TABLE IF NOT EXISTS sync_state (
    id INTEGER PRIMARY KEY CHECK (id = 1),  -- Singleton row
    last_sync_at REAL DEFAULT 0,
    last_server_sequence INTEGER DEFAULT 0,
    config_version INTEGER DEFAULT 0
);

-- ============================================================
-- ALARM LOG (v1.0.6)
-- ============================================================

CREATE TABLE IF NOT EXISTS alarm_log (
    alarm_id TEXT PRIMARY KEY,
    error_code TEXT NOT NULL,
    error_title TEXT NOT NULL,
    severity TEXT NOT NULL,
    category TEXT NOT NULL,
    details TEXT DEFAULT '',
    source TEXT DEFAULT '',
    status TEXT DEFAULT 'active',
    raised_at REAL NOT NULL,
    acknowledged_at REAL,
    resolved_at REAL,
    support_requested INTEGER DEFAULT 0,
    support_requested_at REAL,
    synced INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_alarm_log_status ON alarm_log(status);
CREATE INDEX IF NOT EXISTS idx_alarm_log_severity ON alarm_log(severity);
CREATE INDEX IF NOT EXISTS idx_alarm_log_raised ON alarm_log(raised_at);

-- Product barcodes (synced from cloud)
CREATE TABLE IF NOT EXISTS product_barcode (
    barcode_data TEXT PRIMARY KEY,
    product_id TEXT NOT NULL,
    ppg_code TEXT NOT NULL,
    batch_number TEXT NOT NULL,
    product_name TEXT NOT NULL,
    color TEXT DEFAULT '',
    barcode_type TEXT DEFAULT 'code128',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_barcode_product ON product_barcode(product_id);
CREATE INDEX IF NOT EXISTS idx_barcode_ppg ON product_barcode(ppg_code);

-- Initialize singleton sync state
INSERT OR IGNORE INTO sync_state (id) VALUES (1);
