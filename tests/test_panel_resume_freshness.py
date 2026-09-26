from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "app/api/static/dex-terminal.js").read_text()
HTML = (ROOT / "app/api/static/index.html").read_text()


def test_panel_refreshes_immediately_when_tab_resumes():
    assert "document.addEventListener('visibilitychange',refreshOnResume)" in JS
    assert "window.addEventListener('focus',refreshOnResume)" in JS
    assert "window.addEventListener('pageshow',refreshOnResume)" in JS


def test_main_equity_card_has_single_writer():
    assert JS.count("document.getElementById('metricEquity')") == 0
    assert JS.count("$('metricEquity').textContent=money(s.equity)") == 1


def test_panel_script_cache_bust_version_updated():
    assert "/static/dex-terminal.js?v=5" in HTML
