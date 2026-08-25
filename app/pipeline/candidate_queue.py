import heapq
import time


class CandidateAdmissionQueue:
    """
    Strictly bounded in-memory admission queue.

    Rules:
    - duplicate identities collapse into one live entry
    - active entries <= max_pending
    - best/worst auxiliary heaps are periodically compacted
    - cooldown identities are expiry-pruned
    - auxiliary structures have explicit hard bounds
    - no trade/execution authority
    """

    def __init__(
        self,
        max_pending=100000,
        cooldown_seconds=20,
        *,
        heap_compaction_factor=4,
        cooldown_compaction_factor=4,
    ):
        self.max_pending = max(
            1,
            int(max_pending),
        )

        self.cooldown_seconds = max(
            0.0,
            float(cooldown_seconds),
        )

        self.heap_compaction_factor = max(
            2,
            int(heap_compaction_factor),
        )

        self.cooldown_compaction_factor = max(
            2,
            int(cooldown_compaction_factor),
        )

        self._entries = {}
        self._best_heap = []
        self._worst_heap = []
        self._cooldown_until = {}

        self._version = 0

        self.duplicate_collapsed = 0
        self.cooldown_skipped = 0
        self.overflow_rejected = 0
        self.evicted_low_priority = 0
        self.cold_skipped = 0

        self.heap_compactions = 0
        self.cooldown_prunes = 0

    @staticmethod
    def normalize_token(value):
        if not value:
            return None

        token = str(value).strip().lower()

        if token.startswith("bsc_"):
            token = token[4:]

        return token

    @classmethod
    def identity_key(cls, row):
        pool = cls.normalize_token(
            row.get("pool")
        )

        token = cls.normalize_token(
            row.get("token")
        )

        if not token and not pool:
            return None

        chain = str(
            row.get("chain") or "bsc"
        ).strip().lower()

        if not chain:
            chain = "bsc"

        if pool:
            return f"{chain}:pool:{pool}"

        return f"{chain}:token:{token}"

    @staticmethod
    def priority(row):
        state = str(
            row.get("market_state") or ""
        ).strip().upper()

        heat_rank = {
            "HOT": 2,
            "WARM": 1,
        }.get(state, 0)

        return (
            heat_rank,
            float(
                row.get("seismic_score")
                or 0
            ),
            float(
                row.get("liquidity")
                or 0
            ),
            float(
                row.get(
                    "volume_24h",
                    row.get("volume24") or 0,
                )
                or 0
            ),
            int(
                row.get(
                    "buys_24h",
                    row.get("buys24") or 0,
                )
                or 0
            ),
        )

    def __len__(self):
        return len(self._entries)

    @property
    def pending_count(self):
        return len(self._entries)

    @property
    def best_heap_size(self):
        return len(self._best_heap)

    @property
    def worst_heap_size(self):
        return len(self._worst_heap)

    @property
    def cooldown_size(self):
        return len(self._cooldown_until)

    @property
    def max_heap_entries(self):
        return (
            self.max_pending
            * self.heap_compaction_factor
        )

    @property
    def max_cooldown_entries(self):
        return (
            self.max_pending
            * self.cooldown_compaction_factor
        )

    def _next_version(self):
        self._version += 1
        return self._version

    def _is_current(
        self,
        identity,
        version,
    ):
        entry = self._entries.get(
            identity
        )

        return (
            entry is not None
            and entry["version"] == version
        )

    def _push_heaps(
        self,
        identity,
        priority,
        version,
        first_seen,
    ):
        heat, seismic, liquidity, volume, buys = priority

        heapq.heappush(
            self._best_heap,
            (
                -heat,
                -seismic,
                -liquidity,
                -volume,
                -buys,
                first_seen,
                version,
                identity,
            ),
        )

        heapq.heappush(
            self._worst_heap,
            (
                heat,
                seismic,
                liquidity,
                volume,
                buys,
                -first_seen,
                version,
                identity,
            ),
        )

    def _rebuild_heaps(self):
        best = []
        worst = []

        for identity, entry in (
            self._entries.items()
        ):
            heat, seismic, liquidity, volume, buys = (
                entry["priority"]
            )

            first_seen = entry[
                "first_seen"
            ]

            version = entry[
                "version"
            ]

            best.append(
                (
                    -heat,
                    -seismic,
                    -liquidity,
                    -volume,
                    -buys,
                    first_seen,
                    version,
                    identity,
                )
            )

            worst.append(
                (
                    heat,
                    seismic,
                    liquidity,
                    volume,
                    buys,
                    -first_seen,
                    version,
                    identity,
                )
            )

        heapq.heapify(best)
        heapq.heapify(worst)

        self._best_heap = best
        self._worst_heap = worst
        self.heap_compactions += 1

    def _compact_heaps_if_needed(
        self,
    ):
        live = len(self._entries)

        if live == 0:
            if (
                self._best_heap
                or self._worst_heap
            ):
                self._best_heap.clear()
                self._worst_heap.clear()
                self.heap_compactions += 1

            return

        threshold = max(
            self.max_pending,
            live
            * self.heap_compaction_factor,
        )

        if (
            len(self._best_heap)
            > threshold
            or len(self._worst_heap)
            > threshold
        ):
            self._rebuild_heaps()

    def _prune_cooldowns(
        self,
        now=None,
        *,
        force=False,
    ):
        if not self._cooldown_until:
            return

        now = (
            time.monotonic()
            if now is None
            else now
        )

        if (
            not force
            and len(
                self._cooldown_until
            )
            <= self.max_cooldown_entries
        ):
            return

        expired = [
            identity
            for identity, until
            in self._cooldown_until.items()
            if until <= now
        ]

        for identity in expired:
            self._cooldown_until.pop(
                identity,
                None,
            )

        if expired:
            self.cooldown_prunes += len(
                expired
            )

        # Expiry pruning alone is not a hard bound.
        # If all cooldowns are still active, evict the
        # earliest-expiring identities until the declared
        # maximum is satisfied.
        overflow = (
            len(self._cooldown_until)
            - self.max_cooldown_entries
        )

        if overflow > 0:
            victims = sorted(
                self._cooldown_until.items(),
                key=lambda item: item[1],
            )[:overflow]

            for identity, _ in victims:
                self._cooldown_until.pop(
                    identity,
                    None,
                )

            self.cooldown_prunes += len(
                victims
            )

    def _maintenance(
        self,
        now=None,
    ):
        self._compact_heaps_if_needed()
        self._prune_cooldowns(
            now,
            force=(
                len(
                    self._cooldown_until
                )
                > self.max_cooldown_entries
            ),
        )

    def _clean_best_heap(self):
        while self._best_heap:
            *_, version, identity = (
                self._best_heap[0]
            )

            if self._is_current(
                identity,
                version,
            ):
                return

            heapq.heappop(
                self._best_heap
            )

    def _clean_worst_heap(self):
        while self._worst_heap:
            *_, version, identity = (
                self._worst_heap[0]
            )

            if self._is_current(
                identity,
                version,
            ):
                return

            heapq.heappop(
                self._worst_heap
            )

    def _current_worst(self):
        self._clean_worst_heap()

        if not self._worst_heap:
            return None

        (
            heat,
            seismic,
            liquidity,
            volume,
            buys,
            _,
            version,
            identity,
        ) = self._worst_heap[0]

        if not self._is_current(
            identity,
            version,
        ):
            return None

        return (
            (
                heat,
                seismic,
                liquidity,
                volume,
                buys,
            ),
            identity,
        )

    def enqueue(self, row):
        token = self.normalize_token(
            row.get("token")
        )

        identity = self.identity_key(
            row
        )

        if not token or not identity:
            return False

        if str(row.get("market_state") or "").strip().upper() == "COLD":
            self.cold_skipped += 1
            return False

        now = time.monotonic()

        self._maintenance(now)

        cooldown_until = (
            self._cooldown_until.get(
                identity,
                0,
            )
        )

        if cooldown_until > now:
            self.cooldown_skipped += 1
            return False

        if (
            cooldown_until
            and cooldown_until <= now
        ):
            self._cooldown_until.pop(
                identity,
                None,
            )

        priority = self.priority(row)

        existing = self._entries.get(
            identity
        )

        if existing is not None:
            first_seen = existing[
                "first_seen"
            ]

            self.duplicate_collapsed += 1

        else:
            first_seen = now

            if (
                len(self._entries)
                >= self.max_pending
            ):
                worst = (
                    self._current_worst()
                )

                if worst is not None:
                    (
                        worst_priority,
                        worst_identity,
                    ) = worst

                    if (
                        priority
                        <= worst_priority
                    ):
                        self.overflow_rejected += 1
                        return False

                    del self._entries[
                        worst_identity
                    ]

                    self.evicted_low_priority += 1

        version = self._next_version()

        normalized = dict(row)
        normalized["token"] = token
        normalized["chain"] = str(
            row.get("chain") or "bsc"
        ).strip().lower()

        normalized[
            "identity"
        ] = identity

        self._entries[identity] = {
            "row": normalized,
            "priority": priority,
            "first_seen": first_seen,
            "last_seen": now,
            "version": version,
        }

        self._push_heaps(
            identity,
            priority,
            version,
            first_seen,
        )

        self._compact_heaps_if_needed()

        return True

    def enqueue_many(self, rows):
        accepted = 0

        for row in rows:
            if self.enqueue(row):
                accepted += 1

        return accepted

    def pop(self):
        while True:
            self._clean_best_heap()

            if not self._best_heap:
                self._maintenance()
                return None

            (
                _,
                _,
                _,
                _,
                _,
                _,
                version,
                identity,
            ) = heapq.heappop(
                self._best_heap
            )

            if not self._is_current(
                identity,
                version,
            ):
                continue

            entry = self._entries.pop(
                identity
            )

            self._maintenance()

            return entry["row"]

    def mark_analyzed(
        self,
        token,
        chain="bsc",
        pool=None,
    ):
        normalized = self.normalize_token(
            token
        )

        if not normalized:
            return

        normalized_pool = self.normalize_token(pool)
        if normalized_pool:
            identity = (
                f"{str(chain).strip().lower()}:"
                f"pool:{normalized_pool}"
            )
        else:
            identity = (
                f"{str(chain).strip().lower()}:"
                f"token:{normalized}"
            )

        now = time.monotonic()

        self._cooldown_until[
            identity
        ] = (
            now
            + self.cooldown_seconds
        )

        self._prune_cooldowns(
            now,
            force=(
                len(
                    self._cooldown_until
                )
                > self.max_cooldown_entries
            ),
        )

    def compact(self):
        """
        Explicit maintenance hook for long-running runtimes.
        """
        now = time.monotonic()

        self._rebuild_heaps()

        self._prune_cooldowns(
            now,
            force=True,
        )

        return self.stats()

    def stats(self):
        return {
            "pending": len(
                self._entries
            ),
            "duplicates_collapsed": (
                self.duplicate_collapsed
            ),
            "cooldown_skipped": (
                self.cooldown_skipped
            ),
            "overflow_rejected": (
                self.overflow_rejected
            ),
            "evicted_low_priority": (
                self.evicted_low_priority
            ),
            "cold_skipped": self.cold_skipped,
            "best_heap_size": (
                len(self._best_heap)
            ),
            "worst_heap_size": (
                len(self._worst_heap)
            ),
            "cooldown_size": (
                len(
                    self._cooldown_until
                )
            ),
            "max_pending": (
                self.max_pending
            ),
            "max_heap_entries": (
                self.max_heap_entries
            ),
            "max_cooldown_entries": (
                self.max_cooldown_entries
            ),
            "heap_compactions": (
                self.heap_compactions
            ),
            "cooldown_prunes": (
                self.cooldown_prunes
            ),
            "strictly_bounded": (
                len(self._entries)
                <= self.max_pending
                and len(self._best_heap)
                <= self.max_heap_entries
                and len(self._worst_heap)
                <= self.max_heap_entries
                and len(self._cooldown_until)
                <= self.max_cooldown_entries
            ),
            "trade_permission": False,
            "decision_authority": False,
            "execution_authority": False,
        }
