from pathlib import Path


def test_auto_runtime_selects_canonical_trade_type():
    engine = Path(
        "app/pipeline/engine.py"
    ).read_text(encoding="utf-8")

    assert "selected_trade_type = (" in engine
    assert 'else "NORMAL"' in engine
    assert (
        '"trade_policy": "VUR_KAC"'
        not in engine
    )
    assert (
        '"trade_policy": selected_trade_type'
        in engine
    )
    assert '"control_mode": "AUTO"' in engine
    assert '"trade_type": (' in engine


def test_engine_passes_trade_type_into_plan():
    engine = Path(
        "app/pipeline/engine.py"
    ).read_text(encoding="utf-8")

    assert "trade_type=(" in engine
    assert "selected_trade_type" in engine
