from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SUMMARY_KEY = "PHASE9_PANEL_DETAIL"
DEFAULT_DETAIL_LIMIT = 12
DETAIL_COLUMN = "wallet_details_json"

TRIGGER_NAMES = (
    "phase9_panel_detail_wallet_insert",
    "phase9_panel_detail_wallet_update",
    "phase9_panel_detail_success_insert",
    "phase9_panel_detail_success_update",
    "phase9_panel_detail_whale_insert",
    "phase9_panel_detail_whale_update",
)

REQUIRED_TABLES = (
    "wallet_discovery_registry",
    "wallet_success_score",
    "whale_activity_snapshot",
)


def _columns(connection: sqlite3.Connection, table: str) -> set[str]:
    return {
        str(row[1])
        for row in connection.execute(
            f'PRAGMA table_info("{table}")'
        ).fetchall()
    }


def _ensure_summary_schema(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS intelligence_summary_readmodel (
            summary_key TEXT PRIMARY KEY,
            generated_at TEXT,
            tracked_wallets INTEGER,
            active_wallets INTEGER,
            successful_wallets INTEGER,
            active_whales INTEGER,
            dominant_pattern TEXT,
            dominant_direction TEXT,
            wallets_involved INTEGER,
            vezir_summary TEXT
        )
        """
    )

    if DETAIL_COLUMN not in _columns(
        connection,
        "intelligence_summary_readmodel",
    ):
        connection.execute(
            "ALTER TABLE intelligence_summary_readmodel "
            "ADD COLUMN wallet_details_json TEXT"
        )


def _verify_bridge_tables(connection: sqlite3.Connection) -> None:
    existing = {
        str(row[0])
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }

    missing = [name for name in REQUIRED_TABLES if name not in existing]
    if missing:
        raise RuntimeError(
            "Phase 9 panel bridge tables missing: " + ", ".join(missing)
        )


def _detail_rows(
    connection: sqlite3.Connection,
    *,
    limit: int = DEFAULT_DETAIL_LIMIT,
) -> list[dict[str, Any]]:
    rows = connection.execute(
        """
        WITH registry AS (
            SELECT
                lower(wallet_uid) AS wallet_key,
                MIN(wallet_uid) AS wallet_uid,
                MAX(chain) AS chain,
                MAX(address) AS address,
                MIN(first_seen_at) AS first_seen_at,
                MAX(last_seen_at) AS last_seen_at,
                'TRANSACTION_FROM_ONLY' AS discovery_source
            FROM wallet_discovery_registry
            WHERE UPPER(COALESCE(discovery_source, '')) = 'TRANSACTION_FROM_ONLY'
              AND COALESCE(wallet_uid, '') <> ''
            GROUP BY lower(wallet_uid)
            ORDER BY MAX(COALESCE(last_seen_at, first_seen_at, 0)) DESC
            LIMIT ?
        )
        SELECT
            registry.wallet_uid,
            registry.chain,
            registry.address,
            registry.first_seen_at,
            registry.last_seen_at,
            registry.discovery_source,
            COALESCE(
                (
                    SELECT UPPER(NULLIF(TRIM(s.qualification_state), ''))
                    FROM wallet_success_score AS s
                    WHERE lower(s.wallet_uid) = registry.wallet_key
                    ORDER BY COALESCE(s.calculated_at, 0) DESC, s.rowid DESC
                    LIMIT 1
                ),
                'UNKNOWN'
            ) AS success_state,
            (
                SELECT s.sample_depth
                FROM wallet_success_score AS s
                WHERE lower(s.wallet_uid) = registry.wallet_key
                ORDER BY COALESCE(s.calculated_at, 0) DESC, s.rowid DESC
                LIMIT 1
            ) AS success_sample_depth,
            COALESCE(
                (
                    SELECT UPPER(NULLIF(TRIM(w.whale_state), ''))
                    FROM whale_activity_snapshot AS w
                    WHERE lower(w.wallet_uid) = registry.wallet_key
                    ORDER BY COALESCE(w.generated_at, 0) DESC, w.rowid DESC
                    LIMIT 1
                ),
                'UNKNOWN'
            ) AS whale_state,
            COALESCE(
                (
                    SELECT UPPER(NULLIF(TRIM(w.direction), ''))
                    FROM whale_activity_snapshot AS w
                    WHERE lower(w.wallet_uid) = registry.wallet_key
                    ORDER BY COALESCE(w.generated_at, 0) DESC, w.rowid DESC
                    LIMIT 1
                ),
                'UNKNOWN'
            ) AS whale_direction
        FROM registry
        ORDER BY COALESCE(last_seen_at, first_seen_at, 0) DESC
        """,
        (max(1, min(int(limit), DEFAULT_DETAIL_LIMIT)),),
    ).fetchall()

    return [dict(row) for row in rows]


def _counts(connection: sqlite3.Connection) -> dict[str, int]:
    tracked = int(
        connection.execute(
            """
            SELECT COUNT(DISTINCT lower(wallet_uid))
            FROM wallet_discovery_registry
            WHERE UPPER(COALESCE(discovery_source, ''))='TRANSACTION_FROM_ONLY'
              AND COALESCE(wallet_uid, '') <> ''
            """
        ).fetchone()[0]
        or 0
    )

    active = int(
        connection.execute(
            """
            SELECT COUNT(DISTINCT lower(wallet_uid))
            FROM wallet_discovery_registry
            WHERE UPPER(COALESCE(discovery_source, ''))='TRANSACTION_FROM_ONLY'
              AND UPPER(COALESCE(lifecycle_state, 'ACTIVE'))='ACTIVE'
              AND COALESCE(wallet_uid, '') <> ''
            """
        ).fetchone()[0]
        or 0
    )

    successful = int(
        connection.execute(
            """
            SELECT COUNT(DISTINCT lower(wallet_uid))
            FROM wallet_success_score
            WHERE UPPER(COALESCE(qualification_state, ''))='SUCCESSFUL'
              AND COALESCE(wallet_uid, '') <> ''
            """
        ).fetchone()[0]
        or 0
    )

    whales = int(
        connection.execute(
            """
            SELECT COUNT(DISTINCT lower(wallet_uid))
            FROM whale_activity_snapshot
            WHERE UPPER(COALESCE(whale_state, '')) NOT IN ('', 'UNKNOWN', 'NONE')
              AND COALESCE(wallet_uid, '') <> ''
            """
        ).fetchone()[0]
        or 0
    )

    return {
        "tracked_wallets": tracked,
        "active_wallets": active,
        "successful_wallets": successful,
        "active_whales": whales,
    }


def _write_summary(connection: sqlite3.Connection) -> dict[str, Any]:
    details = _detail_rows(connection)
    counts = _counts(connection)
    generated_at = datetime.now(timezone.utc).isoformat()

    connection.execute(
        "DELETE FROM intelligence_summary_readmodel WHERE summary_key=?",
        (SUMMARY_KEY,),
    )

    connection.execute(
        """
        INSERT INTO intelligence_summary_readmodel(
            summary_key,
            generated_at,
            tracked_wallets,
            active_wallets,
            successful_wallets,
            active_whales,
            dominant_pattern,
            dominant_direction,
            wallets_involved,
            vezir_summary,
            wallet_details_json
        )
        VALUES(?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            SUMMARY_KEY,
            generated_at,
            counts["tracked_wallets"],
            counts["active_wallets"],
            counts["successful_wallets"],
            counts["active_whales"],
            "PHASE9_WALLET_TRACKING",
            "UNKNOWN",
            counts["tracked_wallets"],
            "",
            json.dumps(
                details,
                sort_keys=True,
                separators=(",", ":"),
                default=str,
            ),
        ),
    )

    return {
        **counts,
        "detail_rows": len(details),
        "generated_at": generated_at,
    }


def _sql_detail_json() -> str:
    return """
    COALESCE(
        (
            WITH registry AS (
                SELECT
                    lower(wallet_uid) AS wallet_key,
                    MIN(wallet_uid) AS wallet_uid,
                    MAX(chain) AS chain,
                    MAX(address) AS address,
                    MIN(first_seen_at) AS first_seen_at,
                    MAX(last_seen_at) AS last_seen_at,
                    'TRANSACTION_FROM_ONLY' AS discovery_source
                FROM wallet_discovery_registry
                WHERE UPPER(COALESCE(discovery_source, ''))='TRANSACTION_FROM_ONLY'
                  AND COALESCE(wallet_uid, '') <> ''
                GROUP BY lower(wallet_uid)
                ORDER BY MAX(COALESCE(last_seen_at, first_seen_at, 0)) DESC
                LIMIT 12
            ),
            details AS (
                SELECT
                    registry.wallet_uid,
                    registry.chain,
                    registry.address,
                    registry.first_seen_at,
                    registry.last_seen_at,
                    registry.discovery_source,
                    COALESCE(
                        (
                            SELECT UPPER(NULLIF(TRIM(s.qualification_state), ''))
                            FROM wallet_success_score AS s
                            WHERE lower(s.wallet_uid)=registry.wallet_key
                            ORDER BY COALESCE(s.calculated_at, 0) DESC, s.rowid DESC
                            LIMIT 1
                        ),
                        'UNKNOWN'
                    ) AS success_state,
                    (
                        SELECT s.sample_depth
                        FROM wallet_success_score AS s
                        WHERE lower(s.wallet_uid)=registry.wallet_key
                        ORDER BY COALESCE(s.calculated_at, 0) DESC, s.rowid DESC
                        LIMIT 1
                    ) AS success_sample_depth,
                    COALESCE(
                        (
                            SELECT UPPER(NULLIF(TRIM(w.whale_state), ''))
                            FROM whale_activity_snapshot AS w
                            WHERE lower(w.wallet_uid)=registry.wallet_key
                            ORDER BY COALESCE(w.generated_at, 0) DESC, w.rowid DESC
                            LIMIT 1
                        ),
                        'UNKNOWN'
                    ) AS whale_state,
                    COALESCE(
                        (
                            SELECT UPPER(NULLIF(TRIM(w.direction), ''))
                            FROM whale_activity_snapshot AS w
                            WHERE lower(w.wallet_uid)=registry.wallet_key
                            ORDER BY COALESCE(w.generated_at, 0) DESC, w.rowid DESC
                            LIMIT 1
                        ),
                        'UNKNOWN'
                    ) AS whale_direction
                FROM registry
                ORDER BY COALESCE(last_seen_at, first_seen_at, 0) DESC
            )
            SELECT json_group_array(
                json_object(
                    'wallet_uid', wallet_uid,
                    'chain', chain,
                    'address', address,
                    'first_seen_at', first_seen_at,
                    'last_seen_at', last_seen_at,
                    'discovery_source', discovery_source,
                    'success_state', success_state,
                    'success_sample_depth', success_sample_depth,
                    'whale_state', whale_state,
                    'whale_direction', whale_direction
                )
            )
            FROM details
        ),
        '[]'
    )
    """.strip()


def _summary_trigger_body() -> str:
    detail_json = _sql_detail_json()
    return f"""
        DELETE FROM intelligence_summary_readmodel
        WHERE summary_key='{SUMMARY_KEY}';

        INSERT INTO intelligence_summary_readmodel(
            summary_key,
            generated_at,
            tracked_wallets,
            active_wallets,
            successful_wallets,
            active_whales,
            dominant_pattern,
            dominant_direction,
            wallets_involved,
            vezir_summary,
            wallet_details_json
        )
        VALUES(
            '{SUMMARY_KEY}',
            strftime('%Y-%m-%dT%H:%M:%fZ', 'now'),
            (
                SELECT COUNT(DISTINCT lower(wallet_uid))
                FROM wallet_discovery_registry
                WHERE UPPER(COALESCE(discovery_source, ''))='TRANSACTION_FROM_ONLY'
                  AND COALESCE(wallet_uid, '') <> ''
            ),
            (
                SELECT COUNT(DISTINCT lower(wallet_uid))
                FROM wallet_discovery_registry
                WHERE UPPER(COALESCE(discovery_source, ''))='TRANSACTION_FROM_ONLY'
                  AND UPPER(COALESCE(lifecycle_state, 'ACTIVE'))='ACTIVE'
                  AND COALESCE(wallet_uid, '') <> ''
            ),
            (
                SELECT COUNT(DISTINCT lower(wallet_uid))
                FROM wallet_success_score
                WHERE UPPER(COALESCE(qualification_state, ''))='SUCCESSFUL'
                  AND COALESCE(wallet_uid, '') <> ''
            ),
            (
                SELECT COUNT(DISTINCT lower(wallet_uid))
                FROM whale_activity_snapshot
                WHERE UPPER(COALESCE(whale_state, '')) NOT IN ('', 'UNKNOWN', 'NONE')
                  AND COALESCE(wallet_uid, '') <> ''
            ),
            'PHASE9_WALLET_TRACKING',
            'UNKNOWN',
            (
                SELECT COUNT(DISTINCT lower(wallet_uid))
                FROM wallet_discovery_registry
                WHERE UPPER(COALESCE(discovery_source, ''))='TRANSACTION_FROM_ONLY'
                  AND COALESCE(wallet_uid, '') <> ''
            ),
            '',
            {detail_json}
        );
    """


def _install_triggers(connection: sqlite3.Connection) -> None:
    body = _summary_trigger_body()
    specs = (
        (TRIGGER_NAMES[0], "INSERT", "wallet_discovery_registry"),
        (TRIGGER_NAMES[1], "UPDATE", "wallet_discovery_registry"),
        (TRIGGER_NAMES[2], "INSERT", "wallet_success_score"),
        (TRIGGER_NAMES[3], "UPDATE", "wallet_success_score"),
        (TRIGGER_NAMES[4], "INSERT", "whale_activity_snapshot"),
        (TRIGGER_NAMES[5], "UPDATE", "whale_activity_snapshot"),
    )

    for name, event, table in specs:
        connection.execute(f"DROP TRIGGER IF EXISTS {name}")
        connection.executescript(
            f"""
            CREATE TRIGGER {name}
            AFTER {event} ON {table}
            BEGIN
                {body}
            END;
            """
        )


def apply_phase9_panel_detail(
    db_path: str | Path,
) -> dict[str, Any]:
    path = Path(db_path)
    if not path.exists():
        raise FileNotFoundError(path)

    connection = sqlite3.connect(str(path), timeout=30)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA busy_timeout=30000")

    try:
        _verify_bridge_tables(connection)
        _ensure_summary_schema(connection)
        summary = _write_summary(connection)
        _install_triggers(connection)
        connection.commit()

        trigger_count = int(
            connection.execute(
                """
                SELECT COUNT(*)
                FROM sqlite_master
                WHERE type='trigger'
                  AND name IN (?,?,?,?,?,?)
                """,
                TRIGGER_NAMES,
            ).fetchone()[0]
            or 0
        )

        row = connection.execute(
            """
            SELECT wallet_details_json
            FROM intelligence_summary_readmodel
            WHERE summary_key=?
            """,
            (SUMMARY_KEY,),
        ).fetchone()

        detail_rows = []
        if row is not None:
            try:
                parsed = json.loads(row[0] or "[]")
                if isinstance(parsed, list):
                    detail_rows = parsed
            except (TypeError, ValueError, json.JSONDecodeError):
                detail_rows = []

        return {
            "state": "READY",
            **summary,
            "detail_rows": len(detail_rows),
            "triggers_installed": trigger_count,
            "detail_limit": DEFAULT_DETAIL_LIMIT,
            "panel_read_only": True,
            "decision_authority": False,
            "paper_authority": False,
            "live_authority": False,
            "wallet_authority": False,
            "signing_authority": False,
            "execution_authority": False,
        }
    finally:
        connection.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="data/paper_trades.db")
    args = parser.parse_args()

    result = apply_phase9_panel_detail(args.db)

    print("PHASE9_PANEL_DETAIL_STATE=" + str(result["state"]))
    print("DETAIL_ROWS=" + str(result["detail_rows"]))
    print("TRACKED_WALLETS=" + str(result["tracked_wallets"]))
    print("SUCCESSFUL_WALLETS=" + str(result["successful_wallets"]))
    print("ACTIVE_WHALES=" + str(result["active_whales"]))
    print("DETAIL_TRIGGERS=" + str(result["triggers_installed"]))
    print("PANEL_READ_ONLY=true")
    print("PHASE9_PANEL_DETAIL=PASS")


if __name__ == "__main__":
    main()
