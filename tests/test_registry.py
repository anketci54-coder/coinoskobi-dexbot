import pytest

from app.config.registry import (
    dex_supports_chain,
    enabled_dexes,
    enabled_networks,
    get_dex,
    get_network,
    get_source,
)


def test_bsc_is_enabled():
    network = get_network("BSC")

    assert network["name"] == "bsc"
    assert network["chain_id"] == 56
    assert network["enabled"] is True


def test_future_networks_exist_but_disabled():
    ethereum = get_network(
        "ethereum"
    )

    base = get_network(
        "base"
    )

    assert ethereum["enabled"] is False
    assert base["enabled"] is False


def test_only_bsc_is_enabled_initially():
    assert enabled_networks() == [
        "bsc"
    ]


def test_pancakeswap_supports_bsc():
    assert dex_supports_chain(
        "pancakeswap_v2",
        "bsc",
    )


def test_pancakeswap_does_not_claim_ethereum():
    assert not dex_supports_chain(
        "pancakeswap_v2",
        "ethereum",
    )


def test_enabled_bsc_dexes():
    dexes = enabled_dexes(
        "bsc"
    )

    assert "pancakeswap_v2" in dexes
    assert "pancakeswap_v3" in dexes


def test_future_uniswap_v3_disabled():
    dex = get_dex(
        "uniswap_v3"
    )

    assert dex["enabled"] is False
    assert "ethereum" in dex["chains"]
    assert "base" in dex["chains"]


def test_gecko_source_binding():
    source = get_source(
        "geckoterminal"
    )

    assert source["enabled"] is True
    assert source["adapter"] == "gecko_bsc"
    assert source["networks"] == {"bsc"}


def test_unknown_registry_entries_fail():
    with pytest.raises(KeyError):
        get_network("unknown")

    with pytest.raises(KeyError):
        get_dex("unknown")

    with pytest.raises(KeyError):
        get_source("unknown")
