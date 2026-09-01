from app.dex.related_wallet_evidence import related_wallet_evidence
from app.dex.successful_wallet import SuccessfulWalletTracker
from app.dex.wallet_holdings import WalletHoldingsReadModel


def test_success_requires_repeated_realized_outcomes():
    tracker = SuccessfulWalletTracker()
    wallet = "bsc:0xabc"
    for i in range(19):
        tracker.observe_outcome(wallet, f"bsc:0x{i:040x}", 25, realized=True)
    assert tracker.snapshot(wallet)["state"] != "SUCCESSFUL"
    result = tracker.observe_outcome(wallet, "bsc:0xffff", 25, realized=True)
    assert result["state"] == "SUCCESSFUL"
    assert result["execution_authority"] is False


def test_holdings_are_bounded_and_zero_removes_position():
    model = WalletHoldingsReadModel(max_wallets=1, max_tokens_per_wallet=2)
    wallet = "bsc:0xabc"
    model.observe(wallet, "bsc:0x1", 10, value_usd=5)
    model.observe(wallet, "bsc:0x2", 20, value_usd=6)
    model.observe(wallet, "bsc:0x3", 30, value_usd=7)
    snap = model.snapshot(wallet)
    assert snap["token_count"] == 2
    assert all(row["token_id"] != "bsc:0x1" for row in snap["holdings"])
    model.observe(wallet, "bsc:0x2", 0)
    assert model.snapshot(wallet)["token_count"] == 1


def test_related_wallet_requires_multiple_evidence_classes():
    weak = related_wallet_evidence(
        "bsc:0xaaa", "bsc:0xbbb", direct_funding=True
    )
    assert weak["state"] == "WEAK_RELATIONSHIP"
    assert weak["auto_merge"] is False

    strong = related_wallet_evidence(
        "bsc:0xaaa",
        "bsc:0xbbb",
        direct_funding=True,
        repeated_transfers=5,
        common_funder=True,
        coordinated_entries=5,
    )
    assert strong["state"] == "STRONG_RELATIONSHIP"
    assert strong["identity_proof"] is False
    assert strong["ownership_claim"] is False
    assert strong["execution_authority"] is False
