from collections import Counter


def analyze_wallet_flow(
    wallet_events,
):
    """
    wallet_events:
    [
        {
            "wallet": "...",
            "notional_usd": 123.0,
            "is_new_wallet": False,
        }
    ]

    Address activity is evidence only.
    It is NOT identity or whale authority.
    """

    wallet_events = wallet_events or []

    contribution = Counter()
    tx_count = Counter()
    new_wallets = set()

    total_notional = 0.0

    for event in wallet_events:
        wallet = str(
            event.get("wallet") or ""
        ).strip().lower()

        if not wallet:
            continue

        try:
            notional = float(
                event.get("notional_usd") or 0
            )
        except (TypeError, ValueError):
            notional = 0.0

        if notional < 0:
            notional = 0.0

        contribution[wallet] += notional
        tx_count[wallet] += 1
        total_notional += notional

        if event.get("is_new_wallet") is True:
            new_wallets.add(wallet)

    unique_wallets = len(contribution)
    total_transactions = sum(tx_count.values())

    top_wallet_notional = (
        max(contribution.values())
        if contribution
        else 0.0
    )

    top_wallet_share = (
        top_wallet_notional / total_notional
        if total_notional > 0
        else 0.0
    )

    repeated_transactions = sum(
        count - 1
        for count in tx_count.values()
        if count > 1
    )

    repeat_ratio = (
        repeated_transactions
        / total_transactions
        if total_transactions > 0
        else 0.0
    )

    new_wallet_ratio = (
        len(new_wallets) / unique_wallets
        if unique_wallets > 0
        else 0.0
    )

    if unique_wallets == 0:
        state = "NO_DATA"

    elif (
        top_wallet_share >= 0.70
        or repeat_ratio >= 0.70
    ):
        state = "HIGHLY_CONCENTRATED"

    elif (
        top_wallet_share >= 0.45
        or repeat_ratio >= 0.45
    ):
        state = "CONCENTRATED"

    else:
        state = "DIVERSE"

    return {
        "unique_wallets": unique_wallets,
        "total_transactions": total_transactions,
        "total_notional_usd": total_notional,
        "top_wallet_share": top_wallet_share,
        "repeat_ratio": repeat_ratio,
        "new_wallet_count": len(new_wallets),
        "new_wallet_ratio": new_wallet_ratio,
        "concentration_state": state,
        "identity_authority": False,
        "whale_authority": False,
        "decision_authority": False,
        "paper_authority": False,
        "live_authority": False,
        "wallet_authority": False,
        "execution_authority": False,
    }
