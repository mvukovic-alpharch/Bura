import numpy as np

from pitchalpha.simulation import estimate_factor_strengths,sample_minutes,simulate_slate


def players():
    base={"match_id":1,"position":"F","p_start":0.0,"p_60":0.0,"p_75":0.0,"p_90":0.0,
          "expected_minutes":20,"expected_minutes_if_start":80,"nonstart_appearance_rate_10":1.0,
          "nonstart_minutes_10":18,"nonstart_minutes_std_10":2,"cold_start":False,
          "forecast_pa_dk_b001":5,"forecast_pa_dk_e002":6,"forecast_pa_dk_ml002":7}
    return [{**base,"player_id":1,"player_name":"A","team_id":10},
            {**base,"player_id":2,"player_name":"B","team_id":10}]


def test_nonstarter_can_appear_and_minutes_are_bounded():
    matrix,starts=sample_minutes(players(),1000,np.random.default_rng(1))
    assert not starts.any()
    assert (matrix>0).all()
    assert matrix.max() <= 45


def test_simulation_is_seed_reproducible_and_exposes_contract():
    kwargs=dict(slate_players=players(),n_simulations=1000,residuals_by_position={"F":[-2,0,3]},
                factor_strengths={"same_team_correlation":.1,"opposing_team_correlation":0,"defense_correlation":0},seed=7)
    a=simulate_slate(**kwargs); b=simulate_slate(**kwargs)
    assert np.array_equal(a["simulation_matrix"],b["simulation_matrix"])
    assert a["metadata"]["random_seed"] == 7
    assert {"mean","standard_deviation","p10","p25","p50","p75","p90","p95","tail_probabilities"} <= a["player_distributions"][0].keys()


def test_factor_strengths_are_estimated_from_residual_pairs():
    rows=[]
    for match in range(20):
        value=(-1)**match
        rows += [{"match_id":match,"team_id":1,"position":"F","residual":value},
                 {"match_id":match,"team_id":1,"position":"M","residual":value},
                 {"match_id":match,"team_id":2,"position":"F","residual":-value}]
    factors=estimate_factor_strengths(rows)
    assert factors["same_team_correlation"] > 0
    assert factors["opposing_team_correlation"] < 0


def test_negative_opponent_factor_produces_negative_simulated_correlation():
    p=players(); p[1]["team_id"]=20
    result=simulate_slate(p,5000,residuals_by_position={"F":[-2,0,2]},
        factor_strengths={"same_team_correlation":0,"opposing_team_correlation":-.15,"defense_correlation":0},seed=9)
    assert result["player_correlations"][0,1] < 0
