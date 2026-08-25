import pytest

from app.universe.discovery import (
    PAIR_CREATED_TOPIC, PANCAKE_FACTORY_STREAMS, POOL_CREATED_TOPIC,
    PancakeUniverseDiscovery,
)
from app.universe.registry import UniverseRegistry


def address(n):
    return "0x" + f"{n:040x}"


def topic_address(n):
    return "0x" + "0" * 24 + f"{n:040x}"


def word(n):
    return f"{n:064x}"


def v2_log(block=10):
    return {"topics": [PAIR_CREATED_TOPIC, topic_address(1), topic_address(2)],
            "data": "0x" + word(3) + word(1), "blockNumber": block,
            "transactionHash": "0x" + "a" * 64}


def v3_log(block=20):
    return {"topics": [POOL_CREATED_TOPIC, topic_address(4),
                       topic_address(5), "0x" + word(2500)],
            "data": "0x" + word(50) + word(6), "blockNumber": hex(block),
            "transactionHash": bytes.fromhex("b" * 64)}


class Reader:
    def __init__(self, responses):
        self.responses, self.calls = list(responses), []

    def __call__(self, **request):
        self.calls.append(request)
        return self.responses.pop(0)


def test_v2_existing_backfill_is_bounded_and_resumes(tmp_path):
    registry = UniverseRegistry(tmp_path / "cache.db")
    reader = Reader([[v2_log(10)], []])
    discovery = PancakeUniverseDiscovery(registry, reader, max_block_span=10)
    stream = PANCAKE_FACTORY_STREAMS[0]
    first = discovery.scan(
        stream, start_block=1, finalized_block=25, branch="EXISTING")
    second = discovery.scan(
        stream, start_block=1, finalized_block=25, branch="EXISTING")
    assert (first["from_block"], first["to_block"]) == (1, 10)
    assert (second["from_block"], second["to_block"]) == (11, 20)
    assert registry.count() == 1
    assert registry.get_pool("bsc", "pancakeswap_v2", address(3))[
        "discovery_branch"] == "EXISTING"


def test_v3_new_tail_decodes_fee_and_pool(tmp_path):
    registry = UniverseRegistry(tmp_path / "cache.db")
    reader = Reader([[v3_log()]])
    discovery = PancakeUniverseDiscovery(registry, reader, max_block_span=50)
    result = discovery.scan(
        PANCAKE_FACTORY_STREAMS[1], start_block=20,
        finalized_block=20, branch="NEW")
    row = registry.get_pool("bsc", "pancakeswap_v3", address(6))
    assert result["state"] == "CAUGHT_UP"
    assert (row["token0"], row["token1"], row["fee_tier"]) == (
        address(4), address(5), 2500)


def test_empty_range_advances_checkpoint(tmp_path):
    registry = UniverseRegistry(tmp_path / "cache.db")
    reader = Reader([[]])
    discovery = PancakeUniverseDiscovery(registry, reader, max_block_span=100)
    stream = PANCAKE_FACTORY_STREAMS[0]
    discovery.scan(
        stream, start_block=100, finalized_block=110, branch="EXISTING")
    saved = registry.checkpoint(
        "bsc", stream["dex"], stream["factory"], stream["event_kind"])
    assert saved["last_scanned_block"] == 110
    assert registry.count() == 0


def test_caught_up_scan_makes_no_provider_call(tmp_path):
    registry = UniverseRegistry(tmp_path / "cache.db")
    reader = Reader([[]])
    discovery = PancakeUniverseDiscovery(registry, reader)
    stream = PANCAKE_FACTORY_STREAMS[0]
    discovery.scan(stream, start_block=5, finalized_block=5, branch="NEW")
    result = discovery.scan(
        stream, start_block=5, finalized_block=5, branch="NEW")
    assert result["provider_call"] is False
    assert len(reader.calls) == 1


def test_decode_failure_does_not_advance_checkpoint(tmp_path):
    registry = UniverseRegistry(tmp_path / "cache.db")
    reader = Reader([[{"topics": [], "data": "0x", "blockNumber": 7}]])
    discovery = PancakeUniverseDiscovery(registry, reader)
    stream = PANCAKE_FACTORY_STREAMS[0]
    with pytest.raises(ValueError):
        discovery.scan(stream, start_block=7, finalized_block=7, branch="NEW")
    assert registry.checkpoint(
        "bsc", stream["dex"], stream["factory"], stream["event_kind"]) is None


def test_block_bounds_and_branch_are_strict(tmp_path):
    registry = UniverseRegistry(tmp_path / "cache.db")
    discovery = PancakeUniverseDiscovery(registry, Reader([]))
    with pytest.raises(ValueError):
        discovery.scan(PANCAKE_FACTORY_STREAMS[0], start_block=-1,
                       finalized_block=1, branch="EXISTING")
    with pytest.raises(ValueError):
        discovery.scan(PANCAKE_FACTORY_STREAMS[0], start_block=1,
                       finalized_block=1, branch="UNKNOWN")

