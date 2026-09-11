from app.config.contracts import UNISWAP_V3_BSC_FACTORY
from app.universe.schema import (
    DEX_UNISWAP_V3,
    canonical_address,
    canonical_discovery_branch,
)


POOL_CREATED_TOPIC = (
    "0x783cca1c0412dd0d695e784568c96da2e9c22ff9"
    "89357a2e8b1d9b2b4e6b7118"
)

UNISWAP_V3_FACTORY_STREAM = {
    "chain": "bsc",
    "dex": DEX_UNISWAP_V3,
    "factory": UNISWAP_V3_BSC_FACTORY,
    "event_kind": "POOL_CREATED",
    "topic0": POOL_CREATED_TOPIC,
}


def _hex(value):
    if isinstance(value, bytes):
        return "0x" + value.hex()
    return str(value or "").strip().lower()


def _word(data, index):
    raw = _hex(data).removeprefix("0x")
    word = raw[index * 64:(index + 1) * 64]
    if len(word) != 64:
        raise ValueError("invalid event data")
    return word


def _topic_address(value):
    raw = _hex(value).removeprefix("0x")
    if len(raw) != 64:
        raise ValueError("invalid indexed address topic")
    return canonical_address("0x" + raw[-40:])


def _data_address(data, index):
    return canonical_address("0x" + _word(data, index)[-40:])


def _block_number(value):
    if isinstance(value, str):
        return int(value, 16) if value.startswith("0x") else int(value)
    return int(value)


def decode_pool_created(log, *, branch="EXISTING", stream=None):
    stream = stream or UNISWAP_V3_FACTORY_STREAM
    branch = canonical_discovery_branch(branch)
    topics = list(log.get("topics") or [])
    if len(topics) != 4 or _hex(topics[0]) != POOL_CREATED_TOPIC:
        raise ValueError("invalid Uniswap V3 PoolCreated log")
    tick_spacing_raw = _word(log.get("data"), 0)
    tick_spacing = int(tick_spacing_raw, 16)
    if tick_spacing >= 1 << 255:
        tick_spacing -= 1 << 256
    return {
        "chain": stream["chain"],
        "dex": DEX_UNISWAP_V3,
        "pool": _data_address(log.get("data"), 1),
        "token0": _topic_address(topics[1]),
        "token1": _topic_address(topics[2]),
        "fee_tier": int(_hex(topics[3]), 16),
        "factory": canonical_address(stream["factory"]),
        "creation_block": _block_number(log["blockNumber"]),
        "creation_tx": _hex(log.get("transactionHash")) or None,
        "discovery_branch": branch,
        "profile": {"tick_spacing": tick_spacing},
    }


class UniswapV3UniverseDiscovery:
    """Bounded, resumable Uniswap V3 PoolCreated ingestion."""

    def __init__(self, registry, log_reader, *, max_block_span=2000):
        self.max_block_span = int(max_block_span)
        if self.max_block_span < 1:
            raise ValueError("positive max block span required")
        self.registry = registry
        self.log_reader = log_reader

    def scan(self, *, start_block, finalized_block, branch="EXISTING"):
        branch = canonical_discovery_branch(branch)
        start_block = int(start_block)
        finalized_block = int(finalized_block)
        if start_block < 0 or finalized_block < 0:
            raise ValueError("block numbers must be non-negative")

        stream = UNISWAP_V3_FACTORY_STREAM
        factory = canonical_address(stream["factory"])
        saved = self.registry.checkpoint(
            stream["chain"], stream["dex"], factory,
            stream["event_kind"], branch,
        )
        from_block = (
            max(int(saved["last_scanned_block"]) + 1, start_block)
            if saved is not None else start_block
        )
        if from_block > finalized_block:
            return {
                "state": "CAUGHT_UP", "branch": branch,
                "from_block": from_block, "to_block": None,
                "registered": 0, "provider_call": False,
            }

        to_block = min(finalized_block, from_block + self.max_block_span - 1)
        logs = list(self.log_reader(
            address=factory,
            topic0=stream["topic0"],
            from_block=from_block,
            to_block=to_block,
        ))
        rows = [decode_pool_created(log, branch=branch) for log in logs]
        self.registry.ingest(rows, checkpoint={
            "chain": stream["chain"], "dex": stream["dex"],
            "factory": factory, "event_kind": stream["event_kind"],
            "discovery_branch": branch,
            "last_scanned_block": to_block,
            "last_finalized_block": to_block,
        })
        return {
            "state": "CAUGHT_UP" if to_block == finalized_block else "PARTIAL",
            "branch": branch, "from_block": from_block,
            "to_block": to_block, "registered": len(rows),
            "provider_call": True,
        }


__all__ = [
    "POOL_CREATED_TOPIC",
    "UNISWAP_V3_FACTORY_STREAM",
    "UniswapV3UniverseDiscovery",
    "decode_pool_created",
]
