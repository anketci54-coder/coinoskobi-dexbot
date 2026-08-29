from app.dex.runtime_market_flow import RuntimeMarketFlowStore


TOKEN = "0x0000000000000000000000000000000000000001"
QUOTE = "0x0000000000000000000000000000000000000002"


def address(value):
    return "0x" + f"{value:040x}"


def test_default_store_has_bounded_rotation_headroom():
    store = RuntimeMarketFlowStore()

    assert store.max_pairs == 512

    tracked = address(1000)

    initial = [tracked] + [
        address(2000 + i)
        for i in range(255)
    ]

    for pair in initial:
        result = store.register_pair(
            pair,
            TOKEN,
            QUOTE,
        )
        assert result["state"] == "REGISTERED"

    store._snapshot_state[tracked] = {
        "spread": 4,
        "velocity": 2,
        "price_usd": 1.0,
        "liquidity_usd": 1000.0,
    }

    # Simulate one WSS target refresh replacing part of a full
    # 256-pair active set. The tracked active pair must retain its
    # observation history instead of being evicted by registration
    # order churn.
    rotated = [
        address(5000 + i)
        for i in range(16)
    ] + initial[:240]

    for pair in rotated:
        result = store.register_pair(
            pair,
            TOKEN,
            QUOTE,
        )
        assert result["state"] == "REGISTERED"

    assert store.pair_count <= store.max_pairs
    assert tracked in store._pairs
    assert store._snapshot_state[tracked]["spread"] == 4
    assert store._snapshot_state[tracked]["velocity"] == 2

    status = store.status()

    assert status["bounded"] is True
    assert status["decision_authority"] is False
    assert status["execution_authority"] is False
