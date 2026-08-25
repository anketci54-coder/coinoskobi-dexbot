import pytest

from app.universe.registry import UniverseRegistry
from app.universe.seismic import SeismicClassifier, SeismicPolicy


def address(value):
    return "0x" + f"{value:040x}"


def history(current, count=8):
    rows = [
        {"observed_at": f"2026-08-25T15:{index:02d}:00+00:00",
         "change_m5": 0.1, "volume_m5_usd": 100,
         "txns_m5": 10, "liquidity_usd": 1000}
        for index in range(count)
    ]
    rows.append({
        "observed_at": "2026-08-25T16:00:00+00:00",
        "change_m5": current[0], "volume_m5_usd": current[1],
        "txns_m5": current[2], "liquidity_usd": current[3],
    })
    return rows


def classify(state, rows):
    return SeismicClassifier().classify(
        chain="bsc", dex="pancakeswap_v2", pool=address(1),
        market_state=state, history=rows,
    )


def test_insufficient_history_never_promotes():
    result = classify("COLD", history((20, 50000, 5000, 1000), count=3))
    assert result["next_state"] == "COLD"
    assert result["reason"] == "INSUFFICIENT_HISTORY"


def test_two_pool_relative_anomalies_promote_cold_to_warm():
    result = classify("COLD", history((2, 1000, 10, 1000)))
    assert result["next_state"] == "WARM"
    assert result["evidence_count"] == 2


def test_three_strong_anomalies_promote_to_hot():
    result = classify("WARM", history((2, 1000, 100, 1000)))
    assert result["next_state"] == "HOT"
    assert result["evidence_count"] == 3


def test_liquidity_collapse_blocks_promotion():
    result = classify("COLD", history((2, 1000, 100, 500)))
    assert result["next_state"] == "COLD"
    assert result["reason"] == "NO_ROBUST_MOVEMENT"


def test_hot_cools_one_state_at_a_time():
    result = classify("HOT", history((0.1, 100, 10, 1000)))
    assert result["next_state"] == "WARM"
    assert result["reason"] == "HOT_EVIDENCE_SUBSIDED"


def test_policy_guards_invalid_magic_configuration():
    with pytest.raises(ValueError):
        SeismicPolicy(warm_z=5, hot_z=3)


def test_evaluation_is_audited_and_state_change_is_atomic(tmp_path):
    registry = UniverseRegistry(tmp_path / "cache.db")
    registry.ingest([{
        "chain": "bsc", "dex": "pancakeswap_v2", "pool": address(1),
        "token0": address(2), "token1": address(3), "factory": address(4),
        "creation_block": 1, "discovery_branch": "EXISTING",
    }])
    evaluation = classify("COLD", history((2, 1000, 10, 1000)))
    assert registry.apply_seismic_evaluation(evaluation) == "WARM"
    assert registry.get_pool("bsc", "pancakeswap_v2", address(1))[
        "market_state"] == "WARM"
    assert registry.db.execute(
        "SELECT reason FROM universe_seismic_evaluation_v1"
    ).fetchone()[0] == "ROBUST_MULTI_SIGNAL_WARM"
    with pytest.raises(ValueError, match="stale"):
        registry.apply_seismic_evaluation(evaluation)
