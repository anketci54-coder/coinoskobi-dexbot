from __future__ import annotations

import json
import sqlite3
import threading
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

import requests

from app.api.news_impact import impact_snapshot
from app.api.wallet_intelligence_feed import arkham_config_status


NEWS_SOURCES = (
    ("CoinDesk", "https://www.coindesk.com/arc/outboundfeeds/rss/"),
    ("Cointelegraph", "https://cointelegraph.com/rss"),
)
CALENDAR_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
HTTP_TIMEOUT = 5.0
NEWS_TTL_SECONDS = 120.0
CALENDAR_TTL_SECONDS = 300.0
ARKHAM_PANEL_WALLET_LIMIT = 12
ARKHAM_PANEL_ASSET_LIMIT_PER_WALLET = 20
ARKHAM_PANEL_CHANGE_LIMIT = 80
_CACHE_LOCK = threading.RLock()
_CACHE: dict[str, dict[str, Any]] = {}


def _ro(path: Path | str) -> sqlite3.Connection:
    con = sqlite3.connect(f"file:{Path(path)}?mode=ro", uri=True, timeout=5)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA busy_timeout=5000")
    return con


def _table_exists(con: sqlite3.Connection, name: str) -> bool:
    return con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone() is not None


def watch_probe_detail(paper_db: Path | str, *, limit: int = 100) -> dict[str, Any]:
    limit = max(1, min(int(limit), 250))
    path = Path(paper_db)
    if not path.exists():
        return {"available": False, "rows": [], "reason": "PAPER_DB_MISSING"}
    con = _ro(path)
    try:
        if not _table_exists(con, "watch_probe_trades"):
            return {"available": False, "rows": [], "reason": "WATCH_TABLE_MISSING"}
        rows = con.execute(
            """SELECT id, token, pool, opened_at, entry_price, entry_usdt, token_amount,
            last_observed_at, last_price, max_price, min_price, status, mark_return_pct,
            mfe_pct, mae_pct, peak_drawdown_pct, realizable_exit_usdt, realizable_return_pct,
            exit_state, exit_quality, exit_reason, last_exit_probe_at, closed_at
            FROM watch_probe_trades WHERE token <> '0xtoken' ORDER BY id DESC LIMIT ?""",
            (limit,),
        ).fetchall()
    finally:
        con.close()
    return {"available": True, "count": len(rows), "rows": [dict(row) for row in rows], "paper_only": True, "trade_authority": False, "wallet_authority": False, "execution_authority": False}


def _arkham_holdings_panel(con: sqlite3.Connection, provider: dict[str, Any]) -> dict[str, Any]:
    authority = {
        "read_only": True,
        "decision_authority": False,
        "paper_authority": False,
        "live_authority": False,
        "wallet_authority": False,
        "signing_authority": False,
        "execution_authority": False,
    }
    required = {
        "wallet_discovery_registry",
        "wallet_success_score",
        "wallet_holding_snapshot",
        "wallet_holding_change_evidence",
        "wallet_holding_scan_state",
    }
    existing = {
        str(row[0])
        for row in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    missing = sorted(required - existing)
    if missing:
        state = "INACTIVE_NO_API_KEY" if provider.get("configured") is not True else "WAITING_FOR_RUNTIME"
        return {
            "state": state,
            "available": False,
            "missing_tables": missing,
            "wallets": [],
            "changes": [],
            **authority,
        }

    wallet_rows = con.execute(
        """
        WITH successful AS (
            SELECT
                lower(s.wallet_uid) AS wallet_key,
                MIN(s.wallet_uid) AS wallet_uid,
                MAX(COALESCE(s.calculated_at, 0)) AS calculated_at,
                MAX(COALESCE(s.sample_depth, 0)) AS sample_depth
            FROM wallet_success_score AS s
            WHERE UPPER(COALESCE(s.qualification_state,''))='SUCCESSFUL'
              AND COALESCE(s.wallet_uid,'')<>''
            GROUP BY lower(s.wallet_uid)
        )
        SELECT
            successful.wallet_uid,
            successful.calculated_at,
            successful.sample_depth,
            lower(COALESCE(r.chain,'bsc')) AS chain,
            lower(COALESCE(r.address,'')) AS address,
            h.last_scan_at,
            h.last_success_at,
            h.last_provider_state,
            h.total_value_usd,
            h.asset_count
        FROM successful
        JOIN wallet_discovery_registry AS r
          ON lower(r.wallet_uid)=successful.wallet_key
        LEFT JOIN wallet_holding_scan_state AS h
          ON lower(h.wallet_uid)=successful.wallet_key
        WHERE UPPER(COALESCE(r.discovery_source,''))='TRANSACTION_FROM_ONLY'
          AND lower(COALESCE(r.chain,''))='bsc'
          AND COALESCE(r.address,'')<>''
        GROUP BY successful.wallet_key
        ORDER BY successful.calculated_at DESC, successful.wallet_uid ASC
        LIMIT ?
        """,
        (ARKHAM_PANEL_WALLET_LIMIT,),
    ).fetchall()
    wallets = [dict(row) for row in wallet_rows]
    wallet_uids = [str(row.get("wallet_uid") or "").lower() for row in wallets if row.get("wallet_uid")]

    holdings_by_wallet: dict[str, list[dict[str, Any]]] = {uid: [] for uid in wallet_uids}
    changes: list[dict[str, Any]] = []
    if wallet_uids:
        placeholders = ",".join("?" for _ in wallet_uids)
        holding_rows = con.execute(
            f"""
            SELECT
                wallet_uid, token_id, token_address, pricing_id, symbol, name,
                balance, value_usd, price_usd, price_change_24h_pct,
                observed_at, provider
            FROM wallet_holding_snapshot
            WHERE lower(wallet_uid) IN ({placeholders})
            ORDER BY lower(wallet_uid) ASC,
                     COALESCE(value_usd, -1.0) DESC,
                     observed_at DESC,
                     token_id ASC
            """,
            tuple(wallet_uids),
        ).fetchall()
        for raw in holding_rows:
            item = dict(raw)
            key = str(item.get("wallet_uid") or "").lower()
            bucket = holdings_by_wallet.get(key)
            if bucket is not None and len(bucket) < ARKHAM_PANEL_ASSET_LIMIT_PER_WALLET:
                bucket.append(item)

        change_rows = con.execute(
            f"""
            SELECT
                id, wallet_uid, token_id, change_type,
                previous_balance, current_balance,
                previous_value_usd, current_value_usd,
                observed_at, provider
            FROM wallet_holding_change_evidence
            WHERE lower(wallet_uid) IN ({placeholders})
            ORDER BY observed_at DESC, id DESC
            LIMIT ?
            """,
            (*wallet_uids, ARKHAM_PANEL_CHANGE_LIMIT),
        ).fetchall()
        changes = [dict(row) for row in change_rows]

    for wallet in wallets:
        key = str(wallet.get("wallet_uid") or "").lower()
        wallet["holdings"] = holdings_by_wallet.get(key, [])

    if not wallets:
        state = "NO_SUCCESSFUL_WALLETS"
    elif provider.get("configured") is not True:
        state = "INACTIVE_NO_API_KEY"
    else:
        states = {str(row.get("last_provider_state") or "").upper() for row in wallets}
        state = "READY" if any(s in {"READY", "PARTIAL_ASSET_CAP", "PARTIAL_REJECTED_ROWS"} for s in states) else "WAITING_FOR_FIRST_SCAN"

    return {
        "state": state,
        "available": bool(wallets),
        "wallet_count": len(wallets),
        "wallets": wallets,
        "changes": changes,
        "wallet_limit": ARKHAM_PANEL_WALLET_LIMIT,
        "asset_limit_per_wallet": ARKHAM_PANEL_ASSET_LIMIT_PER_WALLET,
        "change_limit": ARKHAM_PANEL_CHANGE_LIMIT,
        **authority,
    }


def wallet_intelligence_detail(paper_db: Path | str) -> dict[str, Any]:
    path = Path(paper_db)
    provider = arkham_config_status()
    if not path.exists():
        return {"available": False, "reason": "PAPER_DB_MISSING", "rows": [], "provider": provider}
    con = _ro(path)
    try:
        holdings = _arkham_holdings_panel(con, provider)
        if not _table_exists(con, "intelligence_summary_readmodel"):
            return {
                "available": False,
                "reason": "READMODEL_MISSING",
                "rows": [],
                "provider": provider,
                "arkham_holdings": holdings,
            }
        row = con.execute("SELECT * FROM intelligence_summary_readmodel ORDER BY generated_at DESC LIMIT 1").fetchone()
        if row is None:
            return {
                "available": True,
                "rows": [],
                "tracked_wallets": 0,
                "provider": provider,
                "arkham_holdings": holdings,
                "read_only": True,
            }
        data = dict(row)
        try:
            details = json.loads(data.get("wallet_details_json")) if data.get("wallet_details_json") else []
        except Exception:
            details = []
        generated = float(data.get("generated_at") or 0.0)
        age = max(0.0, time.time() - generated) if generated else None
        return {
            "available": True,
            "tracked_wallets": int(data.get("tracked_wallets") or 0),
            "successful_wallets": int(data.get("successful_wallets") or 0),
            "active_whales": int(data.get("active_whales") or 0),
            "generated_at": generated or None,
            "age_seconds": age,
            "stale": bool(age is None or age > 900),
            "rows": details if isinstance(details, list) else [],
            "provider": provider,
            "arkham_holdings": holdings,
            "read_only": True,
        }
    finally:
        con.close()


def auto_trade_health(paper_db: Path | str, *, hours: float = 6.0) -> dict[str, Any]:
    path = Path(paper_db)
    if not path.exists():
        return {"available": False, "reason": "PAPER_DB_MISSING"}
    cutoff = time.time() - max(0.25, float(hours)) * 3600.0
    con = _ro(path)
    try:
        if not _table_exists(con, "candidate_decision_history"):
            return {"available": False, "reason": "DECISION_TABLE_MISSING"}
        columns = {r[1] for r in con.execute("PRAGMA table_info(candidate_decision_history)")}
        reason_col = "reason" if "reason" in columns else None
        action_col = "decision_action" if "decision_action" in columns else None
        total = int(con.execute("SELECT COUNT(*) FROM candidate_decision_history WHERE observed_at >= ?", (cutoff,)).fetchone()[0])
        latest = con.execute("SELECT MAX(observed_at) FROM candidate_decision_history").fetchone()[0]
        reasons = []
        if reason_col:
            reasons = [dict(r) for r in con.execute(f"SELECT COALESCE({reason_col},'UNKNOWN') AS reason, COUNT(*) AS count FROM candidate_decision_history WHERE observed_at >= ? GROUP BY COALESCE({reason_col},'UNKNOWN') ORDER BY count DESC LIMIT 8", (cutoff,)).fetchall()]
        actions = []
        if action_col:
            actions = [dict(r) for r in con.execute(f"SELECT COALESCE({action_col},'UNKNOWN') AS action, COUNT(*) AS count FROM candidate_decision_history WHERE observed_at >= ? GROUP BY COALESCE({action_col},'UNKNOWN') ORDER BY count DESC LIMIT 8", (cutoff,)).fetchall()]
        open_paper = int(con.execute("SELECT COUNT(*) FROM paper_trades WHERE status='OPEN'").fetchone()[0]) if _table_exists(con, "paper_trades") else 0
        return {"available": True, "window_hours": float(hours), "decision_count": total, "latest_decision_at": latest, "latest_age_seconds": (max(0.0, time.time() - float(latest)) if latest else None), "reasons": reasons, "actions": actions, "open_paper_positions": open_paper, "paper_only": True, "live_authority": False}
    finally:
        con.close()


def _cached(key: str, ttl: float, loader):
    now = time.monotonic()
    with _CACHE_LOCK:
        row = _CACHE.get(key)
        if row and now - float(row["at"]) < ttl:
            return row["value"]
    try:
        value = loader()
    except Exception as exc:
        value = {"available": False, "error_type": type(exc).__name__}
    with _CACHE_LOCK:
        _CACHE[key] = {"at": now, "value": value}
    return value


def _parse_rss(source: str, url: str) -> list[dict[str, Any]]:
    response = requests.get(url, timeout=HTTP_TIMEOUT, headers={"User-Agent": "Coinoskobi-Panel/1.0", "Accept": "application/rss+xml, application/xml, text/xml"})
    response.raise_for_status()
    root = ET.fromstring(response.content)
    rows = []
    for item in root.findall(".//item")[:20]:
        title = " ".join((item.findtext("title") or "").split())
        link = (item.findtext("link") or "").strip()
        published = (item.findtext("pubDate") or "").strip()
        if title:
            rows.append({"source": source, "title": title[:300], "url": link[:500], "published_at": published})
    return rows


def live_news_feed() -> dict[str, Any]:
    def load():
        rows, states = [], []
        for source, url in NEWS_SOURCES:
            try:
                batch = _parse_rss(source, url)
                rows.extend(batch)
                states.append({"source": source, "available": True, "count": len(batch)})
            except Exception as exc:
                states.append({"source": source, "available": False, "error_type": type(exc).__name__})
        return {"available": bool(rows), "items": rows[:30], "sources": states, "impact": impact_snapshot(limit=20), "fetched_at": time.time()}
    return _cached("news", NEWS_TTL_SECONDS, load)


def economic_calendar_feed() -> dict[str, Any]:
    def load():
        response = requests.get(CALENDAR_URL, timeout=HTTP_TIMEOUT, headers={"User-Agent": "Coinoskobi-Panel/1.0", "Accept": "application/json"})
        response.raise_for_status()
        payload = response.json()
        rows = []
        for item in list(payload or [])[:120]:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title") or "").strip()
            if title:
                rows.append({"title": title[:220], "country": str(item.get("country") or "").strip().upper()[:12], "impact": str(item.get("impact") or "").strip()[:24], "date": str(item.get("date") or "").strip()[:40], "forecast": item.get("forecast"), "previous": item.get("previous")})
        return {"available": bool(rows), "items": rows, "source": "Forex Factory weekly export", "fetched_at": time.time()}
    return _cached("calendar", CALENDAR_TTL_SECONDS, load)


def register_panel_acceptance_routes(app, *, paper_db: Path | str) -> None:
    @app.get("/api/watch-probes-detail-v2")
    def api_watch_probe_detail_v2(limit: int = 100):
        return watch_probe_detail(paper_db, limit=limit)

    @app.get("/api/wallet-intelligence-v2")
    def api_wallet_intelligence_v2():
        return wallet_intelligence_detail(paper_db)

    @app.get("/api/auto-trade-health-v2")
    def api_auto_trade_health_v2():
        return auto_trade_health(paper_db)

    @app.get("/api/live-news-v2")
    def api_live_news_v2():
        return live_news_feed()

    @app.get("/api/economic-calendar-v2")
    def api_economic_calendar_v2():
        return economic_calendar_feed()

    @app.get("/api/news-impact-v2")
    def api_news_impact_v2(limit: int = 20):
        return impact_snapshot(limit=limit)
