import sqlite3
from datetime import datetime, timezone

import pytest

from app.universe.discovery import PAIR_CREATED_TOPIC
from app.universe.registry import UniverseRegistry
from app.universe.runtime import FullUniverseObservationRuntime


def address(value):
    return "0x" + f"{value:040x}"


def topic_address(value):
    return "0x" + "0" * 24 + f"{value:040x}"


def word(value):
    return f"{value:064x}"


class LogReader:
    def __call__(self, **request):
        if request["topic0"] == PAIR_CREATED_TOPIC and request["from_block"] == 1:
            return [{
                "topics": [
                    PAIR_CREATED_TOPIC,
                    topic_address(1),
                    topic_address(2),
                ],
                "data": "0x" + word(3) + word(1),
                "blockNumber": 1,
                "transactionHash": "0x" + "a" * 64,
            }]
        return []


class SnapshotClient:
    def fetch(self, due):
        return [{
            "chain": row["chain"],
            "dex": row["dex"],
            "pool": row["pool"],
            "source": "dexscreener",
            "observed_at": "2026-08-25T16:00:00+00:00",
            "price_usd": 1.0,
            "liquidity_usd": 1000.0,
            "volume_m5_usd": 100.0,
            "volume_h24_usd": 1000.0,
            "txns_m5": 10,
            "change_m5": 1.0,
        } for row in due]


class PromoteClassifier:
    def __init__(self, next_state):
        self.next_state = next_state

    def classify(self, *, chain, dex, pool, market_state, history):
        return {
            "chain": chain,
            "dex": dex,
            "pool": pool,
            "observed_at": history[-1]["observed_at"],
            "policy": "test",
            "previous_state": market_state,
            "next_state": self.next_state,
            "score": 9.0,
            "price_z": 6.0,
            "volume_z": 6.0,
            "txns_z": 6.0,
            "liquidity_ratio": 1.0,
            "evidence_count": 3,
            "reason": f"TEST_PROMOTE_{self.next_state}",
        }


@pytest.mark.parametrize(
    ("next_state", "expected_due"),
    [
        ("HOT", "2026-08-25T16:00:15+00:00"),
        ("WARM", "2026-08-25T16:01:00+00:00"),
    ],
)
def test_state_promotion_applies_new_cadence_immediately(next_state, expected_due):
    registry = UniverseRegistry(connection=sqlite3.connect(":memory:"))
    runtime = FullUniverseObservationRuntime(
        start_blocks={"pancakeswap_v2": 1, "pancakeswap_v3": 1},
        registry=registry,
        log_reader=LogReader(),
        finalized_block_reader=lambda: 20,
        snapshot_client=SnapshotClient(),
        confirmation_depth=0,
        discovery_block_span=10,
        discovery_batches_per_cycle=1,
        observation_batches_per_cycle=1,
    )
    runtime.observer.now_func = lambda: datetime(
        2026, 8, 25, 16, 0, tzinfo=timezone.utc
    )
    runtime.classifier = PromoteClassifier(next_state)

    result = runtime.run_once()

    row = registry.get_pool("bsc", "pancakeswap_v2", address(3))
    assert row["market_state"] == next_state
    assert row["next_observation_at"] == expected_due
    assert result["decision_authority"] is False
    assert result["paper_authority"] is False
    assert result["live_authority"] is False
    assert result["wallet_authority"] is False
    assert result["execution_authority"] is False
