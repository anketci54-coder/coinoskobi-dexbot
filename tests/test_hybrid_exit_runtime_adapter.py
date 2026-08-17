from app.risk.hybrid_exit_runtime_adapter import (
    build_hybrid_exit_runtime_input,
)


def position():
    return {
        "entry_price": 1.0,
        "current_price": 1.10,
        "highest_price": 1.20,
        "sl_price": 0.90,
    }


def signal(**overrides):
    data = {
        "freshness": "FRESH",
        "coverage": 1.0,
        "flow_momentum": 0.40,
        "flow_acceleration": 0.10,
        "liquidity_health": "STABLE",
        "price_impact_health": "HEALTHY",
    }
    data.update(overrides)
    return data


def test_position_contract_is_preserved():
    result = build_hybrid_exit_runtime_input(
        position_state=position(),
        signal_bundle=signal(),
        trend_health="HEALTHY",
        exit_pressure="NONE",
    )

    assert result["entry_price"] == 1.0
    assert result["current_price"] == 1.10
    assert result["highest_price"] == 1.20
    assert result["static_sl_price"] == 0.90


def test_categories_are_normalized():
    result = build_hybrid_exit_runtime_input(
        position_state=position(),
        signal_bundle=signal(
            liquidity_health="DETERIORATING",
            price_impact_health="CRITICAL",
        ),
        trend_health="WEAKENING",
        exit_pressure="HIGH",
    )

    assert result["liquidity_health"] == 0.30
    assert result["trend_health"] == 0.35
    assert result["exit_pressure"] == 1.0
    assert result["price_impact_health"] == 0.0


def test_dict_category_producers_are_supported():
    result = build_hybrid_exit_runtime_input(
        position_state=position(),
        signal_bundle=signal(),
        trend_health={
            "trend_health": "STRONG",
        },
        exit_pressure={
            "exit_pressure": "BUILDING",
        },
    )

    assert result["trend_health"] == 1.0
    assert result["exit_pressure"] == 0.50


def test_signed_flow_is_preserved_and_clamped():
    result = build_hybrid_exit_runtime_input(
        position_state=position(),
        signal_bundle=signal(
            flow_momentum=-4.0,
            flow_acceleration=3.0,
        ),
        trend_health="HEALTHY",
        exit_pressure="NONE",
    )

    assert result["flow_momentum"] == -1.0
    assert result["flow_acceleration"] == 1.0


def test_unknown_categories_are_neutral():
    result = build_hybrid_exit_runtime_input(
        position_state=position(),
        signal_bundle=signal(
            liquidity_health="SOMETHING_NEW",
            price_impact_health="SOMETHING_NEW",
        ),
        trend_health="SOMETHING_NEW",
        exit_pressure="SOMETHING_NEW",
    )

    assert result["liquidity_health"] == 0.50
    assert result["trend_health"] == 0.50
    assert result["exit_pressure"] == 0.0
    assert result["price_impact_health"] == 0.50


def test_stale_signal_forces_neutral_runtime_evidence():
    result = build_hybrid_exit_runtime_input(
        position_state=position(),
        signal_bundle=signal(
            freshness="STALE",
            flow_momentum=-1.0,
            flow_acceleration=-1.0,
            liquidity_health="CRITICAL",
            price_impact_health="CRITICAL",
        ),
        trend_health="BREAK",
        exit_pressure="HIGH",
    )

    assert result["evidence_ready"] is False
    assert result["liquidity_health"] == 0.50
    assert result["flow_momentum"] == 0.0
    assert result["flow_acceleration"] == 0.0
    assert result["trend_health"] == 0.50
    assert result["exit_pressure"] == 0.0
    assert result["price_impact_health"] == 0.50


def test_partial_coverage_forces_neutral_runtime_evidence():
    result = build_hybrid_exit_runtime_input(
        position_state=position(),
        signal_bundle=signal(
            coverage=0.80,
            liquidity_health="CRITICAL",
        ),
        trend_health="BREAK",
        exit_pressure="HIGH",
    )

    assert result["evidence_ready"] is False
    assert result["liquidity_health"] == 0.50
    assert result["trend_health"] == 0.50
    assert result["exit_pressure"] == 0.0


def test_hard_block_and_sellability_are_not_normalized_away():
    result = build_hybrid_exit_runtime_input(
        position_state=position(),
        signal_bundle=signal(),
        trend_health="HEALTHY",
        exit_pressure="NONE",
        hard_block=True,
        sellability="SELLABILITY_BLOCK",
    )

    assert result["hard_block"] is True
    assert result["sellability"] == "SELLABILITY_BLOCK"


def test_authority_is_zero():
    result = build_hybrid_exit_runtime_input(
        position_state=position(),
        signal_bundle=signal(),
        trend_health="HEALTHY",
        exit_pressure="NONE",
    )

    assert result["decision_authority"] is False
    assert result["paper_authority"] is False
    assert result["live_authority"] is False
    assert result["wallet_authority"] is False
    assert result["execution_authority"] is False
