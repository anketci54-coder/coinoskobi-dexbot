from pathlib import Path


JS = Path("app/api/static/panel-canonical.js")
PANEL = Path("app/api/panel.py")


def test_panel_clears_restored_dom_before_live_refresh():
    js = JS.read_text(encoding="utf-8")

    assert "function clearLiveSnapshot()" in js
    assert "window.addEventListener('pageshow'" in js
    assert "event.persisted" in js
    assert "clearLiveSnapshot();refresh()" in js


def test_panel_document_is_served_no_store():
    source = PANEL.read_text(encoding="utf-8")

    assert '"Cache-Control"' in source
    assert '"no-store, no-cache, "' in source
    assert '"must-revalidate, max-age=0"' in source
    assert '"Pragma"' in source
    assert '"no-cache"' in source
