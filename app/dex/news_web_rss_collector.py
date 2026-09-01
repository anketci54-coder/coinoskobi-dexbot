from email.utils import parsedate_to_datetime
import ipaddress
from urllib.parse import urlparse
import xml.etree.ElementTree as ET

import requests


class NewsWebRSSCollector:
    """Bounded Web/RSS fetcher for the news observation plane.

    Fetches only caller-configured public HTTP(S) URLs, uses short timeouts,
    caps response size and item count, and returns normalized raw messages for
    NewsCollectorRuntime. No trade or execution authority exists here.
    """

    def __init__(
        self,
        *,
        session=None,
        timeout=3.0,
        max_bytes=512_000,
        max_items=50,
    ):
        self.session = session or requests.Session()
        self.timeout = max(0.1, float(timeout))
        self.max_bytes = max(1024, int(max_bytes))
        self.max_items = max(1, int(max_items))

    def fetch_rss(
        self,
        url,
        *,
        source_id=None,
        source_trust=0.5,
        official=False,
        verified=False,
    ):
        response = self._get(url)
        if response["state"] != "READY":
            return response

        try:
            root = ET.fromstring(response["text"])
        except ET.ParseError as exc:
            return _result(
                "PARSE_ERROR",
                error=f"{type(exc).__name__}: {exc}",
            )

        items = []

        rss_items = root.findall(".//item")
        if rss_items:
            for node in rss_items[: self.max_items]:
                title = _text(node.find("title"))
                description = _text(node.find("description"))
                link = _text(node.find("link"))
                published = _timestamp(_text(node.find("pubDate")))
                text = " ".join(
                    part for part in (title, description) if part
                )
                if not text or published is None:
                    continue
                items.append(
                    self._message(
                        url=url,
                        source_id=source_id,
                        source_trust=source_trust,
                        official=official,
                        verified=verified,
                        text=text,
                        published_at=published,
                        metadata={"url": link or url},
                    )
                )
        else:
            entries = root.findall(".//{*}entry")
            for node in entries[: self.max_items]:
                title = _text(node.find("{*}title"))
                summary = _text(node.find("{*}summary")) or _text(
                    node.find("{*}content")
                )
                published = _timestamp(
                    _text(node.find("{*}published"))
                    or _text(node.find("{*}updated"))
                )
                link = None
                link_node = node.find("{*}link")
                if link_node is not None:
                    link = link_node.attrib.get("href")
                text = " ".join(
                    part for part in (title, summary) if part
                )
                if not text or published is None:
                    continue
                items.append(
                    self._message(
                        url=url,
                        source_id=source_id,
                        source_trust=source_trust,
                        official=official,
                        verified=verified,
                        text=text,
                        published_at=published,
                        metadata={"url": link or url},
                    )
                )

        return _result("READY", messages=items)

    def fetch_web_text(
        self,
        url,
        *,
        source_id=None,
        source_trust=0.5,
        official=False,
        verified=False,
        published_at=None,
    ):
        published = _timestamp(published_at)
        if published is None:
            return _result("MISSING_PUBLISHED_AT")

        response = self._get(url)
        if response["state"] != "READY":
            return response

        text = " ".join(response["text"].split())
        if not text:
            return _result("EMPTY")

        message = self._message(
            url=url,
            source_id=source_id,
            source_trust=source_trust,
            official=official,
            verified=verified,
            text=text,
            published_at=published,
            metadata={"url": url},
        )
        return _result("READY", messages=[message])

    def _get(self, url):
        if not _safe_public_url(url):
            return _result("INVALID_URL")

        try:
            response = self.session.get(
                url,
                timeout=self.timeout,
                headers={
                    "User-Agent": "Coinoskobi-News/1.0",
                    "Accept": "application/rss+xml, application/atom+xml, text/xml, text/plain, text/html",
                },
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            return _result(
                "FETCH_ERROR",
                error=f"{type(exc).__name__}: {exc}"[:500],
            )

        content = response.content
        if len(content) > self.max_bytes:
            return _result("TOO_LARGE")

        encoding = response.encoding or "utf-8"
        text = content.decode(encoding, errors="replace")
        return _result("READY", text=text)

    @staticmethod
    def _message(
        *,
        url,
        source_id,
        source_trust,
        official,
        verified,
        text,
        published_at,
        metadata,
    ):
        host = urlparse(url).hostname or "unknown"
        return {
            "source_id": source_id or host,
            "text": text,
            "published_at": float(published_at),
            "source_trust": source_trust,
            "official": bool(official),
            "verified": bool(verified),
            "metadata": dict(metadata or {}),
        }


def _safe_public_url(value):
    parsed = urlparse(str(value or ""))
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return False
    if parsed.username or parsed.password:
        return False

    host = str(parsed.hostname or "").strip().lower().rstrip(".")
    if not host or host == "localhost" or host.endswith(".localhost"):
        return False

    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return True

    return not (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_multicast
        or address.is_reserved
        or address.is_unspecified
    )


def _text(node):
    if node is None:
        return None
    value = "".join(node.itertext()).strip()
    return value or None


def _timestamp(value):
    if value in (None, ""):
        return None
    try:
        return parsedate_to_datetime(str(value)).timestamp()
    except (TypeError, ValueError, OverflowError):
        pass
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None


def _result(state, *, messages=None, text=None, error=None):
    return {
        "state": state,
        "messages": list(messages or []),
        "text": text,
        "error": error,
        "trade_signal": False,
        "decision_authority": False,
        "paper_authority": False,
        "live_authority": False,
        "wallet_authority": False,
        "signing_authority": False,
        "execution_authority": False,
    }
