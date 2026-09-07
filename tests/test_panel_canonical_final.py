from pathlib import Path

from app.api import _panel as panel_api


ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "app" / "api" / "static"
HTML = STATIC / "index.html"
JS = STATIC / "panel-canonical.js"
CSS = STATIC / "panel-canonical.css"
REFINEMENT_JS = STATIC / "panel-refinement-v3.js"
PREMIUM_CSS = STATIC / "panel-premium-v5.css"
PREMIUM_JS = STATIC / "panel-premium-v5.js"
PREMIUM_ACCOUNTING_CSS = STATIC / "panel-premium-accounting-v5.css"
PREMIUM_ACCOUNTING_JS = STATIC / "panel-premium-accounting-v5.js"
INIT = ROOT / "app" / "api" / "__init__.py"
LEGACY_MANUAL_PAPER = ROOT / "app" / "api" / "panel_manual_paper.py"
LEGACY_VEZIR_MODULES = (
    ROOT / "app" / "api" / "vezir_chat.py",
    ROOT / "app" / "api" / "vezir_memory.py",
    ROOT / "app" / "api" / "vezir_learning.py",
)
LEGACY_PANEL_ASSETS = (
    "panel-premium-v2.css",
    "panel-premium-v2.js",
    "panel-radar-trade-v3.css",
    "panel-radar-trade-v3.js",
    "panel-readable.css",
)


def test_root_panel_has_one_canonical_frontend_owner():
    html = HTML.read_text(encoding="utf-8")
    init = INIT.read_text(encoding="utf-8")
    assert "/static/panel-canonical.css?v=6" in html
    assert "/static/panel-canonical.js?v=9" in html
    assert "/static/panel-refinement-v3.js?v=6" in html
    assert "/static/panel-premium-v5.css?v=1" in html
    assert "/static/panel-premium-v5.js?v=1" in html
    assert "/static/panel-premium-accounting-v5.css?v=1" in html
    assert "/static/panel-premium-accounting-v5.js?v=1" in html
    assert "result.join('\\n')" in JS.read_text(encoding="utf-8")
    assert "panel-premium-v2" not in html
    assert "panel-radar-trade-v3" not in html
    assert "panel-premium-v2" not in init
    assert "panel-radar-trade-v3" not in init
    assert "middleware" not in init


def test_premium_panel_keeps_real_data_contracts_and_icon_slots():
    html = HTML.read_text(encoding="utf-8")
    premium_css = PREMIUM_CSS.read_text(encoding="utf-8")
    premium_js = PREMIUM_JS.read_text(encoding="utf-8")

    for element_id in (
        'balance',
        'dailyPnl',
        'totalPnl',
        'openCount',
        'riskUsed',
        'radarBody',
        'walletRows',
        'newsStream',
        'chatBody',
    ):
        assert f'id="{element_id}"' in html

    assert 'data-icon-slot="brand"' in html
    assert 'data-icon-slot="radar"' in html
    assert 'data-icon-slot="wallet"' in html
    assert '.premium-shell' in premium_css
    assert 'SATIŞ YÖNETİMİ' in premium_js
    assert '/api/manual-paper/preview-v2' in premium_js
    assert 'Hedef fiyat uydurulmaz' in premium_js
    assert 'eth_sendRawTransaction' not in premium_js
    assert 'PRIVATE_KEY' not in premium_js


def test_premium_accounting_separates_mark_realized_risk_and_exposure():
    html = HTML.read_text(encoding="utf-8")
    accounting_css = PREMIUM_ACCOUNTING_CSS.read_text(encoding="utf-8")
    accounting_js = PREMIUM_ACCOUNTING_JS.read_text(encoding="utf-8")

    assert 'panel-premium-accounting-v5.css?v=1' in html
    assert 'panel-premium-accounting-v5.js?v=1' in html
    assert '/api/dashboard' in accounting_js
    assert '/api/accounting-ledger-v2?limit=100' in accounting_js
    assert '/api/watch-probes-detail-v2?limit=100' in accounting_js
    assert '/api/portfolio-marks-v2' in accounting_js
    assert 'MARK NEDİR?' in accounting_js
    assert 'REALİZE ÇIKIŞ NEDİR?' in accounting_js
    assert 'RİSK ≠ MARUZİYET' in accounting_js
    assert 'MODELLENEN RİSK' in accounting_js
    assert 'TAHMİNİ ÇIKIŞ PNL' in accounting_js
    assert 'TAHMİNİ NET PNL' in accounting_js
    assert 'VEZİR ÖZETİ' in accounting_js
    assert '.premium-accounting-modal' in accounting_css
    assert 'eth_sendRawTransaction' not in accounting_js
    assert 'PRIVATE_KEY' not in accounting_js
    assert 'WALLET_ADDRESS' not in accounting_js


def test_legacy_panel_assets_are_removed():
    for name in LEGACY_PANEL_ASSETS:
        assert not (STATIC / name).exists(), name


def test_legacy_manual_paper_v1_route_is_removed():
    assert not LEGACY_MANUAL_PAPER.exists()

    route_paths = {
        route.path
        for route in panel_api.app.routes
    }

    assert "/api/manual-paper/order-v2" in route_paths
    assert "/api/manual-paper/order" not in route_paths


def test_legacy_vezir_v1_cluster_is_removed():
    for path in LEGACY_VEZIR_MODULES:
        assert not path.exists(), path.name

    route_paths = {
        route.path
        for route in panel_api.app.routes
    }

    assert "/api/vezir/ask" in route_paths
    assert "/api/vezir/chat-v2" not in route_paths


def test_canonical_runtime_owns_required_real_connections():
    js = JS.read_text(encoding="utf-8")
    for endpoint in (
        "/api/dashboard",
        "/api/universe-panel",
        "/api/watch-probes",
        "/api/operations-summary",
        "/api/vezir/ask",
        "/api/manual-paper/order-v2",
    ):
        assert endpoint in js
    assert "setInterval(refresh,5000)" in js
    assert "setInterval(refreshTickers,20000)" in js


def test_panel_exposes_operational_sections_without_fake_news():
    html = HTML.read_text(encoding="utf-8")
    js = JS.read_text(encoding="utf-8")
    refinement = REFINEMENT_JS.read_text(encoding="utf-8")
    for label in (
        "RADAR MERKEZİ",
        "CÜZDAN / BALİNA TAKİP",
        "PİYASA HABERLERİ",
        "EKONOMİK TAKVİM",
        "AIRDROP / IDO / ICO",
        "VEZİR",
    ):
        assert label in html
    assert "1 USDT TESTLER" not in html
    assert "1 USDT TESTLER" in refinement
    assert "Sahte haber gösterilmiyor" in js
    assert "Sahte etkinlik gösterilmiyor" in js


def test_manual_ticket_is_explicitly_paper_only():
    html = HTML.read_text(encoding="utf-8")
    js = JS.read_text(encoding="utf-8")
    assert "MANUEL İŞLEMLER SADECE PAPER" in html
    assert "Live execution, wallet ve signing kapalıdır" in html
    assert "confirmed:true" in js
    assert "ALIMI ONAYLA" in js
    assert "SATIŞI ONAYLA" in js


def test_canonical_assets_are_responsive_and_self_contained():
    css = CSS.read_text(encoding="utf-8")
    premium_css = PREMIUM_CSS.read_text(encoding="utf-8")
    accounting_css = PREMIUM_ACCOUNTING_CSS.read_text(encoding="utf-8")
    assert "@media(max-width:1180px)" in css
    assert "@media(max-width:680px)" in css
    assert ".radar-entry.open .radar-detail" in css
    assert "body.manual .order-btn" in css
    assert "@media(max-width:1000px)" in premium_css
    assert ".premium-sell-ticket" in premium_css
    assert "@media(max-width:720px)" in accounting_css


def test_radar_filter_survives_page_reload():
    js = JS.read_text(encoding="utf-8")

    assert "coinoskobi.radar.filter" in js
    assert "localStorage.getItem(FILTER_STORAGE_KEY)" in js
    assert "localStorage.setItem(FILTER_STORAGE_KEY,value)" in js
    assert "VALID_FILTERS" in js
    assert "'ACTIVE'" in js
    assert "restoreFilter()" in js
