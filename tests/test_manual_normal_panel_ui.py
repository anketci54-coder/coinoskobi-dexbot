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
        "payload.sl_price=sl"
        in js
    )

    assert (
        "payload.tp1_price=tp1"
        in js
    )

    assert (
        "!sameNumber(\n        sl,\n        systemSl"
        in js
    )

    assert (
        "!sameNumber(\n        tp1,\n        systemTp1"
        in js
    )

    assert (
        "PLAN YENİDEN HESAPLANMALI"
        in js
    )

    assert (
        "Yatırım miktarı preview sonrasında değişti."
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


def test_manual_normal_unchanged_system_levels_are_not_overrides():
    js = Path(
        "app/api/static/dex-terminal.js"
    ).read_text(
        encoding="utf-8"
    )

    assert "preview.system_sl_price" in js
    assert "preview.system_tp1_price" in js

    payload_start = js.index(
        "const payload={",
        js.index("async function confirmBuy()"),
    )
    payload_end = js.index(
        "    };",
        payload_start,
    )
    payload_block = js[
        payload_start:payload_end
    ]

    assert "sl_price:" not in payload_block
    assert "tp1_price:" not in payload_block


def test_vur_kac_position_does_not_render_normal_tp_lifecycle():
    js = Path(
        "app/api/static/dex-terminal.js"
    ).read_text(
        encoding="utf-8"
    )

    assert "const isVurKac=" in js

    assert (
        "const tp1State=isVurKac"
        in js
    )

    assert (
        "const tp2State=isVurKac"
        in js
    )

    assert (
        "const tp3State=isVurKac"
        in js
    )
