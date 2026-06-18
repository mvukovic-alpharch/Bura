-- Bura racing module schema (paper mode). Event-driven, not continuous.

CREATE TABLE tracks (
    track_id    TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    tier        TEXT                       -- 'marquee' | 'mid' | 'minor'
);

CREATE TABLE horses (
    horse_id    TEXT PRIMARY KEY,
    name        TEXT NOT NULL
);

CREATE TABLE races (
    race_id          TEXT PRIMARY KEY,
    track_id         TEXT REFERENCES tracks(track_id),
    race_date        DATE NOT NULL,
    race_number      INT NOT NULL,
    surface          TEXT NOT NULL,         -- dirt | turf | synthetic
    distance_furlongs NUMERIC NOT NULL,
    class_level      NUMERIC,
    takeout_win      NUMERIC DEFAULT 0.17,
    takeout_exotic   NUMERIC DEFAULT 0.21
);

CREATE TABLE entries (
    entry_id         BIGSERIAL PRIMARY KEY,
    race_id          TEXT REFERENCES races(race_id),
    program_number   INT NOT NULL,
    horse_id         TEXT REFERENCES horses(horse_id),
    jockey           TEXT, trainer TEXT,
    jockey_sr        NUMERIC, trainer_sr NUMERIC,
    post_position    INT, weight NUMERIC,
    morning_line     NUMERIC,
    run_style        TEXT,                  -- E|EP|P|S, filled by model
    pace_fit         NUMERIC,
    model_win_prob   NUMERIC,
    UNIQUE(race_id, program_number)
);

CREATE TABLE past_performances (
    pp_id            BIGSERIAL PRIMARY KEY,
    horse_id         TEXT REFERENCES horses(horse_id),
    race_date        DATE NOT NULL,
    speed_fig        NUMERIC, class_level NUMERIC,
    finish_pos       INT, field_size INT,
    early_pace       NUMERIC, late_pace NUMERIC,
    surface          TEXT, distance_furlongs NUMERIC
);

-- tote board over time; the last row per (race, program) before post = close
CREATE TABLE tote_snapshots (
    snap_id          BIGSERIAL PRIMARY KEY,
    race_id          TEXT REFERENCES races(race_id),
    program_number   INT NOT NULL,
    win_odds         NUMERIC NOT NULL,      -- decimal payout incl stake
    minutes_to_post  NUMERIC,
    ts               TIMESTAMPTZ NOT NULL,
    UNIQUE(race_id, program_number, ts)
);

CREATE TABLE results (
    race_id          TEXT PRIMARY KEY REFERENCES races(race_id),
    win_program      INT, place_program INT, show_program INT,
    win_payout       NUMERIC,
    graded_at        TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE bets (
    bet_id           BIGSERIAL PRIMARY KEY,
    race_id          TEXT REFERENCES races(race_id),
    bet_type         TEXT NOT NULL,         -- win | exacta | trifecta
    selection        TEXT NOT NULL,         -- comma program numbers
    stake            NUMERIC NOT NULL,
    entry_odds       NUMERIC,
    paper            BOOLEAN DEFAULT TRUE,
    ts               TIMESTAMPTZ NOT NULL
);

CREATE TABLE clv_log (
    bet_id           BIGINT PRIMARY KEY REFERENCES bets(bet_id),
    entry_odds       NUMERIC NOT NULL,
    close_odds       NUMERIC NOT NULL,
    clv_pct          NUMERIC NOT NULL,
    won              BOOLEAN,
    payout           NUMERIC,
    model_ver        TEXT
);
