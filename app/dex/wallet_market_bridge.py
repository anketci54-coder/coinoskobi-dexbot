def bind_wallet_market_context(
    wallet_evidence,
    behavior,
    entity_link,
    whale_flow,
    reputation,
):
    w = wallet_evidence or {}
    b = behavior or {}
    e = entity_link or {}
    whale = whale_flow or {}
    rep = reputation or {}

    ready = (
        w.get("state") == "READY"
        and b.get("state") in {"OBSERVED", "NEUTRAL"}
        and e.get("state") not in {"UNKNOWN", "UNSUPPORTED"}
        and whale.get("state") != "UNKNOWN"
        and rep.get("state") != "UNKNOWN"
    )

    hard_risk = rep.get("state") == "HARD_RISK_EVIDENCE"

    return {
        "wallet_context_ready": ready,
        "wallet_id": w.get("wallet_id"),
        "behavior_state": b.get("state", "UNKNOWN"),
        "behavior_tags": b.get("behavior_tags", []),
        "entity_state": e.get("state", "UNKNOWN"),
        "whale_state": whale.get("state", "UNKNOWN"),
        "whale_tags": whale.get("tags", []),
        "reputation_state": rep.get("state", "UNKNOWN"),
        "wallet_hard_risk": hard_risk,
        "market_context_allowed": ready,
        "hard_safety_override_allowed": False,
        "trade_permission": False,
        "decision_authority": False,
        "paper_authority": False,
        "live_authority": False,
        "wallet_authority": False,
        "execution_authority": False,
    }
