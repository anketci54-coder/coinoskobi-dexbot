from pathlib import Path


HTML = Path("app/api/static/index.html")
ACCEPTANCE = Path("app/api/static/panel-canonical-acceptance.js")


def test_accounting_drawer_uses_complete_positions_ledger():
    js = ACCEPTANCE.read_text(encoding="utf-8")

    assert "async function showAccounting()" in js
    assert "get('/api/dashboard')" in js
    assert "get('/api/positions')" in js
    assert "const rows = Array.isArray(ledger) ? ledger : []" in js
    assert "MUHASEBE · PAPER_10K" in js


def test_main_paper_ledger_is_removed_without_losing_accounting_data():
    html = HTML.read_text(encoding="utf-8")
    js = ACCEPTANCE.read_text(encoding="utf-8")

    assert "SİSTEM & PAPER LEDGER" not in html
    assert 'id="ledgerBody"' not in html
    assert "renderLedger" not in html
    assert 'id="accountingButton"' in html
    assert "get('/api/positions')" in js
    assert "dashboard.exits" not in js
