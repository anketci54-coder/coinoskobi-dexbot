from app.dex.news_observation_runtime import NewsObservationRuntime


class StubCollectorRuntime:
    def __init__(self, results):
        self.results = list(results)
        self.calls = []

    def ingest(self, source_type, messages):
        self.calls.append((source_type, messages))
        if self.results:
            return self.results.pop(0)
        return {
            "state": "UNKNOWN",
            "accepted": 0,
            "rejected": 0,
            "classified": 0,
        }


def _result(state, accepted=0, rejected=0, classified=0):
    return {
        "state": state,
        "accepted": accepted,
        "rejected": rejected,
        "classified": classified,
    }


def test_empty_batches_are_unknown():
    runtime = NewsObservationRuntime(
        collector_runtime=StubCollectorRuntime([])
    )

    result = runtime.ingest_batches([])

    assert result["state"] == "UNKNOWN"
    assert result["sources"] == 0
    assert result["accepted"] == 0
    assert result["classified"] == 0


def test_sources_without_accepted_evidence_are_degraded():
    runtime = NewsObservationRuntime(
        collector_runtime=StubCollectorRuntime([
            _result("INVALID_SOURCE"),
            _result("READY", rejected=2),
        ])
    )

    result = runtime.ingest_batches([
        ("UNKNOWN", []),
        ("RSS", [{"text": "noise"}]),
    ])

    assert result["state"] == "DEGRADED"
    assert result["sources"] == 2
    assert result["accepted"] == 0
    assert result["classified"] == 0
    assert result["rejected"] == 2
    assert result["source_states"] == {
        "INVALID_SOURCE": 1,
        "READY": 1,
    }


def test_accepted_classified_evidence_is_ready():
    runtime = NewsObservationRuntime(
        collector_runtime=StubCollectorRuntime([
            _result("READY", accepted=2, classified=2),
        ])
    )

    result = runtime.ingest_batches([
        ("RSS", [{"text": "Airdrop announced"}]),
    ])

    assert result["state"] == "READY"
    assert result["accepted"] == 2
    assert result["classified"] == 2


def test_source_iteration_is_bounded_without_materializing_generator():
    collector = StubCollectorRuntime([
        _result("READY", accepted=1, classified=1),
        _result("READY", accepted=1, classified=1),
    ])
    runtime = NewsObservationRuntime(
        collector_runtime=collector,
        max_sources=2,
    )

    consumed = []

    def batches():
        for index in range(1000):
            consumed.append(index)
            yield ("RSS", [{"text": str(index)}])

    result = runtime.ingest_batches(batches())

    assert result["state"] == "READY"
    assert result["sources"] == 2
    assert len(collector.calls) == 2
    assert consumed == [0, 1]


def test_authority_is_always_false():
    runtime = NewsObservationRuntime(
        collector_runtime=StubCollectorRuntime([
            _result("READY", accepted=1, classified=1),
        ])
    )

    result = runtime.ingest_batches([("RSS", [{}])])

    for key in (
        "trade_signal",
        "decision_authority",
        "paper_authority",
        "live_authority",
        "wallet_authority",
        "signing_authority",
        "execution_authority",
    ):
        assert result[key] is False
