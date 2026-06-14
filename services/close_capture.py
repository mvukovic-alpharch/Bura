"""Close capture — stamps the final pre-event snapshot per (market, book)
into closing_lines. The CLV scorecard depends on this running before
events start. Cron: a few times through the slate, plus a sweep.

Run: python -m services.close_capture
"""
from __future__ import annotations

from utils import db


def capture() -> None:
    # For each market/book, the latest snapshot becomes the closing line.
    # Composite key (market_id, book_id) — the bug-fixed schema lets us
    # store a close per reference book, not one per market.
    sql = """
    INSERT INTO closing_lines (market_id, book_id, close_prob, close_ts)
    SELECT DISTINCT ON (s.market_id, s.book_id)
           s.market_id, s.book_id, s.devig_prob, s.ts
    FROM odds_snapshots s
    WHERE s.devig_prob IS NOT NULL
    ORDER BY s.market_id, s.book_id, s.ts DESC
    ON CONFLICT (market_id, book_id)
    DO UPDATE SET close_prob = EXCLUDED.close_prob,
                  close_ts   = EXCLUDED.close_ts
    WHERE closing_lines.close_ts < EXCLUDED.close_ts;
    """
    db.execute(sql)
    rows = db.fetchall("SELECT COUNT(*) AS n FROM closing_lines")
    print(f"closing_lines now holds {rows[0]['n']} (market,book) closes")


if __name__ == "__main__":
    capture()
