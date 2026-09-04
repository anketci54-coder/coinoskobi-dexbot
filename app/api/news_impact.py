from __future__ import annotations

import re
import time
from typing import Any

from app.dex.news_classifier import classify_news_event
from app.dex.news_intelligence import DEFAULT_NEWS_EVIDENCE_STORE


_EVENT_IMPACT = {
    "HACK": ("NEGATIVE", "HIGH", ("15M", "1H", "6H")),
    "EXPLOIT": ("NEGATIVE", "HIGH", ("15M", "1H", "6H")),
    "DELISTING": ("NEGATIVE", "HIGH", ("1H", "6H", "24H")),
    "REGULATORY": ("CONDITIONAL", "HIGH", ("1H", "6H", "24H")),
    "TOKEN_UNLOCK": ("NEGATIVE", "MEDIUM", ("6H", "24H", "72H")),
    "LISTING": ("POSITIVE", "MEDIUM", ("15M", "1H", "6H")),
    "PARTNERSHIP": ("POSITIVE", "MEDIUM", ("1H", "6H", "24H")),
    "MAINNET_UPGRADE": ("POSITIVE", "MEDIUM", ("1H", "6H", "24H")),
    "AIRDROP": ("VOLATILE", "MEDIUM", ("1H", "6H", "24H")),
    "ICO": ("VOLATILE", "MEDIUM", ("1H", "6H", "24H")),
    "IDO": ("VOLATILE", "MEDIUM", ("1H", "6H", "24H")),
    "TGE": ("VOLATILE", "HIGH", ("15M", "1H", "6H")),
    "SOCIAL_ACCELERATION": ("VOLATILE", "LOW", ("15M", "1H")),
    "RUMOR": ("UNKNOWN", "LOW", ("15M", "1H")),
}

_NEGATIVE_REG = re.compile(
    r"\b(sanctions?|ban(?:ned|s)?|lawsuits?|charges?|probes?|investigations?|freezes?|seizes?|restrictions?|fines?|cease|halt|illegal|yaptırım(?:lar)?|yasak(?:lar)?|dava(?:lar)?|soruşturma(?:lar)?|ceza(?:lar)?)\b",
    re.I,
)
_POSITIVE_REG = re.compile(
    r"\b(approve|approval|approved|licensed|licenses?|license|clarity|frameworks?|framework|authorized|onay|lisans(?:lar)?|çerçeve(?:ler)?)\b",
    re.I,
)


def _regulatory_direction(text: str) -> str:
    if _NEGATIVE_REG.search(text or ""):
        return "NEGATIVE"
    if _POSITIVE_REG.search(text or ""):
        return "POSITIVE"
    return "CONDITIONAL"


def _affected_scope(row: dict[str, Any]) -> list[str]:
    scope = []
    token = row.get("token_id")
    chain = row.get("chain")
    entity = row.get("entity")
    if token:
        scope.append(f"TOKEN:{token}")
    if chain:
        scope.append(f"CHAIN:{chain}")
    if entity:
        scope.append(f"ENTITY:{entity}")
    event = str(row.get("event_type") or "").upper()
    if event in {"REGULATORY", "HACK", "EXPLOIT"} and not scope:
        scope.append("CRYPTO_MARKET")
    return scope or ["UNKNOWN_SCOPE"]


def forecast_news_event(row: dict[str, Any]) -> dict[str, Any]:
    event = str(row.get("event_type") or "").upper()
    text = str(row.get("text") or "")
    direction, risk, horizons = _EVENT_IMPACT.get(
        event,
        ("UNKNOWN", "LOW", ("1H",)),
    )
    if event == "REGULATORY":
        direction = _regulatory_direction(text)

    evidence_confidence = float(row.get("confidence") or 0.0)
    freshness = str(row.get("freshness") or "UNKNOWN").upper()
    source_count = int(row.get("independent_source_count") or 0)
    confidence = evidence_confidence
    if freshness != "FRESH":
        confidence *= 0.5
    if source_count <= 1 and event in {"RUMOR", "SOCIAL_ACCELERATION"}:
        confidence = min(confidence, 0.35)

    if confidence >= 0.80:
        confidence_label = "HIGH"
    elif confidence >= 0.55:
        confidence_label = "MEDIUM"
    elif confidence >= 0.30:
        confidence_label = "LOW"
    else:
        confidence_label = "INSUFFICIENT"

    return {
        "fingerprint": row.get("fingerprint"),
        "event_type": event or "UNKNOWN",
        "direction": direction,
        "risk": risk,
        "horizons": list(horizons),
        "affected_scope": _affected_scope(row),
        "confidence": round(confidence, 4),
        "confidence_label": confidence_label,
        "reason": (
            f"{event or 'UNKNOWN'} olayı; kaynak güveni ve bağımsız doğrulama ile sınırlandırılmış öngörü."
        ),
        "trade_signal": False,
        "decision_authority": False,
        "paper_authority": False,
        "live_authority": False,
        "wallet_authority": False,
        "execution_authority": False,
    }


def impact_snapshot(*, limit: int = 20) -> dict[str, Any]:
    limit = max(1, min(int(limit), 50))
    rows = DEFAULT_NEWS_EVIDENCE_STORE.snapshot(limit=limit)
    forecasts = [forecast_news_event(row) for row in rows]
    actionable = [
        item for item in forecasts
        if item["confidence_label"] in {"MEDIUM", "HIGH"}
        and item["direction"] != "UNKNOWN"
    ]
    return {
        "generated_at": time.time(),
        "event_count": len(rows),
        "actionable_count": len(actionable),
        "forecasts": forecasts,
        "trade_signal": False,
        "decision_authority": False,
        "live_authority": False,
    }


def classify_and_forecast(text: str, *, explicit_event_type: str | None = None) -> dict[str, Any]:
    classification = classify_news_event(text, explicit_event_type=explicit_event_type)
    if classification.get("state") != "CLASSIFIED":
        return {
            "state": "UNCLASSIFIED",
            "trade_signal": False,
            "decision_authority": False,
        }
    row = {
        "event_type": classification.get("event_type"),
        "text": text,
        "confidence": classification.get("classification_confidence") or 0.0,
        "freshness": "FRESH",
        "independent_source_count": 1,
    }
    return {"state": "READY", **forecast_news_event(row)}
