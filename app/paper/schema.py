PAPER_SCHEMA_VERSION = 1

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
    dex TEXT
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


def ensure_paper_schema(conn):
    current = conn.execute(
        "PRAGMA user_version"
    ).fetchone()[0]

    if current > PAPER_SCHEMA_VERSION:
        raise RuntimeError(
            "paper schema newer than application"
        )

    conn.execute(PAPER_TRADES_SCHEMA)

    for sql in INDEXES:
        conn.execute(sql)

    columns = {
        row[1]
        for row in conn.execute(
            "PRAGMA table_info(paper_trades)"
        ).fetchall()
    }

    required = {
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
    }

    missing = sorted(required - columns)

    if missing:
        raise RuntimeError(
            f"paper schema missing columns: {missing}"
        )

    if current < PAPER_SCHEMA_VERSION:
        conn.execute(
            f"PRAGMA user_version={PAPER_SCHEMA_VERSION}"
        )

    conn.commit()

    return {
        "state": "READY",
        "schema_version": PAPER_SCHEMA_VERSION,
        "columns": sorted(columns),
    }
