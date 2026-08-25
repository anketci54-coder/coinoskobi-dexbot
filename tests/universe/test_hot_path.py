import sqlite3

from app.universe.hot_path import HotDeepPathRouter


def address(value):
    return "0x" + f"{value:040x}"


class Registry:
    def __init__(self, rows):
        self.rows = rows
        self.limits = []

    def hot_pools(self, *, limit):
        self.limits.append(limit)
        return self.rows[:limit]


def row(value, *, dex="pancakeswap_v2", token0=None, token1=None,
        score=5):
    return {
        "chain": "bsc", "dex": dex, "pool": address(value),
        "token0": token0 or address(100 + value),
        "token1": token1 or "0x55d398326f99059ff775485246999027b3197955",
        "market_state": "HOT", "seismic_score": score,
        "latest_price_usd": 1, "latest_liquidity_usd": 5000,
        "latest_volume_24h": 9000, "latest_snapshot_source": "dexscreener",
    }


def verifier(pair, token, quote):
    return {"state": "VERIFIED"}


def test_hot_v2_is_native_eligible_and_identity_is_bound():
    registry = Registry([row(1)])
    router = HotDeepPathRouter(registry, pair_membership_verifier=verifier)
    target = router.native_wss_targets(limit=10)[0]
    assert target["pair"] == address(1)
    assert target["token"] == address(101)
    assert target["market_state"] == "HOT"
    assert registry.limits == [10]


def test_hot_v3_remains_deep_candidate_but_not_v2_native_decoder_target():
    router = HotDeepPathRouter(
        Registry([row(2, dex="pancakeswap_v3")]),
        pair_membership_verifier=verifier,
    )
    assert len(router.candidates(limit=10)) == 1
    assert router.native_wss_targets(limit=10) == []
    assert router.status()["v3_snapshot_deep_only"] == 1


def test_ambiguous_quote_identity_fails_closed():
    usdt = "0x55d398326f99059ff775485246999027b3197955"
    wbnb = "0xbb4cdb9cbD36b01bd1cbaebf2de08d9173bc095c".lower()
    router = HotDeepPathRouter(
        Registry([row(3, token0=usdt, token1=wbnb)]),
        pair_membership_verifier=verifier,
    )
    assert router.candidates(limit=10) == []


def test_failed_membership_never_reaches_native_wss():
    router = HotDeepPathRouter(
        Registry([row(4)]),
        pair_membership_verifier=lambda *args: {"state": "MISMATCH"},
    )
    assert router.native_wss_targets(limit=10) == []


def test_registry_hot_read_is_bounded_and_score_ordered():
    from app.universe.registry import UniverseRegistry
    registry = UniverseRegistry(connection=sqlite3.connect(":memory:"))
    for value, score in ((1, 3), (2, 9)):
        pool = row(value, score=score)
        registry.ingest([{
            "chain": "bsc", "dex": pool["dex"], "pool": pool["pool"],
            "token0": pool["token0"], "token1": pool["token1"],
            "factory": address(900), "creation_block": value,
            "discovery_branch": "EXISTING",
        }])
        registry.db.execute(
            "UPDATE universe_pool_registry SET market_state='HOT' WHERE pool=?",
            (pool["pool"],),
        )
        registry.db.execute("""
            INSERT INTO universe_seismic_evaluation_v1(
                chain,dex,pool,observed_at,policy,previous_state,next_state,
                score,evidence_count,reason,created_at
            ) VALUES('bsc',?,?,?,?,?,?,?,?,?,?)
        """, (
            pool["dex"], pool["pool"], f"2026-08-25T16:0{value}:00+00:00",
            "TEST", "WARM", "HOT", score, 3, "TEST", "NOW",
        ))
    registry.db.commit()
    selected = registry.hot_pools(limit=1)
    assert len(selected) == 1
    assert selected[0]["pool"] == address(2)
    assert selected[0]["seismic_score"] == 9
