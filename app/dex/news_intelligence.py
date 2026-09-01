from collections import OrderedDict
import hashlib
import math
import time


EVENT_TYPES = {
    "AIRDROP",
    "IDO",
    "ICO",
    "TGE",
    "LISTING",
    "DELISTING",
    "PARTNERSHIP",
    "EXPLOIT",
    "HACK",
    "TOKEN_UNLOCK",
    "REGULATORY",
    "MAINNET_UPGRADE",
    "SOCIAL_ACCELERATION",
    "RUMOR",
}

SOURCE_TYPES = {
    "WEB",
    "RSS",
    "TELEGRAM",
    "DISCORD",
    "X",
    "OFFICIAL_PROJECT",
    "OFFICIAL_EXCHANGE",
    "OFFICIAL_LAUNCHPAD",
    "SECURITY_RESEARCH",
}


class NewsEvidenceStore:
    """Bounded, evidence-only market/news memory for Phase 5/7.

    Collectors normalize external messages into this contract. This component
    deduplicates, scores source provenance/freshness, and emits intelligence
    evidence only. It never creates a trade, wallet, signing, or execution
    authority.
    """

    def __init__(self, max_events=2048, fresh_seconds=3600):
        self.max_events = max(1, int(max_events))
        self.fresh_seconds = max(1, int(fresh_seconds))
        self._events = OrderedDict()

    def observe(
        self,
        *,
        source_type,
        source_id,
        event_type,
        text,
        published_at,
        observed_at=None,
        token_id=None,
        chain=None,
        entity=None,
        source_trust=0.0,
        verified=False,
        official=False,
        metadata=None,
    ):
        source_type = str(source_type or "").strip().upper()
        event_type = str(event_type or "").strip().upper()
        source_id = str(source_id or "").strip().lower()
        text = " ".join(str(text or "").split())
        published = _finite(published_at)
        observed = _finite(observed_at)
        observed = time.time() if observed is None else observed
        trust = _clamp01(source_trust)

        if (
            source_type not in SOURCE_TYPES
            or event_type not in EVENT_TYPES
            or not source_id
            or not text
            or published is None
            or trust is None
        ):
            return _out("INVALID")

        fingerprint = _fingerprint(
            event_type=event_type,
            token_id=token_id,
            chain=chain,
            entity=entity,
            text=text,
        )

        age_seconds = max(0.0, observed - published)
        freshness = (
            "FRESH" if age_seconds <= self.fresh_seconds else "STALE"
        )

        confidence = trust
        if official:
            confidence = min(1.0, confidence + 0.20)
        if verified:
            confidence = min(1.0, confidence + 0.20)
        if freshness != "FRESH":
            confidence *= 0.50
        if event_type == "RUMOR":
            confidence = min(confidence, 0.35)

        existing = self._events.get(fingerprint)
        sources = []
        if existing:
            sources = list(existing.get("sources") or [])

        source_key = (source_type, source_id)
        known = {
            (row.get("source_type"), row.get("source_id"))
            for row in sources
        }
        if source_key not in known:
            sources.append(
                {
                    "source_type": source_type,
                    "source_id": source_id,
                    "source_trust": trust,
                    "official": bool(official),
                    "verified": bool(verified),
                }
            )

        # Independent corroboration can raise confidence, but duplicated posts
        # from one source never count as independent evidence.
        independent_sources = len(sources)
        corroboration_bonus = min(0.20, max(0, independent_sources - 1) * 0.05)
        confidence = min(1.0, confidence + corroboration_bonus)

        row = {
            "fingerprint": fingerprint,
            "state": _state(confidence, freshness, event_type),
            "event_type": event_type,
            "token_id": _id(token_id),
            "chain": _id(chain),
            "entity": str(entity or "").strip() or None,
            "text": text,
            "published_at": published,
            "last_observed_at": observed,
            "age_seconds": age_seconds,
            "freshness": freshness,
            "confidence": confidence,
            "sources": sources,
            "independent_source_count": independent_sources,
            "metadata": dict(metadata or {}),
            "trade_signal": False,
            "decision_authority": False,
            "paper_authority": False,
            "live_authority": False,
            "wallet_authority": False,
            "signing_authority": False,
            "execution_authority": False,
        }

        self._events[fingerprint] = row
        self._events.move_to_end(fingerprint)

        while len(self._events) > self.max_events:
            self._events.popitem(last=False)

        return dict(row)

    def snapshot(self, *, token_id=None, limit=100):
        token_id = _id(token_id)
        rows = list(reversed(self._events.values()))
        if token_id:
            rows = [row for row in rows if row.get("token_id") == token_id]
        return [dict(row) for row in rows[: max(1, int(limit))]]

    def status(self):
        return {
            "state": "READY",
            "count": len(self._events),
            "bounded": True,
            "max_events": self.max_events,
            "trade_signal": False,
            "decision_authority": False,
            "execution_authority": False,
        }


def normalize_source_event(source_type, payload):
    """Normalize Telegram/Discord/X/web collector payloads without IO."""
    payload = dict(payload or {})
    return {
        "source_type": str(source_type or "").strip().upper(),
        "source_id": payload.get("source_id"),
        "event_type": payload.get("event_type"),
        "text": payload.get("text"),
        "published_at": payload.get("published_at"),
        "token_id": payload.get("token_id"),
        "chain": payload.get("chain"),
        "entity": payload.get("entity"),
        "source_trust": payload.get("source_trust", 0.0),
        "verified": bool(payload.get("verified", False)),
        "official": bool(payload.get("official", False)),
        "metadata": dict(payload.get("metadata") or {}),
    }


def _state(confidence, freshness, event_type):
    if freshness != "FRESH":
        return "STALE"
    if event_type == "RUMOR":
        return "RUMOR"
    if confidence >= 0.80:
        return "CONFIRMED"
    if confidence >= 0.55:
        return "PROBABLE"
    return "UNVERIFIED"


def _fingerprint(*, event_type, token_id, chain, entity, text):
    normalized = "|".join(
        [
            event_type,
            _id(chain) or "",
            _id(token_id) or "",
            str(entity or "").strip().lower(),
            text.strip().lower(),
        ]
    )
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _id(value):
    value = str(value or "").strip().lower()
    return value or None


def _finite(value):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) else None


def _clamp01(value):
    value = _finite(value)
    if value is None:
        return None
    return min(1.0, max(0.0, value))


def _out(state, **payload):
    return {
        "state": state,
        **payload,
        "trade_signal": False,
        "decision_authority": False,
        "paper_authority": False,
        "live_authority": False,
        "wallet_authority": False,
        "signing_authority": False,
        "execution_authority": False,
    }


# Single in-process observation store shared by collectors and market-context
# readers. Bounded by construction; it carries no trade or execution authority.
DEFAULT_NEWS_EVIDENCE_STORE = NewsEvidenceStore()
