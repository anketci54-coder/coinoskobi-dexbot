from dataclasses import dataclass
from statistics import median


POLICY_PROVENANCE = "ROBUST_MAD_BOOTSTRAP_V1"


@dataclass(frozen=True)
class SeismicPolicy:
    minimum_baseline: int = 8
    warm_z: float = 3.0
    hot_z: float = 5.0
    liquidity_floor_ratio: float = 0.80

    def __post_init__(self):
        if self.minimum_baseline < 4:
            raise ValueError("minimum baseline must be at least 4")
        if not 0 < self.warm_z < self.hot_z:
            raise ValueError("warm/hot robust-z order required")
        if not 0 < self.liquidity_floor_ratio <= 1:
            raise ValueError("valid liquidity floor ratio required")


def _number(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _series(rows, field):
    return [value for row in rows if (value := _number(row.get(field))) is not None]


def _robust_z(baseline, current):
    if current is None or not baseline:
        return None
    center = median(baseline)
    deviations = [abs(value - center) for value in baseline]
    mad = median(deviations)
    scale = 1.4826 * mad
    if scale <= 0:
        spread = max(baseline) - min(baseline)
        scale = max(spread / 2.0, abs(center) * 0.05, 1e-9)
    return max(-12.0, min(12.0, (current - center) / scale))


class SeismicClassifier:
    """Pool-relative robust anomaly classification; no provider calls."""

    def __init__(self, policy=None):
        self.policy = policy or SeismicPolicy()

    def classify(self, *, chain, dex, pool, market_state, history):
        market_state = str(market_state).upper()
        if market_state not in {"COLD", "WARM", "HOT"}:
            raise ValueError("invalid market state")
        rows = list(history or [])
        current = rows[-1] if rows else {}
        observed_at = str(current.get("observed_at") or "")
        base = {
            "chain": chain, "dex": dex, "pool": pool,
            "observed_at": observed_at, "policy": POLICY_PROVENANCE,
            "previous_state": market_state,
        }
        baseline = rows[:-1]
        if len(baseline) < self.policy.minimum_baseline:
            return {
                **base, "next_state": market_state, "score": 0.0,
                "price_z": None, "volume_z": None, "txns_z": None,
                "liquidity_ratio": None, "evidence_count": 0,
                "reason": "INSUFFICIENT_HISTORY",
            }

        price_now = _number(current.get("change_m5"))
        volume_now = _number(current.get("volume_m5_usd"))
        txns_now = _number(current.get("txns_m5"))
        liquidity_now = _number(current.get("liquidity_usd"))
        price_z = _robust_z(_series(baseline, "change_m5"), price_now)
        volume_z = _robust_z(_series(baseline, "volume_m5_usd"), volume_now)
        txns_z = _robust_z(_series(baseline, "txns_m5"), txns_now)
        liquidity_base = _series(baseline, "liquidity_usd")
        liquidity_ratio = (
            liquidity_now / median(liquidity_base)
            if liquidity_now is not None and liquidity_base
            and median(liquidity_base) > 0 else None
        )
        z_values = [value for value in (price_z, volume_z, txns_z)
                    if value is not None]
        score = sum(max(0.0, value) for value in z_values) / max(1, len(z_values))
        warm_count = sum(value >= self.policy.warm_z for value in z_values)
        hot_count = sum(value >= self.policy.hot_z for value in z_values)
        liquidity_ok = (
            liquidity_ratio is not None
            and liquidity_ratio >= self.policy.liquidity_floor_ratio
        )
        positive_price = price_now is not None and price_now > 0
        warm = warm_count >= 2 and liquidity_ok and positive_price
        hot = hot_count == 3 and liquidity_ok and positive_price

        if hot:
            next_state, reason = "HOT", "ROBUST_MULTI_SIGNAL_HOT"
        elif warm:
            next_state, reason = "WARM", "ROBUST_MULTI_SIGNAL_WARM"
        elif market_state == "HOT":
            next_state, reason = "WARM", "HOT_EVIDENCE_SUBSIDED"
        else:
            next_state, reason = "COLD", "NO_ROBUST_MOVEMENT"

        return {
            **base, "next_state": next_state, "score": round(score, 6),
            "price_z": price_z, "volume_z": volume_z, "txns_z": txns_z,
            "liquidity_ratio": liquidity_ratio,
            "evidence_count": hot_count if hot else warm_count,
            "reason": reason,
        }


__all__ = ["POLICY_PROVENANCE", "SeismicClassifier", "SeismicPolicy"]
