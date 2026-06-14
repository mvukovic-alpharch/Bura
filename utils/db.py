"""DB + notification helpers. Thin on purpose."""
from __future__ import annotations

import contextlib
import urllib.parse
import urllib.request
import json

import psycopg2
import psycopg2.extras

from config import settings


@contextlib.contextmanager
def db_conn():
    conn = psycopg2.connect(settings.DB_URL)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def fetchall(sql: str, params: tuple = ()) -> list[dict]:
    with db_conn() as c:
        cur = c.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(sql, params)
        return [dict(r) for r in cur.fetchall()]


def execute(sql: str, params: tuple = ()) -> None:
    with db_conn() as c:
        c.cursor().execute(sql, params)


def telegram(msg: str) -> None:
    """Fire-and-forget alert. Silence = healthy."""
    if not settings.TELEGRAM_TOKEN or not settings.TELEGRAM_CHAT_ID:
        return
    url = f"https://api.telegram.org/bot{settings.TELEGRAM_TOKEN}/sendMessage"
    data = urllib.parse.urlencode(
        {"chat_id": settings.TELEGRAM_CHAT_ID, "text": msg}
    ).encode()
    with contextlib.suppress(Exception):
        urllib.request.urlopen(urllib.request.Request(url, data=data), timeout=10)
