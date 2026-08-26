from pathlib import Path


PANEL = Path("app/api/static/index.html")


def test_premium_command_center_readability_contract():
    html = PANEL.read_text(encoding="utf-8")

    assert "İŞLEM MERKEZİ" in html
    assert "FIRSAT RADARI" in html
    assert "VEZİR" in html
    assert "SİSTEM & İSTİHBARAT" in html

    # High-contrast palette must remain explicit on the canonical panel.
    assert "--text:#f6fbff" in html
    assert "--text-2:#d2e1e8" in html
    assert "--muted:#94a9b5" in html

    # Critical hierarchy must stay readable while allowing responsive
    # viewport-fit tuning (for example 14px instead of a brittle 15px lock).
    assert ".brand-title{font-size:18px" in html
    assert ".metric-value" in html and "font-size:14px" in html
    assert ".section-title" in html and "font-size:13px" in html
    assert ".token-title{font-size:13px" in html

    # The live 1366-class layout must fit without reverting to the old
    # oversized minimums that clipped the top-right controls.
    assert ".app{height:100dvh;min-width:1180px" in html
    assert ".topbar{display:grid;grid-template-columns:235px minmax(545px,1fr) 390px" in html
    assert ".workspace{display:grid;grid-template-columns:275px minmax(560px,1fr) 355px" in html


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
