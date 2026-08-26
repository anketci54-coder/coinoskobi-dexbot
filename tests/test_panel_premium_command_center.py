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

    assert "font-size:18px" in html
    assert "font-size:15px" in html
    assert "font-size:13px" in html


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
