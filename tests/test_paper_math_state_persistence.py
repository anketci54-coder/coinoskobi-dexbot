from pathlib import Path


def test_tp_search_state_is_reserialized_before_realization_gate():
    source = Path(
        "app/paper/manager.py"
    ).read_text(
        encoding="utf-8"
    )

    refresh = (
        'common_update[\n'
        '            "math_state_json"\n'
        '        ] = json.dumps(\n'
        '            state,\n'
        '            sort_keys=True,\n'
        '        )'
    )

    assert source.count(refresh) == 1

    refresh_index = source.index(
        refresh
    )

    tp1_index = source.index(
        '"tp1_required_fraction"'
    )

    tp2_index = source.index(
        '"tp2_required_fraction"'
    )

    stage_index = source.index(
        "        if stage is not None:",
        refresh_index,
    )

    assert tp1_index < refresh_index
    assert tp2_index < refresh_index
    assert refresh_index < stage_index


def test_no_fixed_tp_fraction_was_added():
    source = Path(
        "app/paper/manager.py"
    ).read_text(
        encoding="utf-8"
    )

    assert (
        "TP1_CLOSE_FRACTION"
        not in source
    )

    assert (
        "TP2_CLOSE_FRACTION"
        not in source
    )

    assert (
        "TP3_CLOSE_FRACTION"
        not in source
    )



def test_normal_and_vur_kac_have_separate_policy_paths():
    manager = Path(
        "app/paper/manager.py"
    ).read_text(
        encoding="utf-8"
    )

    engine = Path(
        "app/pipeline/engine.py"
    ).read_text(
        encoding="utf-8"
    )

    assert (
        "def _process_normal_math_position("
        in manager
    )

    assert (
        "def _process_vur_kac_position("
        in manager
    )

    normal_start = manager.index(
        "def _process_normal_math_position("
    )

    vur_start = manager.index(
        "def _process_vur_kac_position("
    )

    normal_source = manager[
        normal_start:vur_start
    ]

    assert (
        "vur_kac"
        not in normal_source.lower()
    )

    assert (
        '"NORMAL_STOP_LOSS"'
        in normal_source
    )

    assert (
        '"NORMAL_TAKE_PROFIT"'
        in normal_source
    )

    assert (
        'policy == "VUR_KAC"'
        in manager
    )

    assert (
        '"trade_policy": "NORMAL"'
        in engine
    )

    assert (
        "mathematical_vur_kac_state("
        in manager
    )

    assert (
        '"MATHEMATICAL_VUR_KAC_EXIT"'
        in manager
    )
