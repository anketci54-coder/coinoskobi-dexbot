import time

from app.learning.horizon_integrity import (
    IntegrityCounterfactualObservationStore,
)


# Canonical paper scanner cadence is 300 seconds. A horizon price is accepted
# only inside the immediately following scan window. Anything later is an
# explicit data gap, never a fabricated 5m/15m/30m/60m/6h/24h label.
HORIZON_CAPTURE_WINDOW_SECONDS = 300


class ScientificCounterfactualObservationStore(
    IntegrityCounterfactualObservationStore
):
    """Scientific label-quality guard for durable counterfactual outcomes."""

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
            additions[f"quality_{label}"] = "TEXT"
            additions[f"delay_{label}"] = "REAL"

        for name, column_type in additions.items():
            if name not in columns:
                self._db.execute(
                    "ALTER TABLE counterfactual_observations "
                    f"ADD COLUMN {name} {column_type}"
                )

        self._db.commit()

    def _persist_observe_exact(
        self,
        *,
        token,
        pool,
        current_price,
        evaluated_at,
    ):
        if self._db is None:
            return 0

        token = self._canonical(token)
        pool = self._canonical(pool)
        now = float(evaluated_at)
        price = float(current_price)
        updated = 0

        with self._lock:
            rows = self._db.execute(
                """
                SELECT *
                FROM counterfactual_observations
                WHERE lower(token)=lower(?)
                  AND lower(pool)=lower(?)
                  AND completed_at IS NULL
                ORDER BY id
                """,
                (token, pool),
            ).fetchall()

            for row in rows:
                entry = float(row["entry_price"])
                age = max(
                    0.0,
                    now - float(row["observed_at"]),
                )

                maximum = max(
                    price,
                    float(row["max_price"])
                    if row["max_price"] is not None
                    else price,
                )
                minimum = min(
                    price,
                    float(row["min_price"])
                    if row["min_price"] is not None
                    else price,
                )

                values = {
                    "last_observed_at": now,
                    "last_price": price,
                    "max_price": maximum,
                    "min_price": minimum,
                }

                for seconds, label in self._durable_horizons:
                    price_key = f"price_{label}"
                    quality_key = f"quality_{label}"
                    delay_key = f"delay_{label}"

                    if (
                        row[price_key] is not None
                        or row[quality_key] is not None
                        or age < seconds
                    ):
                        continue

                    delay = max(0.0, age - seconds)
                    values[delay_key] = delay

                    if delay <= HORIZON_CAPTURE_WINDOW_SECONDS:
                        values[price_key] = price
                        values[f"return_{label}"] = (
                            price / entry - 1.0
                        )
                        values[f"observed_{label}_at"] = now
                        values[f"mfe_{label}"] = (
                            maximum / entry - 1.0
                        )
                        values[f"mae_{label}"] = (
                            minimum / entry - 1.0
                        )
                        values[quality_key] = "VALID"
                    else:
                        values[quality_key] = "INTERNAL_GAP"

                if (
                    row["first_2x_at"] is None
                    and maximum >= entry * 2.0
                ):
                    values["first_2x_at"] = now

                if (
                    row["first_5x_at"] is None
                    and maximum >= entry * 5.0
                ):
                    values["first_5x_at"] = now

                if (
                    row["first_10x_at"] is None
                    and maximum >= entry * 10.0
                ):
                    values["first_10x_at"] = now

                if (
                    row["first_50pct_loss_at"] is None
                    and minimum <= entry * 0.5
                ):
                    values["first_50pct_loss_at"] = now

                if (
                    row["first_90pct_loss_at"] is None
                    and minimum <= entry * 0.1
                ):
                    values["first_90pct_loss_at"] = now

                quality_24h = (
                    values.get("quality_24h")
                    or row["quality_24h"]
                )

                if (
                    row["price_24h"] is not None
                    or "price_24h" in values
                    or quality_24h == "INTERNAL_GAP"
                ):
                    values["completed_at"] = now

                sql = (
                    "UPDATE counterfactual_observations SET "
                    + ", ".join(
                        f"{column}=?"
                        for column in values
                    )
                    + " WHERE id=?"
                )

                self._db.execute(
                    sql,
                    tuple(values.values())
                    + (int(row["id"]),),
                )
                updated += 1

            if updated:
                self._db.commit()

        return updated

    def pending_pool_snapshot(
        self,
        *,
        max_entries=120,
        now=None,
    ):
        if self._db is None:
            return {}

        limit = max(1, int(max_entries))
        now = float(time.time() if now is None else now)

        with self._lock:
            rows = self._db.execute(
                """
                WITH grouped AS (
                    SELECT
                        lower(token) AS token,
                        lower(pool) AS pool,
                        MIN(
                            CASE
                                WHEN price_5m IS NULL
                                     AND quality_5m IS NULL
                                    THEN observed_at + 300
                                WHEN price_15m IS NULL
                                     AND quality_15m IS NULL
                                    THEN observed_at + 900
                                WHEN price_30m IS NULL
                                     AND quality_30m IS NULL
                                    THEN observed_at + 1800
                                WHEN price_60m IS NULL
                                     AND quality_60m IS NULL
                                    THEN observed_at + 3600
                                WHEN price_6h IS NULL
                                     AND quality_6h IS NULL
                                    THEN observed_at + 21600
                                WHEN price_24h IS NULL
                                     AND quality_24h IS NULL
                                    THEN observed_at + 86400
                                ELSE 9.0e18
                            END
                        ) AS next_due_at,
                        MIN(
                            COALESCE(last_observed_at, observed_at)
                        ) AS least_recent_observation,
                        MAX(observed_at) AS latest
                    FROM counterfactual_observations
                    WHERE completed_at IS NULL
                    GROUP BY lower(token), lower(pool)
                ), ranked AS (
                    SELECT
                        token,
                        pool,
                        next_due_at,
                        least_recent_observation,
                        latest,
                        COUNT(*) OVER (
                            PARTITION BY token
                        ) AS token_pool_count
                    FROM grouped
                    WHERE next_due_at < 9.0e18
                )
                SELECT *
                FROM ranked
                ORDER BY
                    CASE
                        WHEN next_due_at <= ? THEN 0
                        ELSE 1
                    END,
                    next_due_at ASC,
                    least_recent_observation ASC,
                    latest ASC,
                    token ASC,
                    pool ASC
                LIMIT ?
                """,
                (now, limit),
            ).fetchall()

        result = {}
        for row in rows:
            token = self._canonical(row["token"])
            pool = self._canonical(row["pool"])
            if not token or not pool:
                continue
            handle = self._encode_handle(
                token,
                pool,
                row["token_pool_count"],
            )
            result[handle] = pool

        return result

    def training_quality_snapshot(self):
        base = dict(super().training_quality_snapshot())

        if self._db is None:
            return base

        internal_gaps = {}
        legacy_unclassified = {}

        with self._lock:
            for _, label in self._durable_horizons:
                internal_gaps[label] = int(
                    self._db.execute(
                        f"""
                        SELECT COUNT(*)
                        FROM counterfactual_observations
                        WHERE quality_{label}='INTERNAL_GAP'
                        """
                    ).fetchone()[0]
                )
                legacy_unclassified[label] = int(
                    self._db.execute(
                        f"""
                        SELECT COUNT(*)
                        FROM counterfactual_observations
                        WHERE price_{label} IS NOT NULL
                          AND quality_{label} IS NULL
                        """
                    ).fetchone()[0]
                )

        base.update({
            "scientific_label_policy": "CAPTURE_WINDOW_OR_EXPLICIT_GAP",
            "horizon_capture_window_seconds": (
                HORIZON_CAPTURE_WINDOW_SECONDS
            ),
            "internal_gap_counts": internal_gaps,
            "legacy_unclassified_label_counts": legacy_unclassified,
            "stale_backfill_allowed": False,
            "training_authority": False,
            "paper_authority": False,
            "live_authority": False,
            "wallet_authority": False,
            "execution_authority": False,
        })
        return base
