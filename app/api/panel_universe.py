from __future__ import annotations

import sqlite3
from collections import Counter
from pathlib import Path
from typing import Any


ALLOWED_STATES = {"COLD", "WARM", "HOT"}
DEFAULT_TRANSITION_WINDOW = 1000
MAX_TRANSITION_WINDOW = 5000

# BSC quote assets allowed in the operator-facing COLD list.
# Discovery remains full-universe; this is panel/read-model filtering only.
COLD_QUOTE_TOKENS = {
    "0xbb4cdb9cbd36b01bd1cbaebf2de08d9173bc095c",  # WBNB
    "0x55d398326f99059ff775485246999027b3197955",  # USDT
    "0x8ac76a51cc950d9822d68b83fe1ad97b32cd580d",  # USDC
}
COLD_SCAN_MULTIPLIER = 5


def _connect_readonly(path: str | Path) -> sqlite3.Connection:
    db_path = Path(path)
    connection = sqlite3.connect(
        f"file:{db_path}?mode=ro",
        uri=True,
        timeout=2,
    )
    connection.row_factory = sqlite3.Row
    return connection


def _has_index(
    connection: sqlite3.Connection,
    *,
    table: str,
    index: str,
) -> bool:
    return any(
        str(row[1]) == index
        for row in connection.execute(
            f"PRAGMA index_list('{table}')"
        ).fetchall()
    )


def _recent_registry_candidates(
    connection: sqlite3.Connection,
    *,
    state: str,
    limit: int,
    use_snapshot_index: bool,
) -> list[sqlite3.Row]:
    indexed_by = (
        "INDEXED BY idx_universe_snapshot_at"
        if use_snapshot_index
        else ""
    )
    quote_filter = ""
    params: list[Any] = [state]

    if state == "COLD":
        quotes = sorted(COLD_QUOTE_TOKENS)
        marks = ",".join("?" for _ in quotes)
        quote_filter = f"""
          AND (
              lower(token0) IN ({marks})
              OR lower(token1) IN ({marks})
          )
        """
        params.extend(quotes)
        params.extend(quotes)

    params.append(int(limit))

    return connection.execute(
        f"""
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
        {indexed_by}
        WHERE latest_snapshot_at IS NOT NULL
          AND market_state = ?
          {quote_filter}
        ORDER BY latest_snapshot_at DESC
        LIMIT ?
        """,
        tuple(params),
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


def _recent_transition_rows(
    connection: sqlite3.Connection,
    *,
    limit: int,
) -> list[sqlite3.Row]:
    return connection.execute(
        """
        SELECT id, previous_state, next_state
        FROM universe_seismic_evaluation_v1
        ORDER BY id DESC
        LIMIT ?
        """,
        (int(limit),),
    ).fetchall()


def _gecko_display_names(
    connection: sqlite3.Connection,
    rows: list[sqlite3.Row],
) -> dict[str, str]:
    """Resolve readable names only for the already-bounded panel rows.

    The lookup is display-only and fail-soft. A missing/legacy Gecko cache must
    never make the universe readmodel unavailable.
    """

    pools = list(dict.fromkeys(
        str(row["pool"] or "").strip().lower()
        for row in rows
        if str(row["pool"] or "").strip()
    ))

    if not pools:
        return {}

    marks = ",".join("?" for _ in pools)

    try:
        matches = connection.execute(
            f"""
            SELECT pool, name
            FROM gecko_pool_cache
            WHERE lower(pool) IN ({marks})
              AND NULLIF(TRIM(name), '') IS NOT NULL
            """,
            tuple(pools),
        ).fetchall()
    except sqlite3.Error:
        return {}

    return {
        str(row["pool"] or "").strip().lower(): str(
            row["name"] or ""
        ).strip()
        for row in matches
        if (
            str(row["pool"] or "").strip()
            and str(row["name"] or "").strip()
        )
    }


def universe_panel_payload(
    cache_db: str | Path,
    *,
    limit: int = 40,
    transition_limit: int = DEFAULT_TRANSITION_WINDOW,
) -> dict[str, Any]:
    """Read-only projection for the premium operations terminal.

    No writes, no decision authority, no paper authority, and no execution
    authority. Missing data fails closed to an unavailable payload.
    """

    path = Path(cache_db)
    bounded_limit = max(1, min(int(limit), 100))
    bounded_transition_limit = max(
        1,
        min(int(transition_limit), MAX_TRANSITION_WINDOW),
    )

    if not path.exists():
        return _unavailable("CACHE_DB_MISSING")

    connection = None

    try:
        connection = _connect_readonly(path)
        use_snapshot_index = _has_index(
            connection,
            table="universe_pool_registry",
            index="idx_universe_snapshot_at",
        )

        # Pull only a tiny recent window per state. On the production universe
        # DB this explicitly walks the existing latest_snapshot_at index instead
        # of sorting millions of rows. HOT -> WARM -> COLD batch order preserves
        # operator priority without creating a new DB index or write migration.
        candidates = []
        for state in ("HOT", "WARM", "COLD"):
            state_limit = (
                bounded_limit * COLD_SCAN_MULTIPLIER
                if state == "COLD"
                else bounded_limit
            )
            candidates.extend(
                _recent_registry_candidates(
                    connection,
                    state=state,
                    limit=state_limit,
                    use_snapshot_index=use_snapshot_index,
                )
            )

        rows = candidates
        display_names = _gecko_display_names(
            connection,
            rows,
        )

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

        # Transition display is operational context, not a training aggregate.
        # Keep it explicitly bounded to the most recent seismic evaluations so
        # the read-only panel never scans millions of historical rows.
        transition_rows = _recent_transition_rows(
            connection,
            limit=bounded_transition_limit,
        )

        result_rows = []
        for raw in rows:
            row = dict(raw)
            state = str(row.get("market_state") or "").upper()
            if state not in ALLOWED_STATES:
                continue

            pool_key = str(
                row.get("pool") or ""
            ).strip().lower()

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
                "display_name": display_names.get(pool_key),
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

        state_priority = {
            "HOT": 0,
            "WARM": 1,
            "COLD": 2,
        }

        def row_rank(item):
            state = str(item.get("state") or "").upper()
            seismic = item.get("seismic") or {}

            try:
                liquidity_ratio = float(
                    seismic.get("liquidity_ratio") or 0.0
                )
            except (TypeError, ValueError):
                liquidity_ratio = 0.0

            try:
                liquidity_usd = float(
                    item.get("liquidity_usd") or 0.0
                )
            except (TypeError, ValueError):
                liquidity_usd = 0.0

            if state == "COLD":
                return (
                    state_priority[state],
                    -liquidity_ratio,
                    -liquidity_usd,
                )

            return (
                state_priority.get(state, 9),
                0.0,
                -liquidity_usd,
            )

        result_rows.sort(key=row_rank)
        result_rows = result_rows[:bounded_limit]

    except sqlite3.Error as exc:
        return _unavailable(type(exc).__name__)

    finally:
        if connection is not None:
            connection.close()

    transitions = Counter()
    for row in transition_rows:
        previous_state = str(row["previous_state"] or "").upper()
        next_state = str(row["next_state"] or "").upper()
        if (
            previous_state in ALLOWED_STATES
            and next_state in ALLOWED_STATES
            and previous_state != next_state
        ):
            transitions[f"{previous_state}->{next_state}"] += 1

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
        "transition_scope": "RECENT_BOUNDED_SEISMIC_EVALUATIONS",
        "transition_sample_size": len(transition_rows),
        "transition_window_limit": bounded_transition_limit,
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
        "transition_sample_size": 0,
        "transition_window_limit": None,
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
