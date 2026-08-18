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


def _adaptive_runner_distance(
    *,
    health,
    momentum,
    acceleration,
    pressure,
    atr_pct=None,
):
    """Return a dynamic peak-following distance.

    When a measured ATR percentage is available it is the volatility
    anchor. Otherwise market health supplies a conservative bounded
    distance; this fallback is not presented as ATR.
    """
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
    """Deterministic PAPER exit/runner controller.

    ``static_sl_price`` is retained as an input name for compatibility,
    but it is treated only as the already-established protection floor.
    The controller has no fixed take-profit authority and never lowers
    that floor. A measured ATR can drive the runner distance when the
    runtime supplies one.
    """
    entry = _num(entry_price)
    current = _num(current_price)
    highest = max(_num(highest_price, current), current)
    current_floor = _num(static_sl_price)

    if entry <= 0 or current <= 0:
        return HybridExitDecision(
            action="EMERGENCY_EXIT",
            reason="INVALID_OR_ZERO_PRICE",
            exit_now=True,
            protect_profit=False,
            runner_active=False,
            protection_price=current_floor if current_floor > 0 else None,
            profit_lock_price=None,
            health_score=0.0,
        )

    roi = (current / entry) - 1.0
    peak_roi = (highest / entry) - 1.0
    sellability_text = str(
        sellability or "SELLABILITY_UNKNOWN"
    ).upper()

    if bool(hard_block):
        return HybridExitDecision(
            action="EMERGENCY_EXIT",
            reason="HARD_BLOCK",
            exit_now=True,
            protect_profit=False,
            runner_active=False,
            protection_price=current_floor or None,
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
            protection_price=current_floor or None,
            profit_lock_price=None,
            health_score=0.0,
        )

    # The persisted protection floor is authoritative for downside
    # protection, regardless of whether it originated at entry or was
    # raised by the runner. It is never weakened here.
    if current_floor > 0 and current <= current_floor:
        return HybridExitDecision(
            action="EXIT",
            reason="DYNAMIC_PROTECTION_FLOOR",
            exit_now=True,
            protect_profit=peak_roi > 0,
            runner_active=False,
            protection_price=current_floor,
            profit_lock_price=None,
            health_score=0.0,
        )

    liquidity = _clamp(_num(liquidity_health, 0.50), 0.0, 1.0)
    momentum = _clamp(_num(flow_momentum, 0.0), -1.0, 1.0)
    acceleration = _clamp(_num(flow_acceleration, 0.0), -1.0, 1.0)
    trend = _clamp(_num(trend_health, 0.50), 0.0, 1.0)
    pressure = _clamp(_num(exit_pressure, 0.0), 0.0, 1.0)
    impact = _clamp(_num(price_impact_health, 0.50), 0.0, 1.0)

    momentum01 = (momentum + 1.0) / 2.0
    acceleration01 = (acceleration + 1.0) / 2.0
    health = _clamp(
        liquidity * 0.25
        + trend * 0.25
        + momentum01 * 0.20
        + acceleration01 * 0.10
        + impact * 0.10
        + (1.0 - pressure) * 0.10,
        0.0,
        1.0,
    )

    severe_deterioration = (
        liquidity <= 0.15
        or pressure >= 0.90
        or (momentum <= -0.80 and acceleration <= -0.60)
    )

    if severe_deterioration:
        protection = max(
            current_floor,
            entry if roi > 0 else current_floor,
        )
        return HybridExitDecision(
            action="EXIT",
            reason="SEVERE_MARKET_DETERIORATION",
            exit_now=True,
            protect_profit=roi > 0,
            runner_active=False,
            protection_price=protection or None,
            profit_lock_price=entry if roi > 0 else None,
            health_score=round(health, 4),
        )

    protect_profit = peak_roi > 0
    profit_lock = None
    dynamic_protection = current_floor

    if peak_roi >= 0.08:
        # Profit milestones tighten protection; they are not automatic
        # sell targets. Strong health deliberately leaves more room.
        if health >= 0.80:
            retained_peak_fraction = 0.30
        elif health >= 0.65:
            retained_peak_fraction = 0.45
        elif health >= 0.50:
            retained_peak_fraction = 0.60
        else:
            retained_peak_fraction = 0.75

        locked_roi = max(0.0, peak_roi * retained_peak_fraction)
        profit_lock = entry * (1.0 + locked_roi)
        dynamic_protection = max(dynamic_protection, profit_lock)

    if peak_roi >= 0.12:
        dynamic_protection = max(dynamic_protection, entry)

    # TP3/runner behaviour: follow the peak using measured ATR when
    # supplied. The resulting floor can only move upward.
    if peak_roi >= 0.20:
        runner_distance = _adaptive_runner_distance(
            health=health,
            momentum=momentum,
            acceleration=acceleration,
            pressure=pressure,
            atr_pct=atr_pct,
        )
        peak_floor = highest * (1.0 - runner_distance)
        dynamic_protection = max(dynamic_protection, peak_floor)

    if dynamic_protection > 0 and current <= dynamic_protection:
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

    if roi > 0 and health >= 0.70:
        return HybridExitDecision(
            action="RUNNER",
            reason="POSITIVE_EDGE_HEALTHY",
            exit_now=False,
            protect_profit=protect_profit,
            runner_active=True,
            protection_price=dynamic_protection or None,
            profit_lock_price=profit_lock,
            health_score=round(health, 4),
        )

    if roi > 0 and health < 0.45:
        dynamic_protection = max(dynamic_protection, entry)
        return HybridExitDecision(
            action="DOWNSHIFT",
            reason="POSITIVE_BUT_EDGE_WEAKENING",
            exit_now=False,
            protect_profit=True,
            runner_active=False,
            protection_price=dynamic_protection,
            profit_lock_price=profit_lock,
            health_score=round(health, 4),
        )

    return HybridExitDecision(
        action="HOLD",
        reason="NO_EXIT_CONDITION",
        exit_now=False,
        protect_profit=protect_profit,
        runner_active=False,
        protection_price=dynamic_protection or None,
        profit_lock_price=profit_lock,
        health_score=round(health, 4),
    )
