from app.dex.news_classifier import classify_news_event
from app.dex.news_intelligence import DEFAULT_NEWS_EVIDENCE_STORE
from app.dex.news_source_adapters import (
    DiscordNewsAdapter,
    RSSNewsAdapter,
    TelegramNewsAdapter,
    WebNewsAdapter,
    XNewsAdapter,
)


_ADAPTERS = {
    "TELEGRAM": TelegramNewsAdapter,
    "DISCORD": DiscordNewsAdapter,
    "X": XNewsAdapter,
    "WEB": WebNewsAdapter,
    "RSS": RSSNewsAdapter,
}


class NewsCollectorRuntime:
    """Bounded ingestion boundary for external news/social collectors.

    Network access belongs to provider-specific fetchers outside this class.
    This runtime only normalizes, classifies, and records evidence into the
    canonical bounded store. It grants no decision or execution authority.
    """

    def __init__(self, *, store=None, max_batch=100):
        self.store = store or DEFAULT_NEWS_EVIDENCE_STORE
        self.max_batch = max(1, int(max_batch))

    def ingest(self, source_type, messages):
        source_type = str(source_type or "").strip().upper()
        adapter_cls = _ADAPTERS.get(source_type)
        if adapter_cls is None:
            return _result("INVALID_SOURCE", 0, 0, 0)

        adapter = adapter_cls()
        accepted = 0
        rejected = 0
        classified = 0

        for raw in list(messages or [])[: self.max_batch]:
            normalized = adapter.normalize(raw)
            classification = classify_news_event(
                normalized.get("text"),
                explicit_event_type=normalized.get("event_type"),
            )

            if classification.get("state") != "CLASSIFIED":
                rejected += 1
                continue

            normalized["event_type"] = classification["event_type"]
            metadata = dict(normalized.get("metadata") or {})
            metadata["classification_source"] = classification.get(
                "classification_source"
            )
            metadata["classification_confidence"] = classification.get(
                "classification_confidence"
            )
            normalized["metadata"] = metadata

            row = self.store.observe(**normalized)
            if row.get("state") == "INVALID":
                rejected += 1
                continue

            accepted += 1
            classified += 1

        return _result("READY", accepted, rejected, classified)


def _result(state, accepted, rejected, classified):
    return {
        "state": state,
        "accepted": int(accepted),
        "rejected": int(rejected),
        "classified": int(classified),
        "bounded": True,
        "trade_signal": False,
        "decision_authority": False,
        "paper_authority": False,
        "live_authority": False,
        "wallet_authority": False,
        "signing_authority": False,
        "execution_authority": False,
    }
