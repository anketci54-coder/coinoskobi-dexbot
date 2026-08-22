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



def test_vur_kac_uses_existing_math_tp_and_runner_path():
    source = Path(
        "app/paper/manager.py"
    ).read_text(
        encoding="utf-8"
    )

    assert (
        "mathematical_vur_kac_state("
        in source
    )

    assert (
        '"MATHEMATICAL_VUR_KAC_EXIT"'
        in source
    )

    assert (
        "persistent_vur_kac"
        in source
    )

    assert (
        "TP1_CLOSE_FRACTION"
        not in source
    )

    assert (
        "TP2_CLOSE_FRACTION"
        not in source
    )
