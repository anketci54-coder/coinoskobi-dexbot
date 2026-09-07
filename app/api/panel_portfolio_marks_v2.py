from __future__ import annotations

import math
import sqlite3
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.api.panel_manual_paper_v2 import _sell_accounting
from app.scanner.gecko_scanner import GeckoScanner


MARK_REFRESH_TTL_SECONDS = 30.0
MAX_MARK_POOLS = 30
CACHE_MARK_MAX_AGE_SECONDS = 300.0

_MARK_LOCK = threading.Lock()
_MARK_CACHE: dict[str, Any] = {
    "signature": None,
    "built_monotonic": 0.0,
    "payload": None,
}


def _num(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _timestamp(value: Any) -> float | None:
    number = _num(value)
    if number is not None:
        if number > 10_000_000_000:
            number /= 1000.0
        return number if number > 0 else None

    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.timestamp()


def _connect_readonly(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(
        f"file:{path}?mode=ro",
        uri=True,
        timeout=3,
    )
    connection.row_factory = sqlite3.Row
    return connection


def _open_positions(paper_db: Path) -> list[dict[str, Any]]:
    if not paper_db.exists():
        return []
    connection = _connect_readonly(paper_db)
    try:
        rows = connection.execute(
            """
            SELECT *
            FROM paper_trades
            WHERE paper_account_version='PAPER_10K_V2'
              AND UPPER(COALESCE(status,'OPEN')) != 'CLOSED'
            ORDER BY id
            """
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        connection.close()


def _realized_net(paper_db: Path) -> float:
    if not paper_db.exists():
        return 0.0
    connection = _connect_readonly(paper_db)
    try:
        row = connection.execute(
            """
            SELECT COALESCE(
                SUM(COALESCE(net_pnl_usdt, net_pnl, 0)),
                0
            ) AS realized_net
            FROM paper_trades
            WHERE paper_account_version='PAPER_10K_V2'
              AND UPPER(COALESCE(status,''))='CLOSED'
            """
        ).fetchone()
        return float(row["realized_net"] or 0.0)
    finally:
        connection.close()


def _position_signature(rows: list[dict[str, Any]]) -> tuple[Any, ...]:
    return tuple(
        (
            int(row.get("id") or 0),
            str(row.get("pool") or "").strip().lower(),
            _num(row.get("token_amount")),
            _num(row.get("entry_amount_usdt")),
        )
        for row in rows
    )


def _cache_quotes(
    cache_db: Path,
    pools: list[str],
) -> dict[str, dict[str, Any]]:
    if not cache_db.exists() or not pools:
        return {}

    connection = _connect_readonly(cache_db)
    quotes: dict[str, dict[str, Any]] = {}

    try:
        tables = {
            str(row["name"])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        marks = ",".join("?" for _ in pools)

        if "universe_pool_registry" in tables:
            for row in connection.execute(
                f"""
                SELECT pool, latest_price_usd AS price_usd,
                       latest_snapshot_at AS updated_at, dex
                FROM universe_pool_registry
                WHERE lower(pool) IN ({marks})
                """,
                tuple(pools),
            ).fetchall():
                pool = str(row["pool"] or "").strip().lower()
                price = _num(row["price_usd"])
                observed = _timestamp(row["updated_at"])
                if not pool or price is None or price <= 0 or observed is None:
                    continue
                current = quotes.get(pool)
                if current is None or observed > float(current["observed_at"]):
                    quotes[pool] = {
                        "pool": row["pool"],
                        "price_usd": price,
                        "observed_at": observed,
                        "updated_at": row["updated_at"],
                        "dex": row["dex"],
                        "source": "UNIVERSE_POOL_REGISTRY",
                    }

        if "gecko_pool_cache" in tables:
            for row in connection.execute(
                f"""
                SELECT pool, price_usd, updated_at, dex
                FROM gecko_pool_cache
                WHERE lower(pool) IN ({marks})
                """,
                tuple(pools),
            ).fetchall():
                pool = str(row["pool"] or "").strip().lower()
                price = _num(row["price_usd"])
                observed = _timestamp(row["updated_at"])
                if not pool or price is None or price <= 0 or observed is None:
                    continue
                current = quotes.get(pool)
                if current is None or observed > float(current["observed_at"]):
                    quotes[pool] = {
                        "pool": row["pool"],
                        "price_usd": price,
                        "observed_at": observed,
                        "updated_at": row["updated_at"],
                        "dex": row["dex"],
                        "source": "GECKO_POOL_CACHE",
                    }

        return quotes
    finally:
        connection.close()


def _provider_quotes(pools: list[str]) -> tuple[dict[str, dict[str, Any]], str]:
    if not pools:
        return {}, "NO_OPEN_POOLS"

    try:
        snapshots = GeckoScanner().pool_snapshots(
            pools,
            max_pools=min(MAX_MARK_POOLS, len(pools)),
            persist_followups=False,
        )
    except Exception as exc:
        return {}, f"{type(exc).__name__}"

    now = time.time()
    quotes: dict[str, dict[str, Any]] = {}

    for row in snapshots or []:
        pool = str(row.get("pool") or "").strip().lower()
        price = _num(row.get("price_usd"))
        if pool not in pools or price is None or price <= 0:
            continue
        quotes[pool] = {
            "pool": row.get("pool"),
            "price_usd": price,
            "observed_at": now,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "dex": row.get("dex"),
            "source": "GECKOTERMINAL_MULTI_POOL",
        }

    return quotes, "OK"


def _row_mark(
    position: dict[str, Any],
    quote: dict[str, Any] | None,
) -> dict[str, Any]:
    now = time.time()
    entry = _num(position.get("entry_amount_usdt")) or 0.0
    tokens = _num(position.get("token_amount")) or 0.0
    realized_gross = _num(position.get("realized_gross_proceeds_usdt")) or 0.0

    price = None
    source = "PAPER_DB_FALLBACK"
    age = None
    fresh = False

    if quote is not None:
        quote_price = _num(quote.get("price_usd"))
        observed = _num(quote.get("observed_at"))
        quote_source = str(quote.get("source") or "UNKNOWN")
        quote_age = max(0.0, now - observed) if observed is not None else None
        provider_fresh = quote_source == "GECKOTERMINAL_MULTI_POOL"
        cache_fresh = quote_age is not None and quote_age <= CACHE_MARK_MAX_AGE_SECONDS

        if quote_price is not None and quote_price > 0 and (provider_fresh or cache_fresh):
            price = quote_price
            source = quote_source
            age = quote_age
            fresh = True
        elif quote_price is not None and quote_price > 0:
            source = "PAPER_DB_FALLBACK_STALE_EXTERNAL"
            age = quote_age

    if price is None:
        price = _num(position.get("current_price")) or _num(position.get("entry_price"))

    mark_value = None
    gross_pnl = None
    net_pnl = None
    roi_pct = None

    if price is not None and price > 0:
        mark_value = realized_gross + tokens * price
        gross_pnl = mark_value - entry
        try:
            accounting = _sell_accounting(position, price)
        except Exception:
            accounting = None
        if accounting is not None:
            net_pnl = _num(accounting.get("net"))
            roi = _num(accounting.get("roi"))
            roi_pct = roi * 100.0 if roi is not None else None

    return {
        "id": int(position.get("id") or 0),
        "token": position.get("token"),
        "symbol": position.get("symbol"),
        "pool": position.get("pool"),
        "trade_policy": position.get("trade_policy"),
        "entry_price": _num(position.get("entry_price")),
        "db_current_price": _num(position.get("current_price")),
        "mark_price_usd": price,
        "mark_price_source": source,
        "mark_price_age_seconds": age,
        "mark_price_fresh": bool(fresh),
        "mark_value_usdt": mark_value,
        "mark_gross_pnl_usdt": gross_pnl,
        "estimated_exit_net_pnl_usdt": net_pnl,
        "estimated_exit_roi_pct": roi_pct,
        "entry_amount_usdt": entry,
        "token_amount": tokens,
    }


def _build_payload(
    rows: list[dict[str, Any]],
    *,
    paper_db: Path,
    cache_db: Path,
) -> dict[str, Any]:
    pools = list(dict.fromkeys(
        str(row.get("pool") or "").strip().lower()
        for row in rows
        if str(row.get("pool") or "").strip()
    ))[:MAX_MARK_POOLS]

    cache_quotes = _cache_quotes(cache_db, pools)
    provider_quotes, provider_state = _provider_quotes(pools)

    quotes = dict(cache_quotes)
    quotes.update(provider_quotes)

    mark_rows = [
        _row_mark(
            row,
            quotes.get(str(row.get("pool") or "").strip().lower()),
        )
        for row in rows
    ]

    net_values = [
        _num(row.get("estimated_exit_net_pnl_usdt"))
        for row in mark_rows
        if row.get("mark_price_fresh")
    ]
    gross_values = [
        _num(row.get("mark_gross_pnl_usdt"))
        for row in mark_rows
        if row.get("mark_price_fresh")
    ]
    value_values = [
        _num(row.get("mark_value_usdt"))
        for row in mark_rows
        if row.get("mark_price_fresh")
    ]

    net_known = [value for value in net_values if value is not None]
    gross_known = [value for value in gross_values if value is not None]
    values_known = [value for value in value_values if value is not None]

    realized_net = _realized_net(paper_db)
    full_net_coverage = len(net_known) == len(mark_rows)
    open_net = sum(net_known) if full_net_coverage else None
    total_mark_pnl = realized_net + open_net if open_net is not None else None
    mark_equity = 10_000.0 + total_mark_pnl if total_mark_pnl is not None else None

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "provider_state": provider_state,
        "refresh_ttl_seconds": MARK_REFRESH_TTL_SECONDS,
        "rows": mark_rows,
        "summary": {
            "open_count": len(mark_rows),
            "fresh_mark_count": sum(1 for row in mark_rows if row["mark_price_fresh"]),
            "provider_mark_count": sum(
                1
                for row in mark_rows
                if row["mark_price_source"] == "GECKOTERMINAL_MULTI_POOL"
            ),
            "cache_mark_count": sum(
                1
                for row in mark_rows
                if row["mark_price_fresh"] and row["mark_price_source"] in {
                    "UNIVERSE_POOL_REGISTRY",
                    "GECKO_POOL_CACHE",
                }
            ),
            "mark_value_usdt": sum(values_known) if values_known else None,
            "open_mark_gross_pnl_usdt": sum(gross_known) if gross_known else None,
            "open_mark_net_pnl_usdt": open_net,
            "net_mark_coverage_count": len(net_known),
            "realized_net_usdt": realized_net,
            "total_mark_pnl_usdt": total_mark_pnl,
            "mark_equity_usdt": mark_equity,
        },
        "authority": "READ_ONLY",
        "paper_write_authority": False,
        "live_execution": False,
        "wallet_authority": False,
        "signing_authority": False,
    }


def portfolio_marks_payload(
    *,
    paper_db: Path,
    cache_db: Path,
) -> dict[str, Any]:
    rows = _open_positions(paper_db)
    signature = _position_signature(rows)
    now = time.monotonic()

    cached_payload = _MARK_CACHE.get("payload")
    if (
        cached_payload is not None
        and _MARK_CACHE.get("signature") == signature
        and now - float(_MARK_CACHE.get("built_monotonic") or 0.0)
        < MARK_REFRESH_TTL_SECONDS
    ):
        payload = dict(cached_payload)
        payload["served_from_mark_cache"] = True
        return payload

    with _MARK_LOCK:
        now = time.monotonic()
        cached_payload = _MARK_CACHE.get("payload")
        if (
            cached_payload is not None
            and _MARK_CACHE.get("signature") == signature
            and now - float(_MARK_CACHE.get("built_monotonic") or 0.0)
            < MARK_REFRESH_TTL_SECONDS
        ):
            payload = dict(cached_payload)
            payload["served_from_mark_cache"] = True
            return payload

        payload = _build_payload(
            rows,
            paper_db=paper_db,
            cache_db=cache_db,
        )
        _MARK_CACHE["signature"] = signature
        _MARK_CACHE["built_monotonic"] = time.monotonic()
        _MARK_CACHE["payload"] = payload

        response = dict(payload)
        response["served_from_mark_cache"] = False
        return response


def register_portfolio_marks_v2(
    app,
    *,
    paper_db: Path,
    cache_db: Path,
) -> None:
    @app.get("/api/portfolio-marks-v2")
    def api_portfolio_marks_v2() -> dict[str, Any]:
        return portfolio_marks_payload(
            paper_db=paper_db,
            cache_db=cache_db,
        )
