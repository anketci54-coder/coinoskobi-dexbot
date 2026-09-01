import time

import requests


class TelegramCollector:
    def __init__(self, *, bot_token=None, session=None, timeout=3.0):
        self.bot_token = str(bot_token or "").strip()
        self.session = session or requests.Session()
        self.timeout = max(0.1, float(timeout))

    def fetch_updates(self, *, offset=None, limit=50):
        if not self.bot_token:
            return _result("UNAVAILABLE", "TELEGRAM", [])

        params = {
            "limit": max(1, min(int(limit), 100)),
            "timeout": 0,
            "allowed_updates": ["channel_post", "message"],
        }
        if offset is not None:
            params["offset"] = int(offset)

        url = f"https://api.telegram.org/bot{self.bot_token}/getUpdates"

        try:
            response = self.session.get(
                url,
                params=params,
                timeout=self.timeout,
            )
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError) as exc:
            return _result(
                "FETCH_ERROR",
                "TELEGRAM",
                [],
                error=f"{type(exc).__name__}: {exc}",
            )

        if payload.get("ok") is not True:
            return _result("FETCH_ERROR", "TELEGRAM", [])

        messages = []
        next_offset = offset

        for update in list(payload.get("result") or [])[:100]:
            update_id = update.get("update_id")
            if isinstance(update_id, int):
                next_offset = update_id + 1

            msg = update.get("channel_post") or update.get("message") or {}
            chat = dict(msg.get("chat") or {})
            text = msg.get("text") or msg.get("caption")
            if not text:
                continue

            messages.append(
                {
                    "source_id": str(chat.get("id") or "telegram"),
                    "channel_name": chat.get("title") or chat.get("username"),
                    "message_id": msg.get("message_id"),
                    "text": text,
                    "published_at": float(msg.get("date") or time.time()),
                    "source_trust": 0.5,
                    "official": False,
                    "verified": False,
                }
            )

        return _result(
            "READY",
            "TELEGRAM",
            messages,
            cursor=next_offset,
        )


class DiscordCollector:
    def __init__(self, *, bot_token=None, session=None, timeout=3.0):
        self.bot_token = str(bot_token or "").strip()
        self.session = session or requests.Session()
        self.timeout = max(0.1, float(timeout))

    def fetch_channel(self, channel_id, *, limit=50, before=None):
        channel_id = str(channel_id or "").strip()
        if not self.bot_token or not channel_id:
            return _result("UNAVAILABLE", "DISCORD", [])

        params = {"limit": max(1, min(int(limit), 100))}
        if before:
            params["before"] = str(before)

        try:
            response = self.session.get(
                f"https://discord.com/api/v10/channels/{channel_id}/messages",
                params=params,
                timeout=self.timeout,
                headers={"Authorization": f"Bot {self.bot_token}"},
            )
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError) as exc:
            return _result(
                "FETCH_ERROR",
                "DISCORD",
                [],
                error=f"{type(exc).__name__}: {exc}",
            )

        messages = []
        for row in list(payload or [])[:100]:
            text = str(row.get("content") or "").strip()
            if not text:
                continue
            author = dict(row.get("author") or {})
            messages.append(
                {
                    "source_id": channel_id,
                    "channel_id": channel_id,
                    "message_id": row.get("id"),
                    "author_id": author.get("id"),
                    "text": text,
                    "published_at": _iso_timestamp(row.get("timestamp")),
                    "source_trust": 0.5,
                    "official": False,
                    "verified": bool(author.get("verified", False)),
                }
            )

        return _result("READY", "DISCORD", messages)


class XCollector:
    def __init__(self, *, bearer_token=None, session=None, timeout=3.0):
        self.bearer_token = str(bearer_token or "").strip()
        self.session = session or requests.Session()
        self.timeout = max(0.1, float(timeout))

    def search_recent(self, query, *, max_results=25, next_token=None):
        query = str(query or "").strip()
        if not self.bearer_token or not query:
            return _result("UNAVAILABLE", "X", [])

        params = {
            "query": query,
            "max_results": max(10, min(int(max_results), 100)),
            "tweet.fields": "created_at,public_metrics,author_id",
        }
        if next_token:
            params["next_token"] = str(next_token)

        try:
            response = self.session.get(
                "https://api.x.com/2/tweets/search/recent",
                params=params,
                timeout=self.timeout,
                headers={"Authorization": f"Bearer {self.bearer_token}"},
            )
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError) as exc:
            return _result(
                "FETCH_ERROR",
                "X",
                [],
                error=f"{type(exc).__name__}: {exc}",
            )

        messages = []
        for row in list(payload.get("data") or [])[:100]:
            metrics = dict(row.get("public_metrics") or {})
            text = str(row.get("text") or "").strip()
            if not text:
                continue
            messages.append(
                {
                    "source_id": str(row.get("author_id") or "x"),
                    "account_id": row.get("author_id"),
                    "post_id": row.get("id"),
                    "text": text,
                    "published_at": _iso_timestamp(row.get("created_at")),
                    "reply_count": metrics.get("reply_count"),
                    "repost_count": metrics.get("retweet_count"),
                    "like_count": metrics.get("like_count"),
                    "source_trust": 0.5,
                    "official": False,
                    "verified": False,
                }
            )

        meta = dict(payload.get("meta") or {})
        return _result(
            "READY",
            "X",
            messages,
            cursor=meta.get("next_token"),
        )


def _iso_timestamp(value):
    if not value:
        return time.time()
    try:
        from datetime import datetime
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp()
    except (TypeError, ValueError):
        return time.time()


def _result(state, source_type, messages, *, cursor=None, error=None):
    return {
        "state": state,
        "source_type": source_type,
        "messages": list(messages or []),
        "cursor": cursor,
        "error": error,
        "bounded": True,
        "trade_signal": False,
        "decision_authority": False,
        "paper_authority": False,
        "live_authority": False,
        "wallet_authority": False,
        "signing_authority": False,
        "execution_authority": False,
    }
