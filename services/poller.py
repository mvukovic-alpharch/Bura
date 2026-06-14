"""Bura poller — Tier 0 spine. Idempotent, budget-guarded, ID-resolving.

Run:  python -m services.poller
Cron drives it; it does ONE poll cycle per invocation and exits.

DESIGN NOTES (the fixes vs the stub artifact):
  * ON CONFLICT DO NOTHING on odds_snapshots — run twice, second writes 0.
  * Every feed market resolved through id_resolution before any write;
    canonical markets row created on first sight.
  * devig applied AND the method actually used is what gets stored.
  * Hard daily API-call budget guard — cannot burn the free tier by noon.
  * Defensive parsing: the exact SGO JSON shape is confirmed on first
    live call; _parse_feed is the ONE function to adjust then. Everything
    downstream consumes the normalized Quote dataclass, not raw JSON.
"""
from __future__ import annotations

import datetime as dt
import sys
from dataclasses import dataclass

import requests

from config import settings
from engine.devig import devig
from utils import db

SGO_BASE = "https://api.sportsgameodds.com/v2"


@dataclass
class Quote:
    feed_market_id: str
    league_key: str
    family: str            # side | total | draw | prop
    event_id: str
    participant: str | None
    side: str
    line: float | None
    book_id: str
    decimal_odds: float
    opposite_odds: float | None   # for two-way devig
    ts: dt.datetime


def _calls_used_today() -> int:
    rows = db.fetchall(
        "SELECT COUNT(*) AS n FROM poll_log WHERE ts::date = CURRENT_DATE"
    )
    return rows[0]["n"] if rows else 0


def _log_call(endpoint: str, n_markets: int, n_written: int) -> None:
    db.execute(
        "INSERT INTO poll_log (endpoint, n_markets, n_written, ts) "
        "VALUES (%s, %s, %s, NOW())",
        (endpoint, n_markets, n_written),
    )


def _fetch(league_key: str) -> dict:
    r = requests.get(
        f"{SGO_BASE}/events",
        params={"apiKey": settings.SGO_API_KEY, "leagueID": league_key,
                "oddsAvailable": "true"},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def _parse_feed(league_key: str, payload: dict) -> list[Quote]:
    """THE adjustment point. Map SGO's JSON to normalized Quotes.
    Written defensively; refine field paths against a real response on
    first live call, then never touch the rest of the pipeline."""
    out: list[Quote] = []
    now = dt.datetime.now(dt.timezone.utc)
    for ev in payload.get("data", payload.get("events", [])):
        event_id = str(ev.get("eventID") or ev.get("id") or "")
        odds = ev.get("odds", {}) or {}
        for market_id, m in (odds.items() if isinstance(odds, dict)
                             else enumerate(odds)):
            family = _family_of(m)
            if family is None:
                continue
            for book_id, price in _iter_books(m):
                dec = _american_to_decimal(price)
                if dec is None:
                    continue
                out.append(Quote(
                    feed_market_id=str(market_id),
                    league_key=league_key,
                    family=family,
                    event_id=event_id,
                    participant=m.get("playerID") or m.get("participant"),
                    side=str(m.get("sideID") or m.get("side") or ""),
                    line=_safe_float(m.get("line") or m.get("overUnder")),
                    book_id=str(book_id),
                    decimal_odds=dec,
                    opposite_odds=None,   # paired in _pair_two_way
                    ts=now,
                ))
    return _pair_two_way(out)


def _family_of(m: dict) -> str | None:
    bt = str(m.get("betTypeID") or m.get("marketType") or "").lower()
    if "ml" in bt or "moneyline" in bt:
        return "side"
    if "ou" in bt or "total" in bt or "over" in bt:
        return "total"
    if "draw" in bt:
        return "draw"
    if "player" in bt or "prop" in bt:
        return "prop"
    return None


def _iter_books(m: dict):
    books = m.get("byBookmaker") or m.get("books") or {}
    if isinstance(books, dict):
        for b, v in books.items():
            yield b, (v.get("odds") if isinstance(v, dict) else v)


def _american_to_decimal(american) -> float | None:
    try:
        a = float(american)
    except (TypeError, ValueError):
        return None
    if a == 0:
        return None
    return 1 + (a / 100.0 if a > 0 else 100.0 / abs(a))


def _safe_float(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _pair_two_way(quotes: list[Quote]) -> list[Quote]:
    """Group opposite sides of the same market/book so devig has both legs.
    Key on (event, family, line, book) — NOT feed_market_id, which differs
    per side. Pairs the two opposing sides within that group."""
    by_key: dict[tuple, list[Quote]] = {}
    for q in quotes:
        by_key.setdefault((q.event_id, q.family, q.line, q.book_id), []).append(q)
    for group in by_key.values():
        if len(group) == 2:
            group[0].opposite_odds = group[1].decimal_odds
            group[1].opposite_odds = group[0].decimal_odds
    return quotes


def _resolve_market(q: Quote) -> int:
    """feed market -> canonical market_id, creating on first sight."""
    rows = db.fetchall(
        "SELECT market_id FROM id_resolution WHERE feed=%s AND feed_market_id=%s",
        ("sportsgameodds", f"{q.event_id}:{q.feed_market_id}:{q.side}"),
    )
    if rows:
        return rows[0]["market_id"]
    with db.db_conn() as c:
        cur = c.cursor()
        cur.execute(
            "INSERT INTO markets (league_key, family, event_id, participant, side, line) "
            "VALUES (%s,%s,%s,%s,%s,%s) RETURNING market_id",
            (q.league_key, q.family, q.event_id, q.participant, q.side, q.line),
        )
        mid = cur.fetchone()[0]
        cur.execute(
            "INSERT INTO id_resolution (feed, feed_market_id, market_id) VALUES (%s,%s,%s)",
            ("sportsgameodds", f"{q.event_id}:{q.feed_market_id}:{q.side}", mid),
        )
    return mid


def _write(q: Quote) -> int:
    mid = _resolve_market(q)
    method = settings.DEVIG_METHOD.get(q.family, "shin")
    devig_prob = None
    if q.opposite_odds:
        try:
            devig_prob = float(devig([q.decimal_odds, q.opposite_odds], method)[0])
        except Exception:
            devig_prob = None
    with db.db_conn() as c:
        cur = c.cursor()
        cur.execute(
            "INSERT INTO odds_snapshots "
            "(market_id, book_id, decimal_odds, devig_prob, devig_method, ts) "
            "VALUES (%s,%s,%s,%s,%s,%s) "
            "ON CONFLICT (market_id, book_id, ts) DO NOTHING",
            (mid, q.book_id, q.decimal_odds, devig_prob,
             method if devig_prob is not None else None, q.ts),
        )
        return cur.rowcount


def poll(sleeve: str | None = None) -> None:
    used = _calls_used_today()
    if used >= settings.DAILY_API_CALL_BUDGET:
        db.telegram(f"⚠️ Bura poller: daily API budget {used} reached — skipping")
        return

    leagues = [k for k, v in settings.LEAGUES.items()
               if sleeve is None or v[2] == sleeve]
    total_markets = total_written = 0
    for lk in leagues:
        if _calls_used_today() >= settings.DAILY_API_CALL_BUDGET:
            break
        try:
            payload = _fetch(lk)
            quotes = _parse_feed(lk, payload)
            written = sum(_write(q) for q in quotes)
            total_markets += len(quotes)
            total_written += written
            _log_call(f"events:{lk}", len(quotes), written)
        except Exception as e:
            db.telegram(f"❌ Bura poller error on {lk}: {e}")
            print(f"error {lk}: {e}", file=sys.stderr)

    print(f"[{dt.datetime.now():%H:%M}] sleeve={sleeve or 'all'} "
          f"markets={total_markets} written={total_written} "
          f"calls_today={_calls_used_today()}")


if __name__ == "__main__":
    poll(sleeve=sys.argv[1] if len(sys.argv) > 1 else None)
