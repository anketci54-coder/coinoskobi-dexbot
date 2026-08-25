from app.config.contracts import PANCAKE_FACTORY, PANCAKE_V3_FACTORY
from app.universe.schema import (
    DISCOVERY_EXISTING, DISCOVERY_NEW,
    DEX_PANCAKESWAP_V2, DEX_PANCAKESWAP_V3,
    canonical_address, canonical_discovery_branch,
)

PAIR_CREATED_TOPIC = (
    "0x0d3648bd0f6ba80134a33ba9275ac585d9d315f0"
    "ad8355cddefde31afa28d0e9"
)
POOL_CREATED_TOPIC = (
    "0x783cca1c0412dd0d695e784568c96da2e9c22ff9"
    "89357a2e8b1d9b2b4e6b7118"
)

PANCAKE_FACTORY_STREAMS = (
    {"chain": "bsc", "dex": DEX_PANCAKESWAP_V2,
     "factory": PANCAKE_FACTORY, "event_kind": "PAIR_CREATED",
     "topic0": PAIR_CREATED_TOPIC},
    {"chain": "bsc", "dex": DEX_PANCAKESWAP_V3,
     "factory": PANCAKE_V3_FACTORY, "event_kind": "POOL_CREATED",
     "topic0": POOL_CREATED_TOPIC},
)


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


def decode_v2_pair_created(log, stream, branch):
    topics = list(log.get("topics") or [])
    if len(topics) != 3 or _hex(topics[0]) != PAIR_CREATED_TOPIC:
        raise ValueError("invalid PairCreated log")
    return {
        "chain": stream["chain"], "dex": DEX_PANCAKESWAP_V2,
        "pool": _data_address(log.get("data"), 0),
        "token0": _topic_address(topics[1]),
        "token1": _topic_address(topics[2]),
        "factory": stream["factory"],
        "creation_block": _block_number(log["blockNumber"]),
        "creation_tx": _hex(log.get("transactionHash")) or None,
        "discovery_branch": branch,
    }


def decode_v3_pool_created(log, stream, branch):
    topics = list(log.get("topics") or [])
    if len(topics) != 4 or _hex(topics[0]) != POOL_CREATED_TOPIC:
        raise ValueError("invalid PoolCreated log")
    return {
        "chain": stream["chain"], "dex": DEX_PANCAKESWAP_V3,
        "pool": _data_address(log.get("data"), 1),
        "token0": _topic_address(topics[1]),
        "token1": _topic_address(topics[2]),
        "fee_tier": int(_hex(topics[3]), 16),
        "factory": stream["factory"],
        "creation_block": _block_number(log["blockNumber"]),
        "creation_tx": _hex(log.get("transactionHash")) or None,
        "discovery_branch": branch,
    }


class PancakeUniverseDiscovery:
    """Bounded, resumable PancakeSwap V2/V3 creation-log ingestion."""

    def __init__(self, registry, log_reader, *, max_block_span=2000):
        self.max_block_span = int(max_block_span)
        if self.max_block_span < 1:
            raise ValueError("positive max block span required")
        self.registry = registry
        self.log_reader = log_reader

    def scan(self, stream, *, start_block, finalized_block, branch):
        branch = canonical_discovery_branch(branch)
        start_block, finalized_block = int(start_block), int(finalized_block)
        if start_block < 0 or finalized_block < 0:
            raise ValueError("block numbers must be non-negative")

        factory = canonical_address(stream["factory"])
        saved = self.registry.checkpoint(
            stream["chain"], stream["dex"], factory, stream["event_kind"]
        )
        from_block = (
            int(saved["last_scanned_block"]) + 1
            if saved is not None else start_block
        )
        if from_block > finalized_block:
            return {"state": "CAUGHT_UP", "branch": branch,
                    "from_block": from_block, "to_block": None,
                    "registered": 0, "provider_call": False}

        to_block = min(
            finalized_block, from_block + self.max_block_span - 1
        )
        logs = list(self.log_reader(
            address=factory, topic0=stream["topic0"],
            from_block=from_block, to_block=to_block,
        ))
        decoder = {
            DEX_PANCAKESWAP_V2: decode_v2_pair_created,
            DEX_PANCAKESWAP_V3: decode_v3_pool_created,
        }.get(stream["dex"])
        if decoder is None:
            raise ValueError("unsupported discovery stream")

        rows = [decoder(log, stream, branch) for log in logs]
        self.registry.ingest(rows, checkpoint={
            "chain": stream["chain"], "dex": stream["dex"],
            "factory": factory, "event_kind": stream["event_kind"],
            "last_scanned_block": to_block,
            "last_finalized_block": to_block,
        })
        return {
            "state": "CAUGHT_UP" if to_block == finalized_block else "PARTIAL",
            "branch": branch, "from_block": from_block, "to_block": to_block,
            "registered": len(rows), "provider_call": True,
        }


__all__ = ["DISCOVERY_EXISTING", "DISCOVERY_NEW",
           "PANCAKE_FACTORY_STREAMS", "PancakeUniverseDiscovery"]
