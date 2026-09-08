from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

JS = (
    ROOT
    / "app"
    / "api"
    / "static"
    / "dex-terminal.js"
).read_text(encoding="utf-8")

HTML = (
    ROOT
    / "app"
    / "api"
    / "static"
    / "index.html"
).read_text(encoding="utf-8")

API = (
    ROOT
    / "app"
    / "api"
    / "panel_manual_paper_v2.py"
).read_text(encoding="utf-8")


def test_manual_paper_buy_is_static_and_visible():
    assert "data-v61-buy" in HTML
    assert "+ MANUEL PAPER AL" in HTML
    assert "MANUEL + OTOMATİK PAPER" in HTML


def test_null_values_are_not_rendered_as_zero():
    assert (
        "value === null || value === undefined || value === ''"
        in JS
    )


def test_radar_uses_operator_language_not_dex_version():
    assert "PİYASA OKUMASI" in HTML
    assert "5DK İŞLEM" in HTML
    assert "plainMarketRead" in JS
    assert "Likidite hızla zayıflıyor" in JS
    assert "Fiyat, hacim ve ilgi güçleniyor" in JS
    assert "Satış baskısı güçleniyor" in JS


def test_manual_sell_carries_preview_guard():
    assert "expected_net_pnl_usdt" in JS
    assert "v61SellPreviews" in JS


def test_backend_refuses_preview_to_close_sign_flip():
    assert "expected_net_pnl_usdt" in API
    assert "sign_flipped" in API
    assert "satış yapılmadı" in API


def test_live_execution_stays_locked():
    assert "LIVE EXECUTION KAPALI" in HTML
    assert '"live_execution": False' in API
    assert '"wallet_authority": False' in API
    assert '"signing_authority": False' in API
