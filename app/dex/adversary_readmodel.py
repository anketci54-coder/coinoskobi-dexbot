from collections import deque


class AdversaryReadModel:
    def __init__(self, max_entries=1024):
        self.max_entries = max(1, int(max_entries))
        self._data = {}
        self._order = deque()

    @property
    def size(self):
        return len(self._data)

    def put(self, actor_key, payload):
        if not actor_key:
            return {
                "state": "INVALID",
                "stored": False,
            }

        if (
            actor_key not in self._data
            and self.size >= self.max_entries
        ):
            oldest = self._order.popleft()
            self._data.pop(oldest, None)

        if actor_key not in self._data:
            self._order.append(actor_key)

        self._data[actor_key] = dict(payload or {})

        return {
            "state": "STORED",
            "stored": True,
            "size": self.size,
            "bounded": True,
            "eviction_complexity": "O(1)",
            "decision_authority": False,
            "execution_authority": False,
        }

    def get(self, actor_key, freshness="FRESH"):
        if freshness != "FRESH":
            return _out("STALE", None)

        payload = self._data.get(actor_key)

        if payload is None:
            return _out("UNKNOWN", None)

        return _out("READY", dict(payload))


def hot_path_contract():
    return {
        "precomputed_readmodel_only": True,
        "bounded_cache": True,
        "o1_eviction": True,
        "deep_transaction_trace": False,
        "graph_expansion": False,
        "raw_event_join": False,
        "heavy_actor_aggregation": False,
        "ai_inference": False,
        "external_fetch": False,
        "provider_call": False,
        "decision_authority": False,
        "paper_authority": False,
        "live_authority": False,
        "wallet_authority": False,
        "execution_authority": False,
    }


def _out(state, payload):
    return {
        "state": state,
        "payload": payload,
        "decision_authority": False,
        "execution_authority": False,
    }
