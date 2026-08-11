from app.strategy.exit_intelligence import evaluate_exit_context
from app.strategy.trend_health import classify_trend_health
from app.strategy.momentum_exhaustion import evaluate_exhaustion
from app.strategy.exit_pressure import evaluate_exit_pressure
from app.strategy.runner_health import evaluate_runner_health


def run(price_momentum, signal):
    ctx = evaluate_exit_context({}, {}, signal)
    trend = classify_trend_health(ctx)["trend_health"]
    ex = evaluate_exhaustion(price_momentum, signal)["exhaustion_state"]
    pressure = evaluate_exit_pressure(
        price_momentum, signal, ex
    )["exit_pressure"]
    health = evaluate_runner_health(trend, ex, pressure)

    return trend, ex, pressure, health["runner_health"]


BASE = {
    "freshness": "FRESH",
    "coverage": 1.0,
    "flow_momentum": 0.5,
    "flow_acceleration": 0.2,
    "reserve_trend": "STABLE",
    "liquidity_health": "STABLE_OR_UNKNOWN",
    "participation_quality": "DIVERSE",
    "wallet_concentration": "DIVERSE",
    "price_impact_health": "HEALTHY",
}


def case(**x):
    s = dict(BASE)
    s.update(x)
    return s


def test_clean_sustained_pump():
    t, e, p, h = run(0.5, case())
    assert t == "STRONG"
    assert e == "NONE"
    assert p == "NONE"
    assert h == "RUNNER_HEALTHY"


def test_pump_then_exhaustion():
    _, e, p, h = run(
        0.4,
        case(
            flow_momentum=-0.2,
            flow_acceleration=-0.2,
            participation_quality="CONCENTRATED",
        ),
    )
    assert e == "CONFIRMED"
    assert p == "HIGH"
    assert h in {
        "RUNNER_TIGHTEN",
        "RUNNER_EMERGENCY_EXIT_CONTEXT",
    }


def test_liquidity_withdrawal():
    t, _, p, h = run(
        0.3,
        case(
            reserve_trend="BREAK",
            liquidity_health="CRITICAL",
        ),
    )
    assert t == "BREAK"
    assert p in {"BUILDING", "HIGH"}
    assert h in {
        "RUNNER_EXIT_CANDIDATE",
        "RUNNER_EMERGENCY_EXIT_CONTEXT",
    }


def test_noisy_sideways():
    t, e, p, h = run(
        0.0,
        case(
            flow_momentum=0.0,
            flow_acceleration=0.0,
        ),
    )
    assert t == "HEALTHY"
    assert e == "NONE"
    assert p == "NONE"
    assert h == "RUNNER_HEALTHY"


def test_stale_unknown():
    t, e, p, h = run(
        0.4,
        case(freshness="STALE"),
    )
    assert {t, e, p, h} == {
        "UNKNOWN",
    }
