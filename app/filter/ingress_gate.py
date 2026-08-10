from datetime import datetime, timezone

from app.config.scanner import (
    ALLOWED_DEX,
    CACHE_MAX_AGE_MINUTES,
    MAX_FDV_USD,
    MAX_POOL_AGE_HOURS,
    MIN_BUYS_24H,
    MIN_FDV_USD,
    MIN_LIQUIDITY_USD,
    MIN_VOLUME_24H_USD,
)


LANE_DROP = "DROP"
LANE_DEFER = "DEFER"
LANE_ACTIVE = "ACTIVE"


def _as_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _parse_datetime(value):
    if not value:
        return None

    if isinstance(value, datetime):
        parsed = value
    else:
        value = str(value).strip()

        if value.endswith("Z"):
            value = value[:-1] + "+00:00"

        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)

    return parsed.astimezone(timezone.utc)


class IngressGate:
    """
    Cheap pre-queue eligibility gate.

    DROP:
        Malformed / unsupported / stale candidate.
        No deep-analysis budget this cycle.

    DEFER:
        Structurally valid but current market quality is below
        active admission thresholds.
        Row remains in cache and may qualify next cycle.

    ACTIVE:
        Eligible for CandidateAdmissionQueue.

    No RPC.
    No HTTP.
    No AI.
    No trade authority.
    """

    def classify(self, row, now=None):
        if now is None:
            now = datetime.now(timezone.utc)

        token = row.get("token")

        if not token:
            return {
                "lane": LANE_DROP,
                "reason": "MISSING_TOKEN",
                "row": None,
            }

        dex = row.get("dex")

        if dex not in ALLOWED_DEX:
            return {
                "lane": LANE_DROP,
                "reason": "UNSUPPORTED_DEX",
                "row": None,
            }

        liquidity = _as_float(
            row.get("liquidity")
        )

        volume_24h = _as_float(
            row.get(
                "volume_24h",
                row.get("volume24"),
            )
        )

        buys_24h = _as_int(
            row.get(
                "buys_24h",
                row.get("buys24"),
            )
        )

        fdv = _as_float(
            row.get("fdv")
        )

        if None in (
            liquidity,
            volume_24h,
            buys_24h,
            fdv,
        ):
            return {
                "lane": LANE_DROP,
                "reason": "INVALID_MARKET_DATA",
                "row": None,
            }

        updated_at = _parse_datetime(
            row.get("updated_at")
        )

        if updated_at is None:
            return {
                "lane": LANE_DROP,
                "reason": "INVALID_CACHE_TIMESTAMP",
                "row": None,
            }

        cache_age_minutes = (
            now - updated_at
        ).total_seconds() / 60

        if cache_age_minutes < 0:
            cache_age_minutes = 0

        if cache_age_minutes > CACHE_MAX_AGE_MINUTES:
            return {
                "lane": LANE_DROP,
                "reason": "STALE_CACHE",
                "row": None,
            }

        created_at = _parse_datetime(
            row.get("created_at")
        )

        if created_at is not None:
            pool_age_hours = (
                now - created_at
            ).total_seconds() / 3600

            if (
                pool_age_hours >= 0
                and pool_age_hours > MAX_POOL_AGE_HOURS
            ):
                return {
                    "lane": LANE_DROP,
                    "reason": "POOL_OUT_OF_SCOPE",
                    "row": None,
                }

        normalized = dict(row)

        normalized["liquidity"] = liquidity
        normalized["volume_24h"] = volume_24h
        normalized["buys_24h"] = buys_24h
        normalized["fdv"] = fdv

        defer_reasons = []

        if liquidity < MIN_LIQUIDITY_USD:
            defer_reasons.append(
                "LOW_LIQUIDITY"
            )

        if volume_24h < MIN_VOLUME_24H_USD:
            defer_reasons.append(
                "LOW_VOLUME"
            )

        if buys_24h < MIN_BUYS_24H:
            defer_reasons.append(
                "LOW_BUYS"
            )

        if fdv < MIN_FDV_USD:
            defer_reasons.append(
                "FDV_TOO_LOW"
            )

        if fdv > MAX_FDV_USD:
            defer_reasons.append(
                "FDV_TOO_HIGH"
            )

        if defer_reasons:
            return {
                "lane": LANE_DEFER,
                "reason": ",".join(
                    defer_reasons
                ),
                "row": normalized,
            }

        return {
            "lane": LANE_ACTIVE,
            "reason": "ELIGIBLE",
            "row": normalized,
        }

    def classify_many(self, rows):
        now = datetime.now(timezone.utc)

        active = []
        deferred = []
        dropped = []

        reason_counts = {}

        for row in rows:
            try:
                result = self.classify(
                    row,
                    now=now,
                )
            except Exception:
                result = {
                    "lane": LANE_DROP,
                    "reason": "INGRESS_EXCEPTION",
                    "row": None,
                }

            lane = result["lane"]
            reason = result["reason"]

            reason_counts[reason] = (
                reason_counts.get(reason, 0)
                + 1
            )

            if lane == LANE_ACTIVE:
                active.append(
                    result["row"]
                )

            elif lane == LANE_DEFER:
                deferred.append(
                    result["row"]
                )

            else:
                dropped.append(row)

        return {
            "active": active,
            "deferred": deferred,
            "dropped": dropped,
            "stats": {
                "input": len(rows),
                "active": len(active),
                "deferred": len(deferred),
                "dropped": len(dropped),
                "reasons": reason_counts,
            },
        }
