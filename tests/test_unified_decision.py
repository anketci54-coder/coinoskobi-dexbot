from app.strategy.decision import UnifiedDecisionEngine


def decide(**overrides):
    data = {
        "strategy_decision": "PAPER_BUY",
        "sellability": "UNKNOWN",
        "local_evidence_complete": False,
        "hard_block": False,
        "opportunity_state": "WATCH",
        "opportunity_reason": "ACTIVE_PRICE_SERIES_NOT_READY",
    }
    data.update(overrides)
    return UnifiedDecisionEngine().evaluate(data)


def test_hard_block_always_rejects():
    assert decide(hard_block=True)["decision"] == "REJECT"


def test_sellable_but_not_hot_stays_watch():
    result = decide(
        sellability="SELLABLE",
        opportunity_state="WATCH",
        opportunity_reason="ACTIVE_MOMENTUM_NOT_POSITIVE",
    )
    assert result["decision"] == "WATCH"


def test_hot_and_sellable_becomes_candidate():
    result = decide(
        sellability="SELLABLE",
        opportunity_state="HOT",
        opportunity_reason="ACTIVE_CONTINUATION_READY",
    )
    assert result["decision"] == "PAPER_BUY_CANDIDATE"


def test_hot_with_local_exit_evidence_survives_provider_unknown():
    result = decide(
        sellability="UNKNOWN",
        local_evidence_complete=True,
        opportunity_state="HOT",
        opportunity_reason="ACTIVE_CONTINUATION_READY",
    )
    assert result["decision"] == "PAPER_BUY_CANDIDATE"


def test_unknown_without_hot_opportunity_stays_watch():
    assert decide()["decision"] == "WATCH"


def test_no_authority():
    result = decide(
        sellability="SELLABLE",
        opportunity_state="HOT",
        opportunity_reason="ACTIVE_CONTINUATION_READY",
    )
    for key in (
        "paper_authority",
        "live_authority",
        "wallet_authority",
        "execution_authority",
    ):
        assert result[key] is False
