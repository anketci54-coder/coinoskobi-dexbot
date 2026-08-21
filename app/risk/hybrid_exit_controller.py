import math
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class HybridExitDecision:
    action: str
    reason: str
    exit_now: bool
    protect_profit: bool
    runner_active: bool
    protection_price: Optional[float]
    profit_lock_price: Optional[float]
    health_score: Optional[float]


def _number(v):
    if v is None or isinstance(v, bool):
        return None
    try:
        v = float(v)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def evaluate_hybrid_exit(
    *,
    entry_price,
    current_price,
    highest_price,
    static_sl_price,
    hard_block=False,
    sellability="SELLABILITY_UNKNOWN",
    liquidity_health=None,
    flow_momentum=None,
    flow_acceleration=None,
    trend_health=None,
    exit_pressure=None,
    price_impact_health=None,
    atr_pct=None,
):
    entry = _number(entry_price)
    current = _number(current_price)
    highest = _number(highest_price)
    floor = _number(static_sl_price)

    if entry is None or entry <= 0 or current is None or current <= 0:
        return HybridExitDecision(
            "EMERGENCY_EXIT","INVALID_OR_ZERO_PRICE",True,False,False,
            floor if floor and floor > 0 else None,None,None,
        )

    highest = max(highest if highest is not None else current, current)
    floor = floor if floor is not None and floor > 0 else 0.0
    sell = str(sellability or "SELLABILITY_UNKNOWN").upper()

    if hard_block:
        return HybridExitDecision(
            "EMERGENCY_EXIT","HARD_BLOCK",True,False,False,
            floor or None,None,None,
        )

    if sell in {"SELLABILITY_FAIL","SELLABILITY_BLOCK","UNSELLABLE"}:
        return HybridExitDecision(
            "EMERGENCY_EXIT","SELLABILITY_BLOCK",True,False,False,
            floor or None,None,None,
        )

    if floor > 0 and current <= floor:
        return HybridExitDecision(
            "EXIT","DYNAMIC_PROTECTION_FLOOR",True,highest > entry,False,
            floor,floor if floor > entry else None,None,
        )

    if highest > entry:
        return HybridExitDecision(
            "RUNNER","MATHEMATICAL_FLOOR_RUNNER",False,True,True,
            floor or None,floor if floor > entry else None,None,
        )

    return HybridExitDecision(
        "HOLD","NO_EXIT_CONDITION",False,False,False,
        floor or None,None,None,
    )
