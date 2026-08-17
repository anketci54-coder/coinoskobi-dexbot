import json

from app.pipeline.engine import PipelineEngine


class FakeFlow:
    def __init__(self, snapshot):
        self.result = snapshot
        self.calls = []

    def snapshot(
        self,
        pair,
        candidate=None,
    ):
        self.calls.append(
            (
                pair,
                dict(candidate or {}),
            )
        )
        return self.result


class FakeCache:
    def __init__(self, pool=None):
        self.pool = pool

    def pool_for_token(self, token):
        return self.pool


def engine_for(snapshot, pool=None):
    engine = object.__new__(
        PipelineEngine
    )
    engine.native_market_flow = (
        FakeFlow(snapshot)
    )
    engine.cache = FakeCache(pool)
    return engine


def position(pool=None):
    raw = {}

    if pool:
        raw = {
            "raw_signals": {
                "pool": pool,
                "liquidity": 50000,
            }
        }

    return {
        "id": 1,
        "token": "0xtoken",
        "opening_context_json": (
            json.dumps(raw)
        ),
    }


def test_real_market_and_flow_are_exposed():
    pool = "0xpool"

    engine = engine_for(
        {
            "state": "READY",
            "market_intelligence": {
                "evidence_ready": True,
                "liquidity_usd": 50000,
                "buys": 3,
                "sells": 1,
            },
            "flow_intelligence": {
                "evidence_ready": True,
                "flow_momentum": -0.4,
                "flow_acceleration": -0.2,
                "participation_quality": (
                    "CONCENTRATED"
                ),
            },
            "source": (
                "SCANNER_PLUS_NATIVE_WSS"
            ),
        }
    )

    result = (
        engine._hybrid_exit_runtime_evidence(
            position(pool)
        )
    )

    assert result is not None
    assert result["state"] == "READY"

    bundle = result["signal_bundle"]

    assert bundle[
        "liquidity_usd"
    ] == 50000

    assert bundle[
        "flow_momentum"
    ] == -0.4

    assert bundle[
        "flow_acceleration"
    ] == -0.2

    assert result["synthetic"] is False
    assert (
        result["decision_authority"]
        is False
    )
    assert (
        result["execution_authority"]
        is False
    )


def test_unknown_runtime_evidence_returns_none():
    engine = engine_for(
        {
            "state": "UNKNOWN",
            "market_intelligence": {
                "evidence_ready": False,
            },
            "flow_intelligence": {
                "evidence_ready": False,
            },
        }
    )

    assert (
        engine._hybrid_exit_runtime_evidence(
            position("0xpool")
        )
        is None
    )


def test_cache_pool_fallback_is_allowed():
    engine = engine_for(
        {
            "state": "READY",
            "market_intelligence": {
                "evidence_ready": True,
                "liquidity_usd": 10000,
            },
            "flow_intelligence": {
                "evidence_ready": False,
            },
        },
        pool="0xcachedpool",
    )

    result = (
        engine._hybrid_exit_runtime_evidence(
            position()
        )
    )

    assert result is not None

    assert (
        engine.native_market_flow.calls[
            0
        ][0]
        == "0xcachedpool"
    )


def test_no_pool_returns_none():
    engine = engine_for(
        {
            "state": "READY",
            "market_intelligence": {
                "evidence_ready": True,
            },
            "flow_intelligence": {
                "evidence_ready": True,
            },
        }
    )

    assert (
        engine._hybrid_exit_runtime_evidence(
            position()
        )
        is None
    )


def test_snapshot_failure_fails_closed_to_none():
    class BrokenFlow:
        def snapshot(self, *args, **kwargs):
            raise RuntimeError("boom")

    engine = object.__new__(
        PipelineEngine
    )
    engine.native_market_flow = (
        BrokenFlow()
    )
    engine.cache = FakeCache(
        "0xpool"
    )

    assert (
        engine._hybrid_exit_runtime_evidence(
            position()
        )
        is None
    )


def test_authority_is_always_zero():
    engine = engine_for(
        {
            "state": "READY",
            "market_intelligence": {
                "evidence_ready": True,
                "liquidity_usd": 10000,
            },
            "flow_intelligence": {
                "evidence_ready": True,
                "flow_momentum": 0.2,
            },
        }
    )

    result = (
        engine._hybrid_exit_runtime_evidence(
            position("0xpool")
        )
    )

    for key in (
        "decision_authority",
        "paper_authority",
        "live_authority",
        "wallet_authority",
        "execution_authority",
    ):
        assert result[key] is False
