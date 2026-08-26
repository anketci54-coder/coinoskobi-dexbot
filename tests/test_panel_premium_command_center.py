from pathlib import Path


PANEL = Path("app/api/static/index.html")


def test_premium_command_center_readability_contract():
    html = PANEL.read_text(encoding="utf-8")

    assert "İŞLEM MERKEZİ" in html
    assert "FIRSAT RADARI" in html
    assert "VEZİR" in html
    assert "SİSTEM & İSTİHBARAT" in html

    assert "--text:#f6fbff" in html
    assert "--text-2:#d2e1e8" in html
    assert "--muted:#94a9b5" in html

    assert ".brand-title{font-size:18px" in html
    assert ".market-price{margin-top:7px;font-size:16px" in html
    assert ".stage-title{font-size:16px" in html
    assert ".detail-name{font-size:20px" in html
    assert ".token-title{font-size:13px" in html


def test_command_center_v2_replaces_legacy_three_column_skeleton():
    html = PANEL.read_text(encoding="utf-8")

    assert ".workspace{display:grid;grid-template-columns:minmax(0,1fr) 350px" in html
    assert ".stage-body{display:grid;grid-template-columns:minmax(0,1.15fr) minmax(340px,.85fr)" in html
    assert "class=\"panel mainstage\"" in html
    assert "class=\"right-rail\"" in html

    assert "class=\"left-stack\"" not in html
    assert "class=\"panel positions\"" not in html
    assert "class=\"panel performance\"" not in html


def test_premium_command_center_preserves_real_data_contracts():
    html = PANEL.read_text(encoding="utf-8")

    assert "getJson('/api/dashboard')" in html
    assert "getJson('/api/runtime-candidates')" in html
    assert "getJson('/api/authority')" in html
    assert "sahte veri yok" in html


def test_premium_command_center_has_no_wallet_or_execution_authority():
    html = PANEL.read_text(encoding="utf-8")

    assert "CÜZDAN KAPALI" in html
    assert "READ ONLY" in html

    forbidden = (
        "eth_requestAccounts",
        "wallet_switchEthereumChain",
        "eth_sendTransaction",
        "sendTransaction(",
        "connectWallet(",
    )

    for marker in forbidden:
        assert marker not in html
