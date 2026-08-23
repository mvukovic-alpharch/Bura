from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import itertools
import math
from typing import Mapping, Sequence

import numpy as np


class InfeasibleOptimizerError(RuntimeError): pass


def _pid(player): return str(player.get("player_id"))
def _elig(player):
    value=player.get("position_eligibility") or player.get("positions") or player.get("position") or []
    return [value] if isinstance(value,str) else list(value)


def validate_lineup(lineup: Sequence[Mapping], slate_contract: Mapping, config: Mapping | None=None) -> dict:
    config=config or {}; reasons=[]; players=list(lineup); ids=[_pid(p) for p in players]
    contract_ids={_pid(p) for p in slate_contract["players"]}; slots=list(slate_contract["roster_slots"])
    if len(players)!=len(slots): reasons.append(f"requires exactly {len(slots)} players")
    if len(set(ids))!=len(ids): reasons.append("duplicate player")
    missing=set(ids)-contract_ids
    if missing: reasons.append("player outside slate: "+", ".join(sorted(missing)))
    salary=sum(int(p.get("salary") or 0) for p in players); low=int(config.get("salary_min",0)); high=int(config.get("salary_max",slate_contract["salary_cap"]))
    if salary>min(high,int(slate_contract["salary_cap"])): reasons.append("salary exceeds maximum")
    if salary<low: reasons.append("salary below minimum")
    allowed=slate_contract["eligibility_constraints"]
    if len(players)==len(slots) and not _assign_slots(players,slots,allowed): reasons.append("roster slots cannot be filled by eligibility")
    max_team=config.get("team_max_players")
    if max_team:
        if any(x>int(max_team) for x in Counter(p.get("team") for p in players).values()): reasons.append("team player limit exceeded")
    if config.get("goalkeeper_vs_opponent_forbidden"):
        for g in [p for p in players if "GK" in _elig(p)]:
            if any(p.get("team")==g.get("opponent") for p in players if _pid(p)!=_pid(g)): reasons.append("goalkeeper faces selected opponent")
    stack=config.get("optional_team_stack")
    if stack:
        minimum=int(stack.get("min_players",2)); eligible=set(stack.get("positions",["D","M","F"]))
        counts=Counter(p.get("team") for p in players if set(_elig(p))&eligible)
        if not counts or max(counts.values())<minimum: reasons.append("team stack requirement not met")
    forbidden={frozenset(map(str,x)) for x in config.get("forbidden_player_pairs",[])}
    if any(frozenset(x).issubset(ids) for x in forbidden): reasons.append("forbidden teammate pair selected")
    return {"valid":not reasons,"reasons":reasons,"salary":salary}


def _assign_slots(players,slots,allowed):
    ordered=sorted(range(len(slots)),key=lambda i:sum(bool(set(_elig(p))&set(allowed[slots[i]])) for p in players))
    def visit(k,used):
        if k==len(ordered): return True
        slot=slots[ordered[k]]
        return any(i not in used and set(_elig(p))&set(allowed[slot]) and visit(k+1,used|{i}) for i,p in enumerate(players))
    return visit(0,set())


def _player_score(p,strategy,weights):
    if strategy=="mean": return float(p.get("mean") or -1e6)
    if strategy=="ceiling":
        tail=p.get("tail_probability") or p.get("p_20_plus") or 0
        return sum(float(weights.get(k,0))*float(tail if k=="tail_probability" else p.get(k) or 0) for k in ("mean","p90","p95","tail_probability"))
    return float(p.get("mean") or 0)


def generate_candidates(contract: Mapping, strategy="mean", config: Mapping | None=None) -> list[list[dict]]:
    config=config or {}; slots=contract["roster_slots"]; allowed=contract["eligibility_constraints"]; players=[dict(p) for p in contract["players"]]
    weights=config.get("ceiling_weights",{}); beam=[(0.0,0,tuple(),tuple())]; limit=int(config.get("candidate_pool_size",5000))
    for slot in slots:
        next_states={}
        for score,salary,ids,chosen in beam:
            for i,p in enumerate(players):
                pid=_pid(p)
                if pid in ids or not set(_elig(p))&set(allowed[slot]): continue
                new_salary=salary+int(p.get("salary") or 0)
                if new_salary>min(int(config.get("salary_max",contract["salary_cap"])),int(contract["salary_cap"])): continue
                key=tuple(sorted(ids+(pid,)))
                value=(score+_player_score(p,strategy,weights),new_salary,key,chosen+(i,))
                if key not in next_states or value[0]>next_states[key][0]: next_states[key]=value
        beam=sorted(next_states.values(),key=lambda x:(-x[0],x[2]))[:limit]
        if not beam: raise InfeasibleOptimizerError(f"no feasible candidates while filling {slot}")
    output=[]
    for _,_,_,indexes in beam:
        lineup=[players[i] for i in indexes]
        if validate_lineup(lineup,contract,config)["valid"]: output.append(lineup)
    if not output: raise InfeasibleOptimizerError("no lineup satisfies configured constraints")
    return output


def lineup_metrics(lineup,simulation_matrix,target_score=100.0):
    indexes=[int(p["simulation_index"]) for p in lineup]
    scores=np.asarray(simulation_matrix)[:,indexes].sum(axis=1); player=np.asarray(simulation_matrix)[:,indexes]
    covariance=np.cov(player,rowvar=False); correlations=np.corrcoef(player,rowvar=False)
    pairs=[]
    for i,j in itertools.combinations(range(len(lineup)),2):
        value=float(correlations[i,j]) if np.isfinite(correlations[i,j]) else 0.0
        pairs.append({"player_1":_pid(lineup[i]),"player_2":_pid(lineup[j]),"correlation":value,"covariance":float(covariance[i,j])})
    q=np.quantile(scores,[.1,.5,.9,.95])
    return {"mean":float(scores.mean()),"variance":float(scores.var()),"p10":float(q[0]),"p50":float(q[1]),"p90":float(q[2]),"p95":float(q[3]),
      "probability_exceeding_target":float((scores>=target_score).mean()),"average_pairwise_correlation":float(np.mean([x["correlation"] for x in pairs])) if pairs else 0,
      "covariance_contribution":float(2*sum(x["covariance"] for x in pairs)),"largest_positive_correlation":max(pairs,key=lambda x:x["correlation"],default=None),
      "largest_negative_correlation":min(pairs,key=lambda x:x["correlation"],default=None),"simulation_scores":scores}


def _why_player(p):
    fields=("player_id","name","mean","p90","p95","salary","expected_minutes","p_start","mean_projection_percentile","value_vs_salary","ceiling_vs_salary","team_environment_zscore","cold_start","model_version","scoring_completeness")
    return {k:p.get(k) for k in fields}


def optimize(contract,strategy="mean",simulation_matrix=None,config=None,seed=0):
    config=config or {}; generation=["ceiling"] if strategy=="ceiling" else ["mean"]
    if strategy=="simulation": generation=["mean","ceiling"]
    merged={}
    for mode in generation:
        for lineup in generate_candidates(contract,mode,config): merged[tuple(sorted(_pid(p) for p in lineup))]=lineup
    candidates=list(merged.values()); target=float(config.get("target_score",100))
    ranked=[]
    for lineup in candidates:
        if simulation_matrix is not None:
            metrics=lineup_metrics(lineup,simulation_matrix,target)
            objective={"simulation":metrics.get(config.get("simulation_objective","probability_exceeding_target"),metrics["probability_exceeding_target"]),"mean":sum(float(p.get("mean") or 0) for p in lineup),"ceiling":sum(_player_score(p,"ceiling",config.get("ceiling_weights",{})) for p in lineup)}[strategy]
        else:
            if strategy=="simulation": raise ValueError("simulation strategy requires retained simulation_matrix")
            metrics=None; objective=sum(_player_score(p,strategy,config.get("ceiling_weights",{})) for p in lineup)
        ranked.append((float(objective),tuple(sorted(_pid(p) for p in lineup)),lineup,metrics))
    ranked.sort(key=lambda x:(-x[0],x[1])); best=ranked[0]; runner=ranked[1][0] if len(ranked)>1 else None
    uncertainty=max(best[2],key=lambda p:(float(p.get("p95") or 0)-float(p.get("p10") or 0)),default=None)
    return {"strategy":strategy,"objective_value":best[0],"players":[_why_player(p) for p in best[2]],"player_ids":[_pid(p) for p in best[2]],
      "salary":sum(int(p["salary"]) for p in best[2]),"validation":validate_lineup(best[2],contract,config),"simulation_metrics":_serial_metrics(best[3]),
      "why":{"objective":strategy,"margin_over_nearby_alternative":None if runner is None else best[0]-runner,"largest_positive_correlation":best[3]["largest_positive_correlation"] if best[3] else None,
      "largest_negative_correlation":best[3]["largest_negative_correlation"] if best[3] else None,"largest_source_of_uncertainty":_pid(uncertainty) if uncertainty else None},"_lineup":best[2],"_scores":best[3]["simulation_scores"] if best[3] else None,"candidate_count":len(ranked)}


def _serial_metrics(metrics):
    if metrics is None:return None
    return {k:v for k,v in metrics.items() if k!="simulation_scores"}


def build_portfolio(contract,simulation_matrix,n_lineups=20,config=None,seed=0):
    config=config or {}; pc=config.get("portfolio",config); merged={}
    for mode in ("mean","ceiling"):
        for lineup in generate_candidates(contract,mode,{**config,**pc}): merged[tuple(sorted(_pid(p) for p in lineup))]=lineup
    candidates=list(merged.values()); target=float(config.get("target_score",100))
    scored=[]
    for lineup in candidates:
        m=lineup_metrics(lineup,simulation_matrix,target); scored.append((m["probability_exceeding_target"]+m["p95"]*.001,lineup,m))
    scored.sort(key=lambda x:(-x[0],tuple(sorted(_pid(p) for p in x[1])))); selected=[]; counts=Counter(); max_shared=int(pc.get("max_shared_players",len(contract["roster_slots"])-int(pc.get("min_unique_players",1))))
    def cap(p): return float(pc.get("max_goalkeeper_exposure",1)) if "GK" in _elig(p) else float(pc.get("max_player_exposure",1))
    for base,lineup,m in scored:
        ids={_pid(p) for p in lineup}
        if any(len(ids&{_pid(p) for p in old[1]})>max_shared for old in selected): continue
        if any((counts[_pid(p)]+1)/n_lineups>cap(p)+1e-12 for p in lineup): continue
        overlap=max((len(ids&{_pid(p) for p in old[1]}) for old in selected),default=0)
        adjusted=base-float(pc.get("diversification_penalty",0))*overlap/len(lineup)
        selected.append((adjusted,lineup,m)); counts.update(ids)
        if len(selected)==n_lineups: break
    if len(selected)<n_lineups: raise InfeasibleOptimizerError(f"only {len(selected)} of {n_lineups} lineups satisfy portfolio constraints")
    minimum=pc.get("min_player_exposure",{})
    if isinstance(minimum,dict) and any(counts[str(pid)]/n_lineups<float(value) for pid,value in minimum.items()): raise InfeasibleOptimizerError("configured minimum player exposure not satisfied")
    matrix=np.vstack([x[2]["simulation_scores"] for x in selected]); overlaps=[len({_pid(p) for p in a[1]}&{_pid(p) for p in b[1]}) for a,b in itertools.combinations(selected,2)]
    teams=Counter(p.get("team") for _,lineup,_ in selected for p in lineup); matches=Counter(tuple(sorted((str(p.get("team")),str(p.get("opponent"))))) for _,lineup,_ in selected for p in lineup)
    return {"lineups":[{"player_ids":[_pid(p) for p in x[1]],"salary":sum(int(p["salary"]) for p in x[1]),"metrics":_serial_metrics(x[2])} for x in selected],
      "player_exposure":{k:v/n_lineups for k,v in sorted(counts.items())},"team_exposure":{str(k):v/(n_lineups*len(contract["roster_slots"])) for k,v in sorted(teams.items(),key=lambda x:str(x[0]))},
      "match_exposure":{str(k):v/(n_lineups*len(contract["roster_slots"])) for k,v in sorted(matches.items())},"salary_distribution":{"min":min(x["salary"] for x in [{"salary":sum(int(p["salary"]) for p in y[1])} for y in selected]),"mean":float(np.mean([sum(int(p["salary"]) for p in y[1]) for y in selected])),"max":max(sum(int(p["salary"]) for p in y[1]) for y in selected)},
      "lineup_overlap_distribution":overlaps,"portfolio_score_distribution":{"mean":float(matrix.mean()),"p90":float(np.quantile(matrix,.9)),"p95":float(np.quantile(matrix,.95))},"portfolio_covariance":np.cov(matrix).tolist(),"seed":seed}
