VALID_SIGNAL_STATES = {
    "POSITIVE",
    "NEGATIVE",
    "NEUTRAL",
    "UNKNOWN",
}


def build_entry_signal_attribution(
    *,
    strategy_decision,
    unified_decision,
    hard_block,
    sellability_status,
):
    strategy_state = (
        "POSITIVE"
        if strategy_decision == "PAPER_BUY"
        else "NEUTRAL"
    )

    unified_state = (
        "POSITIVE"
        if unified_decision
        == "PAPER_BUY_CANDIDATE"
        else "NEUTRAL"
    )

    risk_state = (
        "NEGATIVE"
        if bool(hard_block)
        else "POSITIVE"
    )

    if sellability_status == "SELLABILITY_OK":
        sellability_state = "POSITIVE"
    elif sellability_status in {
        "SELLABILITY_BLOCKED",
        "SELLABILITY_FAILED",
    }:
        sellability_state = "NEGATIVE"
    else:
        sellability_state = "UNKNOWN"

    result = {
        "paper_entry": "POSITIVE",
        "strategy_decision": strategy_state,
        "unified_decision": unified_state,
        "risk_gate": risk_state,
        "sellability": sellability_state,
    }

    if not set(result.values()).issubset(
        VALID_SIGNAL_STATES
    ):
        raise ValueError(
            "invalid entry signal state"
        )

    return result


def build_exit_baseline(
    *,
    entry_price,
    take_profit_price,
    stop_loss_price,
):
    entry = float(entry_price)
    take_profit = float(
        take_profit_price
    )
    stop_loss = float(
        stop_loss_price
    )

    if (
        entry <= 0
        or take_profit <= 0
        or stop_loss <= 0
    ):
        raise ValueError(
            "exit baseline prices must be positive"
        )

    return {
        "version": "PHASE13A_V1",
        "entry_price": entry,
        "take_profit_price": take_profit,
        "stop_loss_price": stop_loss,
        "bounded_price_refresh": True,
        "hindsight_reconstructed": False,
        "proposal_only": True,
        "automatic_apply_allowed": False,
        "decision_authority": False,
        "live_authority": False,
        "wallet_authority": False,
        "execution_authority": False,
    }

def to_outcome_relative_states(
    *,
    outcome_class,
    entry_signal_states,
):
    outcome_class = str(
        outcome_class or "UNKNOWN"
    ).upper()

    if outcome_class == "VALID_SIGNAL":
        positive_relative = (
            "SUPPORTS_OUTCOME"
        )
        negative_relative = (
            "OPPOSES_OUTCOME"
        )
    elif outcome_class == "FALSE_POSITIVE":
        positive_relative = (
            "OPPOSES_OUTCOME"
        )
        negative_relative = (
            "SUPPORTS_OUTCOME"
        )
    else:
        positive_relative = "UNKNOWN"
        negative_relative = "UNKNOWN"

    result = {}

    for family, raw_state in dict(
        entry_signal_states or {}
    ).items():
        state = str(
            raw_state or "UNKNOWN"
        ).upper()

        if state == "POSITIVE":
            relative = positive_relative
        elif state == "NEGATIVE":
            relative = negative_relative
        elif state == "NEUTRAL":
            relative = "NEUTRAL"
        else:
            relative = "UNKNOWN"

        result[str(family)] = relative

    return result
