-- trader-agent local database schema
-- Created in {LOCAL_DATA_PATH}/trade-data.db by install.ps1

CREATE TABLE IF NOT EXISTS account_state (
  key   TEXT PRIMARY KEY,
  value TEXT NOT NULL,
  updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS trade_ideas (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  created_at      TEXT    DEFAULT CURRENT_TIMESTAMP,
  ticker          TEXT    NOT NULL,
  strategy        TEXT,                       -- e.g. 'long_call', 'bull_put_spread', 'long_stock'
  thesis          TEXT,
  horizon         TEXT,                       -- 'swing' | 'position'
  entry_trigger   TEXT,
  target          REAL,
  stop            REAL,
  time_stop       TEXT,                       -- e.g. '21 DTE' or '10 sessions'
  invalidation    TEXT,
  size_shares     INTEGER,
  size_contracts  INTEGER,
  max_risk_usd    REAL,
  expected_value  REAL,
  conviction      INTEGER CHECK (conviction BETWEEN 1 AND 5),
  status          TEXT    DEFAULT 'idea'      -- 'idea'|'paper'|'live'|'closed'|'abandoned'
);

CREATE INDEX IF NOT EXISTS idx_trade_ideas_status ON trade_ideas(status);
CREATE INDEX IF NOT EXISTS idx_trade_ideas_ticker ON trade_ideas(ticker);

CREATE TABLE IF NOT EXISTS trade_journal (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  idea_id     INTEGER NOT NULL REFERENCES trade_ideas(id) ON DELETE CASCADE,
  timestamp   TEXT    DEFAULT CURRENT_TIMESTAMP,
  event_type  TEXT    NOT NULL,               -- 'entry'|'adjust'|'exit'|'note'|'mtm'
  price       REAL,
  quantity    INTEGER,
  pnl         REAL,
  notes       TEXT
);

CREATE INDEX IF NOT EXISTS idx_journal_idea ON trade_journal(idea_id);

-- Per-leg detail for options trades (single-leg trades = 1 row; spreads/condors = multiple rows)
CREATE TABLE IF NOT EXISTS option_legs (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  idea_id       INTEGER NOT NULL REFERENCES trade_ideas(id) ON DELETE CASCADE,
  action        TEXT    NOT NULL CHECK (action IN ('buy','sell')),
  right         TEXT    NOT NULL CHECK (right  IN ('call','put')),
  strike        REAL    NOT NULL,
  expiry        TEXT    NOT NULL,            -- YYYY-MM-DD
  quantity      INTEGER NOT NULL,            -- contracts
  premium       REAL,                        -- per share at entry
  delta_at_entry REAL,
  iv_at_entry   REAL,
  open_close    TEXT    DEFAULT 'open' CHECK (open_close IN ('open','closed','assigned','expired'))
);

CREATE INDEX IF NOT EXISTS idx_legs_idea ON option_legs(idea_id);
CREATE INDEX IF NOT EXISTS idx_legs_expiry ON option_legs(expiry);

-- Authoritative open-position view used for heat calculation.
-- A position is "open" when status in ('paper','live') AND not all legs closed/expired/assigned.
CREATE VIEW IF NOT EXISTS open_positions AS
  SELECT
    i.id, i.ticker, i.strategy, i.status, i.max_risk_usd,
    i.created_at, i.horizon
  FROM trade_ideas i
  WHERE i.status IN ('paper','live');

CREATE TABLE IF NOT EXISTS watchlist (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  ticker        TEXT    NOT NULL,
  criteria      TEXT,                          -- trigger condition in prose
  added_at      TEXT    DEFAULT CURRENT_TIMESTAMP,
  triggered_at  TEXT
);

CREATE TABLE IF NOT EXISTS do_not_trade (
  ticker     TEXT PRIMARY KEY,
  reason     TEXT,
  added_at   TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS research_notes (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  ticker      TEXT NOT NULL,
  created_at  TEXT DEFAULT CURRENT_TIMESTAMP,
  file_path   TEXT,                            -- relative path to markdown note
  summary     TEXT
);

CREATE INDEX IF NOT EXISTS idx_notes_ticker ON research_notes(ticker);
