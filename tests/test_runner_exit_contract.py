from app.strategy.runner_exit_contract import build_runner_exit_contract


def test_contract():
    r = build_runner_exit_contract(
        trend_health="WEAKENING",
        exhaustion="CONFIRMED",
        runner_health="RUNNER_TIGHTEN",
        trailing={"recommended_stop": 97},
        exit_pressure="HIGH",
        risk_context={
            "hard_risk": False,
            "reasons": [],
        },
        freshness="FRESH",
        reasons=["FLOW_WEAKENING"],
    )

    assert r["trend_health"] == "WEAKENING"
    assert r["runner_health"] == "RUNNER_TIGHTEN"
    assert r["exit_pressure"] == "HIGH"
    assert r["freshness"] == "FRESH"


def test_hard_risk():
    r = build_runner_exit_contract(
        "BREAK",
        "CONFIRMED",
        "RUNNER_EMERGENCY_EXIT_CONTEXT",
        {},
        "HIGH",
        {
            "hard_risk": True,
            "reasons": ["LIQUIDITY_HARD_RISK"],
        },
        "FRESH",
    )

    assert r["hard_risk"] is True
    assert "LIQUIDITY_HARD_RISK" in r["reasons"]


def test_authority_zero():
    r = build_runner_exit_contract(
        "HEALTHY",
        "NONE",
        "RUNNER_HEALTHY",
        {},
        "NONE",
        {"hard_risk": False, "reasons": []},
        "FRESH",
    )

    assert r["decision_authority"] is False
    assert r["paper_authority"] is False
    assert r["live_authority"] is False
    assert r["wallet_authority"] is False
    assert r["execution_authority"] is False
