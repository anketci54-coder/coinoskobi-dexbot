from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "app" / "api" / "static"
HTML = STATIC / "index.html"
CSS = STATIC / "panel-visual-acceptance-v5.css"
JS = STATIC / "panel-visual-acceptance-v5.js"


def test_visual_acceptance_assets_load_after_premium_layers():
    html = HTML.read_text(encoding="utf-8")
    acceptance_css = "/static/panel-visual-acceptance-v5.css?v=1"
    acceptance_js = "/static/panel-visual-acceptance-v5.js?v=1"
    premium_css = "/static/panel-premium-intel-v5.css?v=1"
    premium_js = "/static/panel-premium-intel-v5.js?v=1"

    assert acceptance_css in html
    assert acceptance_js in html
    assert html.index(acceptance_css) > html.index(premium_css)
    assert html.index(acceptance_js) > html.index(premium_js)


def test_visual_acceptance_polishes_screenshot_findings_without_fake_data():
    css = CSS.read_text(encoding="utf-8")
    js = JS.read_text(encoding="utf-8")

    assert "risk-exposure-line" in css
    assert "acceptance-news-summary" in css
    assert "acceptance-vezir-layout" in css
    assert "scrollbar-color" in css

    assert "AÇIK MARUZİYET" in js
    assert "ADAY SAYISI SKOR DEĞİLDİR" in js
    assert "HENÜZ DOĞRULANMADI" in js
    assert "KANIT BEKLİYOR" in js
    assert "acceptance-news-grid" in js
    assert "acceptance-vezir-layout" in js
    assert "Ne yapmalı:" in js

    for forbidden in (
        "eth_sendRawTransaction",
        "PRIVATE_KEY",
        "WALLET_ADDRESS",
        "/api/manual-paper/order-v2",
    ):
        assert forbidden not in js


def test_visual_acceptance_has_no_network_or_runtime_authority():
    js = JS.read_text(encoding="utf-8")

    assert "fetch(" not in js
    assert "WebSocket" not in js
    assert "setInterval(" not in js
    assert "systemctl" not in js
