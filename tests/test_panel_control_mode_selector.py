from pathlib import Path


def test_auto_manual_selector_present():
    html = Path(
        "app/api/static/index.html"
    ).read_text(
        encoding="utf-8"
    )

    assert 'data-control-mode="AUTO"' in html
    assert 'data-control-mode="MANUAL"' in html
    assert "dex-terminal.js?v=4" in html


def test_selector_reads_and_writes_control_mode_api():
    js = Path(
        "app/api/static/dex-terminal.js"
    ).read_text(
        encoding="utf-8"
    )

    assert "loadPaperControlMode" in js
    assert "setPaperControlMode" in js
    assert "'/api/paper-control-mode'" in js
    assert "method:'POST'" in js
    assert "control_mode:normalized" in js


def test_selector_preserves_existing_position_contract():
    js = Path(
        "app/api/static/dex-terminal.js"
    ).read_text(
        encoding="utf-8"
    )

    assert (
        "Açık pozisyonların mevcut planları"
        in js
    )

    assert (
        "OTOMATİK YENİ GİRİŞ · KAPALI"
        in js
    )


def test_selector_does_not_touch_manager():
    manager = Path(
        "app/paper/manager.py"
    ).read_text(
        encoding="utf-8"
    )

    assert "paperControlMode" not in manager
    assert "setPaperControlMode" not in manager
