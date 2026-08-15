from app.pipeline.tactical_truth import (
    build_tactical_truth,
)


def test_tactical_truth_composes_runtime_truth():
    result = build_tactical_truth(
        market_context={
            "price_usd": 100.0,
        },
        execution_cost={
            "model": "execution_cost_v1",
            "expected_gross_edge_pct": 25.0,
            "known_total_cost_pct": 5.0,
            "net_edge_pct": 20.0,
            "cost_complete": True,
            "feasibility": "POSITIVE_NET_EDGE",
        },
        paper={},
        tp_multiplier=1.20,
        sl_multiplier=0.90,
    )

    assert (
        result["contract"]
        == "phase14_tactical_truth_v1"
    )

    assert (
        result["entry_plan"]["entry_price"]
        == 100.0
    )

    assert (
        result["exit_plan"][
            "take_profit_price"
        ]
        == 120.0
    )

    assert (
        result["exit_plan"][
            "stop_loss_price"
        ]
        == 90.0
    )

    assert (
        result["risk_reward"][
            "reward_to_risk"
        ]
        == 2.0
    )

    assert (
        result["expected_pnl"][
            "net_expected_pnl_pct"
        ]
        == 20.0
    )

    assert result["read_only"] is True
    assert result["proposal_only"] is True
    assert result["hot_path_wait"] is False
    assert result["provider_call"] is False
    assert result["external_fetch"] is False
    assert result["ai_inference"] is False

    assert (
        result["trade_authority"]
        is False
    )
    assert (
        result["decision_authority"]
        is False
    )
    assert (
        result["paper_authority"]
        is False
    )
    assert (
        result["live_authority"]
        is False
    )
    assert (
        result["wallet_authority"]
        is False
    )
    assert (
        result["execution_authority"]
        is False
    )
    assert (
        result[
            "hardblock_override_authority"
        ]
        is False
    )


def test_tactical_truth_preserves_unknowns():
    result = build_tactical_truth(
        market_context={},
        execution_cost={},
        paper={},
        tp_multiplier=1.20,
        sl_multiplier=0.90,
    )

    assert (
        result["entry_plan"]["entry_price"]
        is None
    )

    assert (
        result["exit_plan"][
            "take_profit_price"
        ]
        is None
    )

    assert (
        result["exit_plan"][
            "stop_loss_price"
        ]
        is None
    )

    assert (
        result["risk_reward"][
            "available"
        ]
        is False
    )

    assert (
        result["expected_pnl"][
            "net_expected_pnl_pct"
        ]
        is None
    )


def test_tactical_truth_can_use_paper_entry_price():
    result = build_tactical_truth(
        market_context={},
        execution_cost={
            "net_edge_pct": 7.5,
        },
        paper={
            "entry_price": 10.0,
        },
        tp_multiplier=1.20,
        sl_multiplier=0.90,
    )

    assert (
        result["entry_plan"]["entry_price"]
        == 10.0
    )

    assert (
        result["entry_plan"]["source"]
        == "PAPER_ENTRY_PRICE"
    )

    assert (
        result["exit_plan"][
            "take_profit_price"
        ]
        == 12.0
    )

    assert (
        result["exit_plan"][
            "stop_loss_price"
        ]
        == 9.0
    )

    assert (
        result["risk_reward"][
            "reward_to_risk"
        ]
        == 2.0
    )

    assert (
        result["expected_pnl"][
            "net_expected_pnl_pct"
        ]
        == 7.5
    )
