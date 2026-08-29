from pathlib import Path


PANEL = Path("app/api/static/index.html")


def test_panel_accounting_shows_open_and_closed_trade_ledgers():
    html = PANEL.read_text(encoding="utf-8")

    assert "AÇIK İŞLEMLER" in html
    assert "KAPANAN İŞLEMLER" in html
    assert "state.dashboard?.positions" in html
    assert "state.dashboard?.exits" in html
    assert "CURRENT / EXIT" in html
    assert "holdDuration" in html
    assert "close_reason" in html


def test_main_ledger_combines_open_and_recently_closed_trades():
    html = PANEL.read_text(encoding="utf-8")

    assert "AÇIK ${open.length} · KAPALI ${closed.length}" in html
    assert "const rows=[...open.map" in html
    assert "...closed.map" in html
    assert "r.exit_price??r.current_price" in html
    assert "r.roi_pct" in html
