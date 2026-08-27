import sqlite3
import time
from pathlib import Path

from app.learning.counterfactual_observation import (
    DECISION_CHECKPOINT_SECONDS,
    CounterfactualObservationStore as _BaseCounterfactualObservationStore,
)


_HANDLE_SEPARATOR = "::pool::"
_FOLLOWUP_GRACE_SECONDS = 60 * 60


class IntegrityCounterfactualObservationStore(
    _BaseCounterfactualObservationStore
):
    """
    Data-integrity hardening for durable counterfactual outcomes.

    Guarantees:
    - bounded follow-up is checkpoint-due/overdue first, not newest first;
    - a market price is applied only to the exact token+pool identity;
    - paper-promotion attribution is exact token+pool, never token-only;
    - the exact-pool cache-retention window extends beyond the 24h checkpoint
      so cleanup cannot race the final scheduled observation;
    - ambiguous raw-token observations fail closed instead of cross-writing;
    - legacy rows marked completed without a real 24h observation remain
      visible as quarantined training data and are never backfilled here.

    This layer is observation-only. It grants no paper/live/wallet/signing/
    execution authority.
    """

    @classmethod
    def _encode_handle(cls, token, pool, pool_count):
        token = cls._canonical(token)
        pool = cls._canonical(pool)
        if int(pool_count or 0) <= 1:
            return token
        return f"{token}{_HANDLE_SEPARATOR}{pool}"

    @classmethod
    def _decode_handle(cls, value):
        value = str(value or "").strip().lower()
        if _HANDLE_SEPARATOR not in value:
            return cls._canonical(value), None
        token, pool = value.split(_HANDLE_SEPARATOR, 1)
        return cls._canonical(token), cls._canonical(pool)

    def _register_followup(
        self,
        *,
        token,
        pool,
        observed_at,
    ):
        """
        Preserve the exact pool past the final 24h checkpoint.

        The checkpoint remains exactly 24h.  The extra hour is retention grace
        only; it is never used as a label horizon or reconstructed outcome.
        """
        if not self._cache_db_path:
            return False

        if not self._ensure_cache_followup_registry():
            return False

        try:
            db = sqlite3.connect(
                self._cache_db_path,
                timeout=5,
            )
            db.execute("PRAGMA busy_timeout=5000;")
            db.execute(
                """
                INSERT INTO candidate_followup_registry(
                    pool,
                    token,
                    expires_at,
                    updated_at
                )
                VALUES(?,?,?,?)
                ON CONFLICT(pool) DO UPDATE SET
                    token=excluded.token,
                    expires_at=MAX(
                        candidate_followup_registry.expires_at,
                        excluded.expires_at
                    ),
                    updated_at=excluded.updated_at
                """,
                (
                    self._canonical(pool),
                    self._canonical(token),
                    float(observed_at)
                    + DECISION_CHECKPOINT_SECONDS
                    + _FOLLOWUP_GRACE_SECONDS,
                    float(observed_at),
                ),
            )
            db.commit()
            db.close()
            return True
        except sqlite3.Error:
            return False

    def _resolve_single_pending_pool(self, token):
        if self._db is None:
            return None

        token = self._canonical(token)
        if not token:
            return None

        with self._lock:
            rows = self._db.execute(
                """
                SELECT DISTINCT lower(pool) AS pool
                FROM counterfactual_observations
                WHERE lower(token)=lower(?)
                  AND completed_at IS NULL
                LIMIT 2
                """,
                (token,),
            ).fetchall()

        if len(rows) != 1:
            return None
        return self._canonical(rows[0]["pool"])

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
                    if (
                        row[price_key] is None
                        and age >= seconds
                    ):
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

                if (
                    row["price_24h"] is not None
                    or "price_24h" in values
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

    def _persist_observe(
        self,
        *,
        token,
        current_price,
        evaluated_at,
    ):
        real_token, pool = self._decode_handle(token)
        if pool is None:
            pool = self._resolve_single_pending_pool(real_token)
        if not real_token or not pool:
            return 0
        return self._persist_observe_exact(
            token=real_token,
            pool=pool,
            current_price=current_price,
            evaluated_at=evaluated_at,
        )

    def _sync_pool_cache_price(
        self,
        *,
        pool,
        current_price,
    ):
        if not self._cache_db_path:
            return 0

        path = Path(self._cache_db_path)
        if not path.exists():
            return 0

        try:
            db = sqlite3.connect(path, timeout=5)
            db.execute("PRAGMA busy_timeout=5000;")
            cursor = db.execute(
                """
                UPDATE gecko_pool_cache
                SET price_usd=?,
                    updated_at=datetime('now')
                WHERE lower(pool)=lower(?)
                """,
                (float(current_price), self._canonical(pool)),
            )
            db.commit()
            updated = int(cursor.rowcount or 0)
            db.close()
            return updated
        except sqlite3.Error:
            return 0

    def _sync_exact_pool_cache_price(
        self,
        *,
        token,
        current_price,
    ):
        real_token, pool = self._decode_handle(token)
        if pool is None:
            pool = self._resolve_single_pending_pool(real_token)
        if not pool:
            return 0
        return self._sync_pool_cache_price(
            pool=pool,
            current_price=current_price,
        )

    def _persist_paper_promotion_exact(
        self,
        *,
        token,
        pool,
        observed_at,
    ):
        """Bind PAPER_BUY promotion to the same exact token+pool."""
        if self._db is None:
            return None

        token = self._canonical(token)
        pool = self._canonical(pool)
        if not token or not pool:
            return None

        with self._lock:
            trade = self._db.execute(
                """
                SELECT token, pool, entry_price
                FROM paper_trades
                WHERE lower(token)=lower(?)
                  AND lower(pool)=lower(?)
                  AND status='OPEN'
                ORDER BY id DESC
                LIMIT 1
                """,
                (token, pool),
            ).fetchone()

            if trade is None:
                return None

            price = self._finite_positive(
                trade["entry_price"]
            )
            if price is None:
                return None

            latest = self._db.execute(
                """
                SELECT decision_action
                FROM candidate_decision_history
                WHERE lower(token)=lower(?)
                  AND lower(pool)=lower(?)
                ORDER BY id DESC
                LIMIT 1
                """,
                (token, pool),
            ).fetchone()

            if (
                latest is not None
                and str(latest["decision_action"]).upper()
                == "PAPER_BUY"
            ):
                return None

        context = {
            "paper": "PAPER_BUY",
            "reason": "PAPER_TRADE_OPENED",
            "promotion_from_prior_non_entry": True,
            "hindsight_reconstructed": False,
        }

        transition = self._persist_decision_transition(
            token=token,
            pool=pool,
            entry_price=price,
            signal_state="POSITIVE",
            candidate_action="PAPER_BUY",
            observed_at=observed_at,
            context=context,
            promotion=True,
        )

        if transition["stored"]:
            with self._lock:
                self._db.execute(
                    """
                    UPDATE counterfactual_observations
                    SET promoted_at=COALESCE(
                        promoted_at,
                        ?
                    )
                    WHERE lower(token)=lower(?)
                      AND lower(pool)=lower(?)
                      AND completed_at IS NULL
                    """,
                    (
                        float(observed_at),
                        token,
                        pool,
                    ),
                )
                self._db.commit()

        return transition

    def observe_durable(
        self,
        *,
        token,
        current_price,
        pool=None,
        evaluated_at=None,
    ):
        real_token, handle_pool = self._decode_handle(token)
        exact_pool = self._canonical(pool or handle_pool)
        price = self._finite_positive(current_price)

        if not real_token or price is None:
            return self._out(
                "INVALID",
                durable_updated=0,
            )

        if not exact_pool:
            exact_pool = self._resolve_single_pending_pool(real_token)

        if not exact_pool:
            return self._out(
                "AMBIGUOUS_POOL",
                durable_updated=0,
                cache_updated=0,
                promotion=None,
            )

        now = (
            float(evaluated_at)
            if evaluated_at is not None
            else time.time()
        )

        updated = self._persist_observe_exact(
            token=real_token,
            pool=exact_pool,
            current_price=price,
            evaluated_at=now,
        )

        cache_updated = self._sync_pool_cache_price(
            pool=exact_pool,
            current_price=price,
        )

        promotion = self._persist_paper_promotion_exact(
            token=real_token,
            pool=exact_pool,
            observed_at=now,
        )

        return self._out(
            "OBSERVED",
            durable_updated=updated,
            cache_updated=cache_updated,
            promotion=promotion,
            exact_pool=exact_pool,
        )

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
                                    THEN observed_at + 300
                                WHEN price_15m IS NULL
                                    THEN observed_at + 900
                                WHEN price_30m IS NULL
                                    THEN observed_at + 1800
                                WHEN price_60m IS NULL
                                    THEN observed_at + 3600
                                WHEN price_6h IS NULL
                                    THEN observed_at + 21600
                                WHEN price_24h IS NULL
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
        if self._db is None:
            return {
                "state": "DISABLED",
                "legacy_completed_without_24h": 0,
                "ambiguous_pending_tokens": 0,
                "training_authority": False,
            }

        with self._lock:
            legacy = self._db.execute(
                """
                SELECT COUNT(*)
                FROM counterfactual_observations
                WHERE completed_at IS NOT NULL
                  AND (
                      price_24h IS NULL
                      OR return_24h IS NULL
                      OR observed_24h_at IS NULL
                  )
                """
            ).fetchone()[0]

            ambiguous = self._db.execute(
                """
                SELECT COUNT(*)
                FROM (
                    SELECT lower(token)
                    FROM counterfactual_observations
                    WHERE completed_at IS NULL
                    GROUP BY lower(token)
                    HAVING COUNT(DISTINCT lower(pool)) > 1
                )
                """
            ).fetchone()[0]

        return {
            "state": "READY",
            "legacy_completed_without_24h": int(legacy),
            "ambiguous_pending_tokens": int(ambiguous),
            "legacy_training_disposition": "QUARANTINE",
            "scheduler_policy": "CHECKPOINT_DUE_OVERDUE_FIRST",
            "identity_policy": "EXACT_TOKEN_POOL",
            "promotion_identity_policy": "EXACT_TOKEN_POOL",
            "followup_retention_grace_seconds": _FOLLOWUP_GRACE_SECONDS,
            "training_authority": False,
            "paper_authority": False,
            "live_authority": False,
            "wallet_authority": False,
            "execution_authority": False,
        }

    def status(self):
        base = dict(super().status())
        base["horizon_integrity"] = self.training_quality_snapshot()
        return base
