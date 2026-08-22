PAPER_SCHEMA_VERSION = 3


PAPER_TRADES_SCHEMA = """
CREATE TABLE IF NOT EXISTS paper_trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT,
    closed_at TEXT,

    token TEXT,
    symbol TEXT,

    entry_price REAL,
    current_price REAL,
    exit_price REAL,
    highest_price REAL,
    lowest_price REAL,

    tp_price REAL,
    sl_price REAL,

    amount_bnb REAL,

    gross_pnl REAL,
    net_pnl REAL,
    roi REAL,

    gas_buy REAL,
    gas_sell REAL,
    swap_fee REAL,
    buy_tax REAL,
    sell_tax REAL,
    slippage REAL,
    mev REAL,

    close_reason TEXT,
    status TEXT,

    token_amount REAL DEFAULT 0,

    pool TEXT,
    dex TEXT,

    opening_context_json TEXT,

    paper_account_version TEXT,

    entry_amount_usdt REAL,
    risk_amount_usdt REAL,

    capital_before_usdt REAL,
    capital_after_entry_usdt REAL,

    position_size_pct REAL,
    sizing_reason TEXT,

    gross_pnl_usdt REAL,
    net_pnl_usdt REAL,

    initial_token_amount REAL,

    remaining_cost_basis_usdt REAL,

    realized_gross_proceeds_usdt REAL DEFAULT 0,
    realized_proceeds_usdt REAL DEFAULT 0,
    realized_pnl_usdt REAL DEFAULT 0,

    tp1_done INTEGER DEFAULT 0,
    tp2_done INTEGER DEFAULT 0,
    runner_active INTEGER DEFAULT 0,

    mathematical_plan_json TEXT,
    math_state_json TEXT,

    cost_model_complete INTEGER DEFAULT 0
)
"""


REALIZATIONS_SCHEMA = """
CREATE TABLE IF NOT EXISTS paper_realizations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    position_id INTEGER NOT NULL,

    stage TEXT NOT NULL,

    observed_at TEXT NOT NULL,

    price REAL NOT NULL,

    token_amount REAL NOT NULL,

    close_fraction REAL NOT NULL,

    gross_proceeds_usdt REAL NOT NULL,
    net_proceeds_usdt REAL NOT NULL,

    sold_cost_basis_usdt REAL NOT NULL,

    realized_pnl_usdt REAL NOT NULL,

    FOREIGN KEY(position_id)
    REFERENCES paper_trades(id)
)
"""


OBSERVATIONS_SCHEMA = """
CREATE TABLE IF NOT EXISTS paper_price_observations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    position_id INTEGER NOT NULL,

    observed_at TEXT NOT NULL,

    price REAL NOT NULL,

    FOREIGN KEY(position_id)
    REFERENCES paper_trades(id)
)
"""


INDEXES = (
    """
    CREATE INDEX IF NOT EXISTS
    idx_paper_trades_token_status
    ON paper_trades(token, status)
    """,

    """
    CREATE INDEX IF NOT EXISTS
    idx_paper_trades_status
    ON paper_trades(status)
    """,

    """
    CREATE INDEX IF NOT EXISTS
    idx_paper_realizations_position
    ON paper_realizations(position_id, id)
    """,

    """
    CREATE INDEX IF NOT EXISTS
    idx_paper_price_observations_position
    ON paper_price_observations(position_id, id)
    """,
)


UNIQUE_OPEN_INDEX = """
CREATE UNIQUE INDEX IF NOT EXISTS
idx_paper_trades_one_open_per_token
ON paper_trades(lower(token))
WHERE status='OPEN'
AND token IS NOT NULL
"""


V3_COLUMNS = {
    "paper_account_version": "TEXT",

    "entry_amount_usdt": "REAL",
    "risk_amount_usdt": "REAL",

    "capital_before_usdt": "REAL",
    "capital_after_entry_usdt": "REAL",

    "position_size_pct": "REAL",
    "sizing_reason": "TEXT",

    "gross_pnl_usdt": "REAL",
    "net_pnl_usdt": "REAL",
}


MATHEMATICAL_COLUMNS = {
    "initial_token_amount": "REAL",

    "remaining_cost_basis_usdt": (
        "REAL"
    ),

    "realized_gross_proceeds_usdt": (
        "REAL DEFAULT 0"
    ),

    "realized_proceeds_usdt": (
        "REAL DEFAULT 0"
    ),

    "realized_pnl_usdt": (
        "REAL DEFAULT 0"
    ),

    "tp1_done": (
        "INTEGER DEFAULT 0"
    ),

    "tp2_done": (
        "INTEGER DEFAULT 0"
    ),

    "runner_active": (
        "INTEGER DEFAULT 0"
    ),

    "mathematical_plan_json": (
        "TEXT"
    ),

    "math_state_json": (
        "TEXT"
    ),

    "cost_model_complete": (
        "INTEGER DEFAULT 0"
    ),
}


REQUIRED_COLUMNS = {
    "id",
    "created_at",
    "closed_at",

    "token",
    "symbol",

    "entry_price",
    "current_price",
    "exit_price",
    "highest_price",
    "lowest_price",

    "tp_price",
    "sl_price",

    "amount_bnb",

    "gross_pnl",
    "net_pnl",
    "roi",

    "gas_buy",
    "gas_sell",
    "swap_fee",
    "buy_tax",
    "sell_tax",
    "slippage",
    "mev",

    "close_reason",
    "status",

    "token_amount",

    "pool",
    "dex",

    "opening_context_json",

    *V3_COLUMNS.keys(),
    *MATHEMATICAL_COLUMNS.keys(),
}


def _columns(conn):
    return {
        row[1]
        for row
        in conn.execute(
            "PRAGMA table_info(paper_trades)"
        ).fetchall()
    }


def _add_columns(
    conn,
    mapping,
):
    columns = _columns(
        conn
    )

    for (
        name,
        column_type,
    ) in mapping.items():
        if name not in columns:
            conn.execute(
                "ALTER TABLE paper_trades "
                f"ADD COLUMN {name} "
                f"{column_type}"
            )


def _duplicate_open_groups(
    conn,
):
    return conn.execute(
        """
        SELECT
            lower(token),
            COUNT(*)
        FROM paper_trades
        WHERE status='OPEN'
          AND token IS NOT NULL
        GROUP BY lower(token)
        HAVING COUNT(*) > 1
        """
    ).fetchall()


def _migrate_to_v2(
    conn,
):
    duplicates = (
        _duplicate_open_groups(
            conn
        )
    )

    if duplicates:
        raise RuntimeError(
            "paper schema migration blocked: "
            "duplicate OPEN positions exist"
        )

    conn.execute(
        UNIQUE_OPEN_INDEX
    )


def ensure_paper_schema(
    conn,
):
    current = (
        conn.execute(
            "PRAGMA user_version"
        )
        .fetchone()[0]
    )

    if (
        current
        > PAPER_SCHEMA_VERSION
    ):
        raise RuntimeError(
            "paper schema newer "
            "than application"
        )

    savepoint = (
        "paper_schema_upgrade"
    )

    conn.execute(
        f"SAVEPOINT {savepoint}"
    )

    try:
        conn.execute(
            PAPER_TRADES_SCHEMA
        )

        if (
            "opening_context_json"
            not in _columns(conn)
        ):
            conn.execute(
                "ALTER TABLE paper_trades "
                "ADD COLUMN "
                "opening_context_json TEXT"
            )

        if current < 2:
            _migrate_to_v2(
                conn
            )

        else:
            conn.execute(
                UNIQUE_OPEN_INDEX
            )

        _add_columns(
            conn,
            V3_COLUMNS,
        )

        _add_columns(
            conn,
            MATHEMATICAL_COLUMNS,
        )

        conn.execute(
            REALIZATIONS_SCHEMA
        )

        conn.execute(
            OBSERVATIONS_SCHEMA
        )

        for sql in INDEXES:
            conn.execute(
                sql
            )

        columns = _columns(
            conn
        )

        missing = sorted(
            REQUIRED_COLUMNS
            - columns
        )

        if missing:
            raise RuntimeError(
                "paper schema missing "
                f"columns: {missing}"
            )

        conn.execute(
            "PRAGMA user_version="
            f"{PAPER_SCHEMA_VERSION}"
        )

        conn.execute(
            f"RELEASE SAVEPOINT "
            f"{savepoint}"
        )

        conn.commit()

    except Exception:
        conn.execute(
            f"ROLLBACK TO SAVEPOINT "
            f"{savepoint}"
        )

        conn.execute(
            f"RELEASE SAVEPOINT "
            f"{savepoint}"
        )

        conn.rollback()

        raise

    return {
        "state": "READY",

        "schema_version": (
            PAPER_SCHEMA_VERSION
        ),

        "columns": sorted(
            columns
        ),

        "single_open_db_enforced": True,

        "unique_open_index": (
            "idx_paper_trades_one_open_per_token"
        ),
    }
