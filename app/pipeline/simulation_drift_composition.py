from app.pipeline.simulation_drift import (
    build_simulation_drift,
)
from app.pipeline.simulation_drift_evidence import (
    build_phase15_execution_evidence,
)
from app.pipeline.simulation_drift_classification import (
    classify_simulation_drift,
)


_AUTHORITY_FIELDS = (
    "trade_authority",
    "decision_authority",
    "paper_authority",
    "live_authority",
    "wallet_authority",
    "signing_authority",
    "execution_authority",
    "hardblock_override_authority",
)


def build_phase15_drift_composition(
    *,
    paper_position=None,
    runtime_evidence=None,
):
    """
    Phase 15C pure-local drift composition.

    Binds:
        existing paper/runtime facts
            ->
        Phase 15B execution evidence adapter
            ->
        Phase 15A simulation drift validator

    This layer is composition/readmodel only.

    It does NOT:
    - fetch provider data
    - call RPC / HTTP
    - use wallets
    - sign transactions
    - execute trades
    - open paper positions
    - alter DB state
    - grant decision authority
    - grant execution authority

    Missing evidence remains UNKNOWN/None.
    """

    evidence = build_phase15_execution_evidence(
        paper_position=paper_position,
        runtime_evidence=runtime_evidence,
    )

    drift = build_simulation_drift(
        paper_execution=evidence.get(
            "paper_execution"
        ),
        observed_execution=evidence.get(
            "observed_execution"
        ),
    )

    drift_classification = (
        classify_simulation_drift(drift)
    )

    authority_zero = all(
        evidence.get(field) is False
        and drift.get(field) is False
        and drift_classification.get(field) is False
        for field in _AUTHORITY_FIELDS
    )

    safety_zero = all(
        evidence.get(field) is False
        and drift.get(field) is False
        for field in (
            "provider_call",
            "external_fetch",
            "wallet_use",
            "signing",
            "executed",
        )
    )

    return {
        "contract": (
            "phase15_drift_composition_v1"
        ),

        "execution_evidence": evidence,
        "simulation_drift": drift,
        "drift_classification": drift_classification,

        "evidence_contract": evidence.get(
            "contract"
        ),
        "drift_contract": drift.get(
            "contract"
        ),
        "classification_contract": (
            drift_classification.get("contract")
        ),

        "observed_evidence_count": (
            evidence.get(
                "observed_evidence_count",
                0,
            )
        ),

        "observed_evidence_complete": bool(
            evidence.get(
                "observed_evidence_complete",
                False,
            )
        ),

        "comparable_evidence_count": (
            drift.get(
                "comparable_evidence_count",
                0,
            )
        ),

        "comparison_complete": bool(
            drift.get(
                "comparison_complete",
                False,
            )
        ),

        "missing_observed_fields": list(
            evidence.get(
                "missing_observed_fields"
            )
            or []
        ),

        "authority_zero": authority_zero,
        "safety_zero": safety_zero,

        "bounded": True,
        "deterministic": True,
        "read_only": True,
        "observation_only": True,
        "hot_path_wait": False,

        "provider_call": False,
        "external_fetch": False,
        "wallet_use": False,
        "signing": False,
        "executed": False,

        "trade_authority": False,
        "decision_authority": False,
        "paper_authority": False,
        "live_authority": False,
        "wallet_authority": False,
        "signing_authority": False,
        "execution_authority": False,
        "hardblock_override_authority": False,
    }
