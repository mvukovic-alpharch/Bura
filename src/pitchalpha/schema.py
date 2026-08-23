from __future__ import annotations

import duckdb

TABLES = {
    "matches": """match_id BIGINT, date TIMESTAMPTZ, season INTEGER, league_id INTEGER,
        round VARCHAR, status VARCHAR, home_team_id BIGINT, away_team_id BIGINT,
        home_goals INTEGER, away_goals INTEGER, venue VARCHAR, observed_at TIMESTAMPTZ,
        source_file VARCHAR""",
    "teams": """team_id BIGINT, team VARCHAR, country VARCHAR, founded INTEGER,
        national BOOLEAN, logo VARCHAR, venue_id BIGINT, venue_name VARCHAR,
        observed_at TIMESTAMPTZ, source_file VARCHAR""",
    "players": """player_id BIGINT, player_name VARCHAR, firstname VARCHAR, lastname VARCHAR,
        age INTEGER, birth_date DATE, nationality VARCHAR, height VARCHAR, weight VARCHAR,
        injured BOOLEAN, observed_at TIMESTAMPTZ, source_file VARCHAR""",
    "player_squads": """player_id BIGINT, player_name VARCHAR, team_id BIGINT, team VARCHAR,
        team_code VARCHAR, position VARCHAR, number INTEGER, observed_at TIMESTAMPTZ,
        source_file VARCHAR""",
    "player_match": """match_id BIGINT, date TIMESTAMPTZ, season INTEGER, player_id BIGINT,
        player_name VARCHAR, team_id BIGINT, team VARCHAR, opponent_id BIGINT, opponent VARCHAR,
        home_away VARCHAR, position VARCHAR, started BOOLEAN, minutes INTEGER, goals INTEGER,
        assists INTEGER, shots INTEGER, shots_on_target INTEGER, passes INTEGER, key_passes INTEGER,
        tackles INTEGER, interceptions INTEGER, fouls INTEGER, yellow_cards INTEGER,
        red_cards INTEGER, rating DOUBLE, observed_at TIMESTAMPTZ, source_file VARCHAR""",
    "team_match": """match_id BIGINT, date TIMESTAMPTZ, season INTEGER, team_id BIGINT,
        team VARCHAR, opponent_id BIGINT, opponent VARCHAR, home_away VARCHAR,
        statistic VARCHAR, value VARCHAR, observed_at TIMESTAMPTZ, source_file VARCHAR""",
    "lineups": """match_id BIGINT, team_id BIGINT, team VARCHAR, player_id BIGINT,
        player_name VARCHAR, position VARCHAR, grid VARCHAR, started BOOLEAN,
        formation VARCHAR, coach_id BIGINT, coach VARCHAR, observed_at TIMESTAMPTZ,
        source_file VARCHAR""",
    "injuries": """match_id BIGINT, league_id INTEGER, season INTEGER, team_id BIGINT,
        team VARCHAR, player_id BIGINT, player_name VARCHAR, injury_type VARCHAR,
        reason VARCHAR, fixture_date TIMESTAMPTZ, observed_at TIMESTAMPTZ, source_file VARCHAR""",
    "external_injury_observations": """observation_id VARCHAR, observation_timestamp TIMESTAMPTZ,
        source VARCHAR, source_file VARCHAR, source_sha256 VARCHAR, ingestion_batch_id VARCHAR,
        internal_player_id VARCHAR, api_football_player_id BIGINT, player_name_raw VARCHAR,
        team_raw VARCHAR, position_raw VARCHAR, injury_description VARCHAR, status_raw VARCHAR,
        status VARCHAR, estimated_return_raw VARCHAR, match_confidence DOUBLE, match_method VARCHAR""",
    "odds": """match_id BIGINT, league_id INTEGER, season INTEGER, fixture_date TIMESTAMPTZ,
        bookmaker_id BIGINT, bookmaker VARCHAR, bet_id BIGINT, bet VARCHAR,
        outcome VARCHAR, odd VARCHAR, observed_at TIMESTAMPTZ, source_file VARCHAR""",
    "dfs_slates": """slate_id VARCHAR, imported_at TIMESTAMPTZ, source_file VARCHAR,
        source_sha256 VARCHAR, salary_cap INTEGER, roster_slots VARCHAR, import_status VARCHAR""",
    "dfs_players": """slate_id VARCHAR, dk_player_id VARCHAR, internal_player_id VARCHAR,
        api_football_player_id BIGINT, dk_name VARCHAR, normalized_name VARCHAR, team VARCHAR,
        opponent VARCHAR, game_info VARCHAR, salary INTEGER, status VARCHAR, ownership DOUBLE,
        match_confidence DOUBLE, match_method VARCHAR, imported_at TIMESTAMPTZ, source_file VARCHAR""",
    "dfs_player_eligibility": """slate_id VARCHAR, dk_player_id VARCHAR, position VARCHAR,
        imported_at TIMESTAMPTZ, source_file VARCHAR""",
    "player_mappings": """internal_player_id VARCHAR, api_football_player_id BIGINT,
        dk_player_id VARCHAR, dk_name VARCHAR, normalized_name VARCHAR, team VARCHAR,
        position VARCHAR, match_confidence DOUBLE, match_method VARCHAR, manual_override BOOLEAN,
        created_at TIMESTAMPTZ""",
    "market_observations": """match_id BIGINT, home_team VARCHAR, away_team VARCHAR,
        home_win_prob DOUBLE, draw_prob DOUBLE, away_win_prob DOUBLE, match_total DOUBLE,
        implied_home_goals DOUBLE, implied_away_goals DOUBLE, decomposition_status VARCHAR,
        odds_timestamp TIMESTAMPTZ, odds_source VARCHAR, source_file VARCHAR""",
    "slate_states": """slate_id VARCHAR, slate_date DATE, platform VARCHAR, state_json VARCHAR,
        workflow_state VARCHAR, qa_status VARCHAR, updated_at TIMESTAMPTZ, state_version BIGINT""",
    "decision_journal": """journal_id VARCHAR, timestamp TIMESTAMPTZ, slate_id VARCHAR,
        action VARCHAR, reason VARCHAR, inputs VARCHAR, outputs VARCHAR, model_version VARCHAR,
        data_timestamp TIMESTAMPTZ, result VARCHAR, status VARCHAR""",
    "change_events": """event_id VARCHAR, timestamp TIMESTAMPTZ, slate_id VARCHAR,
        event_type VARCHAR, entity_id VARCHAR, material BOOLEAN, changes VARCHAR,
        affected_actions VARCHAR""",
    "anomaly_investigations": """anomaly_id VARCHAR, timestamp TIMESTAMPTZ, slate_id VARCHAR,
        player_id VARCHAR, residual DOUBLE, investigation VARCHAR, recommendation VARCHAR,
        status VARCHAR""",
    "research_hypotheses": """hypothesis_id VARCHAR, timestamp TIMESTAMPTZ, slate_id VARCHAR,
        hypothesis VARCHAR, evidence VARCHAR, status VARCHAR""",
    "telegram_deliveries": """delivery_id VARCHAR, timestamp TIMESTAMPTZ, message_type VARCHAR,
        slate_id VARCHAR, chat_id VARCHAR, content_hash VARCHAR, delivery_status VARCHAR,
        telegram_message_id VARCHAR, error VARCHAR""",
    "approval_decisions": """decision_id VARCHAR, created_at TIMESTAMPTZ, slate_id VARCHAR,
        decision_type VARCHAR, description VARCHAR, payload VARCHAR, status VARCHAR,
        decided_at TIMESTAMPTZ, decided_by_chat_id VARCHAR""",
    "telegram_bot_state": """state_key VARCHAR, state_value VARCHAR, updated_at TIMESTAMPTZ""",
}


def connect(path) -> duckdb.DuckDBPyConnection:
    path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(path))
    for name, columns in TABLES.items():
        con.execute(f"CREATE TABLE IF NOT EXISTS {name} ({columns})")
    existing = {row[1] for row in con.execute("PRAGMA table_info('player_match')").fetchall()}
    for column, sql_type in (
        ("actual_dk_points", "DOUBLE"),
        ("scoring_completeness", "VARCHAR"),
        ("scoring_complete", "BOOLEAN"),
        ("assisted_shots", "INTEGER"), ("fouls_drawn", "INTEGER"),
        ("saves", "INTEGER"), ("goals_conceded", "INTEGER"),
        ("clean_sheet", "BOOLEAN"), ("goalkeeper_win", "BOOLEAN"),
        ("penalties_missed", "INTEGER"), ("penalties_saved", "INTEGER"),
        ("scoring_missing_components", "VARCHAR"),
    ):
        if column not in existing:
            con.execute(f"ALTER TABLE player_match ADD COLUMN {column} {sql_type}")
    con.execute("""CREATE TABLE IF NOT EXISTS ingestion_runs (
        run_id VARCHAR, started_at TIMESTAMPTZ, completed_at TIMESTAMPTZ,
        season INTEGER, status VARCHAR, details VARCHAR)""")
    return con
