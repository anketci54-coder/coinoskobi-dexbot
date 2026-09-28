from pathlib import Path


def test_history_shows_invested_amount_and_net_gain_loss():
    html = Path("app/api/static/index.html").read_text()
    js = Path("app/api/static/dex-terminal.js").read_text()

    assert "YATIRILAN" in html
    assert "KAZANÇ / KAYIP" in html
    assert "row.entry_amount_usdt" in js
    assert "row.net_pnl_usdt" in js


def test_radar_all_filter_is_hot_warm_only():
    js = Path("app/api/static/dex-terminal.js").read_text()

    assert "['HOT','WARM'].includes" in js
    assert "radarFilter==='ALL'?active" in js
    assert "HOT/WARM" in js
