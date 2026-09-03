from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path
from typing import Any


DEFAULT_BACKFILL_LIMIT = 5000
TRIGGER_NAME = "phase9_panel_readmodel_after_decision"

_PRIMARY_PAYLOAD_PATH = (
    "runtime_intelligence",
    "wallet_readmodel",
    "payload",
)
_FALLBACK_PAYLOAD_PATH = (
    "mathematical_plan",
    "market_context",
    "runtime_intelligence",
    "wallet_readmodel",
    "payload",
)


def _nested(value: Any, path: tuple[str, ...]) -> Any:
    current = value
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _payload_from_context(context: Any) -> dict[str, Any] | None:
    if not isinstance(context, dict):
        return None

    for path in (_PRIMARY_PAYLOAD_PATH, _FALLBACK_PAYLOAD_PATH):
        payload = _nested(context, path)
        if not isinstance(payload, dict):
            continue

        wallet_id = str(payload.get("wallet_id") or "").strip().lower()
        identity_source = str(
            payload.get("identity_source") or ""
        ).strip().upper()

        if wallet_id and identity_source == "TRANSACTION_FROM_ONLY":
            return payload

    return None


def _wallet_parts(wallet_id: Any) -> tuple[str, str, str] | None:
    value = str(wallet_id or "").strip().lower()
    if ":" not in value:
        return None

    chain, address = value.split(":", 1)
    chain = chain.strip()
    address = address.strip()

    if not chain or not address:
        return None

    return value, chain, address


def _ensure_readmodel_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS wallet_discovery_registry (
            wallet_uid TEXT PRIMARY KEY,
            chain TEXT,
            address TEXT,
            first_seen_at REAL,
            last_seen_at REAL,
            discovery_source TEXT,
            freshness_state TEXT,
            lifecycle_state TEXT
        );

        CREATE TABLE IF NOT EXISTS wallet_success_score (
            wallet_uid TEXT PRIMARY KEY,
            calculated_at REAL,
            sample_depth INTEGER,
            consistency_score REAL,
            entry_quality_score REAL,
            exit_quality_score REAL,
            loss_control_score REAL,
            risk_adjusted_score REAL,
            freshness_score REAL,
            success_score REAL,
            qualification_state TEXT
        );

        CREATE TABLE IF NOT EXISTS whale_activity_snapshot (
            wallet_uid TEXT PRIMARY KEY,
            generated_at REAL,
            whale_state TEXT,
            direction TEXT,
            activity_score REAL,
            evidence_count INTEGER
        );
        """
    )


def _write_payload(
    connection: sqlite3.Connection,
    payload: dict[str, Any],
    observed_at: Any,
) -> bool:
    parts = _wallet_parts(payload.get("wallet_id"))
    if parts is None:
        return False

    wallet_uid, chain, address = parts

    try:
        timestamp = float(observed_at)
    except (TypeError, ValueError):
        return False

    cursor = connection.execute(
        """
        UPDATE wallet_discovery_registry
        SET last_seen_at=?,
            discovery_source='TRANSACTION_FROM_ONLY',
            freshness_state='FRESH',
            lifecycle_state='ACTIVE'
        WHERE lower(wallet_uid)=lower(?)
        """,
        (timestamp, wallet_uid),
    )

    if int(cursor.rowcount or 0) == 0:
        connection.execute(
            """
            INSERT INTO wallet_discovery_registry(
                wallet_uid,
                chain,
                address,
                first_seen_at,
                last_seen_at,
                discovery_source,
                freshness_state,
                lifecycle_state
            )
            VALUES(?,?,?,?,?,'TRANSACTION_FROM_ONLY','FRESH','ACTIVE')
            """,
            (
                wallet_uid,
                chain,
                address,
                timestamp,
                timestamp,
            ),
        )

    tracking = payload.get("phase9_wallet_tracking")
    tracking = tracking if isinstance(tracking, dict) else {}
    performance = tracking.get("performance")
    performance = performance if isinstance(performance, dict) else {}

    if str(performance.get("state") or "").strip().upper() == "SUCCESSFUL":
        sample_depth = performance.get("realized_sample_size")

        connection.execute(
            """
            UPDATE wallet_success_score
            SET calculated_at=?,
                sample_depth=COALESCE(?, sample_depth),
                qualification_state='SUCCESSFUL'
            WHERE lower(wallet_uid)=lower(?)
            """,
            (timestamp, sample_depth, wallet_uid),
        )

        connection.execute(
            """
            INSERT OR IGNORE INTO wallet_success_score(
                wallet_uid,
                calculated_at,
                sample_depth,
                consistency_score,
                entry_quality_score,
                exit_quality_score,
                loss_control_score,
                risk_adjusted_score,
                freshness_score,
                success_score,
                qualification_state
            )
            SELECT ?,?,?,?,?,?,?,?,?,?,?
            WHERE NOT EXISTS (
                SELECT 1
                FROM wallet_success_score
                WHERE lower(wallet_uid)=lower(?)
            )
            """,
            (
                wallet_uid,
                timestamp,
                sample_depth,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                "SUCCESSFUL",
                wallet_uid,
            ),
        )

    whale_ready = payload.get("whale_value_evidence_ready") is True
    whale_state = str(payload.get("whale_state") or "").strip().upper()

    if whale_ready and whale_state not in {"", "UNKNOWN", "NONE"}:
        direction = str(
            payload.get("whale_direction") or "UNKNOWN"
        ).strip().upper() or "UNKNOWN"

        connection.execute(
            """
            UPDATE whale_activity_snapshot
            SET generated_at=?,
                whale_state=?,
                direction=?
            WHERE lower(wallet_uid)=lower(?)
            """,
            (timestamp, whale_state, direction, wallet_uid),
        )

        connection.execute(
            """
            INSERT OR IGNORE INTO whale_activity_snapshot(
                wallet_uid,
                generated_at,
                whale_state,
                direction,
                activity_score,
                evidence_count
            )
            SELECT ?,?,?,?,?,?
            WHERE NOT EXISTS (
                SELECT 1
                FROM whale_activity_snapshot
                WHERE lower(wallet_uid)=lower(?)
            )
            """,
            (
                wallet_uid,
                timestamp,
                whale_state,
                direction,
                None,
                None,
                wallet_uid,
            ),
        )

    return True


def _backfill(
    connection: sqlite3.Connection,
    *,
    limit: int,
) -> dict[str, int]:
    rows = connection.execute(
        """
        SELECT id, observed_at, context_json
        FROM candidate_decision_history
        ORDER BY id DESC
        LIMIT ?
        """,
        (max(1, int(limit)),),
    ).fetchall()

    scanned = 0
    accepted = 0

    for row in reversed(rows):
        scanned += 1

        try:
            context = json.loads(row["context_json"] or "{}")
        except (TypeError, ValueError, json.JSONDecodeError):
            continue

        payload = _payload_from_context(context)
        if payload is None:
            continue

        if _write_payload(connection, payload, row["observed_at"]):
            accepted += 1

    return {
        "scanned": scanned,
        "accepted": accepted,
    }


def _sql_json(path: str) -> str:
    return (
        "CASE WHEN json_valid(NEW.context_json) "
        f"THEN json_extract(NEW.context_json, '{path}') END"
    )


def _install_trigger(connection: sqlite3.Connection) -> None:
    primary = "$.runtime_intelligence.wallet_readmodel.payload"
    fallback = (
        "$.mathematical_plan.market_context.runtime_intelligence."
        "wallet_readmodel.payload"
    )

    def field(name: str) -> str:
        return (
            "COALESCE("
            f"{_sql_json(primary + '.' + name)},"
            f"{_sql_json(fallback + '.' + name)}"
            ")"
        )

    wallet = f"LOWER({field('wallet_id')})"
    identity = f"UPPER({field('identity_source')})"
    performance_state = (
        f"UPPER({field('phase9_wallet_tracking.performance.state')})"
    )
    realized_sample = field(
        "phase9_wallet_tracking.performance.realized_sample_size"
    )
    whale_ready = field("whale_value_evidence_ready")
    whale_state = f"UPPER({field('whale_state')})"
    whale_direction = (
        f"UPPER(COALESCE({field('whale_direction')}, 'UNKNOWN'))"
    )

    trigger_sql = f"""
    DROP TRIGGER IF EXISTS {TRIGGER_NAME};

    CREATE TRIGGER {TRIGGER_NAME}
    AFTER INSERT ON candidate_decision_history
    WHEN COALESCE({identity}, '') = 'TRANSACTION_FROM_ONLY'
      AND COALESCE({wallet}, '') <> ''
    BEGIN
        UPDATE wallet_discovery_registry
        SET last_seen_at=NEW.observed_at,
            discovery_source='TRANSACTION_FROM_ONLY',
            freshness_state='FRESH',
            lifecycle_state='ACTIVE'
        WHERE lower(wallet_uid)={wallet};

        INSERT OR IGNORE INTO wallet_discovery_registry(
            wallet_uid,
            chain,
            address,
            first_seen_at,
            last_seen_at,
            discovery_source,
            freshness_state,
            lifecycle_state
        )
        SELECT
            {wallet},
            CASE
                WHEN instr({wallet}, ':') > 0
                THEN substr({wallet}, 1, instr({wallet}, ':') - 1)
                ELSE NULL
            END,
            CASE
                WHEN instr({wallet}, ':') > 0
                THEN substr({wallet}, instr({wallet}, ':') + 1)
                ELSE NULL
            END,
            NEW.observed_at,
            NEW.observed_at,
            'TRANSACTION_FROM_ONLY',
            'FRESH',
            'ACTIVE'
        WHERE NOT EXISTS (
            SELECT 1
            FROM wallet_discovery_registry
            WHERE lower(wallet_uid)={wallet}
        );

        UPDATE wallet_success_score
        SET calculated_at=NEW.observed_at,
            sample_depth=COALESCE({realized_sample}, sample_depth),
            qualification_state='SUCCESSFUL'
        WHERE lower(wallet_uid)={wallet}
          AND COALESCE({performance_state}, '')='SUCCESSFUL';

        INSERT OR IGNORE INTO wallet_success_score(
            wallet_uid,
            calculated_at,
            sample_depth,
            consistency_score,
            entry_quality_score,
            exit_quality_score,
            loss_control_score,
            risk_adjusted_score,
            freshness_score,
            success_score,
            qualification_state
        )
        SELECT
            {wallet},
            NEW.observed_at,
            {realized_sample},
            NULL,NULL,NULL,NULL,NULL,NULL,NULL,
            'SUCCESSFUL'
        WHERE COALESCE({performance_state}, '')='SUCCESSFUL'
          AND NOT EXISTS (
              SELECT 1
              FROM wallet_success_score
              WHERE lower(wallet_uid)={wallet}
          );

        UPDATE whale_activity_snapshot
        SET generated_at=NEW.observed_at,
            whale_state={whale_state},
            direction={whale_direction}
        WHERE lower(wallet_uid)={wallet}
          AND COALESCE({whale_ready}, 0)=1
          AND COALESCE({whale_state}, '') NOT IN ('', 'UNKNOWN', 'NONE');

        INSERT OR IGNORE INTO whale_activity_snapshot(
            wallet_uid,
            generated_at,
            whale_state,
            direction,
            activity_score,
            evidence_count
        )
        SELECT
            {wallet},
            NEW.observed_at,
            {whale_state},
            {whale_direction},
            NULL,
            NULL
        WHERE COALESCE({whale_ready}, 0)=1
          AND COALESCE({whale_state}, '') NOT IN ('', 'UNKNOWN', 'NONE')
          AND NOT EXISTS (
              SELECT 1
              FROM whale_activity_snapshot
              WHERE lower(wallet_uid)={wallet}
          );
    END;
    """

    connection.executescript(trigger_sql)


def apply_phase9_panel_bridge(
    db_path: str | Path,
    *,
    backfill_limit: int = DEFAULT_BACKFILL_LIMIT,
) -> dict[str, Any]:
    path = Path(db_path)
    if not path.exists():
        raise FileNotFoundError(path)

    connection = sqlite3.connect(
        str(path),
        timeout=30,
    )
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA busy_timeout=30000")

    try:
        decision_table = connection.execute(
            """
            SELECT 1
            FROM sqlite_master
            WHERE type='table'
              AND name='candidate_decision_history'
            """
        ).fetchone()

        if decision_table is None:
            raise RuntimeError("candidate_decision_history missing")

        _ensure_readmodel_schema(connection)
        backfill = _backfill(
            connection,
            limit=backfill_limit,
        )
        _install_trigger(connection)
        connection.commit()

        counts = {}
        for name in (
            "wallet_discovery_registry",
            "wallet_success_score",
            "whale_activity_snapshot",
        ):
            counts[name] = int(
                connection.execute(
                    f'SELECT COUNT(*) FROM "{name}"'
                ).fetchone()[0]
            )

        trigger_ready = connection.execute(
            """
            SELECT 1
            FROM sqlite_master
            WHERE type='trigger'
              AND name=?
            """,
            (TRIGGER_NAME,),
        ).fetchone() is not None

        return {
            "state": "READY",
            "backfill_scanned": backfill["scanned"],
            "backfill_phase9_rows": backfill["accepted"],
            "tracked_wallets": counts["wallet_discovery_registry"],
            "successful_wallets": counts["wallet_success_score"],
            "active_whales": counts["whale_activity_snapshot"],
            "trigger_installed": trigger_ready,
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
    parser.add_argument(
        "--db",
        default="data/paper_trades.db",
    )
    parser.add_argument(
        "--backfill-limit",
        type=int,
        default=DEFAULT_BACKFILL_LIMIT,
    )
    args = parser.parse_args()

    result = apply_phase9_panel_bridge(
        args.db,
        backfill_limit=args.backfill_limit,
    )

    print("PHASE9_PANEL_BRIDGE_STATE=" + str(result["state"]))
    print("BACKFILL_SCANNED=" + str(result["backfill_scanned"]))
    print("BACKFILL_PHASE9_ROWS=" + str(result["backfill_phase9_rows"]))
    print("TRACKED_WALLETS=" + str(result["tracked_wallets"]))
    print("SUCCESSFUL_WALLETS=" + str(result["successful_wallets"]))
    print("ACTIVE_WHALES=" + str(result["active_whales"]))
    print("TRIGGER_INSTALLED=" + str(result["trigger_installed"]).lower())
    print("PANEL_READ_ONLY=true")
    print("PHASE9_PANEL_BRIDGE=PASS")


if __name__ == "__main__":
    main()
