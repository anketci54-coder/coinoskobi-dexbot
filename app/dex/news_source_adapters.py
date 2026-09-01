from app.dex.news_intelligence import normalize_source_event


class TelegramNewsAdapter:
    source_type = "TELEGRAM"

    def normalize(self, message):
        return _normalize_social(self.source_type, message)


class DiscordNewsAdapter:
    source_type = "DISCORD"

    def normalize(self, message):
        return _normalize_social(self.source_type, message)


class XNewsAdapter:
    source_type = "X"

    def normalize(self, message):
        return _normalize_social(self.source_type, message)


class WebNewsAdapter:
    source_type = "WEB"

    def normalize(self, message):
        return _normalize_social(self.source_type, message)


class RSSNewsAdapter:
    source_type = "RSS"

    def normalize(self, message):
        return _normalize_social(self.source_type, message)


def _normalize_social(source_type, message):
    message = dict(message or {})

    payload = {
        "source_id": _first(
            message.get("source_id"),
            message.get("channel_id"),
            message.get("account_id"),
            message.get("feed_id"),
            message.get("url"),
        ),
        "event_type": message.get("event_type"),
        "text": _first(
            message.get("text"),
            message.get("content"),
            message.get("body"),
            message.get("title"),
        ),
        "published_at": _first(
            message.get("published_at"),
            message.get("created_at"),
            message.get("timestamp"),
        ),
        "token_id": message.get("token_id"),
        "chain": message.get("chain"),
        "entity": message.get("entity"),
        "source_trust": message.get("source_trust", 0.0),
        "verified": bool(message.get("verified", False)),
        "official": bool(message.get("official", False)),
        "metadata": _metadata(source_type, message),
    }

    return normalize_source_event(source_type, payload)


def _metadata(source_type, message):
    metadata = dict(message.get("metadata") or {})

    aliases = {
        "TELEGRAM": ("message_id", "channel_name", "forwarded_from"),
        "DISCORD": ("message_id", "guild_id", "channel_name", "author_id"),
        "X": ("post_id", "account_handle", "reply_count", "repost_count", "like_count"),
        "WEB": ("url", "domain", "author"),
        "RSS": ("url", "feed_id", "guid"),
    }

    for key in aliases.get(source_type, ()):
        value = message.get(key)
        if value is not None:
            metadata[key] = value

    return metadata


def _first(*values):
    for value in values:
        if value is None:
            continue
        if isinstance(value, str):
            value = value.strip()
            if not value:
                continue
        return value
    return None
