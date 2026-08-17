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
    health_score: float


def _clamp(value, low, high):
    return max(low, min(high, value))


def _num(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


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
):
    """
    Advisory/deterministic PAPER exit controller.

    Important:
    - Does not execute trades.
    - Does not write DB.
    - Does not weaken the static safety floor.
    - No fixed take-profit exit.
    - Profit protection tightens as evidence/profit improves.
    """

    entry = _num(entry_price)
    current = _num(current_price)
    highest = max(_num(highest_price, current), current)
    static_sl = _num(static_sl_price)

    if entry <= 0 or current <= 0:
        return HybridExitDecision(
            action="EMERGENCY_EXIT",
            reason="INVALID_OR_ZERO_PRICE",
            exit_now=True,
            protect_profit=False,
            runner_active=False,
            protection_price=static_sl if static_sl > 0 else None,
            profit_lock_price=None,
            health_score=0.0,
        )

    roi = (current / entry) - 1.0
    peak_roi = (highest / entry) - 1.0

    sellability_text = str(
        sellability or "SELLABILITY_UNKNOWN"
    ).upper()

    # ---------------------------------------------------------
    # 1. ABSOLUTE SAFETY
    # ---------------------------------------------------------

    if bool(hard_block):
        return HybridExitDecision(
            action="EMERGENCY_EXIT",
            reason="HARD_BLOCK",
            exit_now=True,
            protect_profit=False,
            runner_active=False,
            protection_price=static_sl,
            profit_lock_price=None,
            health_score=0.0,
        )

    if sellability_text in {
        "SELLABILITY_FAIL",
        "SELLABILITY_BLOCK",
        "UNSELLABLE",
    }:
        return HybridExitDecision(
            action="EMERGENCY_EXIT",
            reason="SELLABILITY_BLOCK",
            exit_now=True,
            protect_profit=False,
            runner_active=False,
            protection_price=static_sl,
            profit_lock_price=None,
            health_score=0.0,
        )

    # Static SL remains the last deterministic floor.
    if static_sl > 0 and current <= static_sl:
        return HybridExitDecision(
            action="EXIT",
            reason="STATIC_SAFETY_FLOOR",
            exit_now=True,
            protect_profit=False,
            runner_active=False,
            protection_price=static_sl,
            profit_lock_price=None,
            health_score=0.0,
        )

    # ---------------------------------------------------------
    # 2. NORMALIZED MARKET HEALTH
    # ---------------------------------------------------------

    liquidity = _clamp(
        _num(liquidity_health, 0.50),
        0.0,
        1.0,
    )
    momentum = _clamp(
        _num(flow_momentum, 0.0),
        -1.0,
        1.0,
    )
    acceleration = _clamp(
        _num(flow_acceleration, 0.0),
        -1.0,
        1.0,
    )
    trend = _clamp(
        _num(trend_health, 0.50),
        0.0,
        1.0,
    )
    pressure = _clamp(
        _num(exit_pressure, 0.0),
        0.0,
        1.0,
    )
    impact = _clamp(
        _num(price_impact_health, 0.50),
        0.0,
        1.0,
    )

    momentum01 = (momentum + 1.0) / 2.0
    acceleration01 = (acceleration + 1.0) / 2.0

    health = (
        liquidity * 0.25
        + trend * 0.25
        + momentum01 * 0.20
        + acceleration01 * 0.10
        + impact * 0.10
        + (1.0 - pressure) * 0.10
    )

    health = _clamp(health, 0.0, 1.0)

    # ---------------------------------------------------------
    # 3. DETERIORATION / DOWNSHIFT
    # ---------------------------------------------------------

    severe_deterioration = (
        liquidity <= 0.15
        or pressure >= 0.90
        or (
            momentum <= -0.80
            and acceleration <= -0.60
        )
    )

    if severe_deterioration:
        return HybridExitDecision(
            action="EXIT",
            reason="SEVERE_MARKET_DETERIORATION",
            exit_now=True,
            protect_profit=roi > 0,
            runner_active=False,
            protection_price=max(
                static_sl,
                entry if roi > 0 else static_sl,
            ),
            profit_lock_price=entry if roi > 0 else None,
            health_score=round(health, 4),
        )

    # ---------------------------------------------------------
    # 4. PROFIT LOCK
    #
    # These are not take-profit targets.
    # They define how much of an already achieved move may be
    # surrendered before protection becomes dominant.
    # ---------------------------------------------------------

    profit_lock = None
    protect_profit = False

    if peak_roi >= 0.08:
        protect_profit = True

        # Weak health -> protect aggressively.
        # Strong health -> give the runner more breathing room.
        if health >= 0.80:
            retained_peak_fraction = 0.30
        elif health >= 0.65:
            retained_peak_fraction = 0.45
        elif health >= 0.50:
            retained_peak_fraction = 0.60
        else:
            retained_peak_fraction = 0.75

        locked_roi = max(
            0.0,
            peak_roi * retained_peak_fraction,
        )

        profit_lock = entry * (1.0 + locked_roi)

    # ---------------------------------------------------------
    # 5. DYNAMIC RUNNER PROTECTION
    # ---------------------------------------------------------

    dynamic_protection = static_sl

    if protect_profit and profit_lock is not None:
        dynamic_protection = max(
            dynamic_protection,
            profit_lock,
        )

    # Once a meaningful profit exists, protection can never
    # intentionally move below entry.
    if peak_roi >= 0.12:
        dynamic_protection = max(
            dynamic_protection,
            entry,
        )

    if (
        dynamic_protection > 0
        and current <= dynamic_protection
    ):
        return HybridExitDecision(
            action="EXIT",
            reason="DYNAMIC_PROFIT_PROTECTION",
            exit_now=True,
            protect_profit=protect_profit,
            runner_active=False,
            protection_price=dynamic_protection,
            profit_lock_price=profit_lock,
            health_score=round(health, 4),
        )

    # ---------------------------------------------------------
    # 6. RUNNER / DOWNSHIFT / HOLD
    # ---------------------------------------------------------

    if roi > 0 and health >= 0.70:
        return HybridExitDecision(
            action="RUNNER",
            reason="POSITIVE_EDGE_HEALTHY",
            exit_now=False,
            protect_profit=protect_profit,
            runner_active=True,
            protection_price=dynamic_protection,
            profit_lock_price=profit_lock,
            health_score=round(health, 4),
        )

    if roi > 0 and health < 0.45:
        return HybridExitDecision(
            action="DOWNSHIFT",
            reason="POSITIVE_BUT_EDGE_WEAKENING",
            exit_now=False,
            protect_profit=True,
            runner_active=False,
            protection_price=max(
                dynamic_protection,
                entry,
            ),
            profit_lock_price=profit_lock,
            health_score=round(health, 4),
        )

    return HybridExitDecision(
        action="HOLD",
        reason="NO_EXIT_CONDITION",
        exit_now=False,
        protect_profit=protect_profit,
        runner_active=False,
        protection_price=dynamic_protection,
        profit_lock_price=profit_lock,
        health_score=round(health, 4),
    )
