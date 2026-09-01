from app.dex.whale_flow import analyze_whale_flow


def analyze_successful_whale_flow(
    wallet_rows,
    *,
    total_market_value,
    freshness="FRESH",
):
    """Compose SUCCESSFUL wallet reputation with explicit whale evidence.

    A wallet is included only when both independent conditions are present:
    a SUCCESSFUL realized-outcome reputation and caller-supplied whale
    evidence. This module never infers whale status from reputation alone.
    """
    if freshness != "FRESH":
        return _out("UNKNOWN", [], None, 0, 0.0, 0.0)

    eligible = []

    for row in wallet_rows or []:
        row = dict(row or {})
        performance = dict(row.get("performance") or {})

        if performance.get("state") != "SUCCESSFUL":
            continue

        if row.get("is_whale_evidence") is not True:
            continue

        value = _num(row.get("value_usd"))
        inflow = _num(row.get("inflow_usd"))
        outflow = _num(row.get("outflow_usd"))

        if value <= 0:
            continue

        eligible.append(
            {
                "wallet_id": str(row.get("wallet_id") or "").strip().lower() or None,
                "value_usd": value,
                "inflow_usd": inflow,
                "outflow_usd": outflow,
            }
        )

    if not eligible:
        return _out("NO_SUCCESSFUL_WHALE_EVIDENCE", [], None, 0, 0.0, 0.0)

    largest = max(row["value_usd"] for row in eligible)
    inflow = sum(row["inflow_usd"] for row in eligible)
    outflow = sum(row["outflow_usd"] for row in eligible)

    base = analyze_whale_flow(
        total_value=total_market_value,
        largest_wallet_value=largest,
        whale_inflow=inflow,
        whale_outflow=outflow,
        unique_whales=len(eligible),
        freshness=freshness,
    )

    return {
        **base,
        "successful_whale_count": len(eligible),
        "successful_whale_inflow_usd": inflow,
        "successful_whale_outflow_usd": outflow,
        "successful_whale_wallets": [
            row["wallet_id"] for row in eligible if row["wallet_id"]
        ],
        "reputation_required": "SUCCESSFUL_REALIZED_ONLY",
        "explicit_whale_evidence_required": True,
        "paper_authority": False,
        "live_authority": False,
        "wallet_authority": False,
        "signing_authority": False,
    }


def _num(value):
    try:
        return max(0.0, float(value))
    except (TypeError, ValueError):
        return 0.0


def _out(state, tags, share, count, inflow, outflow):
    return {
        "state": state,
        "tags": list(tags),
        "largest_wallet_share": share,
        "successful_whale_count": count,
        "successful_whale_inflow_usd": inflow,
        "successful_whale_outflow_usd": outflow,
        "successful_whale_wallets": [],
        "reputation_required": "SUCCESSFUL_REALIZED_ONLY",
        "explicit_whale_evidence_required": True,
        "trade_signal": False,
        "decision_authority": False,
        "paper_authority": False,
        "live_authority": False,
        "wallet_authority": False,
        "signing_authority": False,
        "execution_authority": False,
    }
