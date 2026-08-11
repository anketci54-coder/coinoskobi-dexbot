def bind_adversary_market_context(
    wallet_context,
    adversary_reputation,
):
    wallet = wallet_context or {}
    adv = adversary_reputation or {}

    wallet_ready = bool(
        wallet.get("wallet_context_ready")
        and wallet.get("market_context_allowed")
    )

    adversary_state = adv.get("state", "UNKNOWN")
    hard_adversary = (
        adversary_state == "HARD_ADVERSARY_EVIDENCE"
        or adv.get("hard_evidence") is True
    )

    unresolved = adversary_state in {
        "UNKNOWN",
        "UNRESOLVED_CONFLICT",
    }

    if not wallet_ready:
        state = "WALLET_CONTEXT_NOT_READY"
        candidate_action = "SAFE_DOWNGRADE"
    elif hard_adversary:
        state = "HARD_ADVERSARY_RISK"
        candidate_action = "BLOCK_CANDIDATE"
    elif adversary_state == "HIGH_RISK":
        state = "HIGH_ADVERSARY_RISK"
        candidate_action = "DOWNGRADE_CANDIDATE"
    elif adversary_state == "ELEVATED_RISK":
        state = "ELEVATED_ADVERSARY_RISK"
        candidate_action = "DOWNGRADE_CANDIDATE"
    elif unresolved:
        state = "UNRESOLVED"
        candidate_action = "SAFE_DOWNGRADE"
    else:
        state = "CONTEXT_READY"
        candidate_action = "NO_ADVERSARY_BLOCK"

    return {
        "state": state,
        "wallet_context_ready": wallet_ready,
        "wallet_id": wallet.get("wallet_id"),
        "wallet_hard_risk": bool(wallet.get("wallet_hard_risk")),
        "adversary_state": adversary_state,
        "adversary_risk_score": adv.get("risk_score"),
        "adversary_hard_risk": hard_adversary,
        "adversary_evidence_tags": adv.get("evidence_tags", []),
        "candidate_action": candidate_action,
        "can_block_or_downgrade_candidate": True,
        "can_upgrade_candidate": False,
        "hard_safety_override_allowed": False,
        "trade_permission": False,
        "trade_signal": False,
        "decision_authority": False,
        "paper_authority": False,
        "live_authority": False,
        "wallet_authority": False,
        "execution_authority": False,
    }
