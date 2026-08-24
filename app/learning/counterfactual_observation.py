import json
import sqlite3
import threading
import time
from collections import OrderedDict

from app.learning.outcome_classification import (
    classify_outcome,
)


class CounterfactualObservationStore:
    """
    Bounded RAM-only observation of non-entered candidates.

    No trade, DB, provider, wallet or execution authority.
    """

    def __init__(
        self,
        *,
        max_entries=512,
        horizon_seconds=300,
        ttl_seconds=1800,
        db_path=None,
    ):
        self.max_entries = max(
            1,
            int(max_entries),
        )
        self.horizon_seconds = max(
            1,
            int(horizon_seconds),
        )
        self.ttl_seconds = max(
            self.horizon_seconds,
            int(ttl_seconds),
        )
        self._rows = OrderedDict()
        self._completed = OrderedDict()
        self._outcomes = OrderedDict()
        self._lock = threading.RLock()
        self.evicted_count = 0
        self.expired_count = 0
        self.evaluated_count = 0

        self._db_path = (
            str(db_path)
            if db_path
            else None
        )

        self._db = None

        if self._db_path:
            self._db = sqlite3.connect(
                self._db_path,
                timeout=30,
                check_same_thread=False,
            )
            self._db.row_factory = sqlite3.Row
            self._db.execute(
                "PRAGMA busy_timeout=30000;"
            )

        self._durable_horizons = (
            (300, "5m"),
            (900, "15m"),
            (1800, "30m"),
            (3600, "60m"),
        )

    def _persist_record(
        self,
        *,
        token,
        pool,
        entry_price,
        signal_state,
        candidate_action,
        observed_at,
        context,
    ):
        if self._db is None:
            return None

        with self._lock:
            existing = self._db.execute(
                """
                SELECT id
                FROM counterfactual_observations
                WHERE lower(token)=lower(?)
                  AND completed_at IS NULL
                ORDER BY id DESC
                LIMIT 1
                """,
                (token,),
            ).fetchone()

            if existing is not None:
                return int(existing["id"])

            cursor = self._db.execute(
                """
                INSERT INTO counterfactual_observations (
                    token,
                    pool,
                    observed_at,
                    entry_price,
                    signal_state,
                    candidate_action,
                    context_json,
                    last_observed_at,
                    last_price,
                    max_price,
                    min_price
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    token,
                    pool,
                    float(observed_at),
                    float(entry_price),
                    str(signal_state),
                    str(candidate_action),
                    json.dumps(
                        context or {},
                        sort_keys=True,
                        separators=(",", ":"),
                        default=str,
                    ),
                    float(observed_at),
                    float(entry_price),
                    float(entry_price),
                    float(entry_price),
                ),
            )

            self._db.commit()

            return int(cursor.lastrowid)

    def _persist_observe(
        self,
        *,
        token,
        current_price,
        evaluated_at,
    ):
        if self._db is None:
            return 0

        now = float(evaluated_at)
        price = float(current_price)

        updated = 0

        with self._lock:
            rows = self._db.execute(
                """
                SELECT *
                FROM counterfactual_observations
                WHERE lower(token)=lower(?)
                  AND completed_at IS NULL
                ORDER BY id
                """,
                (token,),
            ).fetchall()

            for row in rows:
                entry = float(row["entry_price"])
                age = max(
                    0.0,
                    now - float(row["observed_at"]),
                )

                maximum = row["max_price"]
                minimum = row["min_price"]

                maximum = max(
                    price,
                    float(maximum)
                    if maximum is not None
                    else price,
                )

                minimum = min(
                    price,
                    float(minimum)
                    if minimum is not None
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
                        values[
                            f"observed_{label}_at"
                        ] = now

                if (
                    row["price_60m"] is not None
                    or "price_60m" in values
                ):
                    values["completed_at"] = now

                sql = (
                    "UPDATE counterfactual_observations SET "
                    + ", ".join(
                        f"{key}=?"
                        for key in values
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

    def observe_durable(
        self,
        *,
        token,
        current_price,
        evaluated_at=None,
    ):
        key = str(token or "").strip().lower()

        try:
            price = float(current_price)
        except (TypeError, ValueError):
            price = 0.0

        if not key or price <= 0:
            return self._out(
                "INVALID",
                durable_updated=0,
            )

        now = (
            float(evaluated_at)
            if evaluated_at is not None
            else time.time()
        )

        updated = self._persist_observe(
            token=key,
            current_price=price,
            evaluated_at=now,
        )

        return self._out(
            "OBSERVED",
            durable_updated=updated,
        )

    def pending_pool_snapshot(
        self,
        *,
        max_entries=120,
    ):
        if self._db is None:
            return {}

        limit = max(
            1,
            int(max_entries),
        )

        with self._lock:
            rows = self._db.execute(
                """
                SELECT token, pool
                FROM counterfactual_observations
                WHERE completed_at IS NULL
                ORDER BY observed_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

        result = {}

        for row in rows:
            token = str(
                row["token"] or ""
            ).strip().lower()

            pool = str(
                row["pool"] or ""
            ).strip().lower()

            if (
                token
                and pool
                and token not in result
            ):
                result[token] = pool

        return result

    def durable_snapshot(
        self,
        *,
        limit=100,
    ):
        if self._db is None:
            return []

        limit = max(
            1,
            int(limit),
        )

        with self._lock:
            rows = self._db.execute(
                """
                SELECT *
                FROM counterfactual_observations
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

        return [
            dict(row)
            for row in rows
        ]

    @property
    def size(self):
        with self._lock:
            return len(self._rows)

    def record(
        self,
        *,
        token,
        pool,
        entry_price,
        signal_state,
        candidate_action,
        observed_at=None,
        context=None,
    ):
        key = str(token or "").strip().lower()
        pool = str(pool or "").strip().lower()

        try:
            price = float(entry_price)
        except (TypeError, ValueError):
            price = 0.0

        if (
            not key
            or not pool
            or price <= 0
        ):
            return self._out(
                "INVALID",
                stored=False,
            )

        now = (
            float(observed_at)
            if observed_at is not None
            else time.time()
        )

        with self._lock:
            expired_completed = [
                completed_key
                for completed_key, completed_at
                in self._completed.items()
                if now - completed_at
                > self.ttl_seconds
            ]

            for completed_key in expired_completed:
                self._completed.pop(
                    completed_key,
                    None,
                )

            if key in self._completed:
                return self._out(
                    "COOLDOWN",
                    stored=False,
                )

            if key in self._rows:
                return self._out(
                    "EXISTS",
                    stored=False,
                )

            while (
                len(self._rows)
                >= self.max_entries
            ):
                self._rows.popitem(
                    last=False
                )
                self.evicted_count += 1

            self._rows[key] = {
                "token": key,
                "pool": pool,
                "entry_price": price,
                "signal_state": str(
                    signal_state or "UNKNOWN"
                ).upper(),
                "candidate_action": str(
                    candidate_action or "UNKNOWN"
                ).upper(),
                "observed_at": now,
                "context": dict(context or {}),
            }

        durable_id = self._persist_record(
            token=key,
            pool=pool,
            entry_price=price,
            signal_state=str(
                signal_state or "UNKNOWN"
            ).upper(),
            candidate_action=str(
                candidate_action or "UNKNOWN"
            ).upper(),
            observed_at=now,
            context=context or {},
        )

        return self._out(
            "RECORDED",
            stored=True,
            durable_id=durable_id,
        )

    def observe(
        self,
        *,
        token,
        current_price,
        evaluated_at=None,
    ):
        key = str(token or "").strip().lower()

        try:
            price = float(current_price)
        except (TypeError, ValueError):
            price = 0.0

        if not key or price <= 0:
            return self._out("INVALID")

        now = (
            float(evaluated_at)
            if evaluated_at is not None
            else time.time()
        )

        self._persist_observe(
            token=key,
            current_price=price,
            evaluated_at=now,
        )

        with self._lock:
            row = self._rows.get(key)

            if row is None:
                return self._out("UNKNOWN")

            age = max(
                0.0,
                now - row["observed_at"],
            )

            if age > self.ttl_seconds:
                self._rows.pop(key, None)
                self.expired_count += 1
                return self._out(
                    "EXPIRED",
                    age_seconds=age,
                )

            if age < self.horizon_seconds:
                return self._out(
                    "PENDING",
                    age_seconds=age,
                )

            self._rows.pop(key, None)

        realized_return = (
            price / row["entry_price"]
            - 1.0
        )

        if realized_return > 0:
            direction = "UP"
        elif realized_return < 0:
            direction = "DOWN"
        else:
            direction = "FLAT"

        classification = classify_outcome(
            signal_state=row["signal_state"],
            candidate_action=(
                row["candidate_action"]
            ),
            realized_direction=direction,
            realized_return=realized_return,
            evidence_complete=True,
            freshness="FRESH",
        )

        outcome = self._out(
            "EVALUATED",
            token=row["token"],
            pool=row["pool"],
            observed_at=row["observed_at"],
            evaluated_at=now,
            age_seconds=age,
            entry_price=row["entry_price"],
            current_price=price,
            realized_return=realized_return,
            realized_direction=direction,
            signal_state=row["signal_state"],
            candidate_action=row[
                "candidate_action"
            ],
            outcome_class=classification[
                "outcome_class"
            ],
            classification=classification,
            context=row["context"],

            # This observer knows only the
            # later mark-price direction.
            #
            # It does NOT prove that a trade
            # was net-profitable, executable,
            # sellable at evaluation time,
            # or realizable after costs.
            outcome_scope=(
                "PRICE_DIRECTION_ONLY"
            ),
            net_profit_verified=False,
            realizable_profit_verified=False,
            evaluation_sellability_verified=False,
            evaluation_costs_verified=False,

            proposal_only=True,
            automatic_apply_allowed=False,
        )

        outcome_id = (
            f"{key}:{row['observed_at']}"
        )

        with self._lock:
            self.evaluated_count += 1
            self._completed[key] = now
            self._outcomes[outcome_id] = outcome

            while (
                len(self._completed)
                > self.max_entries
            ):
                self._completed.popitem(
                    last=False
                )

            while (
                len(self._outcomes)
                > self.max_entries
            ):
                self._outcomes.popitem(
                    last=False
                )

        return outcome

    def outcome_snapshot(self):
        with self._lock:
            return [
                dict(row)
                for row in self._outcomes.values()
            ]

    def status(self):
        outcomes = self.outcome_snapshot()
        outcome_counts = {}

        for row in outcomes:
            outcome_class = row.get(
                "outcome_class",
                "UNKNOWN",
            )
            outcome_counts[outcome_class] = (
                outcome_counts.get(
                    outcome_class,
                    0,
                )
                + 1
            )

        return {
            "state": "READY",
            "size": self.size,
            "max_entries": self.max_entries,
            "completed_size": len(
                self._completed
            ),
            "outcome_size": len(outcomes),
            "outcome_counts": outcome_counts,
            "horizon_seconds": (
                self.horizon_seconds
            ),
            "ttl_seconds": self.ttl_seconds,
            "evicted_count": self.evicted_count,
            "expired_count": self.expired_count,
            "evaluated_count": (
                self.evaluated_count
            ),
            "bounded": True,
            "ram_only": (
                self._db is None
            ),
            "db_write": (
                self._db is not None
            ),
            "durable_tracking": (
                self._db is not None
            ),
            "durable_horizons_seconds": (
                300,
                900,
                1800,
                3600,
            ),
            "external_fetch": False,
            "provider_call": False,

            "outcome_scope": (
                "PRICE_DIRECTION_ONLY"
            ),

            "missed_opportunity_means_net_profit": (
                False
            ),

            "net_profit_verified": False,
            "realizable_profit_verified": False,

            "proposal_only": True,
            "automatic_apply_allowed": False,
            "decision_authority": False,
            "paper_authority": False,
            "live_authority": False,
            "wallet_authority": False,
            "execution_authority": False,
        }

    @staticmethod
    def _out(state, **values):
        return {
            "state": state,
            **values,
            "trade_permission": False,
            "decision_authority": False,
            "paper_authority": False,
            "live_authority": False,
            "wallet_authority": False,
            "execution_authority": False,
        }
