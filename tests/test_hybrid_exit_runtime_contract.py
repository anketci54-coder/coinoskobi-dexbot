from app.risk.hybrid_exit_controller import (
    evaluate_hybrid_exit,
)
from app.risk.hybrid_exit_runtime_adapter import (
    build_hybrid_exit_runtime_input,
)


def build(
    *,
    current=1.10,
    highest=1.10,
    static_sl=0.90,
    hard_block=False,
    sellability="SELLABILITY_OK",
    freshness="FRESH",
    coverage=1.0,
    liquidity="STABLE",
    momentum=0.40,
    acceleration=0.10,
    trend="HEALTHY",
    pressure="NONE",
    impact="HEALTHY",
):
    adapter = build_hybrid_exit_runtime_input(
        position_state={
            "entry_price": 1.0,
            "current_price": current,
            "highest_price": highest,
            "sl_price": static_sl,
        },
        signal_bundle={
            "freshness": freshness,
            "coverage": coverage,
            "liquidity_health": liquidity,
            "flow_momentum": momentum,
            "flow_acceleration": acceleration,
            "price_impact_health": impact,
        },
        trend_health=trend,
        exit_pressure=pressure,
        hard_block=hard_block,
        sellability=sellability,
    )

    controller_keys = {
        "entry_price", "current_price", "highest_price", "static_sl_price",
        "hard_block", "sellability", "liquidity_health", "flow_momentum",
        "flow_acceleration", "trend_health", "exit_pressure", "price_impact_health",
    }
    controller_input = {key: adapter[key] for key in controller_keys}
    return adapter, evaluate_hybrid_exit(**controller_input)


def test_adapter_can_feed_hybrid_controller():
    adapter, decision = build()
    assert adapter["evidence_ready"] is True
    assert decision.action in {"HOLD", "RUNNER", "DOWNSHIFT", "EXIT", "EMERGENCY_EXIT"}


def test_hard_block_dominates_runtime_health():
    _, decision = build(current=1.30, highest=1.30, hard_block=True, liquidity="HEALTHY", momentum=1.0, acceleration=1.0, trend="STRONG", pressure="NONE", impact="HEALTHY")
    assert decision.action == "EMERGENCY_EXIT"
    assert decision.reason == "HARD_BLOCK"
    assert decision.exit_now is True


def test_persisted_floor_dominates_healthy_intelligence():
    _, decision = build(current=0.89, highest=1.20, static_sl=0.90, liquidity="HEALTHY", momentum=1.0, acceleration=1.0, trend="STRONG", pressure="NONE", impact="HEALTHY")
    assert decision.action == "EXIT"
    assert decision.reason == "DYNAMIC_PROTECTION_FLOOR"
    assert decision.exit_now is True
    assert decision.protection_price == 0.90


def test_stale_intelligence_does_not_create_fake_deterioration():
    adapter, decision = build(current=1.02, highest=1.02, freshness="STALE", liquidity="CRITICAL", momentum=-1.0, acceleration=-1.0, trend="BREAK", pressure="HIGH", impact="CRITICAL")
    assert adapter["evidence_ready"] is False
    assert adapter["liquidity_health"] == 0.50
    assert adapter["flow_momentum"] == 0.0
    assert adapter["flow_acceleration"] == 0.0
    assert adapter["trend_health"] == 0.50
    assert adapter["exit_pressure"] == 0.0
    assert decision.reason != "SEVERE_MARKET_DETERIORATION"


def test_runtime_adapter_has_no_execution_authority():
    adapter, _ = build()
    assert adapter["decision_authority"] is False
    assert adapter["paper_authority"] is False
    assert adapter["live_authority"] is False
    assert adapter["wallet_authority"] is False
    assert adapter["execution_authority"] is False
