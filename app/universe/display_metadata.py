from __future__ import annotations

from datetime import datetime, timezone

from app.universe.schema import canonical_address, canonical_chain, canonical_dex


TABLE = "universe_pool_display_metadata_v1"


def _utc_now():
    return datetime.now(timezone.utc).isoformat()


def _text(value, *, limit):
    value = str(value or "").strip()
    return value[:limit] or None


def ensure_display_metadata_schema(connection):
    with connection:
        connection.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {TABLE}(
                chain TEXT NOT NULL,
                dex TEXT NOT NULL,
                pool TEXT NOT NULL,
                base_token TEXT,
                quote_token TEXT,
                base_symbol TEXT,
                quote_symbol TEXT,
                base_name TEXT,
                quote_name TEXT,
                display_name TEXT,
                source TEXT NOT NULL,
                observed_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY(chain, dex, pool)
            )
            """
        )
        connection.execute(
            f"""
            CREATE INDEX IF NOT EXISTS idx_universe_pool_display_pool
            ON {TABLE}(pool)
            """
        )


def persist_snapshot_display_metadata(connection, snapshots):
    rows = []
    updated_at = _utc_now()

    for raw in snapshots or []:
        row = dict(raw)
        display_name = _text(row.get("display_name"), limit=160)
        base_symbol = _text(row.get("base_symbol"), limit=64)
        quote_symbol = _text(row.get("quote_symbol"), limit=64)
        base_name = _text(row.get("base_name"), limit=128)
        quote_name = _text(row.get("quote_name"), limit=128)

        if display_name is None:
            if base_symbol and quote_symbol:
                display_name = f"{base_symbol} / {quote_symbol}"
            else:
                display_name = base_symbol or quote_symbol

        if not any((display_name, base_symbol, quote_symbol, base_name, quote_name)):
            continue

        rows.append(
            {
                "chain": canonical_chain(row.get("chain", "bsc")),
                "dex": canonical_dex(row["dex"]),
                "pool": canonical_address(row["pool"]),
                "base_token": canonical_address(
                    row.get("base_token"), required=False
                ),
                "quote_token": canonical_address(
                    row.get("quote_token"), required=False
                ),
                "base_symbol": base_symbol,
                "quote_symbol": quote_symbol,
                "base_name": base_name,
                "quote_name": quote_name,
                "display_name": display_name,
                "source": str(row.get("source") or "unknown").strip().lower(),
                "observed_at": str(row.get("observed_at") or updated_at),
                "updated_at": updated_at,
            }
        )

    if not rows:
        return 0

    ensure_display_metadata_schema(connection)

    with connection:
        connection.executemany(
            f"""
            INSERT INTO {TABLE}(
                chain,dex,pool,base_token,quote_token,
                base_symbol,quote_symbol,base_name,quote_name,
                display_name,source,observed_at,updated_at
            ) VALUES(
                :chain,:dex,:pool,:base_token,:quote_token,
                :base_symbol,:quote_symbol,:base_name,:quote_name,
                :display_name,:source,:observed_at,:updated_at
            )
            ON CONFLICT(chain,dex,pool) DO UPDATE SET
                base_token=COALESCE(excluded.base_token,base_token),
                quote_token=COALESCE(excluded.quote_token,quote_token),
                base_symbol=COALESCE(excluded.base_symbol,base_symbol),
                quote_symbol=COALESCE(excluded.quote_symbol,quote_symbol),
                base_name=COALESCE(excluded.base_name,base_name),
                quote_name=COALESCE(excluded.quote_name,quote_name),
                display_name=COALESCE(excluded.display_name,display_name),
                source=excluded.source,
                observed_at=excluded.observed_at,
                updated_at=excluded.updated_at
            """,
            rows,
        )

    return len(rows)


__all__ = [
    "TABLE",
    "ensure_display_metadata_schema",
    "persist_snapshot_display_metadata",
]
