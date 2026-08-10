import pytest

from app.pipeline.candidate import Candidate


def base_row():
    return {
        "pool": "0xABCDEF",
        "token": "0x123456",
        "quote_token": "0x999999",
        "dex": "PancakeSwap_V2",
        "liquidity": "12000",
        "volume_24h": "8000",
        "buys_24h": "42",
        "fdv": "150000",
        "price_usd": "0.001",
        "created_at": "2026-08-10T00:00:00Z",
    }


def test_candidate_normalizes_common_fields():
    candidate = Candidate.from_row(
        base_row(),
        chain="BSC",
        chain_id=56,
        source="GeckoTerminal",
    )

    assert candidate.chain == "bsc"
    assert candidate.chain_id == 56
    assert candidate.dex == "pancakeswap_v2"
    assert candidate.pool == "0xabcdef"
    assert candidate.token == "0x123456"
    assert candidate.quote_token == "0x999999"
    assert candidate.source == "geckoterminal"

    assert candidate.liquidity == 12000.0
    assert candidate.volume_24h == 8000.0
    assert candidate.buys_24h == 42
    assert candidate.fdv == 150000.0
    assert candidate.price_usd == 0.001


def test_token_identity_is_chain_aware():
    bsc = Candidate.from_row(
        base_row(),
        chain="bsc",
        chain_id=56,
        source="gecko",
    )

    eth = Candidate.from_row(
        base_row(),
        chain="ethereum",
        chain_id=1,
        source="gecko",
    )

    assert (
        bsc.token_identity
        != eth.token_identity
    )

    assert (
        bsc.token_identity_key
        != eth.token_identity_key
    )


def test_pool_identity_is_chain_and_dex_aware():
    first = Candidate.from_row(
        base_row(),
        chain="bsc",
        chain_id=56,
        source="gecko",
    )

    row = base_row()
    row["dex"] = "pancakeswap_v3"

    second = Candidate.from_row(
        row,
        chain="bsc",
        chain_id=56,
        source="gecko",
    )

    assert (
        first.pool_identity
        != second.pool_identity
    )


def test_candidate_accepts_base_token_alias():
    row = base_row()

    row.pop("token")
    row["base_token"] = "0x777777"

    candidate = Candidate.from_row(
        row,
        chain="bsc",
        chain_id=56,
        source="gecko",
    )

    assert candidate.token == "0x777777"


def test_candidate_requires_chain():
    with pytest.raises(ValueError):
        Candidate.from_row(
            base_row(),
            chain="",
            chain_id=56,
            source="gecko",
        )


def test_candidate_requires_token():
    row = base_row()

    row.pop("token")

    with pytest.raises(ValueError):
        Candidate.from_row(
            row,
            chain="bsc",
            chain_id=56,
            source="gecko",
        )


def test_candidate_requires_pool():
    row = base_row()

    row.pop("pool")

    with pytest.raises(ValueError):
        Candidate.from_row(
            row,
            chain="bsc",
            chain_id=56,
            source="gecko",
        )


def test_candidate_to_dict_contains_identity_keys():
    candidate = Candidate.from_row(
        base_row(),
        chain="bsc",
        chain_id=56,
        source="gecko",
    )

    data = candidate.to_dict()

    assert (
        data["token_identity"]
        == "bsc:0x123456"
    )

    assert (
        data["pool_identity"]
        == "bsc:pancakeswap_v2:0xabcdef"
    )
