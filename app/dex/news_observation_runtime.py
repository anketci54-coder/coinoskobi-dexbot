from itertools import islice

from app.dex.news_collector_runtime import NewsCollectorRuntime


class NewsObservationRuntime:
    """Single bounded observation-plane entrypoint for all news sources."""

    def __init__(
        self,
        *,
        collector_runtime=None,
        max_sources=32,
    ):
        self.collector_runtime = collector_runtime or NewsCollectorRuntime()
        self.max_sources = max(1, int(max_sources))

    def ingest_batches(self, batches):
        accepted = 0
        rejected = 0
        classified = 0
        sources = 0
        states = {}

        for source_type, messages in islice(batches or (), self.max_sources):
            result = self.collector_runtime.ingest(source_type, messages)
            sources += 1
            accepted += int(result.get("accepted") or 0)
            rejected += int(result.get("rejected") or 0)
            classified += int(result.get("classified") or 0)
            state = str(result.get("state") or "UNKNOWN")
            states[state] = states.get(state, 0) + 1

        if accepted > 0 and classified > 0:
            runtime_state = "READY"
        elif sources > 0:
            runtime_state = "DEGRADED"
        else:
            runtime_state = "UNKNOWN"

        return {
            "state": runtime_state,
            "sources": sources,
            "accepted": accepted,
            "rejected": rejected,
            "classified": classified,
            "source_states": states,
            "bounded": True,
            "trade_signal": False,
            "decision_authority": False,
            "paper_authority": False,
            "live_authority": False,
            "wallet_authority": False,
            "signing_authority": False,
            "execution_authority": False,
        }
