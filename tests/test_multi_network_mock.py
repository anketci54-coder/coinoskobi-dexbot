from app.config import registry as registry_module
from app.pipeline.candidate_queue import CandidateAdmissionQueue
from app.scanner.adapters import registry as adapter_registry
from app.scanner.adapters.source_router import normalize_source_rows


ADDRESS = "0xabc123"


def install_mock_network(monkeypatch):
    monkeypatch.setitem(
        registry_module.NETWORKS,
        "mocknet",
        {
            "chain_id": 999999,
            "enabled": True,
            "rpc_key": "mocknet",
        },
    )

    monkeypatch.setitem(
        registry_module.DEXES,
        "mockdex",
        {
            "enabled": True,
            "chains": {"mocknet"},
        },
    )

    source = registry_module.SOURCES["geckoterminal"]

    networks = dict(source["networks"])

    networks["mocknet"] = {
        "adapter": "mocknet_test",
    }

    monkeypatch.setitem(
        registry_module.SOURCES,
        "geckoterminal",
        {
            **source,
            "networks": networks,
        },
    )


def bsc_row():
    return {
        "pool": "0xbscpool",
        "base_token": f"bsc_{ADDRESS}",
        "quote_token": "bsc_0xquote",
        "dex": "pancakeswap_v2",
        "liquidity": 15000,
        "volume_24h": 8000,
        "buys_24h": 50,
        "fdv": 100000,
        "price_usd": 0.001,
        "created_at": None,
    }


def mock_row():
    return {
        "pool": "0xmockpool",
        "token": ADDRESS,
        "quote_token": "0xquote",
        "dex": "mockdex",
        "liquidity": 16000,
        "volume_24h": 9000,
        "buys_24h": 60,
        "fdv": 120000,
        "price_usd": 0.002,
        "created_at": None,
    }


def test_only_bsc_is_enabled_without_mock():
    assert registry_module.enabled_networks() == ["bsc"]


def test_mock_network_binding(monkeypatch):
    install_mock_network(monkeypatch)

    network = registry_module.get_network("mocknet")

    assert network["enabled"] is True
    assert network["chain_id"] == 999999

    binding = registry_module.get_source_network(
        "geckoterminal",
        "mocknet",
    )

    assert binding["adapter"] == "mocknet_test"


def test_mockdex_supports_only_mocknet(monkeypatch):
    install_mock_network(monkeypatch)

    assert registry_module.dex_supports_chain(
        "mockdex",
        "mocknet",
    )

    assert not registry_module.dex_supports_chain(
        "mockdex",
        "bsc",
    )


def test_same_address_on_two_networks_stays_distinct(
    monkeypatch,
):
    install_mock_network(monkeypatch)

    bsc = normalize_source_rows(
        "geckoterminal",
        "bsc",
        [bsc_row()],
    )["candidates"][0]

    mock = normalize_source_rows(
        "geckoterminal",
        "mocknet",
        [mock_row()],
    )["candidates"][0]

    assert bsc.token_identity_key == f"bsc:{ADDRESS}"
    assert mock.token_identity_key == f"mocknet:{ADDRESS}"

    assert (
        bsc.token_identity_key
        != mock.token_identity_key
    )


def test_queue_keeps_same_address_from_two_networks(
    monkeypatch,
):
    install_mock_network(monkeypatch)

    bsc = normalize_source_rows(
        "geckoterminal",
        "bsc",
        [bsc_row()],
    )["candidates"][0].to_dict()

    mock = normalize_source_rows(
        "geckoterminal",
        "mocknet",
        [mock_row()],
    )["candidates"][0].to_dict()

    queue = CandidateAdmissionQueue(
        max_pending=100,
        cooldown_seconds=60,
    )

    assert queue.enqueue(bsc)
    assert queue.enqueue(mock)

    assert queue.pending_count == 2


def test_duplicate_collapses_only_inside_same_network(
    monkeypatch,
):
    install_mock_network(monkeypatch)

    bsc = normalize_source_rows(
        "geckoterminal",
        "bsc",
        [bsc_row()],
    )["candidates"][0].to_dict()

    mock = normalize_source_rows(
        "geckoterminal",
        "mocknet",
        [mock_row()],
    )["candidates"][0].to_dict()

    queue = CandidateAdmissionQueue(
        max_pending=100,
        cooldown_seconds=60,
    )

    queue.enqueue(bsc)
    queue.enqueue(bsc)

    queue.enqueue(mock)
    queue.enqueue(mock)

    assert queue.pending_count == 2
    assert queue.duplicate_collapsed == 2
