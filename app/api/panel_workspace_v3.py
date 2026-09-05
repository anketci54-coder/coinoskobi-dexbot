from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import re
import sqlite3
import time

from app.api.news_impact import classify_and_forecast
from app.api.panel_acceptance import economic_calendar_feed, live_news_feed, wallet_intelligence_detail


_EVENT_BASE_SCORE = {
    "HACK": 96,
    "EXPLOIT": 94,
    "DELISTING": 90,
    "REGULATORY": 88,
    "TGE": 86,
    "TOKEN_UNLOCK": 82,
    "LISTING": 80,
    "AIRDROP": 78,
    "IDO": 78,
    "ICO": 76,
    "PARTNERSHIP": 68,
    "MAINNET_UPGRADE": 68,
    "SOCIAL_ACCELERATION": 58,
    "RUMOR": 42,
}
_EVENT_LABEL_TR = {
    "HACK": "HACK / SALDIRI",
    "EXPLOIT": "AÇIK / EXPLOIT",
    "DELISTING": "DELİST",
    "REGULATORY": "REGÜLASYON",
    "TGE": "TOKEN ÜRETİMİ",
    "TOKEN_UNLOCK": "TOKEN KİLİT AÇILIMI",
    "LISTING": "LİSTELEME",
    "AIRDROP": "AIRDROP",
    "IDO": "IDO",
    "ICO": "ICO",
    "PARTNERSHIP": "ORTAKLIK",
    "MAINNET_UPGRADE": "MAINNET / GÜNCELLEME",
    "SOCIAL_ACCELERATION": "SOSYAL HIZLANMA",
    "RUMOR": "SÖYLENTİ",
    "MARKET": "PİYASA",
}
_DIRECTION_TR = {
    "POSITIVE": "pozitif",
    "NEGATIVE": "negatif",
    "VOLATILE": "yüksek oynaklık",
    "CONDITIONAL": "koşullu",
    "UNKNOWN": "belirsiz",
}
_LAUNCH_EVENTS = {"AIRDROP", "IDO", "ICO", "TGE", "LISTING"}
_MARKET_KEYWORDS = re.compile(
    r"\b(bitcoin|btc|ethereum|eth|bnb|crypto|cryptocurrency|sec|fed|etf|binance|pancake|stablecoin|hack|exploit|listing|airdrop|ido|ico|tge|token unlock)\b",
    re.I,
)

_CALENDAR_TRANSLATIONS = (
    (re.compile(r"consumer price index|\bcpi\b", re.I), "TÜKETİCİ ENFLASYONU (CPI)"),
    (re.compile(r"producer price index|\bppi\b", re.I), "ÜRETİCİ ENFLASYONU (PPI)"),
    (re.compile(r"interest rate|rate decision|federal funds", re.I), "FAİZ KARARI"),
    (re.compile(r"non.?farm payroll|\bnfp\b", re.I), "TARIM DIŞI İSTİHDAM"),
    (re.compile(r"unemployment", re.I), "İŞSİZLİK"),
    (re.compile(r"gross domestic product|\bgdp\b", re.I), "BÜYÜME (GDP)"),
    (re.compile(r"retail sales", re.I), "PERAKENDE SATIŞLAR"),
    (re.compile(r"jobless claims", re.I), "İŞSİZLİK BAŞVURULARI"),
    (re.compile(r"fomc", re.I), "FOMC"),
    (re.compile(r"powell", re.I), "FED BAŞKANI POWELL"),
    (re.compile(r"ecb", re.I), "ECB"),
)


def _state(score: int) -> str:
    if score >= 80:
        return "HOT"
    if score >= 55:
        return "WARM"
    return "COLD"


def _hours_label(values: Any) -> str:
    if not isinstance(values, (list, tuple)):
        return ""
    return "/".join(str(value).replace("H", "S") for value in values[:3])


def _rank_news_item(item: dict[str, Any]) -> dict[str, Any] | None:
    title = " ".join(str(item.get("title") or "").split())
    if not title:
        return None

    forecast = classify_and_forecast(title)
    event_type = str(forecast.get("event_type") or "").upper()
    ready = forecast.get("state") == "READY"

    if ready:
        base = _EVENT_BASE_SCORE.get(event_type, 50)
        confidence = float(forecast.get("confidence") or 0.0)
        score = min(100, int(round(base + confidence * 8.0)))
        direction = str(forecast.get("direction") or "UNKNOWN").upper()
        label = _EVENT_LABEL_TR.get(event_type, event_type or "PİYASA")
        horizon = _hours_label(forecast.get("horizons"))
        summary = f"{label}; olası etki {_DIRECTION_TR.get(direction, 'belirsiz')}."
        if horizon:
            summary += f" İzleme ufku {horizon}."
    elif _MARKET_KEYWORDS.search(title):
        event_type = "MARKET"
        direction = "UNKNOWN"
        score = 48
        label = "PİYASA"
        summary = "Kripto piyasasını ilgilendiren gelişme; doğrulanmış olay sınıfı oluşmadı."
    else:
        return None

    return {
        "state": _state(score),
        "importance_score": score,
        "event_type": event_type,
        "title_tr": f"{label} · {_DIRECTION_TR.get(direction, 'belirsiz').upper()}",
        "summary_tr": summary,
        "source_title": title[:300],
        "source": str(item.get("source") or "").strip()[:80],
        "url": str(item.get("url") or "").strip()[:500],
        "published_at": str(item.get("published_at") or "").strip()[:120],
        "launch_event": event_type in _LAUNCH_EVENTS,
        "trade_signal": False,
        "decision_authority": False,
    }


def ranked_news_brief(*, limit: int = 10, launch_limit: int = 8) -> dict[str, Any]:
    payload = live_news_feed()
    raw = payload.get("items") if isinstance(payload, dict) else []
    ranked = []
    for item in raw if isinstance(raw, list) else []:
        if not isinstance(item, dict):
            continue
        row = _rank_news_item(item)
        if row is not None:
            ranked.append(row)

    ranked.sort(key=lambda row: (int(row["importance_score"]), bool(row["launch_event"])), reverse=True)
    launches = [row for row in ranked if row["launch_event"]][: max(1, min(int(launch_limit), 20))]
    items = ranked[: max(1, min(int(limit), 20))]
    return {
        "available": bool(items),
        "items": items,
        "launch_items": launches,
        "source_count": len(payload.get("sources") or []) if isinstance(payload, dict) else 0,
        "fetched_at": payload.get("fetched_at") if isinstance(payload, dict) else None,
        "trade_signal": False,
        "decision_authority": False,
        "live_authority": False,
    }


def _calendar_title_tr(title: str) -> str:
    for pattern, replacement in _CALENDAR_TRANSLATIONS:
        if pattern.search(title):
            return replacement
    return "EKONOMİK VERİ"


def _rank_calendar_item(item: dict[str, Any]) -> dict[str, Any] | None:
    title = " ".join(str(item.get("title") or "").split())
    if not title:
        return None
    impact = str(item.get("impact") or "").strip().upper()
    country = str(item.get("country") or "").strip().upper()

    if "HIGH" in impact:
        score = 92
    elif "MED" in impact:
        score = 66
    elif "LOW" in impact:
        score = 35
    else:
        score = 45

    important_country = country in {"USD", "EUR", "CNY", "GBP", "JPY"}
    if important_country:
        score = min(100, score + 4)
    if score < 55:
        return None

    forecast = item.get("forecast")
    previous = item.get("previous")
    detail_parts = [part for part in (
        f"ülke {country}" if country else None,
        f"beklenti {forecast}" if forecast not in (None, "") else None,
        f"önceki {previous}" if previous not in (None, "") else None,
    ) if part]

    return {
        "state": _state(score),
        "importance_score": score,
        "title_tr": _calendar_title_tr(title),
        "summary_tr": "; ".join(detail_parts) if detail_parts else "Piyasa etkisi için izleniyor.",
        "source_title": title[:240],
        "country": country,
        "impact": impact,
        "date": str(item.get("date") or "").strip()[:80],
        "forecast": forecast,
        "previous": previous,
        "trade_signal": False,
        "decision_authority": False,
    }


def ranked_calendar_brief(*, limit: int = 8) -> dict[str, Any]:
    payload = economic_calendar_feed()
    raw = payload.get("items") if isinstance(payload, dict) else []
    ranked = []
    for item in raw if isinstance(raw, list) else []:
        if not isinstance(item, dict):
            continue
        row = _rank_calendar_item(item)
        if row is not None:
            ranked.append(row)
    ranked.sort(key=lambda row: int(row["importance_score"]), reverse=True)
    return {
        "available": bool(ranked),
        "items": ranked[: max(1, min(int(limit), 20))],
        "fetched_at": payload.get("fetched_at") if isinstance(payload, dict) else None,
        "trade_signal": False,
        "decision_authority": False,
        "live_authority": False,
    }


def _ro(path: Path | str) -> sqlite3.Connection:
    con = sqlite3.connect(f"file:{Path(path)}?mode=ro", uri=True, timeout=5)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA busy_timeout=5000")
    return con


def _table_exists(con: sqlite3.Connection, name: str) -> bool:
    return con.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (name,),
    ).fetchone() is not None


def wallet_brief(paper_db: Path | str, *, limit: int = 8) -> dict[str, Any]:
    path = Path(paper_db)
    detail = wallet_intelligence_detail(path)
    holdings = detail.get("arkham_holdings") if isinstance(detail, dict) else {}
    holdings = holdings if isinstance(holdings, dict) else {}

    if not path.exists():
        return {
            "available": False,
            "candidates": 0,
            "successful": 0,
            "holdings_wallets": 0,
            "rows": [],
            "reason": "PAPER_DB_MISSING",
            "read_only": True,
        }

    con = _ro(path)
    try:
        candidates = 0
        rows: list[dict[str, Any]] = []
        candidate_source = None

        if _table_exists(con, "wallet_discovery_source_evidence"):
            candidates = int(con.execute(
                "SELECT COUNT(DISTINCT lower(wallet_uid)) FROM wallet_discovery_source_evidence WHERE active=1"
            ).fetchone()[0])
            rows = [dict(row) for row in con.execute(
                """
                SELECT wallet_uid, source, provider, candidate_state,
                       external_rank, last_seen_at
                FROM wallet_discovery_source_evidence
                WHERE active=1
                ORDER BY last_seen_at DESC, COALESCE(external_rank, 2147483647) ASC
                LIMIT ?
                """,
                (max(1, min(int(limit), 20)),),
            ).fetchall()]
            if candidates or rows:
                candidate_source = "EVIDENCE"

        if not rows and _table_exists(con, "wallet_discovery_registry"):
            registry_rows = [dict(row) for row in con.execute(
                """
                SELECT wallet_uid,
                       discovery_source AS source,
                       freshness_state,
                       lifecycle_state,
                       last_seen_at
                FROM wallet_discovery_registry
                WHERE COALESCE(wallet_uid,'')<>''
                  AND UPPER(COALESCE(lifecycle_state,'ACTIVE'))<>'INACTIVE'
                ORDER BY COALESCE(last_seen_at,0) DESC, lower(wallet_uid) ASC
                LIMIT ?
                """,
                (max(1, min(int(limit), 20)),),
            ).fetchall()]
            candidates = int(con.execute(
                """
                SELECT COUNT(DISTINCT lower(wallet_uid))
                FROM wallet_discovery_registry
                WHERE COALESCE(wallet_uid,'')<>''
                  AND UPPER(COALESCE(lifecycle_state,'ACTIVE'))<>'INACTIVE'
                """
            ).fetchone()[0])
            rows = [
                {
                    "wallet_uid": row.get("wallet_uid"),
                    "source": row.get("source") or "REGISTRY",
                    "provider": None,
                    "candidate_state": row.get("freshness_state") or row.get("lifecycle_state") or "OBSERVED",
                    "external_rank": None,
                    "last_seen_at": row.get("last_seen_at"),
                }
                for row in registry_rows
            ]
            if candidates or rows:
                candidate_source = "REGISTRY"

        successful = 0
        if _table_exists(con, "wallet_success_score"):
            cols = {str(row[1]) for row in con.execute("PRAGMA table_info(wallet_success_score)").fetchall()}
            if "qualification_state" in cols:
                successful = int(con.execute(
                    "SELECT COUNT(DISTINCT lower(wallet_uid)) FROM wallet_success_score WHERE UPPER(COALESCE(qualification_state,''))='SUCCESSFUL'"
                ).fetchone()[0])
    finally:
        con.close()

    now = time.time()
    clean_rows = []
    for row in rows:
        seen = row.get("last_seen_at")
        try:
            age_seconds = max(0.0, now - float(seen))
        except (TypeError, ValueError):
            age_seconds = None
        clean_rows.append({
            "wallet_uid": row.get("wallet_uid"),
            "source": row.get("source"),
            "provider": row.get("provider"),
            "candidate_state": row.get("candidate_state") or "OBSERVED",
            "external_rank": row.get("external_rank"),
            "last_seen_at": seen,
            "age_seconds": age_seconds,
        })

    holding_wallets = holdings.get("wallets") if isinstance(holdings.get("wallets"), list) else []
    return {
        "available": bool(clean_rows or holding_wallets),
        "candidates": candidates,
        "successful": successful,
        "holdings_wallets": len(holding_wallets),
        "rows": clean_rows,
        "candidate_source": candidate_source,
        "holdings_state": holdings.get("state"),
        "provider": detail.get("provider") if isinstance(detail, dict) else None,
        "generated_at": datetime.now(timezone.utc).timestamp(),
        "read_only": True,
        "success_authority": False,
        "trade_authority": False,
        "decision_authority": False,
        "wallet_authority": False,
        "execution_authority": False,
    }


def register_panel_workspace_v3_routes(app, *, paper_db: Path | str) -> None:
    @app.get("/api/market-brief-v3")
    def api_market_brief_v3() -> dict[str, Any]:
        return ranked_news_brief()

    @app.get("/api/calendar-brief-v3")
    def api_calendar_brief_v3() -> dict[str, Any]:
        return ranked_calendar_brief()

    @app.get("/api/wallet-brief-v3")
    def api_wallet_brief_v3() -> dict[str, Any]:
        return wallet_brief(paper_db)
