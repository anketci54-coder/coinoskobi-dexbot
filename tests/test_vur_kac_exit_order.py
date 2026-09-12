from pathlib import Path


def test_vur_kac_partial_realization_precedes_trend_floor_close():
    source = Path("app/paper/manager.py").read_text()
    method = source.split(
        "    def _process_vur_kac_position(",
        1,
    )[1].split(
        "    def _process_legacy_position(",
        1,
    )[0]

    hard_exit = method.index('"HARD_SAFETY_EXIT"')
    partial_realization = method.index("if stage is not None:")
    trend_floor = method.index('"MATHEMATICAL_TREND_FLOOR"')

    assert hard_exit < partial_realization < trend_floor
