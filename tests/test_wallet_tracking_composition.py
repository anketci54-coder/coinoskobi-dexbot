from app.dex.wallet_tracking_composition import WalletTrackingComposition


def test_composition_keeps_authority_closed():
    tracking = WalletTrackingComposition()
    wallet = "bsc:0xabc"

    tracking.observe_outcome(wallet, "bsc:0xtoken", 12.0, realized=True)
    tracking.observe_holding(wallet, "bsc:0xtoken", 100.0, value_usd=25.0)

    snap = tracking.snapshot(wallet)
    assert snap["performance"]["state"] == "INSUFFICIENT_SAMPLE"
    assert snap["holdings"]["state"] == "READY"
    assert snap["holdings"]["known_value_usd"] == 25.0
    assert snap["entity_auto_merge"] is False
    assert snap["trade_signal"] is False
    assert snap["decision_authority"] is False
    assert snap["wallet_authority"] is False
    assert snap["execution_authority"] is False


def test_related_wallet_is_evidence_only():
    tracking = WalletTrackingComposition()
    result = tracking.related_wallet(
        "bsc:0xaaa",
        "bsc:0xbbb",
        direct_funding=True,
        repeated_transfers=4,
        shared_funder=True,
        coordinated_entries=3,
        coordinated_exits=2,
    )
    assert result["state"] in {"STRONG_LINK", "POSSIBLE_LINK"}
    assert result["auto_merge"] is False
    assert result["ownership_claim"] is False
    assert result["decision_authority"] is False
    assert result["execution_authority"] is False
