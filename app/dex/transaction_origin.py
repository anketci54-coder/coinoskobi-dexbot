import asyncio
import threading
import time
from collections import OrderedDict


_ORIGIN_EVIDENCE_MAX = 16384
_ORIGIN_EVIDENCE = OrderedDict()
_ORIGIN_EVIDENCE_LOCK = threading.RLock()


def _normalize_hash(transaction_hash):
    return str(transaction_hash or "").strip().lower()


def _normalize_address(address):
    value = str(address or "").strip().lower()
    return value or None


def remember_transaction_origin(transaction_hash, address):
    """
    Process-local bounded evidence bridge.

    Stores only an already-resolved tx.from fact. It never fetches,
    guesses, or treats a Swap sender as a wallet identity.
    """
    tx_hash = _normalize_hash(transaction_hash)
    address = _normalize_address(address)

    if not tx_hash or not address:
        return False

    with _ORIGIN_EVIDENCE_LOCK:
        _ORIGIN_EVIDENCE.pop(tx_hash, None)
        _ORIGIN_EVIDENCE[tx_hash] = address

        while len(_ORIGIN_EVIDENCE) > _ORIGIN_EVIDENCE_MAX:
            _ORIGIN_EVIDENCE.popitem(last=False)

    return True


def resolved_transaction_origin(transaction_hash):
    """Return a previously proven tx.from value, or None."""
    tx_hash = _normalize_hash(transaction_hash)

    if not tx_hash:
        return None

    with _ORIGIN_EVIDENCE_LOCK:
        address = _ORIGIN_EVIDENCE.get(tx_hash)

        if address is not None:
            _ORIGIN_EVIDENCE.move_to_end(tx_hash)

        return address


def forget_transaction_origin(transaction_hash):
    tx_hash = _normalize_hash(transaction_hash)

    if not tx_hash:
        return False

    with _ORIGIN_EVIDENCE_LOCK:
        return _ORIGIN_EVIDENCE.pop(tx_hash, None) is not None


def transaction_origin_evidence_status():
    with _ORIGIN_EVIDENCE_LOCK:
        return {
            "state": "READY",
            "size": len(_ORIGIN_EVIDENCE),
            "max_entries": _ORIGIN_EVIDENCE_MAX,
            "bounded": True,
            "identity_source": "TRANSACTION_FROM_ONLY",
            "swap_sender_is_wallet": False,
            "decision_authority": False,
            "execution_authority": False,
        }


class TransactionOriginResolver:
    """
    Bounded tx-hash -> tx.from resolver.

    The hot path performs one immediate bounded provider attempt. A failed
    provider lookup may schedule exactly one bounded follow-up after the
    negative TTL. The follow-up can only publish a proven transaction.from
    value into the existing evidence bridge and grants no trade authority.
    """

    def __init__(
        self,
        max_entries=8192,
        fetcher=None,
        timeout_seconds=1.5,
        negative_ttl_seconds=5.0,
        retry_delay_seconds=None,
        max_pending_retries=64,
    ):
        self.max_entries = max(1, int(max_entries))
        self.fetcher = fetcher or self._default_fetcher
        self.timeout_seconds = max(0.05, float(timeout_seconds))
        self.negative_ttl_seconds = max(
            0.0,
            float(negative_ttl_seconds),
        )
        self.retry_delay_seconds = max(
            0.05,
            float(
                retry_delay_seconds
                if retry_delay_seconds is not None
                else max(0.10, self.negative_ttl_seconds + 0.05)
            ),
        )
        self.max_pending_retries = max(
            1,
            min(self.max_entries, int(max_pending_retries)),
        )
        self._cache = OrderedDict()
        self._negative = OrderedDict()
        self._retry_tasks = OrderedDict()
        self._lock = threading.RLock()
        self.provider_calls = 0
        self.cache_hits = 0
        self.negative_hits = 0
        self.resolve_failures = 0
        self.evictions = 0
        self.retry_scheduled = 0
        self.retry_attempts = 0
        self.retry_successes = 0
        self.retry_failures = 0
        self.retry_dropped = 0
        self.retry_cancelled = 0

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

        self._negative[tx_hash] = (
            time.monotonic()
            + self.negative_ttl_seconds
        )
        self._negative.move_to_end(tx_hash)

        while len(self._negative) > self.max_entries:
            self._negative.popitem(last=False)

    def _schedule_retry(self, tx_hash):
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return False

        with self._lock:
            existing = self._retry_tasks.get(tx_hash)

            if existing is not None and not existing.done():
                return False

            if len(self._retry_tasks) >= self.max_pending_retries:
                self.retry_dropped += 1
                return False

            task = loop.create_task(self._retry_once(tx_hash))
            self._retry_tasks[tx_hash] = task
            self._retry_tasks.move_to_end(tx_hash)
            self.retry_scheduled += 1

        def cleanup(done_task):
            with self._lock:
                current = self._retry_tasks.get(tx_hash)
                if current is done_task:
                    self._retry_tasks.pop(tx_hash, None)

        task.add_done_callback(cleanup)
        return True

    async def _retry_once(self, tx_hash):
        try:
            await asyncio.sleep(self.retry_delay_seconds)

            with self._lock:
                if tx_hash in self._cache:
                    return

                self._negative.pop(tx_hash, None)
                self.retry_attempts += 1

            result = await self.resolve(
                tx_hash,
                _allow_background_retry=False,
            )

            with self._lock:
                if result.get("state") == "READY":
                    self.retry_successes += 1
                else:
                    self.retry_failures += 1

        except asyncio.CancelledError:
            with self._lock:
                self.retry_cancelled += 1
            raise

    async def resolve(
        self,
        transaction_hash,
        *,
        _allow_background_retry=True,
    ):
        tx_hash = _normalize_hash(transaction_hash)

        if not tx_hash:
            return self._out(
                "UNKNOWN",
                None,
                None,
                "TX_HASH_MISSING",
            )

        with self._lock:
            cached = self._cache.get(tx_hash)

            if cached is not None:
                self._cache.move_to_end(tx_hash)
                self.cache_hits += 1
                remember_transaction_origin(tx_hash, cached)
                return self._out(
                    "READY",
                    tx_hash,
                    cached,
                    "CACHE",
                )

            if self._negative_hit(tx_hash):
                return self._out(
                    "UNKNOWN",
                    tx_hash,
                    None,
                    "NEGATIVE_TTL",
                )

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

            if _allow_background_retry:
                self._schedule_retry(tx_hash)

            return self._out(
                "UNKNOWN",
                tx_hash,
                None,
                f"PROVIDER_ERROR:{type(exc).__name__}",
            )

        address = self._extract_from(result)

        if not address:
            with self._lock:
                self.resolve_failures += 1
                self._remember_negative(tx_hash)

            if _allow_background_retry:
                self._schedule_retry(tx_hash)

            return self._out(
                "UNKNOWN",
                tx_hash,
                None,
                "TX_FROM_MISSING",
            )

        with self._lock:
            self._negative.pop(tx_hash, None)

            if (
                tx_hash not in self._cache
                and len(self._cache) >= self.max_entries
            ):
                self._cache.popitem(last=False)
                self.evictions += 1

            self._cache[tx_hash] = address
            self._cache.move_to_end(tx_hash)

        remember_transaction_origin(tx_hash, address)

        return self._out(
            "READY",
            tx_hash,
            address,
            "PROVIDER",
        )

    def forget(self, transaction_hash):
        tx_hash = _normalize_hash(transaction_hash)

        if not tx_hash:
            return False

        forget_transaction_origin(tx_hash)

        with self._lock:
            self._negative.pop(tx_hash, None)
            task = self._retry_tasks.pop(tx_hash, None)
            removed = self._cache.pop(tx_hash, None) is not None

        if task is not None and not task.done():
            task.cancel()

        return removed or task is not None

    def status(self):
        with self._lock:
            return {
                "state": "READY",
                "size": len(self._cache),
                "negative_size": len(self._negative),
                "max_entries": self.max_entries,
                "timeout_seconds": self.timeout_seconds,
                "negative_ttl_seconds": self.negative_ttl_seconds,
                "retry_delay_seconds": self.retry_delay_seconds,
                "max_pending_retries": self.max_pending_retries,
                "pending_retries": len(self._retry_tasks),
                "provider_calls": self.provider_calls,
                "cache_hits": self.cache_hits,
                "negative_hits": self.negative_hits,
                "resolve_failures": self.resolve_failures,
                "evictions": self.evictions,
                "retry_scheduled": self.retry_scheduled,
                "retry_attempts": self.retry_attempts,
                "retry_successes": self.retry_successes,
                "retry_failures": self.retry_failures,
                "retry_dropped": self.retry_dropped,
                "retry_cancelled": self.retry_cancelled,
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

        return _normalize_address(value)

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
