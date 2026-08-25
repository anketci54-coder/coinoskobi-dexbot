import hashlib
import json
import math
import sqlite3
import threading
import time
from collections import OrderedDict
from pathlib import Path

from app.learning.outcome_classification import (
    classify_outcome,
)


DECISION_CHECKPOINT_SECONDS = 24 * 60 * 60

DURABLE_HORIZONS = (
    (300, "5m"),
    (900, "15m"),
    (1800, "30m"),
    (3600, "60m"),
    (21600, "6h"),
    (86400, "24h"),
)


class CounterfactualObservationStore:
    """
    Bounded observation of non-entered candidates.

    Durable mode has two independent responsibilities:

    1. keep timestamped WATCH/REJECT decision transitions so a token is
       never treated as permanently rejected;
    2. follow the exact pool long enough to measure what happened after
       each non-entry decision.

    Follow-up is observation/re-evaluation support only.  It grants no
    trade, paper, live, wallet, signing or execution authority.
    """

    def __init__(
        self,
        *,
        max_entries=512,
        horizon_seconds=300,
        ttl_seconds=1800,
        db_path=None,
        cache_db_path=None,
    ):
        self.max_entries = max(1, int(max_entries))
        self.horizon_seconds = max(1, int(horizon_seconds))
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

        self._db_path = str(db_path) if db_path else None
        self._db = None

        if cache_db_path is not None:
            self._cache_db_path = str(cache_db_path)
        elif self._is_canonical_paper_db(self._db_path):
            self._cache_db_path = "data/cache/cache.db"
        else:
            self._cache_db_path = None

        self._durable_horizons = DURABLE_HORIZONS

        if self._db_path:
            self._db = sqlite3.connect(
                self._db_path,
                timeout=30,
                check_same_thread=False,
            )
            self._db.row_factory = sqlite3.Row
            self._db.execute("PRAGMA busy_timeout=30000;")
            self._ensure_durable_schema()

        self._ensure_cache_followup_registry()

    @staticmethod
    def _is_canonical_paper_db(db_path):
        if not db_path:
            return False

        value = str(db_path).replace("\\", "/")
        return value.endswith("data/paper_trades.db")

    @staticmethod
    def _canonical(value):
        value = str(value or "").strip().lower()
        if value.startswith("bsc_"):
            value = value[4:]
        return value

    @staticmethod
    def _json(value):
        return json.dumps(
            value or {},
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )

    def _ensure_durable_schema(self):
        if self._db is None:
            return

        self._db.execute(
            """
            CREATE TABLE IF NOT EXISTS counterfactual_observations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                token TEXT NOT NULL,
                pool TEXT NOT NULL,
                observed_at REAL NOT NULL,
                entry_price REAL NOT NULL,
                signal_state TEXT NOT NULL,
                candidate_action TEXT NOT NULL,
                context_json TEXT NOT NULL DEFAULT '{}',
                last_observed_at REAL,
                last_price REAL,
                max_price REAL,
                min_price REAL,
                price_5m REAL,
                return_5m REAL,
                observed_5m_at REAL,
                price_15m REAL,
                return_15m REAL,
                observed_15m_at REAL,
                price_30m REAL,
                return_30m REAL,
                observed_30m_at REAL,
                price_60m REAL,
                return_60m REAL,
                observed_60m_at REAL,
                completed_at REAL
            )
            """
        )

        additions = {
            "price_6h": "REAL",
            "return_6h": "REAL",
            "observed_6h_at": "REAL",
            "mfe_6h": "REAL",
            "mae_6h": "REAL",
            "price_24h": "REAL",
            "return_24h": "REAL",
            "observed_24h_at": "REAL",
            "mfe_24h": "REAL",
            "mae_24h": "REAL",
            "mfe_5m": "REAL",
            "mae_5m": "REAL",
            "mfe_15m": "REAL",
            "mae_15m": "REAL",
            "mfe_30m": "REAL",
            "mae_30m": "REAL",
            "mfe_60m": "REAL",
            "mae_60m": "REAL",
            "decision_history_id": "INTEGER",
            "promoted_at": "REAL",
            "first_2x_at": "REAL",
            "first_5x_at": "REAL",
            "first_10x_at": "REAL",
            "first_50pct_loss_at": "REAL",
            "first_90pct_loss_at": "REAL",
        }

        columns = {
            row[1]
            for row in self._db.execute(
                "PRAGMA table_info(counterfactual_observations)"
            ).fetchall()
        }

        for name, column_type in additions.items():
            if name not in columns:
                self._db.execute(
                    "ALTER TABLE counterfactual_observations "
                    f"ADD COLUMN {name} {column_type}"
                )

        self._db.execute(
            """
            CREATE TABLE IF NOT EXISTS candidate_decision_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                token TEXT NOT NULL,
                pool TEXT NOT NULL,
                observed_at REAL NOT NULL,
                decision_action TEXT NOT NULL,
                reason TEXT,
                signal_state TEXT NOT NULL,
                entry_price REAL,
                fingerprint TEXT NOT NULL,
                context_json TEXT NOT NULL DEFAULT '{}',
                promotion INTEGER NOT NULL DEFAULT 0
            )
            """
        )

        self._db.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_candidate_decision_token_pool_time
            ON candidate_decision_history(
                token,
                pool,
                observed_at
            )
            """
        )

        self._db.execute(
            """
            CREATE INDEX IF NOT EXISTS
            idx_counterfactual_pending_pool_time
            ON counterfactual_observations(
                pool,
                completed_at,
                observed_at
            )
            """
        )

        self._db.commit()

    def _ensure_cache_followup_registry(self):
        if not self._cache_db_path:
            return False

        path = Path(self._cache_db_path)
        if not path.exists():
            return False

        try:
            db = sqlite3.connect(path, timeout=5)
            db.execute("PRAGMA busy_timeout=5000;")

            db.execute(
                """
                CREATE TABLE IF NOT EXISTS
                candidate_followup_registry (
                    pool TEXT PRIMARY KEY,
                    token TEXT NOT NULL,
                    expires_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                )
                """
            )

            cache_exists = db.execute(
                """
                SELECT 1
                FROM sqlite_master
                WHERE type='table'
                  AND name='gecko_pool_cache'
                """
            ).fetchone()

            if cache_exists is not None:
                db.execute(
                    """
                    CREATE TRIGGER IF NOT EXISTS
                    preserve_candidate_followup_pool
                    BEFORE DELETE ON gecko_pool_cache
                    WHEN EXISTS (
                        SELECT 1
                        FROM candidate_followup_registry r
                        WHERE lower(r.pool)=lower(OLD.pool)
                          AND r.expires_at > unixepoch()
                    )
                    BEGIN
                        SELECT RAISE(IGNORE);
                    END
                    """
                )

            db.commit()
            db.close()
            return True

        except sqlite3.Error:
            return False

    def _register_followup(
        self,
        *,
        token,
        pool,
        observed_at,
    ):
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
                    + DECISION_CHECKPOINT_SECONDS,
                    float(observed_at),
                ),
            )
            db.commit()
            db.close()
            return True

        except sqlite3.Error:
            return False

    def _sync_exact_pool_cache_price(
        self,
        *,
        token,
        current_price,
    ):
        if (
            self._db is None
            or not self._cache_db_path
        ):
            return 0

        path = Path(self._cache_db_path)
        if not path.exists():
            return 0

        pools = [
            row[0]
            for row in self._db.execute(
                """
                SELECT DISTINCT pool
                FROM counterfactual_observations
                WHERE lower(token)=lower(?)
                  AND completed_at IS NULL
                """,
                (self._canonical(token),),
            ).fetchall()
        ]

        if not pools:
            return 0

        try:
            db = sqlite3.connect(path, timeout=5)
            db.execute("PRAGMA busy_timeout=5000;")
            updated = 0

            for pool in pools:
                cursor = db.execute(
                    """
                    UPDATE gecko_pool_cache
                    SET price_usd=?,
                        updated_at=datetime('now')
                    WHERE lower(pool)=lower(?)
                    """,
                    (
                        float(current_price),
                        self._canonical(pool),
                    ),
                )
                updated += int(cursor.rowcount or 0)

            db.commit()
            db.close()
            return updated

        except sqlite3.Error:
            return 0

    def _decision_fingerprint(
        self,
        *,
        signal_state,
        candidate_action,
        context,
    ):
        context = dict(context or {})

        payload = {
            "decision_action": str(
                context.get("paper")
                or candidate_action
                or "UNKNOWN"
            ).upper(),
            "reason": context.get("reason"),
            "signal_state": str(
                signal_state or "UNKNOWN"
            ).upper(),
            "hard_block": bool(
                context.get("hard_block")
            ),
            "sellability": context.get(
                "sellability"
            ),
            "plan_blockers": sorted(
                str(value)
                for value in (
                    context.get("plan_blockers")
                    or []
                )
            ),
            "sizing_blockers": sorted(
                str(value)
                for value in (
                    context.get("sizing_blockers")
                    or []
                )
            ),
            "sizing_reason": context.get(
                "sizing_reason"
            ),
        }

        raw = self._json(payload)
        return hashlib.sha256(
            raw.encode("utf-8")
        ).hexdigest()

    def _persist_decision_transition(
        self,
        *,
        token,
        pool,
        entry_price,
        signal_state,
        candidate_action,
        observed_at,
        context,
        promotion=False,
    ):
        if self._db is None:
            return {
                "stored": False,
                "decision_id": None,
                "transition_from": None,
            }

        key = self._canonical(token)
        pool = self._canonical(pool)
        now = float(observed_at)
        context = dict(context or {})

        decision_action = str(
            context.get("paper")
            or candidate_action
            or "UNKNOWN"
        ).upper()

        fingerprint = self._decision_fingerprint(
            signal_state=signal_state,
            candidate_action=decision_action,
            context=context,
        )

        with self._lock:
            previous = self._db.execute(
                """
                SELECT *
                FROM candidate_decision_history
                WHERE lower(token)=lower(?)
                  AND lower(pool)=lower(?)
                ORDER BY id DESC
                LIMIT 1
                """,
                (key, pool),
            ).fetchone()

            if previous is not None:
                same = (
                    previous["fingerprint"]
                    == fingerprint
                )
                age = max(
                    0.0,
                    now - float(
                        previous["observed_at"]
                    ),
                )

                if (
                    same
                    and age
                    < DECISION_CHECKPOINT_SECONDS
                ):
                    return {
                        "stored": False,
                        "decision_id": int(
                            previous["id"]
                        ),
                        "transition_from": previous[
                            "decision_action"
                        ],
                    }

            cursor = self._db.execute(
                """
                INSERT INTO candidate_decision_history(
                    token,
                    pool,
                    observed_at,
                    decision_action,
                    reason,
                    signal_state,
                    entry_price,
                    fingerprint,
                    context_json,
                    promotion
                )
                VALUES(?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    key,
                    pool,
                    now,
                    decision_action,
                    context.get("reason"),
                    str(
                        signal_state
                        or "UNKNOWN"
                    ).upper(),
                    float(entry_price)
                    if entry_price is not None
                    else None,
                    fingerprint,
                    self._json(context),
                    int(bool(promotion)),
                ),
            )

            self._db.commit()

            return {
                "stored": True,
                "decision_id": int(
                    cursor.lastrowid
                ),
                "transition_from": (
                    previous["decision_action"]
                    if previous is not None
                    else None
                ),
            }

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
        decision_history_id,
    ):
        if self._db is None:
            return None

        with self._lock:
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
                    min_price,
                    decision_history_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    self._canonical(token),
                    self._canonical(pool),
                    float(observed_at),
                    float(entry_price),
                    str(signal_state),
                    str(candidate_action),
                    self._json(context),
                    float(observed_at),
                    float(entry_price),
                    float(entry_price),
                    float(entry_price),
                    decision_history_id,
                ),
            )
            self._db.commit()
            return int(cursor.lastrowid)

    @staticmethod
    def _finite_positive(value):
        try:
            value = float(value)
        except (TypeError, ValueError):
            return None

        if not math.isfinite(value) or value <= 0:
            return None
        return value

    def _persist_paper_promotion(
        self,
        *,
        token,
        observed_at,
    ):
        if self._db is None:
            return None

        key = self._canonical(token)

        with self._lock:
            trade = self._db.execute(
                """
                SELECT token, pool, entry_price
                FROM paper_trades
                WHERE lower(token)=lower(?)
                  AND status='OPEN'
                ORDER BY id DESC
                LIMIT 1
                """,
                (key,),
            ).fetchone()

            if trade is None:
                return None

            pool = self._canonical(
                trade["pool"]
            )
            price = self._finite_positive(
                trade["entry_price"]
            )

            if not pool or price is None:
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
                (key, pool),
            ).fetchone()

            if (
                latest is not None
                and str(
                    latest["decision_action"]
                ).upper()
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
            token=key,
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
                        key,
                        pool,
                    ),
                )
                self._db.commit()

        return transition

    def _persist_observe(
        self,
        *,
        token,
        current_price,
        evaluated_at,
    ):
        if self._db is None:
            return 0

        key = self._canonical(token)
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
                (key,),
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

    def observe_durable(
        self,
        *,
        token,
        current_price,
        evaluated_at=None,
    ):
        key = self._canonical(token)
        price = self._finite_positive(current_price)

        if not key or price is None:
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

        cache_updated = self._sync_exact_pool_cache_price(
            token=key,
            current_price=price,
        )

        promotion = self._persist_paper_promotion(
            token=key,
            observed_at=now,
        )

        return self._out(
            "OBSERVED",
            durable_updated=updated,
            cache_updated=cache_updated,
            promotion=promotion,
        )

    def pending_pool_snapshot(
        self,
        *,
        max_entries=120,
    ):
        if self._db is None:
            return {}

        limit = max(1, int(max_entries))

        with self._lock:
            rows = self._db.execute(
                """
                SELECT token, pool, MAX(observed_at) AS latest
                FROM counterfactual_observations
                WHERE completed_at IS NULL
                GROUP BY lower(token), lower(pool)
                ORDER BY latest DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

        result = {}

        for row in rows:
            token = self._canonical(row["token"])
            pool = self._canonical(row["pool"])

            if token and pool and token not in result:
                result[token] = pool

        return result

    def durable_snapshot(
        self,
        *,
        limit=100,
    ):
        if self._db is None:
            return []

        limit = max(1, int(limit))

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

        return [dict(row) for row in rows]

    def decision_snapshot(
        self,
        *,
        limit=100,
    ):
        if self._db is None:
            return []

        limit = max(1, int(limit))

        with self._lock:
            rows = self._db.execute(
                """
                SELECT *
                FROM candidate_decision_history
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

        return [dict(row) for row in rows]

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
        key = self._canonical(token)
        pool = self._canonical(pool)
        price = self._finite_positive(entry_price)

        if not key or not pool or price is None:
            return self._out(
                "INVALID",
                stored=False,
            )

        now = (
            float(observed_at)
            if observed_at is not None
            else time.time()
        )

        signal_state = str(
            signal_state or "UNKNOWN"
        ).upper()
        candidate_action = str(
            candidate_action or "UNKNOWN"
        ).upper()
        context = dict(context or {})

        transition = self._persist_decision_transition(
            token=key,
            pool=pool,
            entry_price=price,
            signal_state=signal_state,
            candidate_action=candidate_action,
            observed_at=now,
            context=context,
        )

        durable_id = None

        if transition["stored"]:
            durable_id = self._persist_record(
                token=key,
                pool=pool,
                entry_price=price,
                signal_state=signal_state,
                candidate_action=candidate_action,
                observed_at=now,
                context=context,
                decision_history_id=(
                    transition["decision_id"]
                ),
            )

            self._register_followup(
                token=key,
                pool=pool,
                observed_at=now,
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

            ram_state = "RECORDED"

            if key in self._completed:
                ram_state = "COOLDOWN"

            elif key in self._rows:
                ram_state = "EXISTS"

            else:
                while len(self._rows) >= self.max_entries:
                    self._rows.popitem(last=False)
                    self.evicted_count += 1

                self._rows[key] = {
                    "token": key,
                    "pool": pool,
                    "entry_price": price,
                    "signal_state": signal_state,
                    "candidate_action": candidate_action,
                    "observed_at": now,
                    "context": context,
                }

        if transition["stored"]:
            return self._out(
                "RECORDED",
                stored=True,
                durable_id=durable_id,
                decision_id=transition[
                    "decision_id"
                ],
                transition_from=transition[
                    "transition_from"
                ],
                ram_state=ram_state,
                reevaluation_eligible=True,
                reevaluation_window_seconds=(
                    DECISION_CHECKPOINT_SECONDS
                ),
            )

        return self._out(
            ram_state,
            stored=(ram_state == "RECORDED"),
            durable_id=None,
            decision_id=transition[
                "decision_id"
            ],
            transition_from=transition[
                "transition_from"
            ],
            reevaluation_eligible=True,
            reevaluation_window_seconds=(
                DECISION_CHECKPOINT_SECONDS
            ),
        )

    def observe(
        self,
        *,
        token,
        current_price,
        evaluated_at=None,
    ):
        key = self._canonical(token)
        price = self._finite_positive(current_price)

        if not key or price is None:
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

        self._sync_exact_pool_cache_price(
            token=key,
            current_price=price,
        )

        self._persist_paper_promotion(
            token=key,
            observed_at=now,
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
            price / row["entry_price"] - 1.0
        )

        if realized_return > 0:
            direction = "UP"
        elif realized_return < 0:
            direction = "DOWN"
        else:
            direction = "FLAT"

        classification = classify_outcome(
            signal_state=row["signal_state"],
            candidate_action=row[
                "candidate_action"
            ],
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
            outcome_scope="PRICE_DIRECTION_ONLY",
            net_profit_verified=False,
            realizable_profit_verified=False,
            evaluation_sellability_verified=False,
            evaluation_costs_verified=False,
            proposal_only=True,
            automatic_apply_allowed=False,
        )

        outcome_id = f"{key}:{row['observed_at']}"

        with self._lock:
            self.evaluated_count += 1
            self._completed[key] = now
            self._outcomes[outcome_id] = outcome

            while len(self._completed) > self.max_entries:
                self._completed.popitem(last=False)

            while len(self._outcomes) > self.max_entries:
                self._outcomes.popitem(last=False)

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

        decision_count = 0
        pending_durable = 0

        if self._db is not None:
            with self._lock:
                decision_count = int(
                    self._db.execute(
                        """
                        SELECT COUNT(*)
                        FROM candidate_decision_history
                        """
                    ).fetchone()[0]
                )
                pending_durable = int(
                    self._db.execute(
                        """
                        SELECT COUNT(*)
                        FROM counterfactual_observations
                        WHERE completed_at IS NULL
                        """
                    ).fetchone()[0]
                )

        return {
            "state": "READY",
            "size": self.size,
            "max_entries": self.max_entries,
            "completed_size": len(self._completed),
            "outcome_size": len(outcomes),
            "outcome_counts": outcome_counts,
            "horizon_seconds": self.horizon_seconds,
            "ttl_seconds": self.ttl_seconds,
            "evicted_count": self.evicted_count,
            "expired_count": self.expired_count,
            "evaluated_count": self.evaluated_count,
            "decision_history_count": decision_count,
            "pending_durable_count": pending_durable,
            "bounded": True,
            "ram_only": self._db is None,
            "db_write": self._db is not None,
            "durable_tracking": self._db is not None,
            "durable_horizons_seconds": tuple(
                seconds
                for seconds, _
                in self._durable_horizons
            ),
            "reevaluation_window_seconds": (
                DECISION_CHECKPOINT_SECONDS
            ),
            "permanent_reject": False,
            "decision_history_timestamped": True,
            "external_fetch": False,
            "provider_call": False,
            "outcome_scope": "PRICE_DIRECTION_ONLY",
            "missed_opportunity_means_net_profit": False,
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
