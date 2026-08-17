PAPER_CAPITAL_USDT = 10_000.0
MAX_POSITION_PCT = 0.10
MAX_RISK_PCT = 0.01
UNKNOWN_SELLABILITY_FACTOR = 0.50


def calculate_paper_position_size(
    *,
    score,
    confidence,
    hard_block,
    sellability,
    available_capital_usdt,
    sl_distance_pct=0.10,
):
    available = max(0.0, float(available_capital_usdt or 0))

    result = {
        "entry_amount_usdt": 0.0,
        "risk_amount_usdt": 0.0,
        "position_size_pct": 0.0,
        "capital_before_usdt": available,
        "capital_after_entry_usdt": available,
        "sizing_reason": None,
    }

    if hard_block:
        result["sizing_reason"] = "HARD_BLOCK"
        return result

    if sellability in {
        "SELLABILITY_FAIL",
        "SELLABILITY_BLOCK",
    }:
        result["sizing_reason"] = "SELLABILITY_BLOCK"
        return result

    if available <= 0:
        result["sizing_reason"] = "NO_AVAILABLE_CAPITAL"
        return result

    score = max(0.0, min(100.0, float(score or 0)))
    confidence = max(0.0, min(100.0, float(confidence or 0)))

    # Deterministic quality factor.
    quality = (score / 100.0) * (confidence / 100.0)

    # Maximum 10% of total paper capital.
    capital_cap = min(
        available,
        PAPER_CAPITAL_USDT * MAX_POSITION_PCT,
    )

    # Maximum 1% account risk based on SL distance.
    sl_distance = max(0.0001, float(sl_distance_pct))
    risk_budget = PAPER_CAPITAL_USDT * MAX_RISK_PCT
    risk_position_cap = risk_budget / sl_distance

    base = min(capital_cap, risk_position_cap)
    amount = base * quality

    if sellability in {
        None,
        "",
        "SELLABILITY_UNKNOWN",
        "SELLABILITY_SKIPPED",
    }:
        amount *= UNKNOWN_SELLABILITY_FACTOR
        reason = "QUALITY_WEIGHTED_UNKNOWN_SELLABILITY_CAP"
    else:
        reason = "QUALITY_WEIGHTED"

    amount = max(0.0, min(amount, available))

    risk = amount * sl_distance

    result.update({
        "entry_amount_usdt": round(amount, 2),
        "risk_amount_usdt": round(risk, 2),
        "position_size_pct": round(
            (amount / PAPER_CAPITAL_USDT) * 100.0,
            4,
        ),
        "capital_after_entry_usdt": round(
            available - amount,
            2,
        ),
        "sizing_reason": reason,
    })

    return result
