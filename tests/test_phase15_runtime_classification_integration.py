import app.pipeline.engine as engine_module
from app.pipeline.engine import PipelineEngine


def test_phase15h_engine_projects_runtime_classification(
    monkeypatch,
):
    engine = PipelineEngine.__new__(PipelineEngine)

    monkeypatch.setattr(
        engine_module,
        "token_analyze",
        lambda _: {
            "name": "Phase15H",
            "symbol": "P15H",
        },
    )

    monkeypatch.setattr(
        engine_module,
        "pair_analyze",
        lambda _: {
            "exists": True,
        },
    )

    monkeypatch.setattr(
        engine_module,
        "risk_analyze",
        lambda _: {
            "honeypot": False,
            "sellable": True,
        },
    )

    monkeypatch.setattr(
        engine_module,
        "sellability_analyze",
        lambda _: {
            "status": "SELLABILITY_OK",
        },
    )

    # Reuse the engine's real Phase15 composition,
    # classifier and Command Center projection.
    #
    # Only surrounding analyzers are bounded here.
    engine.paper_db = None

    context = {
        "price_usd": 1.0,
        "liquidity_usd": 100000.0,
        "slippage_pct": 2.0,
        "mev_cost_pct": 0.1,
        "quote_delay_ms": 100,
        "execution_delay_ms": 250,
    }

    # Capture the real Phase15 composition input while
    # preserving the production implementation.
    real_builder = (
        engine_module.build_phase15_drift_composition
    )
    captured = {}

    def capture_builder(
        *,
        paper_position=None,
        runtime_evidence=None,
        phase15h_execution=None,
    ):
        captured["paper"] = dict(
            paper_position or {}
        )
        captured["runtime"] = dict(
            runtime_evidence or {}
        )
        captured["phase15h"] = dict(
            phase15h_execution or {}
        )

        # Supply a paper baseline only for comparison.
        paper = dict(paper_position or {})
        paper.update({
            "entry_price": 1.0,
            "exit_price": 1.0,
            "slippage": 0.5,
            "liquidity_usd": 100000.0,
            "sellability": "SELLABILITY_OK",
        })

        # Complete synthetic observed evidence inside
        # the test only. Production code is untouched.
        runtime = dict(runtime_evidence or {})
        runtime.update({
            "entry_price": 1.0,
            "exit_price": 1.0,
            "slippage_pct": 2.0,
            "mev_cost_pct": 0.1,
            "quote_delay_ms": 100,
            "execution_delay_ms": 250,
            "liquidity_usd": 100000.0,
            "sellability": "SELLABILITY_OK",
        })

        return real_builder(
            paper_position=paper,
            runtime_evidence=runtime,
            phase15h_execution=phase15h_execution,
        )

    monkeypatch.setattr(
        engine_module,
        "build_phase15_drift_composition",
        capture_builder,
    )

    phase15h_execution = {
        "buy": {
            "contract": "phase15h_transaction_simulation_v1",
            "status": "SUCCESS",
            "block": {
                "number": 123191429,
                "hash": "0xabc",
                "chain_id": 56,
            },
            "received_token_raw": 2000,
            "recipient_balance_delta_raw": 2000,
            "gas_used": 120000,
            "effective_gas_price": 1_000_000_000,
            "execution_gas_cost_wei": 120_000_000_000_000,
            "fill_status": "SIMULATED_RECIPIENT_DELTA",
        },
        "sell": {
            "contract": "phase15h_transaction_simulation_v1",
            "status": "SUCCESS",
            "block": {
                "number": 123191430,
                "hash": "0xdef",
                "chain_id": 56,
            },
            "received_quote_raw": 990,
            "recipient_balance_delta_raw": 990,
            "gas_used": 110000,
            "effective_gas_price": 1_000_000_000,
            "execution_gas_cost_wei": 110_000_000_000_000,
            "fill_status": "SIMULATED_RECIPIENT_DELTA",
        },
    }

    result = engine.run(
        "0xphase15h",
        market_context=context,
        phase15h_execution=phase15h_execution,
    )

    assert result["success"] is True

    data = result["data"]
    source = data["simulation_drift"]
    classification = source[
        "drift_classification"
    ]
    projected = data["command_center"][
        "simulation_drift"
    ]

    assert captured["runtime"]["slippage_pct"] == 2.0
    assert captured["phase15h"]["buy"]["status"] == "SUCCESS"

    bound = source["execution_evidence"]["phase15h_execution_evidence"]
    assert bound["buy"]["status"] == "SUCCESS"
    assert bound["sell"]["status"] == "SUCCESS"
    assert bound["buy"]["received_token_raw"] == 2000
    assert bound["sell"]["received_quote_raw"] == 990
    assert source["execution_evidence"]["phase15h_round_trip_complete"] is True

    assert (
        classification["contract"]
        == "phase15_drift_classification_v1"
    )
    assert classification["classification"] == "HIGH_DRIFT"
    assert classification["severity"] == "HIGH"

    assert projected["classification"] == "HIGH_DRIFT"
    assert projected["severity"] == "HIGH"
    assert (
        projected["classification_contract"]
        == "phase15_drift_classification_v1"
    )

    # Phase15H is integration proof only.
    assert classification["blocks_trade"] is False
    assert classification["blocks_paper"] is False
    assert classification["risk_gate_binding"] is False

    assert projected["blocks_trade"] is False
    assert projected["blocks_paper"] is False
    assert projected["risk_gate_binding"] is False
    assert projected["observation_only"] is True

    assert projected["decision_authority"] is False
    assert projected["execution_authority"] is False
    assert (
        projected["hardblock_override_authority"]
        is False
    )

def test_phase15h_runtime_buy_runs_only_after_paper_open(monkeypatch, caplog):
    calls = []
    caplog.set_level("INFO", logger="app.pipeline.engine")

    def fake_buy(**kwargs):
        calls.append(dict(kwargs))
        return {
            "contract": "phase15h_transaction_simulation_v1",
            "side": "BUY",
            "status": "SUCCESS",
            "block": {
                "number": kwargs["block_number"],
                "hash": "0xabc",
                "chain_id": 56,
            },
            "received_token_raw": 123,
            "recipient_balance_delta_raw": 123,
        }

    monkeypatch.setattr(
        engine_module,
        "simulate_paper_buy",
        fake_buy,
    )

    evidence = engine_module._runtime_phase15h_buy_evidence(
        token_address="0x0000000000000000000000000000000000000002",
        paper={
            "action": "PAPER_BUY",
            "trade_type": "VUR_KAC",
            "entry_amount_usdt": 600.0,
        },
        exit_evidence={
            "runtime_price_latest_block": 123456,
            "wbnb_usd_estimate": 600.0,
        },
        sellability_data={"buy_tax": 1.0},
    )

    assert evidence["buy"]["status"] == "SUCCESS"
    assert evidence["buy"]["trade_type"] == "VUR_KAC"
    assert len(calls) == 1
    assert calls[0]["amount_in_wei"] == 10 ** 18
    assert calls[0]["block_number"] == 123456
    assert calls[0]["fee_on_transfer"] is True
    assert "PHASE15H_RUNTIME_BUY" in caplog.text
    assert "trade_type=VUR_KAC" in caplog.text
    assert "status=SUCCESS" in caplog.text
    assert "block=123456" in caplog.text

    skipped = engine_module._runtime_phase15h_buy_evidence(
        token_address="0x0000000000000000000000000000000000000002",
        paper={
            "action": "WATCH",
            "entry_amount_usdt": 600.0,
        },
        exit_evidence={
            "runtime_price_latest_block": 123456,
            "wbnb_usd_estimate": 600.0,
        },
    )

    assert skipped is None
    assert len(calls) == 1

