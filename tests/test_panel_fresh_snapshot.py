from pathlib import Path


HTML = Path("app/api/static/index.html")
PANEL = Path("app/api/panel.py")


def test_panel_clears_restored_dom_before_live_refresh():
    html = HTML.read_text(encoding="utf-8")

    assert "function clearLiveSnapshot()" in html
    assert "window.addEventListener('pageshow'" in html
    assert "event.persisted" in html
    assert "clearLiveSnapshot();refresh()" in html


def test_panel_document_is_served_no_store():
    source = PANEL.read_text(encoding="utf-8")

    assert '"Cache-Control"' in source
    assert '"no-store, no-cache, "' in source
    assert '"must-revalidate, max-age=0"' in source
    assert '"Pragma"' in source
    assert '"no-cache"' in source
