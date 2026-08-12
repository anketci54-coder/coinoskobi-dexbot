from collections import deque


MEMORY_TYPES = {
    "FALSE_POSITIVE",
    "FALSE_NEGATIVE",
    "AVOIDED_LOSS",
    "MISSED_OPPORTUNITY",
    "EXIT_FAILURE",
}


class OutcomeMemory:
    def __init__(self, max_entries=1024):
        self.max_entries = max(1, int(max_entries))
        self._items = deque()
        self._seen = set()
        self.dropped = 0

    @property
    def size(self):
        return len(self._items)

    def add(
        self,
        outcome_id,
        outcome_class,
        chain=None,
        token=None,
        wallet_id=None,
        entity_id=None,
        actor_id=None,
        market_regime=None,
        signal_family=None,
        freshness="FRESH",
    ):
        if not outcome_id:
            return _out("INVALID", False)

        if freshness != "FRESH":
            return _out("STALE_REJECTED", False)

        outcome_class = (outcome_class or "").upper()

        if outcome_class not in MEMORY_TYPES:
            return _out("IGNORED", False)

        if outcome_id in self._seen:
            return _out("DUPLICATE", False)

        if self.size >= self.max_entries:
            old = self._items.popleft()
            self._seen.discard(old["outcome_id"])
            self.dropped += 1

        row = {
            "outcome_id": outcome_id,
            "outcome_class": outcome_class,
            "chain": chain,
            "token": token,
            "wallet_id": wallet_id,
            "entity_id": entity_id,
            "actor_id": actor_id,
            "market_regime": market_regime,
            "signal_family": signal_family,
            "freshness": freshness,
        }

        self._items.append(row)
        self._seen.add(outcome_id)

        return {
            "state": "STORED",
            "stored": True,
            "size": self.size,
            "bounded": True,
            "persistent_reputation_from_single_event": False,
            "trade_permission": False,
            "decision_authority": False,
            "execution_authority": False,
        }

    def count_by_class(self, outcome_class):
        target = (outcome_class or "").upper()

        return sum(
            1
            for row in self._items
            if row["outcome_class"] == target
        )

    def repeated_error_count(
        self,
        signal_family=None,
        market_regime=None,
    ):
        error_types = {
            "FALSE_POSITIVE",
            "FALSE_NEGATIVE",
            "EXIT_FAILURE",
        }

        count = 0

        for row in self._items:
            if row["outcome_class"] not in error_types:
                continue

            if (
                signal_family is not None
                and row.get("signal_family") != signal_family
            ):
                continue

            if (
                market_regime is not None
                and row.get("market_regime") != market_regime
            ):
                continue

            count += 1

        return count

    def snapshot(self):
        return list(self._items)


def _out(state, stored):
    return {
        "state": state,
        "stored": stored,
        "bounded": True,
        "persistent_reputation_from_single_event": False,
        "trade_permission": False,
        "decision_authority": False,
        "paper_authority": False,
        "live_authority": False,
        "wallet_authority": False,
        "execution_authority": False,
    }
