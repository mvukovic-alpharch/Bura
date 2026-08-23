from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import duckdb


def replace_rows(con: duckdb.DuckDBPyConnection, table: str, rows: Iterable[dict[str, Any]], keys: list[str]):
    rows = list(rows)
    latest = {tuple(row.get(key) for key in keys): row for row in rows}
    rows = list(latest.values())
    con.execute("BEGIN")
    try:
        con.execute(f"DELETE FROM {table}")
        if not rows:
            con.execute("COMMIT")
            return 0
        columns = list(rows[0])
        placeholders = ",".join("?" for _ in columns)
        con.executemany(
            f"INSERT INTO {table} ({','.join(columns)}) VALUES ({placeholders})",
            [[row.get(column) for column in columns] for row in rows],
        )
        con.execute("COMMIT")
    except Exception:
        con.execute("ROLLBACK")
        raise
    return len(rows)
