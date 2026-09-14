from pathlib import Path


def test_manual_normal_buy_uses_preview_before_confirm():
    js = Path(
        "app/api/static/dex-terminal.js"
    ).read_text(
        encoding="utf-8"
    )

    assert "data-v61-buy-preview" in js
    assert "async function previewBuy()" in js

    assert (
        "'/api/manual-paper/preview-v2'"
        in js
    )

    assert (
        "SİSTEM PLANINI HESAPLA"
        in js
    )

    assert (
        "confirmation-time fresh quote"
        in js
    )

    assert (
        "async function confirmBuy()"
        in js
    )

    assert (
        "sl_price:Number.isFinite(sl)"
        in js
    )

    assert (
        "tp1_price:Number.isFinite(tp1)"
        in js
    )


def test_manual_normal_position_table_shows_lifecycle():
    html = Path(
        "app/api/static/index.html"
    ).read_text(
        encoding="utf-8"
    )

    js = Path(
        "app/api/static/dex-terminal.js"
    ).read_text(
        encoding="utf-8"
    )

    for label in (
        "<th>ENTRY</th>",
        "<th>CURRENT</th>",
        "<th>SL</th>",
        "<th>TP1</th>",
        "<th>TP2</th>",
        "<th>TP3 / TREND</th>",
    ):
        assert label in html

    assert "row.tp1_done" in js
    assert "row.tp2_done" in js
    assert "row.runner_active" in js

    assert "ANA PARA ALINDI" in js
    assert "TREND AKTİF" in js

    assert (
        "data-preview-position"
        in js
    )


def test_manual_panel_keeps_paper_only_language():
    js = Path(
        "app/api/static/dex-terminal.js"
    ).read_text(
        encoding="utf-8"
    )

    assert (
        "Live emir, wallet signing "
        "veya zincir işlemi yoktur."
        in js
    )

    assert (
        "Risk Gate ve sellability "
        "bypass edilemez."
        in js
    )
