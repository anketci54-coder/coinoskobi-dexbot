from app.dex.news_signal_fusion import fuse_news_signals


def bind_news_market_context(context, row, news_store):
    """Attach bounded news evidence to an existing candidate market context.

    This bridge is additive and evidence-only. Missing store/token evidence is
    explicit UNKNOWN and never changes trade/decision authority.
    """
    context = dict(context or {})
    row = dict(row or {})

    token_id = _token_id(row)

    if news_store is None or not token_id:
        context["news_intelligence"] = _unknown(token_id)
        return context

    snapshot = getattr(news_store, "snapshot", None)
    if not callable(snapshot):
        context["news_intelligence"] = _unknown(token_id)
        return context

    events = snapshot(token_id=token_id, limit=100) or []
    fusion = fuse_news_signals(events, token_id=token_id)

    context["news_intelligence"] = {
        "state": fusion.get("state", "UNKNOWN"),
        "token_id": token_id,
        "event_count": len(events),
        "signal": fusion,
        "fresh_event_types": sorted(
            {
                str(event.get("event_type") or "").strip().upper()
                for event in events
                if event.get("freshness") == "FRESH"
                and event.get("event_type")
            }
        ),
        "trade_signal": False,
        "decision_authority": False,
        "paper_authority": False,
        "live_authority": False,
        "wallet_authority": False,
        "signing_authority": False,
        "execution_authority": False,
    }

    return context


def _token_id(row):
    for key in ("token", "base_token", "token_id"):
        value = str(row.get(key) or "").strip().lower()
        if value:
            if value.startswith("bsc_"):
                value = value[4:]
            return value
    return None


def _unknown(token_id):
    return {
        "state": "UNKNOWN",
        "token_id": token_id,
        "event_count": 0,
        "signal": {
            "state": "UNKNOWN",
            "trade_signal": False,
            "decision_authority": False,
            "execution_authority": False,
        },
        "fresh_event_types": [],
        "trade_signal": False,
        "decision_authority": False,
        "paper_authority": False,
        "live_authority": False,
        "wallet_authority": False,
        "signing_authority": False,
        "execution_authority": False,
    }
