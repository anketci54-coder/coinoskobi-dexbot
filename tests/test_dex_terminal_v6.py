from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "app" / "api" / "static"
HTML = STATIC / "index.html"
CSS = STATIC / "dex-terminal.css"
JS = STATIC / "dex-terminal.js"


LEGACY_ASSETS = {
    "panel-canonical-acceptance.js",
    "panel-canonical.css",
    "panel-canonical.js",
    "panel-performance-v5.js",
    "panel-premium-accounting-v5.css",
    "panel-premium-accounting-v5.js",
    "panel-premium-intel-v5.css",
    "panel-premium-intel-v5.js",
    "panel-premium-v5.css",
    "panel-premium-v5.js",
    "panel-premium-wallet-v5.css",
    "panel-premium-wallet-v5.js",
    "panel-refinement-v3.css",
    "panel-refinement-v3.js",
    "panel-visual-acceptance-v5.css",
    "panel-visual-acceptance-v5.js",
}


def test_v6_is_single_frontend_owner():
    html = HTML.read_text(encoding="utf-8")

    assert '/static/dex-terminal.css?v=2' in html
    assert '/static/dex-terminal.js?v=2' in html

    for asset in LEGACY_ASSETS:
        assert asset not in html
        assert not (STATIC / asset).exists(), asset


def test_v6_navigation_owns_real_distinct_pages():
    html = HTML.read_text(encoding="utf-8")

    for page in (
        "home",
        "radar",
        "positions",
        "history",
        "wallet",
        "news",
        "calendar",
        "launch",
        "vezir",
    ):
        assert f'data-page="{page}"' in html
        assert f'data-page-target="{page}"' in html

    assert "AÇIK POZİSYONLAR" in html
    assert "İŞLEM GEÇMİŞİ" in html
    assert "CÜZDAN İSTİHBARATI" in html
    assert "HABER AKIŞI" in html
    assert "EKONOMİK TAKVİM" in html
    assert "AIRDROP / IDO / ICO" in html
    assert "VEZİR 2.0" in html


def test_v6_is_dex_specific_and_has_no_cex_orderbook_language():
    html = HTML.read_text(encoding="utf-8")
    js = JS.read_text(encoding="utf-8")
    text = (html + "\n" + js).upper()

    for required in (
        "BSC",
        "DEX",
        "PANCAKESWAP",
        "POOL",
        "LİKİDİTE",
        "CÜZDAN",
        "AIRDROP / IDO / ICO",
    ):
        assert required in text

    for forbidden in (
        "BINANCE ORDER BOOK",
        "BYBIT",
        "FUTURES",
        "PERPETUAL",
        "FUNDING RATE",
        "OPEN INTEREST",
        "LEVERAGE",
        "KALDIRAÇ",
    ):
        assert forbidden not in text


def test_v6_binds_only_existing_readmodels_and_paper_preview():
    js = JS.read_text(encoding="utf-8")

    for endpoint in (
        "/api/dashboard",
        "/api/universe-panel",
        "/api/accounting-ledger-v2?limit=",
        "/api/wallet-brief-v3",
        "/api/wallet-intelligence-v2",
        "/api/market-brief-v3",
        "/api/calendar-brief-v3",
        "/api/manual-paper/preview-v2",
        "/api/vezir/ask",
    ):
        assert endpoint in js

    assert "LEDGER_PAGE_SIZE = 200" in js
    assert "before_id=${encodeURIComponent(beforeId)}" in js
    assert "page?.next_before_id" in js

    for forbidden in (
        "eth_sendRawTransaction",
        "PRIVATE_KEY",
        "WALLET_ADDRESS",
        "signTransaction",
    ):
        assert forbidden not in js


def test_v6_keeps_live_execution_locked_in_ui():
    html = HTML.read_text(encoding="utf-8")

    assert "LIVE KAPALI" in html
    assert "LIVE EXECUTION KAPALI" in html
    assert "WALLET AUTHORITY KAPALI" in html
    assert "PAPER_10K" in html


def test_v6_layout_is_responsive():
    css = CSS.read_text(encoding="utf-8")

    assert "@media(max-width:1200px)" in css
    assert "@media(max-width:820px)" in css
    assert "@media(max-width:560px)" in css
    assert ".terminal-shell" in css
    assert ".terminal-page.active" in css
