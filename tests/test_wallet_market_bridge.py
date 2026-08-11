from app.dex.wallet_market_bridge import bind_wallet_market_context


BASE_WALLET = {
    "state": "READY",
    "wallet_id": "bsc:0xabc",
}

BASE_BEHAVIOR = {
    "state": "OBSERVED",
    "behavior_tags": ["ACCUMULATION_EVIDENCE"],
}

BASE_ENTITY = {"state": "STRONG_LINK"}

BASE_WHALE = {
    "state": "DISTRIBUTED",
    "tags": ["MULTI_WHALE_ACTIVITY"],
}

BASE_REP = {"state": "LOW_RISK"}


def test_ready():
    r = bind_wallet_market_context(
        BASE_WALLET,
        BASE_BEHAVIOR,
        BASE_ENTITY,
        BASE_WHALE,
        BASE_REP,
    )
    assert r["wallet_context_ready"] is True
    assert r["market_context_allowed"] is True


def test_unknown_wallet_blocks():
    w = dict(BASE_WALLET)
    w["state"] = "UNKNOWN"

    r = bind_wallet_market_context(
        w, BASE_BEHAVIOR, BASE_ENTITY, BASE_WHALE, BASE_REP
    )
    assert r["wallet_context_ready"] is False


def test_unknown_entity_blocks():
    r = bind_wallet_market_context(
        BASE_WALLET,
        BASE_BEHAVIOR,
        {"state": "UNKNOWN"},
        BASE_WHALE,
        BASE_REP,
    )
    assert r["wallet_context_ready"] is False


def test_stale_reputation_blocks():
    r = bind_wallet_market_context(
        BASE_WALLET,
        BASE_BEHAVIOR,
        BASE_ENTITY,
        BASE_WHALE,
        {"state": "UNKNOWN"},
    )
    assert r["wallet_context_ready"] is False


def test_hard_risk_preserved():
    r = bind_wallet_market_context(
        BASE_WALLET,
        BASE_BEHAVIOR,
        BASE_ENTITY,
        BASE_WHALE,
        {"state": "HARD_RISK_EVIDENCE"},
    )
    assert r["wallet_hard_risk"] is True
    assert r["hard_safety_override_allowed"] is False


def test_no_trade_permission():
    r = bind_wallet_market_context(
        BASE_WALLET,
        BASE_BEHAVIOR,
        BASE_ENTITY,
        BASE_WHALE,
        BASE_REP,
    )
    assert r["trade_permission"] is False
    assert r["decision_authority"] is False
    assert r["paper_authority"] is False
    assert r["live_authority"] is False
    assert r["wallet_authority"] is False
    assert r["execution_authority"] is False
