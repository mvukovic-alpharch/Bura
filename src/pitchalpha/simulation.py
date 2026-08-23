"""Fast reproducible empirical Monte Carlo slate simulation."""
from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Mapping, Sequence

import numpy as np


MODEL_FIELDS={"PA-DK-B001":"forecast_pa_dk_b001","PA-DK-E002":"forecast_pa_dk_e002","PA-DK-ML002":"forecast_pa_dk_ml002"}
DEFAULT_THRESHOLDS=(10,15,20,25,30,35)


def _clip_probability(value): return float(np.clip(float(value or 0),0,1))


def sample_minutes(players:Sequence[Mapping],n_simulations:int,rng:np.random.Generator):
    """Sample starts, start-minutes, and substitute appearances separately."""
    matrix=np.zeros((n_simulations,len(players)),dtype=np.float32); starts=np.zeros_like(matrix,dtype=bool)
    for j,p in enumerate(players):
        p_start=_clip_probability(p.get("p_start")); starts[:,j]=rng.random(n_simulations)<p_start
        n_start=int(starts[:,j].sum())
        if n_start:
            # Use calibrated threshold probabilities conditional on a start.
            q60=_clip_probability((p.get("p_60") or 0)/max(p_start,1e-6)); q75=_clip_probability((p.get("p_75") or 0)/max(p_start,1e-6)); q90=_clip_probability((p.get("p_90") or 0)/max(p_start,1e-6))
            q75=min(q60,q75); q90=min(q75,q90); u=rng.random(n_start)
            mean=float(p.get("expected_minutes_if_start") or 75); sd=max(3,float(p.get("start_minutes_std_10") or 8))
            values=np.clip(rng.normal(mean,sd,n_start),1,95)
            values[u<q90]=np.clip(rng.normal(90,2,(u<q90).sum()),85,95)
            band75=(u>=q90)&(u<q75); values[band75]=rng.uniform(75,89,band75.sum())
            band60=(u>=q75)&(u<q60); values[band60]=rng.uniform(60,74,band60.sum())
            values[u>=q60]=np.clip(values[u>=q60],1,59)
            matrix[starts[:,j],j]=values
        nonstart=~starts[:,j]; rate=_clip_probability(p.get("nonstart_appearance_rate_10"))
        appears=nonstart&(rng.random(n_simulations)<rate); count=int(appears.sum())
        if count:
            mean=float(p.get("nonstart_minutes_10") or 18); sd=max(2,float(p.get("nonstart_minutes_std_10") or 7))
            matrix[appears,j]=np.clip(rng.normal(mean,sd,count),1,45)
    return matrix,starts


def conditional_means(players,minutes,model="ensemble"):
    values=[]
    for p in players:
        if model=="ensemble":
            # PA-EXP-003: baseline led MAE/correlation, ML led RMSE/top-5, E002 led bias.
            forecasts=[float(p.get(field) or 0) for field in MODEL_FIELDS.values()]
            base=sum(forecasts)/len(forecasts)
        else: base=float(p.get(MODEL_FIELDS[model]) or 0)
        expected=max(1,float(p.get("expected_minutes") or 1)); values.append(base/expected)
    return np.maximum(-10,minutes*np.asarray(values,dtype=np.float32))


def estimate_factor_strengths(rows):
    """Estimate standardized residual pair dependence; no fixed large coefficients."""
    by_position={}
    for p in {r["position"] for r in rows}:
        vals=np.array([r["residual"] for r in rows if r["position"]==p],dtype=float); by_position[p]=(vals.mean(),vals.std() or 1)
    groups={}
    for r in rows:
        z=(r["residual"]-by_position[r["position"]][0])/by_position[r["position"]][1]
        groups.setdefault(r["match_id"],[]).append({**r,"z":z})
    same=[]; opposing=[]; defense=[]
    for group in groups.values():
        for i,a in enumerate(group):
            for b in group[i+1:]:
                product=a["z"]*b["z"]
                if a["team_id"]==b["team_id"]:
                    same.append(product)
                    if a["position"] in {"D","G"} and b["position"] in {"D","G"}: defense.append(product)
                else: opposing.append(product)
    clip=lambda x:float(np.clip(np.mean(x) if x else 0,-.25,.25))
    return {"same_team_correlation":clip(same),"opposing_team_correlation":clip(opposing),"defense_correlation":clip(defense)}


def _empirical_residuals(residuals_by_position,position,n,rng):
    pool=np.asarray(residuals_by_position.get(position) or [0.0],dtype=float); centered=pool-pool.mean(); sd=centered.std() or 1
    return rng.choice(centered,n,replace=True)/sd,sd


def simulate_slate(slate_players,n_simulations=25000,model="ensemble",residuals_by_position=None,
                   factor_strengths=None,correlated=True,thresholds=DEFAULT_THRESHOLDS,seed=None):
    start_time=time.perf_counter(); players=list(slate_players); rng=np.random.default_rng(seed)
    residuals_by_position=residuals_by_position or {p.get("position"):[0.0] for p in players}
    factors=factor_strengths or {"same_team_correlation":0.0,"opposing_team_correlation":0.0,"defense_correlation":0.0}
    minutes,starts=sample_minutes(players,n_simulations,rng); scores=conditional_means(players,minutes,model)
    match_factors={m:rng.normal(size=n_simulations) for m in {p["match_id"] for p in players}}
    match_teams={}
    for p in players: match_teams.setdefault(p["match_id"],[]); match_teams[p["match_id"]].append(p["team_id"])
    match_sign={}
    for match,teams in match_teams.items():
        unique=sorted(set(teams),key=str)
        for index,team in enumerate(unique): match_sign[(match,team)]=(-1.0 if index%2 else 1.0) if factors["opposing_team_correlation"]<0 else 1.0
    team_factors={t:rng.normal(size=n_simulations) for t in {p["team_id"] for p in players}}
    defense_factors={t:rng.normal(size=n_simulations) for t in {p["team_id"] for p in players}}
    team_loading=np.sqrt(max(0,factors["same_team_correlation"])); defense_loading=np.sqrt(max(0,factors["defense_correlation"])); opp=factors["opposing_team_correlation"]
    match_loading=np.sqrt(abs(opp)); total=min(.8,team_loading**2+defense_loading**2+match_loading**2); idio=np.sqrt(max(.2,1-total))
    for j,p in enumerate(players):
        empirical,scale=_empirical_residuals(residuals_by_position,p["position"],n_simulations,rng)
        shock=idio*empirical
        if correlated:
            shock += team_loading*team_factors[p["team_id"]] + match_loading*match_sign[(p["match_id"],p["team_id"])]*match_factors[p["match_id"]]
            if p["position"] in {"D","G"}: shock += defense_loading*defense_factors[p["team_id"]]
        scores[:,j]+=scale*shock
        scores[minutes[:,j]<=0,j]=0
    quantiles=np.quantile(scores,[.1,.25,.5,.75,.9,.95],axis=0); distributions=[]
    for j,p in enumerate(players):
        item={"player_id":p["player_id"],"player_name":p.get("player_name"),"position":p["position"],
              "mean":float(scores[:,j].mean()),"standard_deviation":float(scores[:,j].std()),
              **{name:float(quantiles[i,j]) for i,name in enumerate(("p10","p25","p50","p75","p90","p95"))},
              "cold_start":bool(p.get("cold_start")),"cold_start_reason":p.get("cold_start_reason")}
        item["tail_probabilities"]={f"p_{x}_plus":float((scores[:,j]>=x).mean()) for x in thresholds}; distributions.append(item)
    correlations=np.corrcoef(scores,rowvar=False)
    return {"player_distributions":distributions,"simulation_matrix":scores,"player_correlations":correlations,
            "minutes_matrix":minutes,"metadata":{"n_simulations":n_simulations,"model":model,"model_versions":list(MODEL_FIELDS),
            "correlated":correlated,"factor_strengths":factors,"random_seed":seed,"runtime_seconds":time.perf_counter()-start_time}}
