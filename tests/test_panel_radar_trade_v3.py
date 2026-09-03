from pathlib import Path


JS = Path("app/api/static/panel-radar-trade-v3.js")
CSS = Path("app/api/static/panel-radar-trade-v3.css")
INIT = Path("app/api/__init__.py")


def test_radar_ticket_uses_confirmed_paper_only_order_route():
    source = JS.read_text(encoding="utf-8")
    assert "/api/manual-paper/order-v2" in source
    assert "confirmed:true" in source
    assert "ALIM MİKTARI (USDT)" in source
    assert "ALIMI ONAYLA" in source
    assert "SATIŞI ONAYLA" in source
    assert "server güncel fiyatı tekrar doğrular" in source
    assert "Sadece PAPER hesap" in source
    assert "Bayat fiyatla emir reddedilir" in source


def test_radar_ticket_never_contains_wallet_or_live_execution_calls():
    source = JS.read_text(encoding="utf-8")
    forbidden = (
        "eth_requestAccounts",
        "wallet_switchEthereumChain",
        "eth_sendTransaction",
        "sendTransaction(",
        "connectWallet(",
        "signTransaction(",
        "PRIVATE_KEY",
        "RPC_URL",
    )
    for marker in forbidden:
        assert marker not in source


def test_radar_ticket_assets_are_cache_busted_and_v2_route_is_registered():
    source = INIT.read_text(encoding="utf-8")
    assert 'panel-radar-trade-v3.css?v=2' in source
    assert 'panel-radar-trade-v3.js?v=2' in source
    assert "register_manual_paper_routes_v2" in source
    assert "register_manual_paper_routes(" not in source


def test_radar_ticket_has_responsive_modal_styles():
    source = CSS.read_text(encoding="utf-8")
    assert ".v3-order-modal" in source
    assert ".v3-order-card" in source
    assert "@media (max-width:760px)" in source
