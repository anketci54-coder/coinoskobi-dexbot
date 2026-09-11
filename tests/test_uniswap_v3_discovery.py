from app.universe.registry import UniverseRegistry
from app.universe.uniswap_v3 import (
    POOL_CREATED_TOPIC,
    UNISWAP_V3_FACTORY_STREAM,
    UniswapV3UniverseDiscovery,
    decode_pool_created,
)


TOKEN0 = "0x0000000000000000000000000000000000000001"
TOKEN1 = "0x0000000000000000000000000000000000000002"
POOL = "0x0000000000000000000000000000000000000003"


def _topic_address(address):
    return "0x" + "0" * 24 + address.removeprefix("0x")


def _word(value):
    return f"{value & ((1 << 256) - 1):064x}"


def _pool_created_log(block=123):
    return {
        "topics": [
            POOL_CREATED_TOPIC,
            _topic_address(TOKEN0),
            _topic_address(TOKEN1),
            _word(500),
        ],
        "data": "0x" + _word(10) + _word(int(POOL, 16)),
        "blockNumber": block,
        "transactionHash": "0x" + "a" * 64,
    }


def test_decode_uniswap_v3_pool_created():
    row = decode_pool_created(_pool_created_log())
    assert row["chain"] == "bsc"
    assert row["dex"] == "uniswap_v3"
    assert row["factory"] == UNISWAP_V3_FACTORY_STREAM["factory"].lower()
    assert row["token0"] == TOKEN0
    assert row["token1"] == TOKEN1
    assert row["pool"] == POOL
    assert row["fee_tier"] == 500
    assert row["profile"] == {"tick_spacing": 10}
    assert row["creation_block"] == 123


def test_uniswap_v3_discovery_ingests_and_checkpoints(tmp_path):
    registry = UniverseRegistry(tmp_path / "universe.db")
    calls = []

    def reader(**kwargs):
        calls.append(kwargs)
        return [_pool_created_log()]

    discovery = UniswapV3UniverseDiscovery(
        registry, reader, max_block_span=100,
    )
    result = discovery.scan(start_block=100, finalized_block=250)

    assert result["state"] == "PARTIAL"
    assert result["registered"] == 1
    assert calls == [{
        "address": UNISWAP_V3_FACTORY_STREAM["factory"].lower(),
        "topic0": POOL_CREATED_TOPIC,
        "from_block": 100,
        "to_block": 199,
    }]
    assert registry.get_pool("bsc", "uniswap_v3", POOL)["fee_tier"] == 500
    checkpoint = registry.checkpoint(
        "bsc", "uniswap_v3",
        UNISWAP_V3_FACTORY_STREAM["factory"],
        "POOL_CREATED",
    )
    assert checkpoint["last_scanned_block"] == 199
