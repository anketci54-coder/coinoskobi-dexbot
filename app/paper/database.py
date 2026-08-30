import os
import sqlite3
import threading

from datetime import (
    datetime,
    timezone,
)

from pathlib import Path

from app.paper.schema import (
    ensure_paper_schema,
)

from app.risk.paper_position_sizing import (
    PAPER_CAPITAL_USDT,
    paper_available_capital_usdt,
)


DB = Path(
    os.getenv(
        "COINOSKOBI_PAPER_DB",
        "data/paper_trades.db",
    )
)


class PaperDatabase:
    _instance = None
    _initialized = False
    _db_lock = (
        threading.RLock()
    )

    def __new__(cls):
        with cls._db_lock:
            if cls._instance is None:
                cls._instance = (
                    super().__new__(
                        cls
                    )
                )

            return cls._instance

    def __init__(self):
        with self._db_lock:
            if (
                self.__class__._initialized
            ):
                return

            DB.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            self.conn = (
                sqlite3.connect(
                    DB,
                    timeout=30,
                    check_same_thread=False,
                )
            )

            self.conn.row_factory = (
                sqlite3.Row
            )

            self.conn.execute(
                "PRAGMA journal_mode=WAL;"
            )

            self.conn.execute(
                "PRAGMA foreign_keys=ON;"
            )

            self.conn.execute(
                "PRAGMA busy_timeout=30000;"
            )

            self.conn.execute(
                "PRAGMA synchronous=NORMAL;"
            )

            ensure_paper_schema(
                self.conn
            )

            self.__class__._initialized = True

    def has_open_position(
        self,
        token,
    ):
        with self._db_lock:
            row = self.conn.execute(
                """
                SELECT 1
                FROM paper_trades
                WHERE lower(token)=lower(?)
                  AND status='OPEN'
                LIMIT 1
                """,
                (
                    token,
                ),
            ).fetchone()

            return (
                row is not None
            )

    def has_trade_history(
        self,
        token,
    ):
        with self._db_lock:
            row = self.conn.execute(
                """
                SELECT 1
                FROM paper_trades
                WHERE lower(token)=lower(?)
                LIMIT 1
                """,
                (
                    token,
                ),
            ).fetchone()

            return (
                row is not None
            )

    def _insert_unlocked(
        self,
        trade,
    ):
        trade = dict(
            trade
            or {}
        )

        if not trade.get(
            "created_at"
        ):
            trade[
                "created_at"
            ] = (
                datetime.now(
                    timezone.utc
                ).isoformat()
            )

        cols = ",".join(
            trade.keys()
        )

        vals = ",".join(
            "?"
            * len(trade)
        )

        self.conn.execute(
            f"INSERT INTO "
            f"paper_trades "
            f"({cols}) "
            f"VALUES ({vals})",
            tuple(
                trade.values()
            ),
        )

    def insert(
        self,
        trade,
    ):
        with self._db_lock:
            self._insert_unlocked(
                trade
            )

            self.conn.commit()

    def insert_if_no_open_position(
        self,
        trade,
    ):
        return (
            self.insert_if_below_open_limit(
                trade,
                2 ** 31 - 1,
            )
        )

    def insert_if_below_open_limit(
        self,
        trade,
        max_open_positions,
    ):
        token = (
            trade
            or {}
        ).get(
            "token"
        )

        if not token:
            raise ValueError(
                "trade token is required"
            )

        limit = max(
            1,
            int(
                max_open_positions
            ),
        )

        with self._db_lock:
            try:
                self.conn.execute(
                    "BEGIN IMMEDIATE"
                )

                duplicate = (
                    self.conn.execute(
                        """
                        SELECT 1
                        FROM paper_trades
                        WHERE lower(token)=lower(?)
                        LIMIT 1
                        """,
                        (
                            token,
                        ),
                    )
                    .fetchone()
                )

                if (
                    duplicate
                    is not None
                ):
                    self.conn.rollback()
                    return False

                opened = (
                    self.conn.execute(
                        """
                        SELECT COUNT(*)
                        FROM paper_trades
                        WHERE status='OPEN'
                        """
                    )
                    .fetchone()[0]
                )

                if opened >= limit:
                    self.conn.rollback()
                    return False

                if (
                    str(
                        trade.get(
                            "paper_account_version"
                        )
                        or ""
                    ).upper()
                    == "PAPER_10K_V2"
                    and str(
                        trade.get(
                            "status"
                        )
                        or ""
                    ).upper()
                    == "OPEN"
                ):
                    try:
                        requested_entry = float(
                            trade.get(
                                "entry_amount_usdt"
                            )
                            or 0.0
                        )
                    except (
                        TypeError,
                        ValueError,
                    ):
                        requested_entry = 0.0

                    free_capital = (
                        paper_available_capital_usdt(
                            self.conn,
                            PAPER_CAPITAL_USDT,
                        )
                    )

                    if (
                        requested_entry <= 0
                        or requested_entry
                        > free_capital + 1e-9
                    ):
                        self.conn.rollback()
                        return False

                self._insert_unlocked(
                    trade
                )

                self.conn.commit()

                return True

            except sqlite3.IntegrityError:
                self.conn.rollback()
                return False

            except Exception:
                self.conn.rollback()
                raise

    def open_positions(self):
        with self._db_lock:
            rows = (
                self.conn.execute(
                    """
                    SELECT *
                    FROM paper_trades
                    WHERE status='OPEN'
                    ORDER BY id
                    """
                )
                .fetchall()
            )

            return [
                dict(row)
                for row in rows
            ]

    def closed_positions(
        self,
        after_id=0,
    ):
        with self._db_lock:
            rows = (
                self.conn.execute(
                    """
                    SELECT *
                    FROM paper_trades
                    WHERE status='CLOSED'
                      AND id > ?
                    ORDER BY id
                    """,
                    (
                        int(
                            after_id
                            or 0
                        ),
                    ),
                )
                .fetchall()
            )

            return [
                dict(row)
                for row in rows
            ]

    def update_position(
        self,
        trade_id,
        values,
    ):
        values = dict(
            values
            or {}
        )

        if not values:
            return

        with self._db_lock:
            sql = ",".join(
                f"{key}=?"
                for key
                in values
            )

            self.conn.execute(
                f"UPDATE paper_trades "
                f"SET {sql} "
                f"WHERE id=?",
                [
                    *values.values(),
                    trade_id,
                ],
            )

            self.conn.commit()

    def close_position(
        self,
        trade_id,
        values=None,
    ):
        values = dict(
            values
            or {}
        )

        values[
            "status"
        ] = "CLOSED"

        with self._db_lock:
            sql = ",".join(
                f"{key}=?"
                for key
                in values
            )

            cur = self.conn.execute(
                f"UPDATE paper_trades "
                f"SET {sql} "
                f"WHERE id=? "
                f"AND status='OPEN'",
                [
                    *values.values(),
                    trade_id,
                ],
            )

            self.conn.commit()

            return (
                cur.rowcount == 1
            )

    def record_price_observation(
        self,
        position_id,
        price,
    ):
        observed_at = (
            datetime.now(
                timezone.utc
            ).isoformat()
        )

        with self._db_lock:
            self.conn.execute(
                """
                INSERT INTO
                paper_price_observations(
                    position_id,
                    observed_at,
                    price
                )
                VALUES (?, ?, ?)
                """,
                (
                    int(
                        position_id
                    ),
                    observed_at,
                    float(price),
                ),
            )

            self.conn.commit()

    def price_observations(
        self,
        position_id,
    ):
        with self._db_lock:
            rows = (
                self.conn.execute(
                    """
                    SELECT price
                    FROM paper_price_observations
                    WHERE position_id=?
                    ORDER BY id
                    """,
                    (
                        int(
                            position_id
                        ),
                    ),
                )
                .fetchall()
            )

            return [
                float(
                    row[0]
                )
                for row
                in rows
            ]

    def apply_partial_realization(
        self,
        trade_id,
        *,
        stage,
        price,
        realization,
        math_state_json,
    ):
        import math

        if stage not in {
            "TP1",
            "TP2",
        }:
            return False

        if not isinstance(
            realization,
            dict,
        ):
            return False

        try:
            price = float(price)
            fraction = float(
                realization[
                    "fraction"
                ]
            )
            supplied_sold = float(
                realization[
                    "sold_tokens"
                ]
            )
            supplied_remaining = float(
                realization[
                    "remaining_tokens"
                ]
            )
            supplied_gross = float(
                realization[
                    "gross_proceeds_usdt"
                ]
            )
            supplied_net = float(
                realization[
                    "net_proceeds_usdt"
                ]
            )
            supplied_sold_basis = float(
                realization[
                    "sold_cost_basis_usdt"
                ]
            )
            supplied_remaining_basis = float(
                realization[
                    "remaining_cost_basis_usdt"
                ]
            )
            supplied_pnl = float(
                realization[
                    "realized_pnl_usdt"
                ]
            )
        except (
            KeyError,
            TypeError,
            ValueError,
        ):
            return False

        numeric = (
            price,
            fraction,
            supplied_sold,
            supplied_remaining,
            supplied_gross,
            supplied_net,
            supplied_sold_basis,
            supplied_remaining_basis,
            supplied_pnl,
        )

        if not all(
            math.isfinite(value)
            for value in numeric
        ):
            return False

        if (
            price <= 0
            or fraction <= 0
            or fraction > 1
        ):
            return False

        def same(left, right):
            return math.isclose(
                float(left),
                float(right),
                rel_tol=1e-12,
                abs_tol=1e-12,
            )

        now = (
            datetime.now(
                timezone.utc
            ).isoformat()
        )

        with self._db_lock:
            try:
                self.conn.execute(
                    "BEGIN IMMEDIATE"
                )

                row = (
                    self.conn.execute(
                        """
                        SELECT *
                        FROM paper_trades
                        WHERE id=?
                          AND status='OPEN'
                        """,
                        (
                            int(
                                trade_id
                            ),
                        ),
                    )
                    .fetchone()
                )

                if row is None:
                    self.conn.rollback()
                    return False

                stage_column = (
                    "tp1_done"
                    if stage == "TP1"
                    else "tp2_done"
                )

                if int(
                    row[
                        stage_column
                    ]
                    or 0
                ):
                    self.conn.rollback()
                    return False

                current_tokens = float(
                    row[
                        "token_amount"
                    ]
                    or 0.0
                )

                stored_basis = row[
                    "remaining_cost_basis_usdt"
                ]

                current_basis = float(
                    (
                        row[
                            "entry_amount_usdt"
                        ]
                        or 0.0
                    )
                    if stored_basis is None
                    else stored_basis
                )

                if (
                    current_tokens <= 0
                    or current_basis < 0
                ):
                    self.conn.rollback()
                    return False

                expected_sold = (
                    current_tokens
                    * fraction
                )

                expected_remaining = (
                    current_tokens
                    - expected_sold
                )

                expected_sold_basis = (
                    current_basis
                    * fraction
                )

                expected_remaining_basis = (
                    current_basis
                    - expected_sold_basis
                )

                expected_gross = (
                    expected_sold
                    * price
                )

                expected_pnl = (
                    supplied_net
                    - expected_sold_basis
                )

                conservation_ok = (
                    supplied_sold
                    <= current_tokens
                    and expected_remaining >= 0
                    and same(
                        supplied_sold,
                        expected_sold,
                    )
                    and same(
                        supplied_remaining,
                        expected_remaining,
                    )
                    and same(
                        supplied_sold_basis,
                        expected_sold_basis,
                    )
                    and same(
                        supplied_remaining_basis,
                        expected_remaining_basis,
                    )
                    and same(
                        supplied_gross,
                        expected_gross,
                    )
                    and same(
                        supplied_pnl,
                        expected_pnl,
                    )
                )

                if not conservation_ok:
                    self.conn.rollback()
                    return False

                realized_gross = (
                    float(
                        row[
                            "realized_gross_proceeds_usdt"
                        ]
                        or 0.0
                    )
                    + expected_gross
                )

                realized_net = (
                    float(
                        row[
                            "realized_proceeds_usdt"
                        ]
                        or 0.0
                    )
                    + supplied_net
                )

                realized_pnl = (
                    float(
                        row[
                            "realized_pnl_usdt"
                        ]
                        or 0.0
                    )
                    + expected_pnl
                )

                runner_active = (
                    1
                    if stage == "TP2"
                    else int(
                        row[
                            "runner_active"
                        ]
                        or 0
                    )
                )

                self.conn.execute(
                    f"""
                    UPDATE paper_trades
                    SET
                        token_amount=?,
                        remaining_cost_basis_usdt=?,
                        realized_gross_proceeds_usdt=?,
                        realized_proceeds_usdt=?,
                        realized_pnl_usdt=?,
                        {stage_column}=1,
                        runner_active=?,
                        math_state_json=?,
                        current_price=?
                    WHERE id=?
                      AND status='OPEN'
                    """,
                    (
                        expected_remaining,
                        expected_remaining_basis,
                        realized_gross,
                        realized_net,
                        realized_pnl,
                        runner_active,
                        math_state_json,
                        price,
                        int(
                            trade_id
                        ),
                    ),
                )

                self.conn.execute(
                    """
                    INSERT INTO
                    paper_realizations(
                        position_id,
                        stage,
                        observed_at,
                        price,
                        token_amount,
                        close_fraction,
                        gross_proceeds_usdt,
                        net_proceeds_usdt,
                        sold_cost_basis_usdt,
                        realized_pnl_usdt
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        int(
                            trade_id
                        ),
                        stage,
                        now,
                        price,
                        expected_sold,
                        fraction,
                        expected_gross,
                        supplied_net,
                        expected_sold_basis,
                        expected_pnl,
                    ),
                )

                self.conn.commit()
                return True

            except Exception:
                self.conn.rollback()
                raise
