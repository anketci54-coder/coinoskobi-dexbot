import heapq
import time


class CandidateAdmissionQueue:
    """
    Bounded in-memory admission queue.

    Amaç:
    - duplicate tokenları collapse etmek
    - yalnız sınırlı sayıda adayı deep-analysis'e vermek
    - analiz edilen aynı tokenın sonraki cycle'ı tekrar işgal etmesini önlemek
    - yüksek öncelikli adayları önce çıkarmak

    Trade authority yoktur.
    Yalnızca admission / scheduling katmanıdır.
    """

    def __init__(
        self,
        max_pending=100000,
        cooldown_seconds=20,
    ):
        self.max_pending = max_pending
        self.cooldown_seconds = cooldown_seconds

        self._entries = {}
        self._best_heap = []
        self._worst_heap = []
        self._cooldown_until = {}

        self._version = 0

        self.duplicate_collapsed = 0
        self.cooldown_skipped = 0
        self.overflow_rejected = 0
        self.evicted_low_priority = 0

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
        token = cls.normalize_token(
            row.get("token")
        )

        if not token:
            return None

        chain = str(
            row.get("chain") or "bsc"
        ).strip().lower()

        if not chain:
            chain = "bsc"

        return f"{chain}:{token}"

    @staticmethod
    def priority(row):
        return (
            float(row.get("liquidity") or 0),
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

    def _next_version(self):
        self._version += 1
        return self._version

    def _is_current(self, token, version):
        entry = self._entries.get(token)

        return (
            entry is not None
            and entry["version"] == version
        )

    def _push_heaps(
        self,
        token,
        priority,
        version,
        first_seen,
    ):
        liquidity, volume, buys = priority

        # En iyi aday için max-heap davranışı.
        heapq.heappush(
            self._best_heap,
            (
                -liquidity,
                -volume,
                -buys,
                first_seen,
                version,
                token,
            ),
        )

        # Kapasite aşımında en kötü adayı bulmak için min-heap.
        heapq.heappush(
            self._worst_heap,
            (
                liquidity,
                volume,
                buys,
                -first_seen,
                version,
                token,
            ),
        )

    def _clean_best_heap(self):
        while self._best_heap:
            *_, version, token = self._best_heap[0]

            if self._is_current(token, version):
                return

            heapq.heappop(self._best_heap)

    def _clean_worst_heap(self):
        while self._worst_heap:
            *_, version, token = self._worst_heap[0]

            if self._is_current(token, version):
                return

            heapq.heappop(self._worst_heap)

    def _current_worst(self):
        self._clean_worst_heap()

        if not self._worst_heap:
            return None

        (
            liquidity,
            volume,
            buys,
            _,
            version,
            token,
        ) = self._worst_heap[0]

        if not self._is_current(token, version):
            return None

        return (
            (liquidity, volume, buys),
            token,
        )

    def enqueue(self, row):
        token = self.normalize_token(row.get("token"))
        identity = self.identity_key(row)

        if not token or not identity:
            return False

        now = time.monotonic()

        cooldown_until = self._cooldown_until.get(
            identity,
            0,
        )

        if cooldown_until > now:
            self.cooldown_skipped += 1
            return False

        priority = self.priority(row)

        existing = self._entries.get(identity)

        if existing is not None:
            first_seen = existing["first_seen"]
            self.duplicate_collapsed += 1

        else:
            first_seen = now

            if len(self._entries) >= self.max_pending:
                worst = self._current_worst()

                if worst is not None:
                    worst_priority, worst_token = worst

                    if priority <= worst_priority:
                        self.overflow_rejected += 1
                        return False

                    del self._entries[worst_token]
                    self.evicted_low_priority += 1

        version = self._next_version()

        normalized = dict(row)
        normalized["token"] = token
        normalized["chain"] = str(
            row.get("chain") or "bsc"
        ).strip().lower()
        normalized["identity"] = identity

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
                return None

            (
                _,
                _,
                _,
                _,
                version,
                token,
            ) = heapq.heappop(self._best_heap)

            if not self._is_current(token, version):
                continue

            entry = self._entries.pop(token)

            return entry["row"]

    def pop_many(self, limit):
        result = []

        while len(result) < limit:
            row = self.pop()

            if row is None:
                break

            result.append(row)

        return result

    def mark_analyzed(self, token, chain="bsc"):
        normalized = self.normalize_token(token)

        if not normalized:
            return

        identity = (
            f"{str(chain).strip().lower()}:"
            f"{normalized}"
        )

        self._cooldown_until[identity] = (
            time.monotonic()
            + self.cooldown_seconds
        )

    def stats(self):
        return {
            "pending": len(self._entries),
            "duplicates_collapsed": self.duplicate_collapsed,
            "cooldown_skipped": self.cooldown_skipped,
            "overflow_rejected": self.overflow_rejected,
            "evicted_low_priority": self.evicted_low_priority,
        }
