def build_outcome_evidence(
    chain,
    observation_id,
    observed_at,
    evaluated_at,
    expected_context=None,
    realized_outcome=None,
    evidence_coverage=1.0,
    freshness="FRESH",
    provenance=None,
):
    chain = (chain or "").strip().lower()
    observation_id = (observation_id or "").strip()

    coverage = _coverage(evidence_coverage)

    if not chain or not observation_id:
        state = "UNKNOWN"
    elif not observed_at or not evaluated_at:
        state = "UNKNOWN"
    elif freshness != "FRESH":
        state = "UNKNOWN"
    elif coverage <= 0:
        state = "UNKNOWN"
    elif realized_outcome is None:
        state = "PENDING_OUTCOME"
    else:
        state = "EVIDENCE_READY"

    return {
        "state": state,
        "outcome_id": (
            f"{chain}:{observation_id}"
            if chain and observation_id
            else None
        ),
        "chain": chain or None,
        "observation_id": observation_id or None,
        "observed_at": observed_at,
        "evaluated_at": evaluated_at,
        "expected_context": expected_context,
        "realized_outcome": realized_outcome,
        "evidence_coverage": coverage,
        "freshness": freshness,
        "provenance": provenance,
        "missing_outcome_is_success": False,
        "missing_outcome_is_failure": False,
        "hindsight_rewrite_allowed": False,
        "trade_permission": False,
        "decision_authority": False,
        "paper_authority": False,
        "live_authority": False,
        "wallet_authority": False,
        "execution_authority": False,
    }


def same_outcome_identity(a, b):
    a = a or {}
    b = b or {}

    return bool(
        a.get("outcome_id")
        and b.get("outcome_id")
        and a["outcome_id"] == b["outcome_id"]
    )


def _coverage(value):
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return 0.0
