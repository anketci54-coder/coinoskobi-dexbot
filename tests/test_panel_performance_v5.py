from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "app" / "api" / "static"
HTML = STATIC / "index.html"
PERF = STATIC / "panel-performance-v5.js"


def test_performance_scheduler_loads_before_refresh_owners():
    html = HTML.read_text(encoding="utf-8")
    perf = '/static/panel-performance-v5.js?v=1'
    canonical = '/static/panel-canonical.js?v=9'
    refinement = '/static/panel-refinement-v3.js?v=6'

    assert perf in html
    assert html.index(perf) < html.index(canonical)
    assert html.index(perf) < html.index(refinement)


def test_performance_scheduler_bounds_heavy_polling_and_hidden_work():
    js = PERF.read_text(encoding="utf-8")

    assert "refresh: 8000" in js
    assert "refreshTickers: 30000" in js
    assert "refreshMarket: 45000" in js
    assert "refreshWallet: 30000" in js
    assert "refreshProviderState: 45000" in js
    assert "refreshAutoHealth: 30000" in js
    assert "document.hidden" in js
    assert "detailPanelOpen()" in js
    assert ".premium-accounting-modal.open" in js
    assert ".premium-wallet-modal.open" in js
    assert ".premium-intel-modal.open" in js


def test_performance_scheduler_does_not_add_execution_authority():
    js = PERF.read_text(encoding="utf-8")

    for forbidden in (
        "eth_sendRawTransaction",
        "PRIVATE_KEY",
        "WALLET_ADDRESS",
        "/api/manual-paper/order-v2",
        "fetch(",
    ):
        assert forbidden not in js
