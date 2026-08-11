from app.dex.sniper_pumpdump import evaluate_sniper_pumpdump


def test_benign_sniper_activity():
    r = evaluate_sniper_pumpdump(
        early_buy_count=1,
        coordinated_early_buy_score=0.1,
        accumulation_concentration=0.2,
        distribution_concentration=0.1,
        synchronized_dump_score=0.0,
        repeat_pumpdump_count=0,
    )
    assert r["state"] == "SNIPER_ACTIVITY"
    assert r["sniper_is_malicious_proof"] is False


def test_strong_pumpdump():
    r = evaluate_sniper_pumpdump(
        early_buy_count=10,
        coordinated_early_buy_score=0.95,
        accumulation_concentration=0.9,
        distribution_concentration=0.95,
        synchronized_dump_score=0.95,
        repeat_pumpdump_count=3,
    )
    assert r["state"] == "STRONG_PUMPDUMP_EVIDENCE"


def test_candidate():
    r = evaluate_sniper_pumpdump(
        early_buy_count=5,
        coordinated_early_buy_score=0.9,
        accumulation_concentration=0.7,
        distribution_concentration=0.85,
        synchronized_dump_score=0.4,
        repeat_pumpdump_count=0,
    )
    assert r["state"] == "PUMPDUMP_CANDIDATE"


def test_repeat_pattern_tag():
    r = evaluate_sniper_pumpdump(
        repeat_pumpdump_count=3,
    )
    assert "REPEAT_PUMPDUMP_ASSOCIATION" in r["evidence_tags"]


def test_synchronized_dump_tag():
    r = evaluate_sniper_pumpdump(
        synchronized_dump_score=0.9,
    )
    assert "SYNCHRONIZED_DUMP" in r["evidence_tags"]


def test_early_buy_not_attack_proof():
    r = evaluate_sniper_pumpdump(
        early_buy_count=10,
    )
    assert r["early_buy_is_attack_proof"] is False


def test_stale_unknown():
    r = evaluate_sniper_pumpdump(
        early_buy_count=10,
        coordinated_early_buy_score=1.0,
        distribution_concentration=1.0,
        synchronized_dump_score=1.0,
        repeat_pumpdump_count=10,
        freshness="STALE",
    )
    assert r["state"] == "UNKNOWN"


def test_authority_zero():
    r = evaluate_sniper_pumpdump(
        early_buy_count=10,
        coordinated_early_buy_score=1.0,
        distribution_concentration=1.0,
        synchronized_dump_score=1.0,
        repeat_pumpdump_count=3,
    )

    assert r["trade_signal"] is False
    assert r["decision_authority"] is False
    assert r["paper_authority"] is False
    assert r["live_authority"] is False
    assert r["wallet_authority"] is False
    assert r["execution_authority"] is False
