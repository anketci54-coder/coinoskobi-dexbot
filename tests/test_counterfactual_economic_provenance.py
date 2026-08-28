import json
import sqlite3

from app.learning.counterfactual_observation import (
    CounterfactualObservationStore,
)
from app.pipeline.engine import PipelineEngine
from app.paper.schema import ensure_paper_schema


def test_counterfactual_persists_economic_provenance(
    tmp_path,
):
    db_path = tmp_path / "paper.db"

    schema_db = sqlite3.connect(db_path)
    ensure_paper_schema(schema_db)
    schema_db.close()

    engine = PipelineEngine.__new__(
        PipelineEngine
    )

    engine.counterfactual_store = (
        CounterfactualObservationStore(
            db_path=db_path,
        )
    )

    mathematical_plan = {
        "paper_eligible": False,
        "blockers": [
            "KNOWN_COMPONENT_EDGE_NOT_POSITIVE",
        ],
        "expected": {
            "gross_horizon_log_edge": 0.01,
            "known_net_horizon_log_edge": -0.002,
            "known_net_edge_fraction": -0.001998,
        },
        "cost_model": {
            "route_friction_fraction": 0.0025,
            "buy_tax_fraction": 0.0,
            "sell_tax_fraction": 0.0,
            "buy_gas_usd": 0.01,
            "sell_gas_usd": 0.01,
            "cost_complete": False,
            "unknown_components": [
                "MEV_MONETARY_COST",
            ],
        },
        "vur_kac_entry": {
            "ready": True,
            "reason": "VUR_KAC_ENTRY_SIGNAL_READY",
            "flow_momentum": 0.2,
            "flow_acceleration": 0.1,
            "freshness": "FRESH",
            "coverage": 1.0,
        },
    }

    sizing_diagnostics = {
        "effective_edge_fraction": 0.0,
        "cost_complete": False,
    }

    vur_kac_shadow = {
        "ready": True,
        "reason": "VUR_KAC_ENTRY_SIGNAL_READY",
        "flow_momentum": 0.2,
        "flow_acceleration": 0.1,
        "freshness": "FRESH",
        "coverage": 1.0,
    }

    row = {
        "token": "0xtoken",
        "pool": "0xpool",
        "price_usd": 1.0,
    }

    summary = {
        "strategy": "PAPER_BUY",
        "unified": "PAPER_BUY_CANDIDATE",
        "paper": "WATCH",
        "reason": "PLAN_BLOCKED",
        "hard_block": False,
        "score": 100.0,
        "confidence": 100.0,
        "sellability": "SELLABILITY_OK",
        "plan_blockers": [
            "KNOWN_COMPONENT_EDGE_NOT_POSITIVE",
        ],
        "sizing_blockers": [
            "NET_EDGE_NOT_POSITIVE",
            "PLAN_AMOUNT_ZERO",
        ],
        "sizing_reason": (
            "MATHEMATICAL_POSITION_SIZE_ZERO"
        ),
        "entry_amount_usdt": 0.0,
        "mathematical_plan": mathematical_plan,
        "sizing_diagnostics": sizing_diagnostics,
        "vur_kac_entry_shadow": vur_kac_shadow,
    }

    result = (
        engine.observe_counterfactual_candidate(
            row,
            summary,
            now=1000.0,
        )
    )

    assert result["record"]["state"] == "RECORDED"

    db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row

    for table in (
        "candidate_decision_history",
        "counterfactual_observations",
    ):
        stored = db.execute(
            f"""
            SELECT context_json
            FROM {table}
            ORDER BY id DESC
            LIMIT 1
            """
        ).fetchone()

        assert stored is not None

        context = json.loads(
            stored["context_json"]
        )

        assert (
            context["economic_provenance_version"]
            == "CANDIDATE_DECISION_V1"
        )

        assert (
            context["mathematical_plan"]
            == mathematical_plan
        )

        assert (
            context["sizing_diagnostics"]
            == sizing_diagnostics
        )

        assert (
            context["vur_kac_entry_shadow"]
            == vur_kac_shadow
        )

        assert (
            context["entry_amount_usdt"]
            == 0.0
        )

        assert (
            context["hindsight_reconstructed"]
            is False
        )

    db.close()
