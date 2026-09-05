from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "app" / "api" / "static" / "index.html"
BRIDGE = ROOT / "app" / "api" / "static" / "panel-canonical-acceptance.js"
CANONICAL = ROOT / "app" / "api" / "static" / "panel-canonical.js"
API_INIT = ROOT / "app" / "api" / "__init__.py"


def test_acceptance_controls_are_present():
    html = HTML.read_text(encoding="utf-8")
    assert 'id="accountingButton"' in html
    assert 'id="watchDetailButton"' in html
    assert 'id="autoTradeState"' in html
    assert "MUHASEBE" in html
    assert "HABER ETKİ" in html
    assert "CÜZDAN / BALİNA TAKİP" in html
    assert "/static/panel-canonical-acceptance.js?v=5" in html
    assert "/static/panel-refinement-v3.js?v=1" in html
    assert html.index("panel-canonical-acceptance.js") < html.index("panel-canonical.js")
    assert html.index("panel-canonical.js") < html.index("panel-refinement-v3.js")


def test_acceptance_bridge_keeps_canonical_vezir_endpoint():
    js = BRIDGE.read_text(encoding="utf-8")
    api_init = API_INIT.read_text(encoding="utf-8")
    assert "/api/vezir/chat-v2" not in js
    assert "/api/vezir/chat-v2" not in api_init
    assert "chat_with_vezir" not in api_init
    assert "'/api/live-news-v2'" in js
    assert "'/api/economic-calendar-v2'" in js
    assert "'/api/wallet-intelligence-v2'" in js
    assert "'/api/watch-probes-detail-v2?limit=100'" in js
    assert "'/api/auto-trade-health-v2'" in js
    assert "'/api/dashboard'" in js


def test_arkham_wallet_detail_is_read_only_and_uses_existing_feed():
    js = BRIDGE.read_text(encoding="utf-8")
    assert "showWalletDetails" in js
    assert "ensureWalletDetailButton" in js
    assert "walletDetailButton" in js
    assert "ARKHAM KAPALI · API KEY YOK" in js
    assert "SON VARLIK DEĞİŞİMLERİ" in js
    assert "CÜZDAN / BALİNA TAKİP · ARKHAM HOLDINGS" in js
    assert "get('/api/wallet-intelligence-v2')" in js


def test_canonical_vezir_uses_bounded_verified_intent_context():
    js = CANONICAL.read_text(encoding="utf-8")
    assert "vezirContext:[]" in js
    assert "state.vezirContext.slice(-4)" in js
    assert "<<VEZIR_CTX:" in js
    assert "state.vezirContext=[...state.vezirContext,code].slice(-4)" in js
    assert "getJSON('/api/vezir/ask'" in js


def test_acceptance_bridge_does_not_create_execution_authority():
    js = BRIDGE.read_text(encoding="utf-8")
    assert "eth_sendRawTransaction" not in js
    assert "PRIVATE_KEY" not in js
    assert "WALLET_ADDRESS" not in js
    assert "confirmed:true" not in js.replace(" ", "")
