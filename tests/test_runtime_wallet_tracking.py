from app.dex.runtime_wallet_tracking import RuntimeWalletTracking


WALLET = "bsc:0x0000000000000000000000000000000000000101"


def actor(state="OBSERVED", origin_state="READY"):
    return {
        "state": state,
        "wallet_id": WALLET,
        "transaction_origin": {
            "state": origin_state,
            "address": WALLET.split(":", 1)[1],
        },
    }


def test_proven_native_actor_enters_tracking_boundary():
    runtime = RuntimeWalletTracking()
    snap = runtime.actor_snapshot(actor())
    assert snap["state"] == "READY"
    assert snap["wallet_id"] == WALLET
    assert snap["identity_source"] == "TRANSACTION_FROM_ONLY"
    assert snap["identity_guessing"] is False
    assert snap["execution_authority"] is False


def test_unresolved_origin_cannot_enter_tracking():
    runtime = RuntimeWalletTracking()
    snap = runtime.actor_snapshot(actor(origin_state="UNKNOWN"))
    assert snap["state"] == "UNKNOWN"
    assert snap["identity_guessing"] is False


def test_outcome_and_holding_bind_to_proven_wallet_only():
    runtime = RuntimeWalletTracking()
    result = runtime.observe_outcome(actor(), "bsc:0xtoken", 25.0, realized=True)
    assert result["wallet_id"] == WALLET
    assert result["realized_sample_size"] == 1

    holding = runtime.observe_holding(actor(), "bsc:0xtoken", 10, value_usd=50)
    assert holding["wallet_id"] == WALLET
    assert holding["token_count"] == 1
    assert holding["known_value_usd"] == 50


def test_unproven_actor_cannot_write_outcome_or_holding():
    runtime = RuntimeWalletTracking()
    bad = actor(state="UNKNOWN")
    assert runtime.observe_outcome(bad, "bsc:0xtoken", 99)["state"] == "UNKNOWN"
    assert runtime.observe_holding(bad, "bsc:0xtoken", 10)["state"] == "UNKNOWN"
