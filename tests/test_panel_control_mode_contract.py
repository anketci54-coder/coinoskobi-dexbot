from pathlib import Path


def test_control_mode_api_contract_present():
    source = Path(
        "app/api/panel_manual_paper_v2.py"
    ).read_text(
        encoding="utf-8"
    )

    assert (
        '@app.get("/api/paper-control-mode")'
        in source
    )

    assert (
        '@app.post("/api/paper-control-mode")'
        in source
    )

    assert (
        '"existing_positions_changed": False'
        in source
    )

    assert (
        '"vur_kac_manual_enabled": False'
        in source
    )


def test_engine_and_database_gate_only_new_auto_entry():
    engine = Path(
        "app/pipeline/engine.py"
    ).read_text(
        encoding="utf-8"
    )

    database = Path(
        "app/paper/database.py"
    ).read_text(
        encoding="utf-8"
    )

    manager = Path(
        "app/paper/manager.py"
    ).read_text(
        encoding="utf-8"
    )

    assert (
        "CONTROL_MODE_MANUAL"
        in engine
    )

    assert (
        "get_control_mode_from_connection("
        in database
    )

    assert (
        '== "MANUAL"'
        in database
    )

    assert (
        '"control_mode"'
        in database
    )

    assert (
        "get_control_mode("
        not in manager
    )

    assert (
        "get_control_mode_from_connection("
        not in manager
    )
