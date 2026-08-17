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
    net_pnl_usdt REAL
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
)

UNIQUE_OPEN_INDEX = """
CREATE UNIQUE INDEX IF NOT EXISTS
idx_paper_trades_one_open_per_token
ON paper_trades(lower(token))
WHERE status='OPEN'
  AND token IS NOT NULL
"""

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
    "buy_tax",
    "sell_tax",
    "swap_fee",
    "slippage",
    "mev",
    "close_reason",
    "status",
    "token_amount",
    "pool",
    "dex",
    "opening_context_json",

    "paper_account_version",
    "entry_amount_usdt",
    "risk_amount_usdt",
    "capital_before_usdt",
    "capital_after_entry_usdt",
    "position_size_pct",
    "sizing_reason",
    "gross_pnl_usdt",
    "net_pnl_usdt",
}


def _duplicate_open_groups(conn):
    return conn.execute(
        """
        SELECT lower(token), COUNT(*)
        FROM paper_trades
        WHERE status='OPEN'
          AND token IS NOT NULL
        GROUP BY lower(token)
        HAVING COUNT(*) > 1
        ORDER BY COUNT(*) DESC
        """
    ).fetchall()


def _verify_columns(conn):
    columns = {
        row[1]
        for row in conn.execute(
            "PRAGMA table_info(paper_trades)"
        ).fetchall()
    }

    missing = sorted(
        REQUIRED_COLUMNS - columns
    )

    if missing:
        raise RuntimeError(
            "paper schema missing columns: "
            f"{missing}"
        )

    return columns


def _migrate_to_v2(conn):
    duplicates = _duplicate_open_groups(conn)

    if duplicates:
        count = sum(
            int(row[1])
            for row in duplicates
        )

        raise RuntimeError(
            "paper schema migration blocked: "
            "duplicate OPEN positions exist "
            f"groups={len(duplicates)} "
            f"rows={count}"
        )

    conn.execute(UNIQUE_OPEN_INDEX)


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


def _migrate_to_v3(conn):
    columns = {
        row[1]
        for row in conn.execute(
            "PRAGMA table_info(paper_trades)"
        ).fetchall()
    }

    for name, column_type in V3_COLUMNS.items():
        if name not in columns:
            conn.execute(
                "ALTER TABLE paper_trades "
                f"ADD COLUMN {name} {column_type}"
            )


def ensure_paper_schema(conn):
    current = conn.execute(
        "PRAGMA user_version"
    ).fetchone()[0]

    if current > PAPER_SCHEMA_VERSION:
        raise RuntimeError(
            "paper schema newer than application"
        )

    savepoint = "paper_schema_upgrade"

    conn.execute(
        f"SAVEPOINT {savepoint}"
    )

    try:
        conn.execute(PAPER_TRADES_SCHEMA)

        for sql in INDEXES:
            conn.execute(sql)

        columns_before = {
            row[1]
            for row in conn.execute(
                "PRAGMA table_info(paper_trades)"
            ).fetchall()
        }

        if "opening_context_json" not in columns_before:
            conn.execute(
                "ALTER TABLE paper_trades "
                "ADD COLUMN opening_context_json TEXT"
            )

        if current < 2:
            _migrate_to_v2(conn)
        else:
            conn.execute(UNIQUE_OPEN_INDEX)

        if current < 3:
            _migrate_to_v3(conn)

        columns = _verify_columns(conn)

        conn.execute(
            f"PRAGMA user_version="
            f"{PAPER_SCHEMA_VERSION}"
        )

        conn.execute(
            f"RELEASE SAVEPOINT {savepoint}"
        )

        conn.commit()

    except Exception:
        conn.execute(
            f"ROLLBACK TO SAVEPOINT {savepoint}"
        )

        conn.execute(
            f"RELEASE SAVEPOINT {savepoint}"
        )

        conn.rollback()
        raise

    return {
        "state": "READY",
        "schema_version": PAPER_SCHEMA_VERSION,
        "columns": sorted(columns),
        "single_open_db_enforced": True,
        "unique_open_index": (
            "idx_paper_trades_one_open_per_token"
        ),
    }
