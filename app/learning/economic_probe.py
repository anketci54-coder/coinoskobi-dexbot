import math
import sqlite3

from datetime import datetime, timezone
from pathlib import Path

from app.learning.horizon_quality import (
    HORIZON_CAPTURE_WINDOW_SECONDS,
    ScientificCounterfactualObservationStore as _ScientificStore,
)


PROBE_ENTRY_USDT = 1.0


def _observation_epoch(value):
    if value is None:
        return None

    if isinstance(value, (int, float)):
        result = float(value)
        return result if math.isfinite(result) else None

    text = str(value).strip()
    if not text:
        return None

    try:
        result = float(text)
    except ValueError:
        try:
            normalized = text[:-1] + "+00:00" if text.endswith("Z") else text
            parsed = datetime.fromisoformat(normalized)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            result = parsed.timestamp()
        except (TypeError, ValueError, OverflowError):
            return None

    return result if math.isfinite(result) else None


def economic_capacity_probe_1usdt(
    *,
    entry_price,
    horizon_price,
    liquidity_usd,
):
    """Conservative 1 USDT capacity check.

    This does not claim executable profit without exact reserve/route evidence.
    It only proves a price-only outcome is economically impossible when the
    claimed 1 USDT exit value exceeds observed pool liquidity.
    """
    try:
        entry = float(entry_price)
        horizon = float(horizon_price)
        liquidity = float(liquidity_usd)
    except (TypeError, ValueError):
        return {
            "state": "UNKNOWN",
            "reason": "PROBE_EVIDENCE_MISSING",
            "price_only_exit_usdt": None,
            "liquidity_usd": None,
        }

    if not all(math.isfinite(x) for x in (entry, horizon, liquidity)):
        return {
            "state": "UNKNOWN",
            "reason": "PROBE_EVIDENCE_INVALID",
            "price_only_exit_usdt": None,
            "liquidity_usd": None,
        }

    if entry <= 0 or horizon <= 0 or liquidity <= 0:
        return {
            "state": "UNKNOWN",
            "reason": "PROBE_EVIDENCE_NONPOSITIVE",
            "price_only_exit_usdt": None,
            "liquidity_usd": liquidity if liquidity > 0 else None,
        }

    price_only_exit = PROBE_ENTRY_USDT * horizon / entry

    if price_only_exit > liquidity:
        state = "LIMITED"
        reason = "PRICE_ONLY_EXIT_EXCEEDS_POOL_LIQUIDITY"
    else:
        state = "UNKNOWN"
        reason = "EXACT_RESERVE_ROUTE_EVIDENCE_REQUIRED"

    return {
        "state": state,
        "reason": reason,
        "price_only_exit_usdt": price_only_exit,
        "liquidity_usd": liquidity,
    }


class EconomicProbeCounterfactualObservationStore(_ScientificStore):
    """Phase 13 economic-capacity labels layered onto scientific horizons."""

    def _ensure_durable_schema(self):
        super()._ensure_durable_schema()

        if self._db is None:
            return

        columns = {
            row[1]
            for row in self._db.execute(
                "PRAGMA table_info(counterfactual_observations)"
            ).fetchall()
        }

        additions = {}
        for _, label in self._durable_horizons:
            additions[f"probe_state_{label}"] = "TEXT"
            additions[f"probe_reason_{label}"] = "TEXT"
            additions[f"probe_exit_usdt_{label}"] = "REAL"
            additions[f"probe_liquidity_usd_{label}"] = "REAL"

        for name, column_type in additions.items():
            if name not in columns:
                self._db.execute(
                    "ALTER TABLE counterfactual_observations "
                    f"ADD COLUMN {name} {column_type}"
                )

        self._db.commit()

    def _nearest_liquidity(self, *, pool, now):
        if not self._cache_db_path:
            return None

        path = Path(self._cache_db_path)
        if not path.exists():
            return None

        try:
            db = sqlite3.connect(
                f"file:{path}?mode=ro",
                uri=True,
                timeout=5,
            )
            db.row_factory = sqlite3.Row
            rows = db.execute(
                """
                SELECT observed_at, liquidity_usd
                FROM market_observation_history
                WHERE lower(pool)=lower(?)
                  AND liquidity_usd IS NOT NULL
                """,
                (pool,),
            ).fetchall()
            db.close()
        except sqlite3.Error:
            return None

        target = float(now)
        nearest = None
        nearest_distance = None

        for row in rows:
            observed_at = _observation_epoch(row["observed_at"])
            try:
                liquidity = float(row["liquidity_usd"])
            except (TypeError, ValueError):
                continue

            if (
                observed_at is None
                or not math.isfinite(liquidity)
                or liquidity <= 0
            ):
                continue

            distance = abs(observed_at - target)
            if nearest_distance is None or distance < nearest_distance:
                nearest = liquidity
                nearest_distance = distance

        if (
            nearest is None
            or nearest_distance is None
            or nearest_distance > HORIZON_CAPTURE_WINDOW_SECONDS
        ):
            return None

        return nearest

    def _persist_observe_exact(
        self,
        *,
        token,
        pool,
        current_price,
        evaluated_at,
    ):
        updated = super()._persist_observe_exact(
            token=token,
            pool=pool,
            current_price=current_price,
            evaluated_at=evaluated_at,
        )

        if not updated or self._db is None:
            return updated

        now = float(evaluated_at)
        liquidity = self._nearest_liquidity(
            pool=pool,
            now=now,
        )

        with self._lock:
            rows = self._db.execute(
                """
                SELECT *
                FROM counterfactual_observations
                WHERE lower(token)=lower(?)
                  AND lower(pool)=lower(?)
                ORDER BY id
                """,
                (token, pool),
            ).fetchall()

            changed = 0
            for row in rows:
                entry = row["entry_price"]
                values = {}

                for _, label in self._durable_horizons:
                    observed_key = f"observed_{label}_at"
                    state_key = f"probe_state_{label}"
                    price_key = f"price_{label}"

                    observed = row[observed_key]
                    if observed is None or row[state_key] is not None:
                        continue

                    try:
                        captured_now = math.isclose(
                            float(observed),
                            now,
                            rel_tol=0.0,
                            abs_tol=1e-6,
                        )
                    except (TypeError, ValueError):
                        captured_now = False

                    if not captured_now:
                        continue

                    probe = economic_capacity_probe_1usdt(
                        entry_price=entry,
                        horizon_price=row[price_key],
                        liquidity_usd=liquidity,
                    )

                    values[state_key] = probe["state"]
                    values[f"probe_reason_{label}"] = probe["reason"]
                    values[f"probe_exit_usdt_{label}"] = probe[
                        "price_only_exit_usdt"
                    ]
                    values[f"probe_liquidity_usd_{label}"] = probe[
                        "liquidity_usd"
                    ]

                if not values:
                    continue

                sql = (
                    "UPDATE counterfactual_observations SET "
                    + ", ".join(f"{key}=?" for key in values)
                    + " WHERE id=?"
                )
                self._db.execute(
                    sql,
                    tuple(values.values()) + (int(row["id"]),),
                )
                changed += 1

            if changed:
                self._db.commit()

        return updated

    def training_quality_snapshot(self):
        base = dict(super().training_quality_snapshot())

        if self._db is None:
            return base

        limited = {}
        unknown = {}

        with self._lock:
            for _, label in self._durable_horizons:
                limited[label] = int(
                    self._db.execute(
                        f"""
                        SELECT COUNT(*)
                        FROM counterfactual_observations
                        WHERE probe_state_{label}='LIMITED'
                        """
                    ).fetchone()[0]
                )
                unknown[label] = int(
                    self._db.execute(
                        f"""
                        SELECT COUNT(*)
                        FROM counterfactual_observations
                        WHERE probe_state_{label}='UNKNOWN'
                        """
                    ).fetchone()[0]
                )

        base.update({
            "economic_probe_amount_usdt": PROBE_ENTRY_USDT,
            "economic_probe_policy": (
                "LIMIT_IF_PRICE_ONLY_EXIT_EXCEEDS_OBSERVED_LIQUIDITY"
            ),
            "economic_probe_limited_counts": limited,
            "economic_probe_unknown_counts": unknown,
            "economic_probe_verified_without_reserves": False,
            "training_authority": False,
            "paper_authority": False,
            "live_authority": False,
            "wallet_authority": False,
            "execution_authority": False,
        })
        return base
