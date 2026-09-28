from __future__ import annotations

import sqlite3
import time
from collections import Counter
from datetime import datetime, timezone

from app.config.scanner import MIN_LIQUIDITY_USD
from app.universe.display_metadata import TABLE as DISPLAY_METADATA_TABLE
from app.universe.scheduler import DEFAULT_MISSING_RETRY_SECONDS, DEFAULT_STATE_INTERVAL_SECONDS
from pathlib import Path
from typing import Any


ALLOWED_STATES = {"COLD", "WARM", "HOT"}
DEFAULT_TRANSITION_WINDOW = 1000
MAX_TRANSITION_WINDOW = 5000
MOVING_COLD_CACHE_TTL_SECONDS = 60.0
_moving_cold_cache: dict[str, dict[str, Any]] = {}

# BSC quote assets allowed in the operator-facing COLD list.
# Discovery remains full-universe; this is panel/read-model filtering only.
COLD_QUOTE_TOKENS = {
    "0x55d398326f99059ff775485246999027b3197955",  # USDT
}


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


def _moving_usdt_cold_candidates(
    connection: sqlite3.Connection,
) -> list[sqlite3.Row]:
    table_exists = connection.execute(
        """
        SELECT 1
        FROM sqlite_master
        WHERE type='table' AND name=?
        """,
        (DISPLAY_METADATA_TABLE,),
    ).fetchone()
    if table_exists is None:
        return []

    metadata_index = (
        "INDEXED BY idx_universe_pool_display_quote"
        if _has_index(
            connection,
            table=DISPLAY_METADATA_TABLE,
            index="idx_universe_pool_display_quote",
        )
        else ""
    )
    registry_index = (
        "INDEXED BY idx_universe_pool_dex"
        if _has_index(
            connection,
            table="universe_pool_registry",
            index="idx_universe_pool_dex",
        )
        else ""
    )

    try:
        return connection.execute(
            f"""
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
                r.state_changed_at
            FROM {DISPLAY_METADATA_TABLE} AS m
            {metadata_index}
            CROSS JOIN universe_pool_registry AS r
            {registry_index}
              ON r.pool=m.pool
             AND r.dex=m.dex
            WHERE m.chain='bsc'
              AND m.dex IN (
                  'pancakeswap_v2',
                  'pancakeswap_v3'
              )
              AND m.quote_symbol='USDT'
              AND m.base_symbol NOT IN (
                  '',
                  'USDT',
                  'WBNB'
              )
              AND r.chain='bsc'
              AND r.market_state='COLD'
              AND r.latest_snapshot_at IS NOT NULL
              AND COALESCE(
                  r.latest_liquidity_usd,
                  0
              ) >= ?
              AND (
                  COALESCE(r.latest_change_5m,0)<>0
                  OR COALESCE(r.latest_txns_5m,0)>0
              )
            ORDER BY
                COALESCE(r.latest_change_5m,0) DESC,
                COALESCE(r.latest_liquidity_usd,0) DESC,
                r.latest_snapshot_at DESC
            """,
            (float(MIN_LIQUIDITY_USD),),
        ).fetchall()
    except sqlite3.Error:
        return []


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


def _snapshot_is_fresh(
    row: dict[str, Any],
    *,
    now: datetime,
) -> bool:
    state = str(
        row.get("market_state")
        or row.get("state")
        or ""
    ).upper()
    if state not in DEFAULT_STATE_INTERVAL_SECONDS:
        return False

    raw = str(
        row.get("latest_snapshot_at")
        or row.get("snapshot_at")
        or ""
    ).strip()
    if not raw:
        return False

    try:
        observed = datetime.fromisoformat(
            raw.replace("Z", "+00:00")
        )
    except ValueError:
        return False

    if observed.tzinfo is None:
        observed = observed.replace(
            tzinfo=timezone.utc
        )
    observed = observed.astimezone(
        timezone.utc
    )

    budget_seconds = (
        int(
            DEFAULT_STATE_INTERVAL_SECONDS[
                state
            ]
        )
        + int(
            DEFAULT_MISSING_RETRY_SECONDS
        )
    )
    age_seconds = (
        now - observed
    ).total_seconds()
    return (
        age_seconds >= 0
        and age_seconds <= budget_seconds
    )


def universe_panel_payload(
    cache_db: str | Path,
    *,
    limit: int = 40,
    transition_limit: int = DEFAULT_TRANSITION_WINDOW,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Read-only projection for the premium operations terminal.

    No writes, no decision authority, no paper authority, and no execution
    authority. Missing data fails closed to an unavailable payload.
    """

    path = Path(cache_db)
    moving_cold_cache_allowed = now is None
    if now is None:
        now = datetime.now(timezone.utc)
    elif now.tzinfo is None:
        now = now.replace(
            tzinfo=timezone.utc
        )
    else:
        now = now.astimezone(
            timezone.utc
        )

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
        use_snapshot_index = False

        state_index = (
            "INDEXED BY idx_universe_state_due"
            if _has_index(
                connection,
                table="universe_pool_registry",
                index="idx_universe_state_due",
            )
            else ""
        )
        counts = {
            "COLD": 0,
            "WARM": int(
                connection.execute(
                    f"""
                    SELECT COUNT(*)
                    FROM universe_pool_registry
                    {state_index}
                    WHERE market_state='WARM'
                    """
                ).fetchone()[0]
            ),
            "HOT": int(
                connection.execute(
                    f"""
                    SELECT COUNT(*)
                    FROM universe_pool_registry
                    {state_index}
                    WHERE market_state='HOT'
                    """
                ).fetchone()[0]
            ),
        }

        # HOT/WARM remains complete. COLD is no longer sampled from the
        # multi-million-row registry; use the indexed BSC/Pancake/USDT moving
        # read path so dormant pools never enter the operator radar.
        candidates = []
        for state in ("HOT", "WARM"):
            candidates.extend(
                _recent_registry_candidates(
                    connection,
                    state=state,
                    limit=max(
                        1,
                        int(counts.get(state, 0)),
                    ),
                    use_snapshot_index=use_snapshot_index,
                )
            )
        cache_key = str(path.resolve())
        moving_cold = None

        if moving_cold_cache_allowed:
            cached = _moving_cold_cache.get(cache_key) or {}
            cached_at = float(cached.get("at") or 0.0)
            if (
                cached_at > 0.0
                and time.monotonic() - cached_at
                < MOVING_COLD_CACHE_TTL_SECONDS
            ):
                moving_cold = list(cached.get("rows") or [])

        if moving_cold is None:
            moving_cold = [
                dict(row)
                for row in _moving_usdt_cold_candidates(
                    connection,
                )
            ]
            if moving_cold_cache_allowed:
                _moving_cold_cache[cache_key] = {
                    "at": time.monotonic(),
                    "rows": moving_cold,
                }

        active_pools = {
            str(row["pool"] or "").lower()
            for row in candidates
            if row["pool"]
        }
        moving_cold = [
            row
            for row in moving_cold
            if str(row.get("pool") or "").lower()
            not in active_pools
        ]

        counts["COLD"] = len(moving_cold)
        candidates.extend(moving_cold)

        rows = candidates
        display_names = _gecko_display_names(
            connection,
            rows,
        )

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
            if not _snapshot_is_fresh(
                row,
                now=now,
            ):
                continue

            pool_key = str(
                row.get("pool") or ""
            ).strip().lower()

            seismic_row = None
            if state in {"HOT", "WARM"}:
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

        def row_rank(item):
            state = str(item.get("state") or "").upper()
            seismic = item.get("seismic") or {}

            try:
                change_5m = float(
                    item.get("change_5m_pct")
                )
            except (TypeError, ValueError):
                change_5m = float("-inf")

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

            if state in {"HOT", "WARM"}:
                liquid_rank = (
                    0
                    if liquidity_usd
                    >= float(MIN_LIQUIDITY_USD)
                    else 1
                )
                return (
                    0,
                    liquid_rank,
                    -change_5m,
                    -liquidity_usd,
                )

            return (
                1,
                0,
                -change_5m,
                -liquidity_usd,
            )

        result_rows.sort(key=row_rank)

        active_rows = [
            row
            for row in result_rows
            if str(row.get("state") or "").upper()
            in {"HOT", "WARM"}
        ]
        cold_rows = [
            row
            for row in result_rows
            if str(row.get("state") or "").upper()
            == "COLD"
        ]

        result_rows = active_rows + cold_rows
        counts = {
            state: sum(
                1
                for row in result_rows
                if str(
                    row.get("state") or ""
                ).upper() == state
            )
            for state in (
                "COLD",
                "WARM",
                "HOT",
            )
        }

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
