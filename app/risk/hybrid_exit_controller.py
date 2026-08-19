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


def _adaptive_runner_distance(*, health, momentum, acceleration, pressure, atr_pct=None):
    """Return a bounded market-measured peak-following distance."""
    measured_atr = _num(atr_pct, 0.0)
    if measured_atr > 0:
        atr = _clamp(measured_atr, 0.005, 0.30)
        trend_room = 1.15 + (health * 1.35)
        pressure_tightening = 1.0 - (pressure * 0.35)
        distance = atr * trend_room * pressure_tightening
    else:
        distance = 0.035 + (health * 0.085)
        distance += max(0.0, momentum) * 0.020
        distance += max(0.0, acceleration) * 0.015
        distance -= pressure * 0.025
    return _clamp(distance, 0.025, 0.22)


def evaluate_hybrid_exit(
    *, entry_price, current_price, highest_price, static_sl_price,
    hard_block=False, sellability="SELLABILITY_UNKNOWN",
    liquidity_health=None, flow_momentum=None, flow_acceleration=None,
    trend_health=None, exit_pressure=None, price_impact_health=None,
    atr_pct=None,
):
    """Deterministic PAPER exit controller with adaptive, monotonic protection.

    There are no fixed profit milestones or take-profit percentages. The
    protection distance is continuously derived from measured volatility and
    market health. Optional intelligence may improve that estimate, but the
    persisted floor is authoritative and can never move down.
    """
    entry = _num(entry_price)
    current = _num(current_price)
    highest = max(_num(highest_price, current), current)
    current_floor = _num(static_sl_price)

    if entry <= 0 or current <= 0:
        return HybridExitDecision("EMERGENCY_EXIT", "INVALID_OR_ZERO_PRICE", True, False, False, current_floor if current_floor > 0 else None, None, 0.0)

    roi = (current / entry) - 1.0
    peak_roi = (highest / entry) - 1.0
    sellability_text = str(sellability or "SELLABILITY_UNKNOWN").upper()

    if bool(hard_block):
        return HybridExitDecision("EMERGENCY_EXIT", "HARD_BLOCK", True, False, False, current_floor or None, None, 0.0)
    if sellability_text in {"SELLABILITY_FAIL", "SELLABILITY_BLOCK", "UNSELLABLE"}:
        return HybridExitDecision("EMERGENCY_EXIT", "SELLABILITY_BLOCK", True, False, False, current_floor or None, None, 0.0)

    if current_floor > 0 and current <= current_floor:
        return HybridExitDecision("EXIT", "DYNAMIC_PROTECTION_FLOOR", True, peak_roi > 0, False, current_floor, None, 0.0)

    liquidity = _clamp(_num(liquidity_health, 0.50), 0.0, 1.0)
    momentum = _clamp(_num(flow_momentum, 0.0), -1.0, 1.0)
    acceleration = _clamp(_num(flow_acceleration, 0.0), -1.0, 1.0)
    trend = _clamp(_num(trend_health, 0.50), 0.0, 1.0)
    pressure = _clamp(_num(exit_pressure, 0.0), 0.0, 1.0)
    impact = _clamp(_num(price_impact_health, 0.50), 0.0, 1.0)
    momentum01 = (momentum + 1.0) / 2.0
    acceleration01 = (acceleration + 1.0) / 2.0
    health = _clamp(
        liquidity * 0.25 + trend * 0.25 + momentum01 * 0.20
        + acceleration01 * 0.10 + impact * 0.10 + (1.0 - pressure) * 0.10,
        0.0, 1.0,
    )

    severe_deterioration = liquidity <= 0.15 or pressure >= 0.90 or (momentum <= -0.80 and acceleration <= -0.60)
    if severe_deterioration:
        protection = max(current_floor, entry if roi > 0 else current_floor)
        return HybridExitDecision("EXIT", "SEVERE_MARKET_DETERIORATION", True, roi > 0, False, protection or None, entry if roi > 0 else None, round(health, 4))

    protect_profit = peak_roi > 0
    profit_lock = None
    dynamic_protection = current_floor

    # Continuous adaptive protection: every positive excursion is evaluated.
    # No 8/12/20% milestones. The market determines breathing room from ATR
    # when available and otherwise from bounded health/momentum/pressure.
    if peak_roi > 0:
        runner_distance = _adaptive_runner_distance(
            health=health, momentum=momentum, acceleration=acceleration,
            pressure=pressure, atr_pct=atr_pct,
        )
        peak_floor = highest * (1.0 - runner_distance)
        dynamic_protection = max(dynamic_protection, peak_floor)
        if peak_floor > entry:
            profit_lock = peak_floor

    if dynamic_protection > 0 and current <= dynamic_protection:
        return HybridExitDecision("EXIT", "DYNAMIC_PROFIT_PROTECTION", True, protect_profit, False, dynamic_protection, profit_lock, round(health, 4))

    if roi > 0 and health >= 0.70:
        return HybridExitDecision("RUNNER", "POSITIVE_EDGE_HEALTHY", False, protect_profit, True, dynamic_protection or None, profit_lock, round(health, 4))

    if roi > 0 and health < 0.45:
        # Weakening positive edge may tighten to break-even, but never lower
        # an already stronger persisted/adaptive floor.
        dynamic_protection = max(dynamic_protection, entry)
        return HybridExitDecision("DOWNSHIFT", "POSITIVE_BUT_EDGE_WEAKENING", False, True, False, dynamic_protection, profit_lock, round(health, 4))

    return HybridExitDecision("HOLD", "NO_EXIT_CONDITION", False, protect_profit, False, dynamic_protection or None, profit_lock, round(health, 4))
