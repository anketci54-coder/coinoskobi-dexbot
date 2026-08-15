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

        return self._out(
            "RECORDED",
            stored=True,
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
            "ram_only": True,
            "db_write": False,
            "external_fetch": False,
            "provider_call": False,
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
