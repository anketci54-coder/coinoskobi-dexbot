OUTCOME_CLASSES = {
    "VALID_SIGNAL",
    "FALSE_POSITIVE",
    "FALSE_NEGATIVE",
    "EXPECTED_LOSS",
    "AVOIDED_LOSS",
    "MISSED_OPPORTUNITY",
    "EXIT_FAILURE",
    "UNKNOWN",
}


def classify_outcome(
    signal_state,
    candidate_action,
    realized_direction=None,
    realized_return=None,
    exit_failed=False,
    evidence_complete=True,
    freshness="FRESH",
):
    if freshness != "FRESH" or not evidence_complete:
        return _out("UNKNOWN")

    signal = (signal_state or "").upper()
    action = (candidate_action or "").upper()
    direction = (realized_direction or "").upper()

    ret = _num_or_none(realized_return)

    if exit_failed:
        state = "EXIT_FAILURE"

    elif signal == "POSITIVE" and action in {
        "ALLOW",
        "NO_BLOCK",
        "NO_ADVERSARY_BLOCK",
    }:
        if direction == "UP" or (ret is not None and ret > 0):
            state = "VALID_SIGNAL"
        elif direction == "DOWN" or (ret is not None and ret < 0):
            state = "FALSE_POSITIVE"
        else:
            state = "UNKNOWN"

    elif signal == "NEGATIVE" and action in {
        "BLOCK",
        "BLOCK_CANDIDATE",
        "DOWNGRADE",
        "DOWNGRADE_CANDIDATE",
        "SAFE_DOWNGRADE",
    }:
        if direction == "DOWN" or (ret is not None and ret < 0):
            state = "AVOIDED_LOSS"
        elif direction == "UP" or (ret is not None and ret > 0):
            state = "FALSE_NEGATIVE"
        else:
            state = "UNKNOWN"

    elif signal == "POSITIVE" and action in {
        "BLOCK",
        "BLOCK_CANDIDATE",
        "DOWNGRADE",
        "DOWNGRADE_CANDIDATE",
        "SAFE_DOWNGRADE",
    }:
        if direction == "UP" or (ret is not None and ret > 0):
            state = "MISSED_OPPORTUNITY"
        elif direction == "DOWN" or (ret is not None and ret < 0):
            state = "EXPECTED_LOSS"
        else:
            state = "UNKNOWN"

    elif signal == "NEGATIVE" and action in {
        "ALLOW",
        "NO_BLOCK",
        "NO_ADVERSARY_BLOCK",
    }:
        if direction == "DOWN" or (ret is not None and ret < 0):
            state = "EXPECTED_LOSS"
        elif direction == "UP" or (ret is not None and ret > 0):
            state = "FALSE_NEGATIVE"
        else:
            state = "UNKNOWN"

    else:
        state = "UNKNOWN"

    return _out(state)


def _out(state):
    return {
        "outcome_class": state,
        "valid_class": state in OUTCOME_CLASSES,
        "hindsight_rewrite_allowed": False,
        "trade_permission": False,
        "decision_authority": False,
        "paper_authority": False,
        "live_authority": False,
        "wallet_authority": False,
        "execution_authority": False,
    }


def _num_or_none(value):
    if value is None:
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None
