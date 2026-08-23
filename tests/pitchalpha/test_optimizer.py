import numpy as np
import pytest

from pitchalpha.optimizer import InfeasibleOptimizerError, build_portfolio, generate_candidates, lineup_metrics, optimize, validate_lineup


def contract():
    positions=["GK","GK","D","D","D","M","M","M","F","F","F","D"]
    players=[]
    for i,pos in enumerate(positions):
        players.append({"player_id":str(i),"name":f"P{i}","position_eligibility":[pos],"salary":4000+i*100,"team":f"T{i%3}","opponent":f"T{(i+1)%3}","mean":20-i/2,"p10":2,"p90":25-i/3,"p95":30-i/4,"simulation_index":i})
    return {"slate_id":"x","salary_cap":25000,"roster_slots":["GK","D","M","F"],"eligibility_constraints":{"GK":["GK"],"D":["D"],"M":["M"],"F":["F"]},"players":players}


def simulations():
    rng=np.random.default_rng(4); return rng.normal(np.arange(12)+5,2,(500,12))


def test_validation_salary_slots_duplicate_and_membership():
    c=contract(); valid=[c["players"][0],c["players"][2],c["players"][5],c["players"][8]]
    assert validate_lineup(valid,c)["valid"]
    assert "duplicate player" in validate_lineup([valid[0],valid[0],valid[2],valid[3]],c)["reasons"]
    assert any("exactly" in x for x in validate_lineup(valid[:3],c)["reasons"])
    bad=[dict(valid[0],player_id="outside"),*valid[1:]]
    assert any("outside slate" in x for x in validate_lineup(bad,c)["reasons"])
    expensive=[dict(x,salary=10000) for x in valid]
    assert "salary exceeds maximum" in validate_lineup(expensive,c)["reasons"]


def test_candidate_eligibility_and_impossible():
    c=contract(); candidates=generate_candidates(c,config={"candidate_pool_size":100})
    assert candidates and all(validate_lineup(x,c)["valid"] for x in candidates)
    broken={**c,"players":[p for p in c["players"] if "GK" not in p["position_eligibility"]]}
    with pytest.raises(InfeasibleOptimizerError): generate_candidates(broken)


def test_simulation_aggregation_covariance_and_reproducibility():
    c=contract(); matrix=simulations(); lineup=[c["players"][0],c["players"][2],c["players"][5],c["players"][8]]
    metrics=lineup_metrics(lineup,matrix,30)
    assert metrics["mean"]==pytest.approx(matrix[:,[0,2,5,8]].sum(1).mean())
    assert metrics["variance"]>=0 and np.isfinite(metrics["covariance_contribution"])
    a=optimize(c,"simulation",matrix,{"candidate_pool_size":100,"target_score":30},seed=8)
    b=optimize(c,"simulation",matrix,{"candidate_pool_size":100,"target_score":30},seed=8)
    assert a["player_ids"]==b["player_ids"]


def test_portfolio_exposure_uniqueness_overlap():
    c=contract(); cfg={"candidate_pool_size":500,"portfolio":{"max_player_exposure":1.0,"max_goalkeeper_exposure":1.0,"min_unique_players":1,"max_shared_players":3,"diversification_penalty":.1}}
    p=build_portfolio(c,simulations(),3,cfg,seed=2)
    assert len(p["lineups"])==3 and max(p["lineup_overlap_distribution"])<=3
    assert all(x<=1 for x in p["player_exposure"].values())
    impossible={"candidate_pool_size":100,"portfolio":{"max_player_exposure":0,"max_goalkeeper_exposure":0,"min_unique_players":1}}
    with pytest.raises(InfeasibleOptimizerError): build_portfolio(c,simulations(),2,impossible)
