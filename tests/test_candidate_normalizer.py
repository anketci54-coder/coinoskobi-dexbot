from app.pipeline.normalizer import CandidateNormalizer


def gecko_row():
    return {
        "pool": "0xABCDEF",
        "base_token": "0x123456",
        "quote_token": "0x999999",
        "name": "Example",
        "dex": "pancakeswap_v2",
        "price_usd": 0.001,
        "fdv": 100000,
        "market_cap": 0,
        "liquidity": 12000,
        "volume_24h": 8000,
        "buys_24h": 42,
        "created_at": "2026-08-10T00:00:00Z",
    }


def test_gecko_bsc_normalizes_to_common_candidate():
    candidate = CandidateNormalizer.gecko_bsc(
        gecko_row()
    )

    assert candidate.chain == "bsc"
    assert candidate.chain_id == 56
    assert candidate.source == "geckoterminal"
    assert candidate.dex == "pancakeswap_v2"

    assert candidate.pool == "0xabcdef"
    assert candidate.token == "0x123456"
    assert candidate.quote_token == "0x999999"

    assert candidate.token_identity_key == (
        "bsc:0x123456"
    )

    assert candidate.pool_identity_key == (
        "bsc:pancakeswap_v2:0xabcdef"
    )


def test_gecko_bsc_many_isolates_bad_row():
    valid = gecko_row()

    invalid = gecko_row()
    invalid["pool"] = None

    result = CandidateNormalizer.gecko_bsc_many([
        valid,
        invalid,
    ])

    assert len(result["candidates"]) == 1
    assert result["rejected"] == 1


def test_same_address_can_exist_on_other_chain():
    candidate = CandidateNormalizer.gecko_bsc(
        gecko_row()
    )

    assert candidate.token_identity_key == (
        "bsc:0x123456"
    )


def test_candidate_dict_preserves_pipeline_fields():
    candidate = CandidateNormalizer.gecko_bsc(
        gecko_row()
    )

    data = candidate.to_dict()

    assert data["chain"] == "bsc"
    assert data["chain_id"] == 56
    assert data["dex"] == "pancakeswap_v2"
    assert data["liquidity"] == 12000
    assert data["volume_24h"] == 8000
    assert data["buys_24h"] == 42
    assert data["fdv"] == 100000
    assert data["price_usd"] == 0.001


def test_gecko_bsc_removes_chain_prefix_from_token():
    row = gecko_row()

    row["base_token"] = (
        "bsc_0x123456"
    )
    row.pop("token", None)

    row["quote_token"] = (
        "bsc_0x999999"
    )

    candidate = CandidateNormalizer.gecko_bsc(
        row
    )

    assert candidate.token == "0x123456"
    assert candidate.quote_token == "0x999999"

    assert candidate.token_identity_key == (
        "bsc:0x123456"
    )
