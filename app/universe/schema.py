import re


SCHEMA_VERSION = "UNIVERSE_REGISTRY_V1"

CHAIN_BSC = "bsc"

DEX_PANCAKESWAP_V2 = "pancakeswap_v2"
DEX_PANCAKESWAP_V3 = "pancakeswap_v3"
SUPPORTED_DEXES = frozenset({
    DEX_PANCAKESWAP_V2,
    DEX_PANCAKESWAP_V3,
})

DISCOVERY_EXISTING = "EXISTING"
DISCOVERY_NEW = "NEW"
DISCOVERY_BRANCHES = frozenset({
    DISCOVERY_EXISTING,
    DISCOVERY_NEW,
})

MARKET_COLD = "COLD"
MARKET_WARM = "WARM"
MARKET_HOT = "HOT"
MARKET_STATES = frozenset({
    MARKET_COLD,
    MARKET_WARM,
    MARKET_HOT,
})

_EVM_ADDRESS = re.compile(r"^0x[0-9a-f]{40}$")


def canonical_address(value, *, required=True):
    address = str(value or "").strip().lower()

    if not address and not required:
        return None

    if not _EVM_ADDRESS.fullmatch(address):
        raise ValueError("valid EVM address required")

    return address


def canonical_chain(value):
    chain = str(value or "").strip().lower()

    if chain != CHAIN_BSC:
        raise ValueError("unsupported chain")

    return chain


def canonical_dex(value):
    dex = str(value or "").strip().lower()

    if dex not in SUPPORTED_DEXES:
        raise ValueError("unsupported DEX")

    return dex


def canonical_discovery_branch(value):
    branch = str(value or "").strip().upper()

    if branch not in DISCOVERY_BRANCHES:
        raise ValueError("invalid discovery branch")

    return branch


def canonical_market_state(value):
    state = str(value or "").strip().upper()

    if state not in MARKET_STATES:
        raise ValueError("invalid market state")

    return state

