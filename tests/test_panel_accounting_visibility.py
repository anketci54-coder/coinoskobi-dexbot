from pathlib import Path


HTML = Path("app/api/static/index.html")
ACCEPTANCE = Path("app/api/static/panel-canonical-acceptance.js")
PANEL = Path("app/api/panel.py")


def test_accounting_drawer_uses_paginated_complete_ledger():
    js = ACCEPTANCE.read_text(encoding="utf-8")

    assert "async function showAccounting()" in js
    assert "async function getAccountingLedger()" in js
    assert "get('/api/dashboard')" in js
    assert "/api/accounting-ledger-v2?limit=100" in js
    assert "before_id=${encodeURIComponent(beforeId)}" in js
    assert "page.next_before_id" in js
    assert "getAccountingLedger()" in js
    assert "const rows = Array.isArray(ledger) ? ledger : []" in js
    assert "MUHASEBE · PAPER_10K" in js
    assert "get('/api/positions')" not in js


def test_accounting_backend_is_cursor_paginated_and_read_only():
    source = PANEL.read_text(encoding="utf-8")

    assert '@app.get("/api/accounting-ledger-v2")' in source
    assert "before_id: int | None = None" in source
    assert 'where_clause += " AND id < ?"' in source
    assert "bounded_limit = max(1, min(int(limit), 200))" in source
    assert "before_id=before_id" in source
    assert '"next_before_id": next_before_id' in source
    assert '"read_only": True' in source
    assert '"execution": False' in source
    assert '"wallet": False' in source
    assert '"signing": False' in source


def test_main_paper_ledger_is_removed_without_losing_accounting_data():
    html = HTML.read_text(encoding="utf-8")
    js = ACCEPTANCE.read_text(encoding="utf-8")

    assert "SİSTEM & PAPER LEDGER" not in html
    assert 'id="ledgerBody"' not in html
    assert "renderLedger" not in html
    assert 'id="accountingButton"' in html
    assert "/api/accounting-ledger-v2?limit=100" in js
    assert "dashboard.exits" not in js


def test_accounting_kpis_are_derived_from_complete_paginated_ledger():
    js = ACCEPTANCE.read_text(encoding="utf-8")

    assert "function accountingSummary(rows, dashboardSummary = {})" in js
    assert "const openRows = rows.filter" in js
    assert "row?.entry_amount_usdt ?? row?.amount_usdt" in js
    assert "row?.net_pnl_usdt ?? row?.net_pnl" in js
    assert "const summary = accountingSummary(rows, dashboard.summary || {})" in js
    assert "const summary = dashboard.summary || {}" not in js
