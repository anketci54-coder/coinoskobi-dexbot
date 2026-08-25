import math

from app.dex.flow_spread import flow_spread


def test_positive_spread():
    r = flow_spread(120, 80)
    assert r["spread"] == 40
    assert r["state"] == "READY"


def test_negative_spread():
    assert flow_spread(70, 100)["spread"] == -30


def test_velocity():
    r = flow_spread(130, 70, prev_spread=40)
    assert r["velocity"] == 20


def test_acceleration():
    r = flow_spread(
        140, 60,
        prev_spread=50,
        prev_velocity=10,
    )
    assert r["velocity"] == 30
    assert r["acceleration"] == 20


def test_beta_binomial_buy_probability():
    r = flow_spread(120, 80)

    assert r["probability_model"] == "BETA_BINOMIAL"
    assert r["posterior_alpha"] == 121.0
    assert r["posterior_beta"] == 81.0
    assert r["buy_probability_mean"] == 121.0 / 202.0

    expected_variance = (
        121.0 * 81.0
        / (202.0 * 202.0 * 203.0)
    )

    assert r["buy_probability_variance"] == expected_variance
    assert r["buy_probability_std"] == math.sqrt(expected_variance)


def test_beta_binomial_prior_is_neutral_without_directional_events():
    r = flow_spread(0, 0)

    assert r["state"] == "READY"
    assert r["buy_probability_mean"] == 0.5
    assert r["posterior_alpha"] == 1.0
    assert r["posterior_beta"] == 1.0


def test_negative_flow_is_unknown():
    r = flow_spread(-1, 2)

    assert r["state"] == "UNKNOWN"
    assert r["buy_probability_mean"] is None


def test_unknown_stale():
    r = flow_spread(100, 50, freshness="STALE")
    assert r["state"] == "UNKNOWN"
    assert r["spread"] is None
    assert r["buy_probability_mean"] is None


def test_unknown_low_coverage():
    assert flow_spread(
        100, 50, coverage=0.8
    )["state"] == "UNKNOWN"


def test_authority_zero():
    r = flow_spread(100, 50)
    assert r["decision_authority"] is False
    assert r["execution_authority"] is False
