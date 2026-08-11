from app.dex.wallet_evidence import normalize_wallet, wallet_evidence


ADDR = "0xABCDEF"


def test_chain_aware_identity():
    bsc = normalize_wallet("BSC", ADDR)
    eth = normalize_wallet("ETH", ADDR)

    assert bsc["wallet_id"] == "bsc:0xabcdef"
    assert eth["wallet_id"] == "eth:0xabcdef"
    assert bsc["wallet_id"] != eth["wallet_id"]


def test_normalization():
    r = normalize_wallet(" BSC ", " 0xABCDEF ")
    assert r["chain"] == "bsc"
    assert r["address"] == "0xabcdef"


def test_missing_wallet_unknown():
    assert normalize_wallet("bsc", None)["state"] == "UNKNOWN"


def test_evidence_ready():
    r = wallet_evidence(
        "bsc",
        ADDR,
        inbound_value=150,
        outbound_value=40,
        buy_count=3,
        sell_count=1,
    )

    assert r["state"] == "READY"
    assert r["net_flow"] == 110
    assert r["participation_count"] == 4


def test_stale_unknown():
    r = wallet_evidence(
        "bsc",
        ADDR,
        freshness="STALE",
    )
    assert r["state"] == "UNKNOWN"


def test_negative_values_clamped():
    r = wallet_evidence(
        "bsc",
        ADDR,
        inbound_value=-10,
        outbound_value=-20,
        buy_count=-2,
        sell_count=-3,
    )

    assert r["inbound_value"] == 0
    assert r["outbound_value"] == 0
    assert r["buy_count"] == 0
    assert r["sell_count"] == 0


def test_identity_guessing_forbidden():
    r = wallet_evidence("bsc", ADDR)
    assert r["identity_guessing"] is False


def test_authority_zero():
    r = wallet_evidence("bsc", ADDR)

    assert r["decision_authority"] is False
    assert r["paper_authority"] is False
    assert r["live_authority"] is False
    assert r["wallet_authority"] is False
    assert r["execution_authority"] is False
