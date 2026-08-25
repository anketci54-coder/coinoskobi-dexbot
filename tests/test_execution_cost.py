from app.strategy.execution_cost import (
    ExecutionCostEngine,
)


def engine():
    return ExecutionCostEngine()


def base_costs():
    return {
        "trade_size_usd": 1000,
        "buy_tax_pct": 1,
        "sell_tax_pct": 1,
        "swap_fee_pct": 0.25,
        "slippage_pct": 0.5,
        "gas_cost_usd": 1,
    }


def test_missing_costs_stay_unknown():
    result = engine().evaluate({})

    assert result["feasibility"] == "UNKNOWN_COST"
    assert result["cost_complete"] is False
    assert result["known_total_cost_pct"] == 0
    assert "buy_tax_pct" in result["unknown_components"]


def test_complete_cost_without_edge():
    context = base_costs()
    context["mev_cost_pct"] = 0.2

    result = engine().evaluate(context)

    assert result["cost_complete"] is True
    assert result["components_pct"]["gas_cost_pct"] == 0.1
    assert round(result["known_total_cost_pct"], 6) == 3.05
    assert result["feasibility"] == "COST_KNOWN_EDGE_UNKNOWN"


def test_positive_net_edge():
    context = base_costs()
    context.update({
        "mev_cost_pct": 0.2,
        "expected_gross_edge_pct": 10,
    })

    result = engine().evaluate(context)

    assert result["feasibility"] == "POSITIVE_NET_EDGE"
    assert result["net_edge_pct"] > 0


def test_negative_net_edge():
    result = engine().evaluate({
        "trade_size_usd": 100,
        "buy_tax_pct": 5,
        "sell_tax_pct": 5,
        "swap_fee_pct": 0.25,
        "slippage_pct": 1,
        "mev_cost_pct": 0.5,
        "gas_cost_usd": 2,
        "expected_gross_edge_pct": 8,
    })

    assert result["feasibility"] == "NEGATIVE_NET_EDGE"
    assert result["net_edge_pct"] < 0


def test_unknown_gas_does_not_become_zero():
    result = engine().evaluate({
        "trade_size_usd": 1000,
        "buy_tax_pct": 1,
        "sell_tax_pct": 1,
        "swap_fee_pct": 0.25,
        "slippage_pct": 0.5,
        "mev_cost_pct": 0.2,
        "gas_cost_usd": None,
        "expected_gross_edge_pct": 20,
    })

    assert result["cost_complete"] is False
    assert result["feasibility"] == "UNKNOWN_COST"
    assert result["net_edge_pct"] is None


def test_unknown_swap_fee_does_not_become_zero():
    result = engine().evaluate({
        "trade_size_usd": 1000,
        "buy_tax_pct": 1,
        "sell_tax_pct": 1,
        "swap_fee_pct": None,
        "slippage_pct": 0.5,
        "mev_cost_pct": 0.2,
        "gas_cost_usd": 1,
        "expected_gross_edge_pct": 20,
    })

    assert "swap_fee_pct" in result["unknown_components"]
    assert result["feasibility"] == "UNKNOWN_COST"


def test_expected_mev_loss_usd_becomes_percent_when_size_known():
    context = base_costs()
    context["mev_expected_loss_usd"] = 2.0

    result = engine().evaluate(context)

    assert result["cost_complete"] is True
    assert result["components_pct"]["mev_cost_pct"] == 0.2
    assert result["mev_expected_loss_usd"] == 2.0
    assert result["mev_cost_source"] == "DIRECT_USD"


def test_nested_mev_analyzer_payload_is_supported():
    context = base_costs()
    context["mev_result"] = {
        "expected_loss": {
            "state": "READY",
            "expected_mev_loss_usd": 3.0,
        }
    }

    result = engine().evaluate(context)

    assert result["cost_complete"] is True
    assert result["components_pct"]["mev_cost_pct"] == 0.3
    assert result["mev_cost_source"] == "MEV_ANALYZER_PAYLOAD"


def test_direct_mev_percent_has_precedence_over_expected_loss():
    context = base_costs()
    context.update({
        "mev_cost_pct": 0.4,
        "mev_expected_loss_usd": 99.0,
    })

    result = engine().evaluate(context)

    assert result["components_pct"]["mev_cost_pct"] == 0.4
    assert result["mev_cost_source"] == "DIRECT_PERCENT"


def test_expected_mev_loss_requires_trade_size_for_conversion():
    result = engine().evaluate({
        "buy_tax_pct": 1,
        "sell_tax_pct": 1,
        "swap_fee_pct": 0.25,
        "slippage_pct": 0.5,
        "gas_cost_usd": 1,
        "mev_expected_loss_usd": 2.0,
    })

    assert result["cost_complete"] is False
    assert "trade_size_usd_for_mev" in result["unknown_components"]
    assert result["components_pct"]["mev_cost_pct"] is None


def test_engine_has_no_authority():
    result = engine().evaluate({})

    assert result["decision_authority"] is False
    assert result["paper_authority"] is False
    assert result["live_authority"] is False
    assert result["wallet_authority"] is False
    assert result["execution_authority"] is False
