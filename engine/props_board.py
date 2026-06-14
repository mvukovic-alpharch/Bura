"""Props Board — the big-5 viewing surface (NBA/NFL/MLB/NHL/EPL).

Takes raw multi-book quotes for player props, devigs them, computes
weighted-consensus fair value, applies the regime gate, and emits
ranked blotter rows. This is the 'view the major player props'
surface — and the calibration ground for the periphery sleeve.
"""
from __future__ import annotations

from dataclasses import dataclass

from .devig import devig
from .regime import classify_market, RegimeCall

__all__ = ["PropQuote", "BoardRow", "build_board"]


@dataclass
class PropQuote:
    market_id: str
    sport: str
    player: str
    market: str            # e.g. "PTS o25.5", "Assists o6.5"
    # decimal odds per book for the SAME side, plus the opposite side
    # needed to devig: {book: (side_odds, other_side_odds)}
    quotes: dict[str, tuple[float, float]]


@dataclass
class BoardRow:
    market_id: str
    sport: str
    player: str
    market: str
    best_book: str
    best_odds: float
    fair_prob: float
    market_prob: float
    edge: float
    ev: float
    regime: str
    action: str


def fair_value(devig_probs: dict[str, float], weights: dict[str, float]) -> float:
    """Precision-weighted consensus. Weights are LEARNED per market family
    by sharpness calibration; uniform fallback if a book is unweighted."""
    num = den = 0.0
    for book, p in devig_probs.items():
        w = weights.get(book, 0.1)
        num += w * p
        den += w
    return num / den if den else float("nan")


def build_board(
    props: list[PropQuote],
    weights: dict[str, float],
    baseline: dict[str, tuple[float, float]],  # sport -> (disp_mean, disp_std)
    min_edge: float = 0.025,
    devig_method: str = "shin",
) -> list[BoardRow]:
    rows: list[BoardRow] = []
    for pq in props:
        # devig each book's two-way quote, keep prob of OUR side
        dv = {
            book: float(devig([side, other], devig_method)[0])
            for book, (side, other) in pq.quotes.items()
        }
        fp = fair_value(dv, weights)

        bm, bs = baseline.get(pq.sport, (0.01, 0.005))
        rc: RegimeCall = classify_market(dv, bm, bs)

        # best executable price for our side
        best_book = max(pq.quotes, key=lambda b: pq.quotes[b][0])
        best_odds = pq.quotes[best_book][0]
        mkt_prob = dv[best_book]

        edge = fp - mkt_prob
        ev = fp * best_odds - 1.0

        if rc.can_bet and edge >= min_edge and ev > 0:
            action = "BET"
        elif edge >= min_edge * 0.6:
            action = "WATCH"
        else:
            action = "PASS"

        rows.append(BoardRow(pq.market_id, pq.sport, pq.player, pq.market,
                             best_book, best_odds, round(fp, 4), round(mkt_prob, 4),
                             round(edge, 4), round(ev, 4), rc.regime, action))
    return sorted(rows, key=lambda r: r.ev, reverse=True)
