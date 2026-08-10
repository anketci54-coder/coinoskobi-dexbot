from datetime import datetime, timezone

from app.config.scanner import (
    ALLOWED_DEX,
    CACHE_MAX_AGE_MINUTES,
    MAX_POOL_AGE_HOURS,
    MAX_RPC_CANDIDATES,
    MAX_FDV_USD,
    MIN_BUYS_24H,
    MIN_FDV_USD,
    MIN_LIQUIDITY_USD,
    MIN_VOLUME_24H_USD,
)


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


class CacheFilter:

    def _accepted(self, rows):

        accepted = []
        now = datetime.now(timezone.utc)

        for row in rows:

            try:
                dex = row.get("dex")

                liquidity = _as_float(row.get("liquidity"))
                volume_24h = _as_float(
                    row.get("volume_24h", row.get("volume24"))
                )
                buys_24h = _as_int(
                    row.get("buys_24h", row.get("buys24"))
                )
                fdv = _as_float(row.get("fdv"))

                if dex not in ALLOWED_DEX:
                    continue

                if None in (
                    liquidity,
                    volume_24h,
                    buys_24h,
                    fdv,
                ):
                    continue

                # Cache freshness is a data-quality gate.
                updated_at = _parse_datetime(row.get("updated_at"))

                if updated_at is None:
                    continue

                cache_age_minutes = (
                    now - updated_at
                ).total_seconds() / 60

                if cache_age_minutes < 0:
                    cache_age_minutes = 0

                if cache_age_minutes > CACHE_MAX_AGE_MINUTES:
                    continue

                # Pool age is enforced when timestamp is available.
                # Missing/invalid pool age alone does not kill observation.
                created_at = _parse_datetime(row.get("created_at"))

                if created_at is not None:
                    pool_age_hours = (
                        now - created_at
                    ).total_seconds() / 3600

                    if pool_age_hours >= 0:
                        if pool_age_hours > MAX_POOL_AGE_HOURS:
                            continue

                if liquidity < MIN_LIQUIDITY_USD:
                    continue

                if volume_24h < MIN_VOLUME_24H_USD:
                    continue

                if buys_24h < MIN_BUYS_24H:
                    continue

                if fdv < MIN_FDV_USD:
                    continue

                if fdv > MAX_FDV_USD:
                    continue

                normalized = dict(row)
                normalized["liquidity"] = liquidity
                normalized["volume_24h"] = volume_24h
                normalized["buys_24h"] = buys_24h
                normalized["fdv"] = fdv

                accepted.append(normalized)

            except Exception:
                # Tek bozuk satır diğer fırsatları durdurmaz.
                continue

        accepted.sort(
            key=lambda x: (
                x["liquidity"],
                x["volume_24h"],
                x["buys_24h"],
            ),
            reverse=True,
        )

        return accepted

    def filter_all(self, rows):
        return self._accepted(rows)

    def filter(self, rows):
        return self._accepted(rows)[:MAX_RPC_CANDIDATES]
