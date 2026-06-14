-- SportsAlpha Phase 0 schema — CORRECTED + extended for regime/periphery.
-- Fixes vs the artifact you were handed:
--   1. closing_lines keyed (market_id, book_id) — multiple reference closes.
--   2. id_resolution table — maps feed IDs to canonical IDs (the missing layer).
--   3. odds_snapshots devig_method stores the method ACTUALLY used.
--   4. regime_baselines + leagues tables for the two new engines.

CREATE TABLE leagues (
    league_key      TEXT PRIMARY KEY,          -- 'hnl', 'nba', ...
    name            TEXT NOT NULL,
    region          TEXT NOT NULL,
    sleeve          TEXT NOT NULL CHECK (sleeve IN ('periphery','benchmark')),
    periphery_score NUMERIC,                   -- recomputed from measured stats
    news_moat       NUMERIC DEFAULT 0
);

CREATE TABLE markets (
    market_id       BIGSERIAL PRIMARY KEY,
    league_key      TEXT REFERENCES leagues(league_key),
    family          TEXT NOT NULL,             -- side | total | prop
    event_id        TEXT NOT NULL,
    participant     TEXT,                      -- player for props
    side            TEXT NOT NULL,
    line            NUMERIC,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- The missing normalization layer: feed -> canonical
CREATE TABLE id_resolution (
    feed            TEXT NOT NULL,             -- 'sportsgameodds', 'polymarket'
    feed_market_id  TEXT NOT NULL,
    market_id       BIGINT REFERENCES markets(market_id),
    PRIMARY KEY (feed, feed_market_id)
);

CREATE TABLE odds_snapshots (
    snap_id         BIGSERIAL PRIMARY KEY,
    market_id       BIGINT NOT NULL REFERENCES markets(market_id),
    book_id         TEXT   NOT NULL,
    decimal_odds    NUMERIC NOT NULL CHECK (decimal_odds > 1.0),
    devig_prob      NUMERIC,
    devig_method    TEXT,                      -- the method ACTUALLY applied
    ts              TIMESTAMPTZ NOT NULL,
    UNIQUE (market_id, book_id, ts)
);
-- write-heavy: index for "latest per book" and baseline windows
CREATE INDEX idx_snap_market_ts ON odds_snapshots (market_id, ts DESC);
CREATE INDEX idx_snap_book_ts   ON odds_snapshots (book_id, ts DESC);

-- FIX #1: composite key — a close per (market, book)
CREATE TABLE closing_lines (
    market_id       BIGINT NOT NULL REFERENCES markets(market_id),
    book_id         TEXT   NOT NULL,
    close_prob      NUMERIC NOT NULL,
    close_ts        TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (market_id, book_id)
);

-- trailing cross-book dispersion stats per (league, family) — regime engine
CREATE TABLE regime_baselines (
    league_key      TEXT REFERENCES leagues(league_key),
    family          TEXT NOT NULL,
    window_days     INT  NOT NULL,
    disp_mean       NUMERIC NOT NULL,
    disp_std        NUMERIC NOT NULL,
    computed_at     TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (league_key, family, window_days)
);

CREATE TABLE bets (
    bet_id          BIGSERIAL PRIMARY KEY,
    market_id       BIGINT REFERENCES markets(market_id),
    book_id         TEXT NOT NULL,
    entry_odds      NUMERIC NOT NULL,
    entry_prob      NUMERIC NOT NULL,
    fair_prob       NUMERIC NOT NULL,
    regime          TEXT,
    stake           NUMERIC NOT NULL,
    paper           BOOLEAN DEFAULT TRUE,      -- Tier 0 = paper only
    ts              TIMESTAMPTZ NOT NULL,
    status          TEXT DEFAULT 'pending'     -- pending | graded | void
);

CREATE TABLE clv_log (
    bet_id          BIGINT PRIMARY KEY REFERENCES bets(bet_id),
    ref_book        TEXT NOT NULL,             -- which close we graded against
    entry_prob      NUMERIC NOT NULL,
    close_prob      NUMERIC NOT NULL,
    clv_bps         NUMERIC NOT NULL,
    realized_pnl    NUMERIC,
    news_state      TEXT,
    model_ver       TEXT
);

CREATE TABLE poll_log (
    poll_id         BIGSERIAL PRIMARY KEY,
    endpoint        TEXT NOT NULL,
    n_markets       INT  NOT NULL DEFAULT 0,
    n_written       INT  NOT NULL DEFAULT 0,
    ts              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_poll_log_ts ON poll_log (ts);

CREATE TABLE sharpness_weights (
    book_id         TEXT NOT NULL,
    league_key      TEXT REFERENCES leagues(league_key),
    family          TEXT NOT NULL,
    weight          NUMERIC NOT NULL,          -- learned inverse-error vs close
    n_obs           INT NOT NULL,
    computed_at     TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (book_id, league_key, family)
);
