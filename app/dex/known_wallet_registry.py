def known_wallet_record(
    wallet_id,
    label,
    source,
    reliability,
    freshness="FRESH",
    provenance=None,
):
    reliability = _score(reliability)

    if not wallet_id or not label or not source:
        state = "UNKNOWN"
    elif freshness != "FRESH":
        state = "STALE"
    elif reliability >= 0.85:
        state = "HIGH_CONFIDENCE_SOURCE"
    elif reliability >= 0.60:
        state = "MEDIUM_CONFIDENCE_SOURCE"
    else:
        state = "LOW_CONFIDENCE_SOURCE"

    return {
        "state": state,
        "wallet_id": wallet_id,
        "label": label,
        "source": source,
        "source_reliability": reliability,
        "freshness": freshness,
        "provenance": provenance,
        "known": bool(wallet_id and label and source),
        "trusted": False,
        "trade_permission": False,
        "identity_proof": False,
        "decision_authority": False,
        "paper_authority": False,
        "live_authority": False,
        "wallet_authority": False,
        "execution_authority": False,
    }


def compare_label_with_behavior(record, behavior_tags):
    r = record or {}
    tags = set(behavior_tags or [])
    label = str(r.get("label") or "").upper()

    if not r.get("known") or r.get("freshness") != "FRESH":
        state = "UNKNOWN"
    elif label == "SMART_MONEY" and "DISTRIBUTION_EVIDENCE" in tags:
        state = "CONTRADICTED"
    elif label == "SMART_MONEY" and "ACCUMULATION_EVIDENCE" in tags:
        state = "SUPPORTED"
    else:
        state = "UNRESOLVED"

    return {
        "state": state,
        "label": r.get("label"),
        "behavior_tags": sorted(tags),
        "label_overrides_behavior": False,
        "trade_permission": False,
        "decision_authority": False,
        "execution_authority": False,
    }


def _score(value):
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return 0.0
