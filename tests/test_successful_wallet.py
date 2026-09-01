from app.dex.successful_wallet import SuccessfulWalletTracker


def test_single_moonshot_does_not_create_successful_wallet():
    tracker = SuccessfulWalletTracker()
    result = tracker.observe_outcome(
        "bsc:0xabc", "bsc:0xtoken", 10000.0, realized=True
    )
    assert result["state"] == "INSUFFICIENT_SAMPLE"
    assert result["trade_signal"] is False
    assert result["execution_authority"] is False


def test_repeated_realized_success_can_qualify():
    tracker = SuccessfulWalletTracker()
    result = None
    for i in range(20):
        result = tracker.observe_outcome(
            "bsc:0xabc", f"bsc:0xtoken{i}", 10.0 if i < 13 else -2.0,
            realized=True,
        )
    assert result["state"] == "SUCCESSFUL"
    assert result["realized_sample_size"] == 20
    assert result["win_rate"] == 0.65
    assert result["decision_authority"] is False
    assert result["wallet_authority"] is False


def test_tracker_is_bounded():
    tracker = SuccessfulWalletTracker(max_wallets=2, max_outcomes_per_wallet=2)
    tracker.observe_outcome("bsc:0x1", "bsc:0xa", 1, realized=True)
    tracker.observe_outcome("bsc:0x1", "bsc:0xb", 2, realized=True)
    tracker.observe_outcome("bsc:0x1", "bsc:0xc", 3, realized=True)
    assert tracker.snapshot("bsc:0x1")["sample_size"] == 2

    tracker.observe_outcome("bsc:0x2", "bsc:0xa", 1, realized=True)
    tracker.observe_outcome("bsc:0x3", "bsc:0xa", 1, realized=True)
    assert tracker.snapshot("bsc:0x1")["state"] == "UNKNOWN"


def test_invalid_outcome_is_rejected():
    tracker = SuccessfulWalletTracker()
    assert tracker.observe_outcome("", "bsc:0xa", 1)["state"] == "INVALID"
    assert tracker.observe_outcome("bsc:0x1", "", 1)["state"] == "INVALID"
    assert tracker.observe_outcome("bsc:0x1", "bsc:0xa", float("inf"))["state"] == "INVALID"
