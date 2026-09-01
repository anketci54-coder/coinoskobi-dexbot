import re

from app.dex.news_intelligence import EVENT_TYPES


_RULES = (
    ("EXPLOIT", (r"\bexploit(ed|ing)?\b", r"\bhack(ed|ing)?\b", r"\bdrain(ed|ing)?\b")),
    ("DELISTING", (r"\bdelist(ed|ing)?\b", r"\bremove(d|s)? trading\b")),
    ("TOKEN_UNLOCK", (r"\btoken unlock\b", r"\bvesting unlock\b", r"\bunlock schedule\b")),
    ("AIRDROP", (r"\bairdrop\b", r"\bclaim window\b", r"\beligibility checker\b")),
    ("IDO", (r"\bido\b", r"\binitial dex offering\b", r"\blaunchpad sale\b")),
    ("ICO", (r"\bico\b", r"\binitial coin offering\b", r"\btoken sale\b")),
    ("TGE", (r"\btge\b", r"\btoken generation event\b")),
    ("LISTING", (r"\blist(ed|ing)?\b", r"\bspot trading\b", r"\btrading pair\b")),
    ("PARTNERSHIP", (r"\bpartner(ship|ed)?\b", r"\bcollaborat(e|ion|ing)\b")),
    (
        "REGULATORY",
        (
            r"\bsecurities and exchange commission\b",
            r"\bsec\s+(charges?|charged|lawsuit|sues?|sued|investigat(?:e|es|ed|ion|ing)|enforcement|filing|complaint|settlement)\b",
            r"\bregulat(or|ory|ion)\b",
            r"\blicen[cs]e\b",
        ),
    ),
    ("MAINNET_UPGRADE", (r"\bmainnet\b", r"\bnetwork upgrade\b", r"\bhard fork\b")),
)


def classify_news_event(text, *, explicit_event_type=None):
    """Deterministically classify market/news text without external IO or AI.

    Explicit upstream labels are accepted only when they belong to the
    canonical EVENT_TYPES contract. Unknown labels never bypass validation.
    No class grants trade authority.
    """
    explicit = str(explicit_event_type or "").strip().upper()
    if explicit:
        if explicit in EVENT_TYPES:
            return _out("CLASSIFIED", explicit, 1.0, "EXPLICIT")
        return _out("UNKNOWN", None, 0.0, "INVALID_EXPLICIT")

    normalized = " ".join(str(text or "").lower().split())
    if not normalized:
        return _out("UNKNOWN", None, 0.0, "EMPTY")

    for event_type, patterns in _RULES:
        if any(re.search(pattern, normalized) for pattern in patterns):
            return _out("CLASSIFIED", event_type, 0.70, "RULE")

    social = _social_acceleration(normalized)
    if social:
        return _out("CLASSIFIED", "SOCIAL_ACCELERATION", 0.50, "RULE")

    return _out("UNKNOWN", None, 0.0, "NO_MATCH")


def _social_acceleration(text):
    phrases = (
        "trending now",
        "going viral",
        "viral now",
        "mentions exploding",
        "social volume spike",
    )
    return any(phrase in text for phrase in phrases)


def _out(state, event_type, confidence, source):
    return {
        "state": state,
        "event_type": event_type,
        "classification_confidence": float(confidence),
        "classification_source": source,
        "trade_signal": False,
        "decision_authority": False,
        "paper_authority": False,
        "live_authority": False,
        "wallet_authority": False,
        "signing_authority": False,
        "execution_authority": False,
    }
