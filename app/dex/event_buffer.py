from collections import deque


class EventBuffer:
    def __init__(self, max_size=1024):
        self.max_size = max(1, int(max_size))
        self._items = deque()
        self.dropped = 0

    @property
    def size(self):
        return len(self._items)

    def push(self, event):
        dropped = None

        if self.size >= self.max_size:
            dropped = self._items.popleft()
            self.dropped += 1

        self._items.append(event)

        return {
            "accepted": True,
            "dropped": dropped,
            "size": self.size,
            "max_size": self.max_size,
            "overflowed": dropped is not None,
            "execution_authority": False,
        }

    def pop(self):
        if not self._items:
            return None
        return self._items.popleft()

    def drain(self, limit=None):
        count = self.size if limit is None else max(0, int(limit))
        out = []

        for _ in range(min(count, self.size)):
            out.append(self._items.popleft())

        return out


def buffer_health(buffer):
    if buffer is None:
        return {
            "state": "UNKNOWN",
            "execution_authority": False,
        }

    ratio = buffer.size / buffer.max_size

    if ratio >= 1:
        state = "FULL"
    elif ratio >= 0.8:
        state = "PRESSURED"
    else:
        state = "HEALTHY"

    return {
        "state": state,
        "size": buffer.size,
        "max_size": buffer.max_size,
        "fill_ratio": ratio,
        "dropped": buffer.dropped,
        "bounded": True,
        "decision_authority": False,
        "execution_authority": False,
    }
