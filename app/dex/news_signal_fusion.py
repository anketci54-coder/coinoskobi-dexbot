POSITIVE_EVENTS = {"AIRDROP", "IDO", "ICO", "TGE", "LISTING", "PARTNERSHIP", "MAINNET_UPGRADE"}
NEGATIVE_EVENTS = {"DELISTING", "EXPLOIT", "HACK", "TOKEN_UNLOCK", "REGULATORY"}


def fuse_news_signals(events, *, token_id=None, max_events=64):
    """Fuse fresh evidence into advisory market intelligence, never a trade signal."""
    token = str(token_id or "").strip().lower() or None
    rows = []
    for event in events or []:
        row = dict(event or {})
        if row.get("freshness") != "FRESH":
            continue
        if token and str(row.get("token_id") or "").strip().lower() != token:
            continue
        rows.append(row)
        if len(rows) >= max(1, int(max_events)):
            break

    if not rows:
        return _out("UNKNOWN", "NEUTRAL", 0.0, [], 0, 0)

    positive = 0.0
    negative = 0.0
    tags = []
    credible = 0

    for row in rows:
        event_type = str(row.get("event_type") or "").upper()
        confidence = _confidence(row.get("confidence"))
        state = str(row.get("state") or "").upper()

        if state in {"CONFIRMED", "PROBABLE"}:
            credible += 1
        else:
            confidence *= 0.35

        if event_type in POSITIVE_EVENTS:
            positive += confidence
        elif event_type in NEGATIVE_EVENTS:
            negative += confidence
        elif event_type == "RUMOR":
            tags.append("RUMOR_PRESENT")

        if event_type and event_type not in tags:
            tags.append(event_type)

    total = positive + negative
    strength = abs(positive - negative) / total if total > 0 else 0.0

    if positive > 0 and negative > 0 and strength < 0.35:
        state = "MIXED"
        direction = "MIXED"
    elif positive > negative and credible > 0:
        state = "READY"
        direction = "POSITIVE"
    elif negative > positive and credible > 0:
        state = "READY"
        direction = "NEGATIVE"
    else:
        state = "UNVERIFIED"
        direction = "NEUTRAL"

    return _out(state, direction, strength, tags, len(rows), credible,
                positive_score=positive, negative_score=negative)


def _confidence(value):
    try:
        return min(1.0, max(0.0, float(value)))
    except (TypeError, ValueError):
        return 0.0


def _out(state, direction, strength, tags, event_count, credible_count, **extra):
    return {
        "state": state,
        "direction": direction,
        "strength": float(strength),
        "tags": list(tags),
        "event_count": int(event_count),
        "credible_event_count": int(credible_count),
        **extra,
        "advisory_only": True,
        "trade_signal": False,
        "decision_authority": False,
        "paper_authority": False,
        "live_authority": False,
        "wallet_authority": False,
        "signing_authority": False,
        "execution_authority": False,
    }
