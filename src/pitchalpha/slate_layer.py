from __future__ import annotations
from collections import defaultdict
from statistics import median, pstdev, mean
import json
from pathlib import Path


def _percentile(value, values):
    clean=sorted(x for x in values if x is not None)
    if value is None or not clean: return None
    return sum(x <= value for x in clean)/len(clean)


def build_market_model_rows(dfs_players: list[dict], projections: list[dict], markets: list[dict] | None=None) -> list[dict]:
    projection_by_id={str(x["player_id"]):x for x in projections}
    market_by_team={}
    for m in markets or []:
        market_by_team[str(m.get("home_team","")).upper()]=m; market_by_team[str(m.get("away_team","")).upper()]=m
    rows=[]
    for player in sorted(dfs_players,key=lambda x:(str(x.get("dk_player_id")),str(x.get("internal_player_id")))):
        p=projection_by_id.get(str(player.get("internal_player_id"))) or projection_by_id.get(str(player.get("api_football_player_id"))) or {}
        market=market_by_team.get(str(player.get("team") or "").upper(),{})
        r={**player,"mean":p.get("mean"),"p10":p.get("p10"),"p50":p.get("p50"),"p90":p.get("p90"),"p95":p.get("p95"),
           "p_start":p.get("p_start"),"expected_minutes":p.get("expected_minutes"),"cold_start":p.get("cold_start"),
           "scoring_completeness":p.get("scoring_completeness"),"match_total":market.get("match_total"),
           "home_win_prob":market.get("home_win_prob"),"draw_prob":market.get("draw_prob"),"away_win_prob":market.get("away_win_prob"),
           "odds_timestamp":market.get("odds_timestamp"),"ownership":player.get("ownership")}
        r["salary_per_mean_point"]=r["salary"]/r["mean"] if r.get("mean") and r["mean"]>0 else None
        r["salary_per_p90_point"]=r["salary"]/r["p90"] if r.get("p90") and r["p90"]>0 else None
        rows.append(r)
    groups=defaultdict(list)
    for r in rows:
        position=(r.get("positions") or r.get("position") or ["UNK"])
        position=position[0] if isinstance(position,list) else str(position).split("/")[0]
        groups[position].append(r); r["peer_position"]=position
    for group in groups.values():
        for r in group:
            peers=[x for x in group if abs(x["salary"]-r["salary"])<=1500] or group
            r["model_vs_peer_group"]=r["mean"]-median([x["mean"] for x in peers if x["mean"] is not None]) if r["mean"] is not None and any(x["mean"] is not None for x in peers) else None
            r["mean_projection_percentile"]=_percentile(r["mean"],[x["mean"] for x in peers])
            r["p90_percentile"]=_percentile(r["p90"],[x["p90"] for x in peers])
            r["salary_percentile"]=_percentile(r["salary"],[x["salary"] for x in peers])
            values=[(x["mean"]/x["salary"] if x.get("mean") is not None else None) for x in peers]
            value=r["mean"]/r["salary"] if r.get("mean") is not None else None
            r["value_percentile"]=_percentile(value,values); r["minutes_percentile"]=_percentile(r["expected_minutes"],[x["expected_minutes"] for x in peers])
            r["value_vs_salary"]=(r["mean"]/r["salary"]*1000) if r.get("mean") is not None else None
            r["ceiling_vs_salary"]=(r["p90"]/r["salary"]*1000) if r.get("p90") is not None else None
    totals=[r["match_total"] for r in rows if r["match_total"] is not None]; sd=pstdev(totals) if len(totals)>1 else 0
    for r in rows: r["team_environment_zscore"]=(r["match_total"]-mean(totals))/sd if r["match_total"] is not None and sd else None
    return rows


def optimizer_contract(rows: list[dict], slate_id: str, rules_path: Path) -> dict:
    rules=json.loads(Path(rules_path).read_text(encoding="utf-8"))
    fields=("internal_player_id","dk_name","positions","salary","team","opponent","mean","p10","p50","p90","p95","simulation_index","p_start","expected_minutes","cold_start","match_total","ownership","scoring_completeness","mean_projection_percentile","value_vs_salary","ceiling_vs_salary","team_environment_zscore","model_version","p_20_plus","p_25_plus")
    players=[]
    for r in sorted(rows,key=lambda x:str(x.get("dk_player_id"))):
        item={k:r.get(k) for k in fields}; item["player_id"]=item.pop("internal_player_id"); item["name"]=item.pop("dk_name"); item["position_eligibility"]=item.pop("positions",r.get("position"))
        players.append(item)
    return {"contract_version":"PA-006-v1","slate_id":slate_id,"salary_cap":rules["salary_cap"],"roster_slots":rules["roster_slots"],"eligibility_constraints":rules["slot_eligibility"],"players":players}
