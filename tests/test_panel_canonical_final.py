from pathlib import Path

from app.api import _panel as panel_api


ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "app" / "api" / "static"
HTML = STATIC / "index.html"
JS = STATIC / "panel-canonical.js"
CSS = STATIC / "panel-canonical.css"
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
    assert "/static/panel-canonical.css?v=1" in html
    assert "/static/panel-canonical.js?v=3" in html
    assert "panel-premium-v2" not in html
    assert "panel-radar-trade-v3" not in html
    assert "panel-premium-v2" not in init
    assert "panel-radar-trade-v3" not in init
    assert "middleware" not in init


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
    for label in (
        "RADAR MERKEZİ",
        "1 USDT TESTLER",
        "CÜZDAN / BALİNA TAKİP",
        "HABER AKIŞI",
        "EKONOMİK TAKVİM",
        "VEZİR",
    ):
        assert label in html
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
    assert "@media(max-width:1180px)" in css
    assert "@media(max-width:680px)" in css
    assert ".radar-entry.open .radar-detail" in css
    assert "body.manual .order-btn" in css
