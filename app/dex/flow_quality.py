def evaluate_flow_quality(
    unique_wallets,
    tx_count,
    largest_actor_share,
):
    if unique_wallets is None or tx_count is None or largest_actor_share is None:
        state = "UNKNOWN"
    elif tx_count <= 1 or largest_actor_share >= 0.80:
        state = "SINGLE_ACTOR_SPIKE"
    elif unique_wallets >= 5 and tx_count >= 8 and largest_actor_share <= 0.50:
        state = "MULTI_ACTOR"
    elif unique_wallets >= 2 and tx_count >= 3:
        state = "LIMITED_PARTICIPATION"
    else:
        state = "WEAK"

    return {
        "flow_quality": state,
        "decision_authority": False,
        "execution_authority": False,
    }
