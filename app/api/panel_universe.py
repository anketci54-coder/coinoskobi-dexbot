from __future__ import annotations

import sqlite3
from collections import Counter
from pathlib import Path
from typing import Any


ALLOWED_STATES = {"COLD", "WARM", "HOT"}
DISPLAY_PRIORITY = {"HOT": 0, "WARM": 1, "COLD": 2}


def _connect_readonly(path: str | Path) -> sqlite3.Connection:
    db_path = Path(path)
    connection = sqlite3.connect(
        f"file:{db_path}?mode=ro",
        uri=True,
        timeout=2,
    )
    connection.row_factory = sqlite3.Row
    return connection


def _recent_registry_candidates(
    connection: sqlite3.Connection,
    *,
    state: str,
    limit: int,
) -> list[sqlite3.Row]:
    return connection.execute(
        """
        SELECT
            chain,
            dex,
            pool,
            token0,
            token1,
            market_state,
            latest_liquidity_usd,
            latest_volume_24h,
            latest_price_usd,
            latest_txns_5m,
            latest_change_5m,
            latest_snapshot_at,
            state_changed_at
        FROM universe_pool_registry
        INDEXED BY idx_universe_snapshot_at
        WHERE latest_snapshot_at IS NOT NULL
          AND market_state = ?
        ORDER BY latest_snapshot_at DESC
        LIMIT ?
        """,
        (state, int(limit)),
    ).fetchall()


def _latest_seismic(
    connection: sqlite3.Connection,
    *,
    chain: str,
    dex: str,
    pool: str,
) -> sqlite3.Row | None:
    return connection.execute(
        """
        SELECT
            score,
            price_z,
            volume_z,
            txns_z,
            liquidity_ratio,
            evidence_count,
            reason,
            previous_state,
            next_state,
            observed_at
        FROM universe_seismic_evaluation_v1
        WHERE chain = ?
          AND dex = ?
          AND pool = ?
        ORDER BY observed_at DESC, id DESC
        LIMIT 1
        """,
        (chain, dex, pool),
    ).fetchone()


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

        # Pull only a tiny, index-friendly recent window per state. This keeps
        # HOT/WARM visible even when the full universe is overwhelmingly COLD,
        # while avoiding a multi-million-row CASE/COALESCE sort.
        candidates = []
        for state in ("HOT", "WARM", "COLD"):
            candidates.extend(
                _recent_registry_candidates(
                    connection,
                    state=state,
                    limit=bounded_limit,
                )
            )

        candidates.sort(
            key=lambda row: (
                DISPLAY_PRIORITY.get(str(row["market_state"]), 99),
                str(row["latest_snapshot_at"] or ""),
            ),
            reverse=False,
        )

        rows = candidates[:bounded_limit]

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

        result_rows = []
        for raw in rows:
            row = dict(raw)
            state = str(row.get("market_state") or "").upper()
            if state not in ALLOWED_STATES:
                continue

            seismic_row = _latest_seismic(
                connection,
                chain=str(row.get("chain") or ""),
                dex=str(row.get("dex") or ""),
                pool=str(row.get("pool") or ""),
            )

            seismic = None
            if seismic_row is not None:
                seismic = {
                    "score": seismic_row["score"],
                    "price_z": seismic_row["price_z"],
                    "volume_z": seismic_row["volume_z"],
                    "txns_z": seismic_row["txns_z"],
                    "liquidity_ratio": seismic_row["liquidity_ratio"],
                    "evidence_count": seismic_row["evidence_count"],
                    "reason": seismic_row["reason"],
                    "previous_state": seismic_row["previous_state"],
                    "next_state": seismic_row["next_state"],
                    "observed_at": seismic_row["observed_at"],
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

    except sqlite3.Error as exc:
        return _unavailable(type(exc).__name__)

    finally:
        if connection is not None:
            connection.close()

    transitions = Counter()
    for row in transition_rows:
        key = f"{row['previous_state']}->{row['next_state']}"
        transitions[key] = int(row["n"])

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
