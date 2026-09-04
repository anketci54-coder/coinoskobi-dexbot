from pathlib import Path


HTML = Path("app/api/static/index.html")
ACCEPTANCE = Path("app/api/static/panel-canonical-acceptance.js")


def test_accounting_drawer_still_shows_open_and_closed_trade_ledgers():
    js = ACCEPTANCE.read_text(encoding="utf-8")

    assert "async function showAccounting()" in js
    assert "const dashboard = await get('/api/dashboard')" in js
    assert "Array.isArray(dashboard.positions)" in js
    assert "Array.isArray(dashboard.exits)" in js
    assert "...positions.map" in js
    assert "...exits.map" in js
    assert "AÇIK" in js
    assert "KAPALI" in js
    assert "MUHASEBE · PAPER_10K" in js


def test_main_paper_ledger_is_removed_without_losing_accounting_data():
    html = HTML.read_text(encoding="utf-8")
    js = ACCEPTANCE.read_text(encoding="utf-8")

    assert "SİSTEM & PAPER LEDGER" not in html
    assert 'id="ledgerBody"' not in html
    assert "renderLedger" not in html
    assert 'id="accountingButton"' in html
    assert "async function showAccounting()" in js
    assert "dashboard.positions" in js
    assert "dashboard.exits" in js
