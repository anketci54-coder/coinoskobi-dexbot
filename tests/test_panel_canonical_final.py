from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "app" / "api" / "static" / "index.html"
JS = ROOT / "app" / "api" / "static" / "panel-canonical.js"
CSS = ROOT / "app" / "api" / "static" / "panel-canonical.css"
INIT = ROOT / "app" / "api" / "__init__.py"


def test_root_panel_has_one_canonical_frontend_owner():
    html = HTML.read_text(encoding="utf-8")
    init = INIT.read_text(encoding="utf-8")
    assert "/static/panel-canonical.css?v=1" in html
    assert "/static/panel-canonical.js?v=1" in html
    assert "panel-premium-v2" not in html
    assert "panel-radar-trade-v3" not in html
    assert "panel-premium-v2" not in init
    assert "panel-radar-trade-v3" not in init
    assert "middleware" not in init


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
