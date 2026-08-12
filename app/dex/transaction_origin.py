import asyncio
import threading
from collections import OrderedDict


class TransactionOriginResolver:
    """
    Bounded tx-hash -> tx.from resolver.

    Important:
    - Swap event sender/recipient is NOT treated as wallet identity.
    - only transaction.from becomes wallet identity
    - successful lookups are cached
    - failed provider lookups remain UNKNOWN and are not cached
    - no trade/execution authority
    """

    def __init__(
        self,
        max_entries=8192,
        fetcher=None,
    ):
        self.max_entries = max(
            1,
            int(max_entries),
        )

        self.fetcher = (
            fetcher
            or self._default_fetcher
        )

        self._cache = OrderedDict()
        self._lock = threading.RLock()

        self.provider_calls = 0
        self.cache_hits = 0
        self.resolve_failures = 0
        self.evictions = 0

    @property
    def size(self):
        with self._lock:
            return len(self._cache)

    async def resolve(
        self,
        transaction_hash,
    ):
        tx_hash = (
            str(transaction_hash or "")
            .strip()
            .lower()
        )

        if not tx_hash:
            return self._out(
                "UNKNOWN",
                None,
                None,
                "TX_HASH_MISSING",
            )

        with self._lock:
            cached = self._cache.get(
                tx_hash
            )

            if cached is not None:
                self._cache.move_to_end(
                    tx_hash
                )

                self.cache_hits += 1

                return self._out(
                    "READY",
                    tx_hash,
                    cached,
                    "CACHE",
                )

        try:
            result = await asyncio.to_thread(
                self.fetcher,
                tx_hash,
            )

            with self._lock:
                self.provider_calls += 1

        except Exception as exc:
            with self._lock:
                self.provider_calls += 1
                self.resolve_failures += 1

            return self._out(
                "UNKNOWN",
                tx_hash,
                None,
                (
                    "PROVIDER_ERROR:"
                    f"{type(exc).__name__}"
                ),
            )

        address = self._extract_from(
            result
        )

        if not address:
            with self._lock:
                self.resolve_failures += 1

            return self._out(
                "UNKNOWN",
                tx_hash,
                None,
                "TX_FROM_MISSING",
            )

        with self._lock:
            if (
                tx_hash not in self._cache
                and len(self._cache)
                >= self.max_entries
            ):
                self._cache.popitem(
                    last=False
                )

                self.evictions += 1

            self._cache[
                tx_hash
            ] = address

            self._cache.move_to_end(
                tx_hash
            )

        return self._out(
            "READY",
            tx_hash,
            address,
            "PROVIDER",
        )

    def forget(
        self,
        transaction_hash,
    ):
        tx_hash = (
            str(transaction_hash or "")
            .strip()
            .lower()
        )

        if not tx_hash:
            return False

        with self._lock:
            return (
                self._cache.pop(
                    tx_hash,
                    None,
                )
                is not None
            )

    def status(self):
        with self._lock:
            return {
                "state": "READY",
                "size": len(
                    self._cache
                ),
                "max_entries": (
                    self.max_entries
                ),
                "provider_calls": (
                    self.provider_calls
                ),
                "cache_hits": (
                    self.cache_hits
                ),
                "resolve_failures": (
                    self.resolve_failures
                ),
                "evictions": (
                    self.evictions
                ),
                "bounded": True,
                "wallet_identity_source": (
                    "TRANSACTION_FROM_ONLY"
                ),
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

        if isinstance(
            result,
            dict,
        ):
            value = result.get(
                "from"
            )
        else:
            value = getattr(
                result,
                "from",
                None,
            )

            if value is None:
                try:
                    value = result[
                        "from"
                    ]
                except Exception:
                    value = None

        if not value:
            return None

        return (
            str(value)
            .strip()
            .lower()
            or None
        )

    @staticmethod
    def _default_fetcher(
        transaction_hash,
    ):
        from app.chains.bsc import w3

        return w3.eth.get_transaction(
            transaction_hash
        )

    @staticmethod
    def _out(
        state,
        transaction_hash,
        address,
        source,
    ):
        return {
            "state": state,
            "transaction_hash": (
                transaction_hash
            ),
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
