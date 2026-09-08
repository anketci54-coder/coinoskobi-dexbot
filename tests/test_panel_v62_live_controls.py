from pathlib import Path

STATIC = Path("app/api/static")
HTML = STATIC / "index.html"
JS = STATIC / "dex-terminal.js"
CSS = STATIC / "dex-terminal.css"


def test_single_canonical_frontend_assets():
    assert JS.exists()
    assert CSS.exists()

    for old in (
        "dex-terminal-v6.js",
        "dex-terminal-v61.js",
        "dex-terminal-v6.css",
        "dex-terminal-v61.css",
    ):
        assert not (STATIC / old).exists()

    html = HTML.read_text(encoding="utf-8")

    assert "/static/dex-terminal.js?v=2" in html
    assert "/static/dex-terminal.css?v=2" in html
    assert "dex-terminal-v6.js" not in html
    assert "dex-terminal-v61.js" not in html


def test_open_position_marks_use_read_only_fresh_preview():
    js = JS.read_text(encoding="utf-8")

    assert "refreshOpenPaperMarks" in js
    assert "/api/manual-paper/preview-v2" in js
    assert "data-preview-position" in js
    assert "positionsPnl" in js
    assert "reference_price" in js
    assert "net_pnl_usdt" in js
    assert "roi_pct" in js


def test_manual_and_automatic_paper_are_visible_without_live_authority():
    js = JS.read_text(encoding="utf-8")

    assert "MANUEL PAPER AL" in js
    assert "PAPER SATIŞI ONAYLA" in js
    assert "OTOMATİK PAPER AL/SAT · RUNTIME" in js

    assert "eth_sendRawTransaction" not in js
    assert "PRIVATE_KEY" not in js
    assert "seed phrase" in js


def test_wallet_detail_combines_context_and_holdings():
    js = JS.read_text(encoding="utf-8")

    assert "showWalletRich" in js
    assert "/api/v61/wallet-readonly" in js
    assert "/api/wallet-intelligence-v2" in js
    assert "/api/wallet-brief-v3" in js
    assert "BAŞARI DURUMU" in js
    assert "BALİNA / YÖN" in js
    assert "TOPLAM PORTFÖY" in js


def test_news_and_calendar_features_are_preserved():
    js = JS.read_text(encoding="utf-8")

    assert "/api/market-brief-v3" in js
    assert "/api/calendar-brief-v3" in js
    assert "HABER" in js
    assert "EKONOMİK TAKVİM" in js
