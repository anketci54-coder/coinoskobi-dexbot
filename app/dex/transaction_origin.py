import asyncio
import threading
import time
from collections import OrderedDict


class TransactionOriginResolver:
    """Bounded tx-hash -> tx.from resolver with timeout and negative TTL."""

    def __init__(self, max_entries=8192, fetcher=None, timeout_seconds=1.5, negative_ttl_seconds=5.0):
        self.max_entries = max(1, int(max_entries))
        self.fetcher = fetcher or self._default_fetcher
        self.timeout_seconds = max(0.05, float(timeout_seconds))
        self.negative_ttl_seconds = max(0.0, float(negative_ttl_seconds))
        self._cache = OrderedDict()
        self._negative = OrderedDict()
        self._lock = threading.RLock()
        self.provider_calls = 0
        self.cache_hits = 0
        self.negative_hits = 0
        self.resolve_failures = 0
        self.evictions = 0

    @property
    def size(self):
        with self._lock:
            return len(self._cache)

    def _negative_hit(self, tx_hash):
        now = time.monotonic()
        expiry = self._negative.get(tx_hash)
        if expiry is None:
            return False
        if expiry <= now:
            self._negative.pop(tx_hash, None)
            return False
        self._negative.move_to_end(tx_hash)
        self.negative_hits += 1
        return True

    def _remember_negative(self, tx_hash):
        if self.negative_ttl_seconds <= 0:
            return
        self._negative[tx_hash] = time.monotonic() + self.negative_ttl_seconds
        self._negative.move_to_end(tx_hash)
        while len(self._negative) > self.max_entries:
            self._negative.popitem(last=False)

    async def resolve(self, transaction_hash):
        tx_hash = str(transaction_hash or "").strip().lower()
        if not tx_hash:
            return self._out("UNKNOWN", None, None, "TX_HASH_MISSING")

        with self._lock:
            cached = self._cache.get(tx_hash)
            if cached is not None:
                self._cache.move_to_end(tx_hash)
                self.cache_hits += 1
                return self._out("READY", tx_hash, cached, "CACHE")
            if self._negative_hit(tx_hash):
                return self._out("UNKNOWN", tx_hash, None, "NEGATIVE_TTL")

        try:
            result = await asyncio.wait_for(
                asyncio.to_thread(self.fetcher, tx_hash),
                timeout=self.timeout_seconds,
            )
            with self._lock:
                self.provider_calls += 1
        except Exception as exc:
            with self._lock:
                self.provider_calls += 1
                self.resolve_failures += 1
                self._remember_negative(tx_hash)
            return self._out("UNKNOWN", tx_hash, None, f"PROVIDER_ERROR:{type(exc).__name__}")

        address = self._extract_from(result)
        if not address:
            with self._lock:
                self.resolve_failures += 1
                self._remember_negative(tx_hash)
            return self._out("UNKNOWN", tx_hash, None, "TX_FROM_MISSING")

        with self._lock:
            self._negative.pop(tx_hash, None)
            if tx_hash not in self._cache and len(self._cache) >= self.max_entries:
                self._cache.popitem(last=False)
                self.evictions += 1
            self._cache[tx_hash] = address
            self._cache.move_to_end(tx_hash)
        return self._out("READY", tx_hash, address, "PROVIDER")

    def forget(self, transaction_hash):
        tx_hash = str(transaction_hash or "").strip().lower()
        if not tx_hash:
            return False
        with self._lock:
            self._negative.pop(tx_hash, None)
            return self._cache.pop(tx_hash, None) is not None

    def status(self):
        with self._lock:
            return {
                "state": "READY",
                "size": len(self._cache),
                "negative_size": len(self._negative),
                "max_entries": self.max_entries,
                "timeout_seconds": self.timeout_seconds,
                "negative_ttl_seconds": self.negative_ttl_seconds,
                "provider_calls": self.provider_calls,
                "cache_hits": self.cache_hits,
                "negative_hits": self.negative_hits,
                "resolve_failures": self.resolve_failures,
                "evictions": self.evictions,
                "bounded": True,
                "wallet_identity_source": "TRANSACTION_FROM_ONLY",
                "swap_sender_is_wallet": False,
                "decision_authority": False,
                "paper_authority": False,
                "live_authority": False,
                "wallet_authority": False,
                "execution_authority": False,
            }

    @staticmethod
    def _extract_from(result):
        if result is None:
            return None
        if isinstance(result, dict):
            value = result.get("from")
        else:
            value = getattr(result, "from", None)
            if value is None:
                try:
                    value = result["from"]
                except Exception:
                    value = None
        if not value:
            return None
        return str(value).strip().lower() or None

    @staticmethod
    def _default_fetcher(transaction_hash):
        from app.chains.bsc import w3
        return w3.eth.get_transaction(transaction_hash)

    @staticmethod
    def _out(state, transaction_hash, address, source):
        return {
            "state": state,
            "transaction_hash": transaction_hash,
            "address": address,
            "source": source,
            "identity_guessing": False,
            "swap_sender_is_wallet": False,
            "decision_authority": False,
            "paper_authority": False,
            "live_authority": False,
            "wallet_authority": False,
            "execution_authority": False,
        }
