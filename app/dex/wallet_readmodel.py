from collections import deque


class WalletReadModel:
    def __init__(self, max_entries=1024):
        self.max_entries = max(1, int(max_entries))
        self._data = {}
        self._order = deque()

    @property
    def size(self):
        return len(self._data)

    def put(self, wallet_id, payload):
        if not wallet_id:
            return {"state": "INVALID"}

        if (
            wallet_id not in self._data
            and self.size >= self.max_entries
        ):
            oldest = self._order.popleft()
            self._data.pop(oldest, None)

        if wallet_id not in self._data:
            self._order.append(wallet_id)

        self._data[wallet_id] = dict(payload or {})

        return {
            "state": "STORED",
            "size": self.size,
            "bounded": True,
            "eviction_complexity": "O(1)",
            "execution_authority": False,
        }

    def get(self, wallet_id, freshness="FRESH"):
        if freshness != "FRESH":
            return _out("STALE", None)

        payload = self._data.get(wallet_id)

        if payload is None:
            return _out("UNKNOWN", None)

        return _out("READY", dict(payload))


def hot_path_contract():
    return {
        "raw_event_join": False,
        "graph_traversal": False,
        "heavy_wallet_aggregation": False,
        "precomputed_readmodel_only": True,
        "bounded_cache": True,
        "o1_eviction": True,
        "decision_authority": False,
        "execution_authority": False,
    }


def _out(state, payload):
    return {
        "state": state,
        "payload": payload,
        "decision_authority": False,
        "execution_authority": False,
    }
