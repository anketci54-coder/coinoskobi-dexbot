from pathlib import Path

JS = Path("app/api/static/dex-terminal.js").read_text()


def test_unverified_open_valuation_is_visible_but_not_rendered_as_pnl():
    assert "unvalued_open_count" in JS
    assert "valuation_state" in JS
    assert "DEĞERLENEMEDİ" in JS
    assert "POZİSYON DEĞERLEME DIŞI" in JS
    assert "valuationUnverified" in JS
