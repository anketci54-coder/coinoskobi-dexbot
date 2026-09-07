from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "app" / "api" / "static"
HTML = STATIC / "index.html"
WALLET_CSS = STATIC / "panel-premium-wallet-v5.css"
WALLET_JS = STATIC / "panel-premium-wallet-v5.js"


def test_premium_wallet_assets_are_wired():
    html = HTML.read_text(encoding="utf-8")
    assert "/static/panel-premium-wallet-v5.css?v=1" in html
    assert "/static/panel-premium-wallet-v5.js?v=1" in html


def test_premium_wallet_uses_real_read_only_sources():
    js = WALLET_JS.read_text(encoding="utf-8")
    assert "/api/wallet-brief-v3" in js
    assert "/api/wallet-intelligence-v2" in js
    assert "NEDEN ADAY?" in js
    assert "BAŞARI / ÖRNEKLEM" in js
    assert "BALİNA / YÖN" in js
    assert "İLGİLİ TOKENLAR" in js
    assert "KANIT GÜVENİ" in js
    assert "Başarı oranı backend tarafından üretilmiyorsa yüzde uydurulmaz" in js


def test_premium_wallet_does_not_gain_execution_authority():
    js = WALLET_JS.read_text(encoding="utf-8")
    for forbidden in (
        "eth_sendRawTransaction",
        "PRIVATE_KEY",
        "WALLET_ADDRESS",
        "/api/manual-paper/order-v2",
        "confirmed:true",
    ):
        assert forbidden not in js


def test_premium_wallet_is_responsive():
    css = WALLET_CSS.read_text(encoding="utf-8")
    assert ".premium-wallet-modal" in css
    assert ".premium-wallet-table" in css
    assert "@media(max-width:1050px)" in css
    assert "@media(max-width:680px)" in css
