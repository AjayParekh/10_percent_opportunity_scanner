-- database/schema.sql
CREATE TABLE IF NOT EXISTS metric_facts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    metric TEXT NOT NULL,
    value REAL,
    reporting_period TEXT,          -- e.g. "2024-Q3" / "FY2024"
    source TEXT NOT NULL,           -- "TheAnnexure" / "NSE" / "manual_import"
    retrieval_date TEXT NOT NULL,
    quality_status TEXT NOT NULL CHECK (
        quality_status IN ('verified', 'missing', 'manual', 'stale')
    ),
    UNIQUE(symbol, metric, reporting_period, source)
);

CREATE TABLE IF NOT EXISTS scrape_audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    target_url TEXT,
    requested_at TEXT NOT NULL,
    http_status INTEGER,
    outcome TEXT,                   -- "ok" / "blocked" / "js_rendered" / "error"
    notes TEXT
);
