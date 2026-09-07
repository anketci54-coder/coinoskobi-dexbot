from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "app" / "api" / "static"
HTML = STATIC / "index.html"
CSS = STATIC / "panel-premium-intel-v5.css"
JS = STATIC / "panel-premium-intel-v5.js"


def test_premium_intel_assets_are_wired():
    html = HTML.read_text(encoding="utf-8")
    assert "/static/panel-premium-intel-v5.css?v=1" in html
    assert "/static/panel-premium-intel-v5.js?v=1" in html


def test_premium_news_workspace_uses_real_read_only_endpoints():
    js = JS.read_text(encoding="utf-8")
    for endpoint in (
        "/api/market-brief-v3",
        "/api/calendar-brief-v3",
        "/api/operations-summary",
        "/api/vezir/ask",
    ):
        assert endpoint in js

    for label in (
        "HABER ETKİSİ",
        "NE YAPMALI?",
        "ETKİ ALANI",
        "ORİJİNAL BAŞLIK",
        "VEZİR 2.0",
        "ÖZET → NEDEN → NE YAPMALI",
        "EKSİK VERİYİ UYDURMAZ",
    ):
        assert label in js


def test_premium_intel_preserves_authority_boundaries():
    js = JS.read_text(encoding="utf-8")
    assert "TRADE SIGNAL YOK · READ ONLY" in js
    assert "Live execution / wallet / signing yetkisi yok" in js
    assert "Vezir trade açamaz" in js
    assert "eth_sendRawTransaction" not in js
    assert "PRIVATE_KEY" not in js
    assert "WALLET_ADDRESS" not in js


def test_premium_intel_is_responsive():
    css = CSS.read_text(encoding="utf-8")
    assert ".premium-intel-modal" in css
    assert ".premium-vezir-layout" in css
    assert "@media(max-width:900px)" in css
    assert "@media(max-width:580px)" in css
