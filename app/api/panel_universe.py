from __future__ import annotations

import sqlite3
from collections import Counter
from pathlib import Path
from typing import Any


ALLOWED_STATES = {"COLD", "WARM", "HOT"}


def _connect_readonly(path: str | Path) -> sqlite3.Connection:
    db_path = Path(path)
    connection = sqlite3.connect(
        f"file:{db_path}?mode=ro",
        uri=True,
        timeout=2,
    )
    connection.row_factory = sqlite3.Row
    return connection


def universe_panel_payload(
    cache_db: str | Path,
    *,
    limit: int = 40,
) -> dict[str, Any]:
    """Read-only projection for the premium operations terminal.

    No writes, no decision authority, no paper authority, and no execution
    authority. Missing data fails closed to an unavailable payload.
    """

    path = Path(cache_db)
    bounded_limit = max(1, min(int(limit), 100))

    if not path.exists():
        return _unavailable("CACHE_DB_MISSING")

    connection = None

    try:
        connection = _connect_readonly(path)

        rows = connection.execute(
            """
            SELECT
                r.chain,
                r.dex,
                r.pool,
                r.token0,
                r.token1,
                r.market_state,
                r.latest_liquidity_usd,
                r.latest_volume_24h,
                r.latest_price_usd,
                r.latest_txns_5m,
                r.latest_change_5m,
                r.latest_snapshot_at,
                r.state_changed_at,
                e.score AS seismic_score,
                e.price_z AS seismic_price_z,
                e.volume_z AS seismic_volume_z,
                e.txns_z AS seismic_txns_z,
                e.liquidity_ratio AS seismic_liquidity_ratio,
                e.evidence_count AS seismic_evidence_count,
                e.reason AS seismic_reason,
                e.previous_state AS seismic_previous_state,
                e.next_state AS seismic_next_state,
                e.observed_at AS seismic_observed_at
            FROM universe_pool_registry AS r
            LEFT JOIN universe_seismic_evaluation_v1 AS e
              ON e.id = (
                  SELECT e2.id
                  FROM universe_seismic_evaluation_v1 AS e2
                  WHERE e2.chain = r.chain
                    AND e2.dex = r.dex
                    AND e2.pool = r.pool
                  ORDER BY e2.observed_at DESC, e2.id DESC
                  LIMIT 1
              )
            WHERE r.market_state IN ('COLD','WARM','HOT')
            ORDER BY
                CASE r.market_state
                    WHEN 'HOT' THEN 0
                    WHEN 'WARM' THEN 1
                    ELSE 2
                END,
                COALESCE(r.latest_snapshot_at, r.state_changed_at) DESC
            LIMIT ?
            """,
            (bounded_limit,),
        ).fetchall()

        counts = {
            str(row["market_state"]): int(row["n"])
            for row in connection.execute(
                """
                SELECT market_state, COUNT(*) AS n
                FROM universe_pool_registry
                WHERE market_state IN ('COLD','WARM','HOT')
                GROUP BY market_state
                """
            ).fetchall()
        }

        transition_rows = connection.execute(
            """
            SELECT previous_state, next_state, COUNT(*) AS n
            FROM universe_seismic_evaluation_v1
            WHERE previous_state <> next_state
              AND previous_state IN ('COLD','WARM','HOT')
              AND next_state IN ('COLD','WARM','HOT')
            GROUP BY previous_state, next_state
            """
        ).fetchall()

    except sqlite3.Error as exc:
        return _unavailable(type(exc).__name__)

    finally:
        if connection is not None:
            connection.close()

    transitions = Counter()
    for row in transition_rows:
        key = f"{row['previous_state']}->{row['next_state']}"
        transitions[key] = int(row["n"])

    result_rows = []
    for raw in rows:
        row = dict(raw)
        state = str(row.get("market_state") or "").upper()
        if state not in ALLOWED_STATES:
            continue

        seismic = None
        if row.get("seismic_observed_at") is not None:
            seismic = {
                "score": row.get("seismic_score"),
                "price_z": row.get("seismic_price_z"),
                "volume_z": row.get("seismic_volume_z"),
                "txns_z": row.get("seismic_txns_z"),
                "liquidity_ratio": row.get("seismic_liquidity_ratio"),
                "evidence_count": row.get("seismic_evidence_count"),
                "reason": row.get("seismic_reason"),
                "previous_state": row.get("seismic_previous_state"),
                "next_state": row.get("seismic_next_state"),
                "observed_at": row.get("seismic_observed_at"),
            }

        result_rows.append({
            "chain": row.get("chain"),
            "dex": row.get("dex"),
            "pool": row.get("pool"),
            "token0": row.get("token0"),
            "token1": row.get("token1"),
            "state": state,
            "liquidity_usd": row.get("latest_liquidity_usd"),
            "volume_24h_usd": row.get("latest_volume_24h"),
            "price_usd": row.get("latest_price_usd"),
            "txns_5m": row.get("latest_txns_5m"),
            "change_5m_pct": row.get("latest_change_5m"),
            "snapshot_at": row.get("latest_snapshot_at"),
            "state_changed_at": row.get("state_changed_at"),
            "seismic": seismic,
        })

    total_count = sum(int(counts.get(state, 0)) for state in ALLOWED_STATES)

    return {
        "available": True,
        "source": "UNIVERSE_CACHE_READ_ONLY",
        "counts": {
            "COLD": counts.get("COLD", 0),
            "WARM": counts.get("WARM", 0),
            "HOT": counts.get("HOT", 0),
        },
        "total_count": total_count,
        "visible_count": len(result_rows),
        "transition_scope": "ALL_RECORDED_SEISMIC_EVALUATIONS",
        "transitions": {
            "COLD_TO_WARM": transitions.get("COLD->WARM", 0),
            "WARM_TO_HOT": transitions.get("WARM->HOT", 0),
            "HOT_TO_COLD": transitions.get("HOT->COLD", 0),
        },
        "rows": result_rows,
        "panel_display_only": True,
        "decision_authority": False,
        "paper_authority": False,
        "live_authority": False,
        "wallet_authority": False,
        "execution_authority": False,
    }


def _unavailable(reason: str) -> dict[str, Any]:
    return {
        "available": False,
        "source": "UNAVAILABLE",
        "reason": str(reason),
        "counts": {"COLD": None, "WARM": None, "HOT": None},
        "total_count": None,
        "visible_count": 0,
        "transition_scope": "UNAVAILABLE",
        "transitions": {
            "COLD_TO_WARM": None,
            "WARM_TO_HOT": None,
            "HOT_TO_COLD": None,
        },
        "rows": [],
        "panel_display_only": True,
        "decision_authority": False,
        "paper_authority": False,
        "live_authority": False,
        "wallet_authority": False,
        "execution_authority": False,
    }
