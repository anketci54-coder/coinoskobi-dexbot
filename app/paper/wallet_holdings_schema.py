from __future__ import annotations


WALLET_HOLDINGS_SCHEMA_VERSION = 1

REQUIRED_TABLES = (
    "wallet_holding_snapshot",
    "wallet_holding_change_evidence",
    "wallet_holding_scan_state",
)


def ensure_wallet_holdings_schema(conn) -> dict[str, object]:
    """Install the bounded Phase 9 holdings persistence schema.

    This schema lives in the canonical paper database but is intentionally
    versioned separately from the paper-trade lifecycle schema. It carries
    observation evidence only and grants no trading authority.
    """
    try:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS wallet_holding_snapshot(
                wallet_uid TEXT NOT NULL,
                token_id TEXT NOT NULL,
                chain TEXT NOT NULL,
                address TEXT NOT NULL,
                token_address TEXT,
                pricing_id TEXT,
                symbol TEXT,
                name TEXT,
                balance REAL NOT NULL,
                value_usd REAL,
                price_usd REAL,
                price_change_24h_pct REAL,
                observed_at REAL NOT NULL,
                provider TEXT NOT NULL,
                PRIMARY KEY(wallet_uid, token_id)
            );
            CREATE INDEX IF NOT EXISTS idx_wallet_holding_snapshot_wallet
            ON wallet_holding_snapshot(wallet_uid, observed_at DESC);

            CREATE TABLE IF NOT EXISTS wallet_holding_change_evidence(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                wallet_uid TEXT NOT NULL,
                token_id TEXT NOT NULL,
                change_type TEXT NOT NULL,
                previous_balance REAL,
                current_balance REAL,
                previous_value_usd REAL,
                current_value_usd REAL,
                observed_at REAL NOT NULL,
                provider TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_wallet_holding_changes_wallet
            ON wallet_holding_change_evidence(wallet_uid, observed_at DESC, id DESC);

            CREATE TABLE IF NOT EXISTS wallet_holding_scan_state(
                wallet_uid TEXT PRIMARY KEY,
                last_scan_at REAL,
                last_success_at REAL,
                last_provider_state TEXT,
                total_value_usd REAL,
                asset_count INTEGER
            );
            """
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise

    existing = {
        str(row[0])
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    missing = [name for name in REQUIRED_TABLES if name not in existing]
    if missing:
        raise RuntimeError(
            "wallet holdings schema missing tables: " + ", ".join(missing)
        )

    return {
        "state": "READY",
        "schema_version": WALLET_HOLDINGS_SCHEMA_VERSION,
        "tables": list(REQUIRED_TABLES),
        "decision_authority": False,
        "paper_authority": False,
        "live_authority": False,
        "wallet_authority": False,
        "signing_authority": False,
        "execution_authority": False,
    }
