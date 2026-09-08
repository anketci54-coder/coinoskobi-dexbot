from pathlib import Path


HTML = Path("app/api/static/index.html")
V6 = Path("app/api/static/dex-terminal.js")
PANEL = Path("app/api/panel.py")


def test_v6_history_uses_complete_paginated_ledger():
    js = V6.read_text(encoding="utf-8")

    assert "async function getAccountingLedger()" in js
    assert "LEDGER_PAGE_SIZE = 200" in js
    assert "MAX_LEDGER_PAGES = 25" in js
    assert "/api/accounting-ledger-v2?limit=${LEDGER_PAGE_SIZE}" in js
    assert "before_id=${encodeURIComponent(beforeId)}" in js
    assert "page?.next_before_id" in js
    assert "seenIds" in js
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


def test_open_positions_and_history_are_distinct_v6_pages():
    html = HTML.read_text(encoding="utf-8")
    js = V6.read_text(encoding="utf-8")

    assert 'data-page="positions"' in html
    assert 'data-page="history"' in html
    assert 'id="positionRows"' in html
    assert 'id="historyRows"' in html
    assert "function renderPositions()" in js
    assert "function renderHistory()" in js
    assert "function closedRows()" in js
    assert "String(row.status||'').toUpperCase()==='CLOSED'" in js


def test_history_kpis_are_derived_from_complete_ledger():
    js = V6.read_text(encoding="utf-8")

    assert "function accountingSummary(rows,dashboardSummary={})" in js
    assert "const openRows=source.filter" in js
    assert "const closedRows=source.filter" in js
    assert "row?.entry_amount_usdt??row?.amount_usdt" in js
    assert "row?.net_pnl_usdt??row?.net_pnl" in js
    assert "const summary=accountingSummary(ledger?.rows||[],dashboard?.summary||{})" in js


def test_v6_has_no_dependency_on_deleted_legacy_acceptance_asset():
    html = HTML.read_text(encoding="utf-8")
    js = V6.read_text(encoding="utf-8")

    assert "panel-canonical-acceptance.js" not in html
    assert "panel-canonical-acceptance.js" not in js
