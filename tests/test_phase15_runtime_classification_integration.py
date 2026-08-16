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
    ):
        captured["paper"] = dict(
            paper_position or {}
        )
        captured["runtime"] = dict(
            runtime_evidence or {}
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
        )

    monkeypatch.setattr(
        engine_module,
        "build_phase15_drift_composition",
        capture_builder,
    )

    result = engine.run(
        "0xphase15h",
        market_context=context,
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
