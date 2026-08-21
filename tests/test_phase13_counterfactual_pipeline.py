from app.learning.counterfactual_observation import (
    CounterfactualObservationStore,
)
from app.pipeline.engine import PipelineEngine


def test_pipeline_observes_watch_without_trade_authority():
    engine = PipelineEngine.__new__(
        PipelineEngine
    )
    engine.counterfactual_store = (
        CounterfactualObservationStore(
            max_entries=8,
            horizon_seconds=300,
            ttl_seconds=900,
        )
    )

    row = {
        "token": "0xtoken",
        "pool": "0xpool",
        "price_usd": 1.0,
    }

    summary = {
        "strategy": "PAPER_BUY",
        "unified": "WATCH",
        "paper": "WATCH",
        "reason": None,
        "hard_block": False,
        "score": 88,
        "confidence": 60,
        "sellability": "SELLABILITY_UNKNOWN",
    }

    first = engine.observe_counterfactual_candidate(
        row,
        summary,
        now=1000,
    )

    assert first["record"]["state"] == "RECORDED"
    assert first["evaluation"]["state"] == "UNKNOWN"

    row["price_usd"] = 1.25

    second = engine.observe_counterfactual_candidate(
        row,
        summary,
        now=1300,
    )

    assert second["evaluation"]["state"] == "EVALUATED"
    assert second["evaluation"]["outcome_class"] == (
        "MISSED_OPPORTUNITY"
    )
    assert second["record"]["state"] == "COOLDOWN"
    assert second["status"]["completed_size"] == 1
    assert second["status"]["provider_call"] is False
    assert second["status"]["execution_authority"] is False


def test_pipeline_does_not_record_skip_or_buy():
    engine = PipelineEngine.__new__(
        PipelineEngine
    )
    engine.counterfactual_store = (
        CounterfactualObservationStore()
    )

    row = {
        "token": "0xtoken",
        "pool": "0xpool",
        "price_usd": 1.0,
    }

    for action in ("SKIP", "PAPER_BUY"):
        result = (
            engine.observe_counterfactual_candidate(
                row,
                {"paper": action},
                now=1000,
            )
        )

        assert result["record"]["state"] == (
            "NOT_ELIGIBLE"
        )

    assert engine.counterfactual_store.size == 0



def test_engine_separates_plan_and_sizing_blockers():
    from pathlib import Path

    source = Path(
        "app/pipeline/engine.py"
    ).read_text(
        encoding="utf-8"
    )

    assert '"PLAN_BLOCKED"' in source

    assert (
        '"POSITION_SIZING_BLOCKED"'
        in source
    )

    assert (
        "MATHEMATICAL_PLAN_BLOCKED"
        not in source
    )

    assert '"plan_blockers"' in source
    assert '"sizing_blockers"' in source
    assert '"sizing_reason"' in source

    assert (
        '"effective_edge_fraction"'
        in source
    )

    assert (
        '"empirical_cost_uncertainty_fraction"'
        in source
    )

    assert '"gap_multiplier"' in source


def test_counterfactual_price_direction_is_not_net_profit_claim():
    engine = PipelineEngine.__new__(
        PipelineEngine
    )

    engine.counterfactual_store = (
        CounterfactualObservationStore(
            max_entries=8,
            horizon_seconds=300,
            ttl_seconds=900,
        )
    )

    row = {
        "token": "0xtoken",
        "pool": "0xpool",
        "price_usd": 1.0,
    }

    summary = {
        "strategy": "PAPER_BUY",
        "unified": "PAPER_BUY_CANDIDATE",
        "paper": "WATCH",
        "reason": "POSITION_SIZING_BLOCKED",
        "hard_block": False,
        "score": 83.33333333333333,
        "confidence": 83.33333333333333,
        "sellability": "SELLABILITY_OK",
    }

    engine.observe_counterfactual_candidate(
        row,
        summary,
        now=1000,
    )

    row["price_usd"] = 1.20

    result = (
        engine.observe_counterfactual_candidate(
            row,
            summary,
            now=1300,
        )
    )

    evaluation = result["evaluation"]

    assert evaluation["outcome_class"] == (
        "MISSED_OPPORTUNITY"
    )

    assert evaluation["outcome_scope"] == (
        "PRICE_DIRECTION_ONLY"
    )

    assert (
        evaluation["net_profit_verified"]
        is False
    )

    assert (
        evaluation[
            "realizable_profit_verified"
        ]
        is False
    )
