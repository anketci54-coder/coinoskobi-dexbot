from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "app" / "api" / "static" / "index.html"
BRIDGE = ROOT / "app" / "api" / "static" / "panel-canonical-acceptance.js"


def test_acceptance_controls_are_present():
    html = HTML.read_text(encoding="utf-8")
    assert 'id="accountingButton"' in html
    assert 'id="watchDetailButton"' in html
    assert 'id="autoTradeState"' in html
    assert "MUHASEBE" in html
    assert "HABER ETKİ" in html
    assert "/static/panel-canonical-acceptance.js?v=2" in html
    assert html.index("panel-canonical-acceptance.js") < html.index("panel-canonical.js")


def test_acceptance_bridge_uses_real_endpoints_and_chat_v2():
    js = BRIDGE.read_text(encoding="utf-8")
    assert "'/api/vezir/chat-v2'" in js
    assert "'/api/live-news-v2'" in js
    assert "'/api/economic-calendar-v2'" in js
    assert "'/api/wallet-intelligence-v2'" in js
    assert "'/api/watch-probes-detail-v2?limit=100'" in js
    assert "'/api/auto-trade-health-v2'" in js
    assert "'/api/dashboard'" in js


def test_acceptance_bridge_does_not_create_execution_authority():
    js = BRIDGE.read_text(encoding="utf-8")
    assert "eth_sendRawTransaction" not in js
    assert "PRIVATE_KEY" not in js
    assert "WALLET_ADDRESS" not in js
    assert "confirmed:true" not in js.replace(" ", "")
