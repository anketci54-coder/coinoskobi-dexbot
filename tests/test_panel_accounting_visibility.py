from pathlib import Path


PANEL = Path("app/api/static/index.html")


def test_accounting_drawer_still_shows_open_and_closed_trade_ledgers():
    html = PANEL.read_text(encoding="utf-8")

    assert "AÇIK İŞLEMLER" in html
    assert "KAPANAN İŞLEMLER" in html
    assert "state.dashboard?.positions" in html
    assert "state.dashboard?.exits" in html
    assert "CURRENT / EXIT" in html
    assert "holdDuration" in html
    assert "/api/positions" in html


def test_main_paper_ledger_is_removed_without_losing_accounting_data():
    html = PANEL.read_text(encoding="utf-8")

    assert "SİSTEM & PAPER LEDGER" not in html
    assert 'id="ledgerBody"' not in html
    assert "renderLedger" not in html
    assert "const source=Array.isArray(state.accountingRows)" in html
    assert "...(state.dashboard?.positions||[])" in html
    assert "...(state.dashboard?.exits||[])" in html
