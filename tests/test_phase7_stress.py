from app.dex.flow_spread import flow_spread
from app.dex.flow_confirmation import confirm_flow
from app.dex.flow_divergence import evaluate_divergence
from app.dex.flow_quality import evaluate_flow_quality
from app.dex.market_regime import classify_market_regime


def run(direction, price_dir, buy, sell, prev_spread, wallets, txs, share):
    spread = flow_spread(
        buy, sell,
        prev_spread=prev_spread,
        prev_velocity=0,
    )

    confirmation = confirm_flow(
        direction,
        spread["spread"],
        spread["velocity"],
        "DIVERSE",
    )["confirmation"]

    divergence = evaluate_divergence(
        price_dir,
        spread["spread"],
        spread["velocity"],
    )["divergence_state"]

    quality = evaluate_flow_quality(
        wallets, txs, share
    )["flow_quality"]

    regime = classify_market_regime(
        direction,
        confirmation,
        divergence,
        quality,
    )["market_regime"]

    return confirmation, divergence, quality, regime


def test_real_bull_flow():
    c, d, q, r = run(
        "BULL", "UP", 150, 50, 60, 12, 20, 0.20
    )
    assert c == "CONFIRMED"
    assert d == "STRENGTHENING"
    assert q == "MULTI_ACTOR"
    assert r == "TRENDING_BULL"


def test_single_actor_spike_not_trend():
    _, _, q, r = run(
        "BULL", "UP", 200, 20, 50, 1, 1, 1.0
    )
    assert q == "SINGLE_ACTOR_SPIKE"
    assert r == "CHOP"


def test_price_up_flow_down_conflict():
    c, d, _, r = run(
        "BULL", "UP", 40, 100, -20, 10, 15, 0.20
    )
    assert c == "CONFLICT"
    assert d == "PRICE_FLOW_DIVERGENCE"
    assert r == "CONFLICT"


def test_weak_spread_transition():
    c, d, _, r = run(
        "BULL", "UP", 110, 90, 30, 10, 15, 0.20
    )
    assert c == "PARTIAL_CONFIRMATION"
    assert d == "CONVERGING"
    assert r == "TRANSITION"


def test_high_volume_low_participation():
    _, _, q, r = run(
        "BULL", "UP", 500, 100, 200, 2, 3, 0.75
    )
    assert q == "LIMITED_PARTICIPATION"
    assert r != "TRENDING_BULL"
