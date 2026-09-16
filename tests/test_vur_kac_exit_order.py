from pathlib import Path


def test_vur_kac_full_exit_preserves_hard_safety_precedence():
    source = Path("app/paper/manager.py").read_text()
    method = source.split(
        "    def _process_vur_kac_position(",
        1,
    )[1].split(
        "    def _process_legacy_position(",
        1,
    )[0]

    hard_exit = method.index('"HARD_SAFETY_EXIT"')
    trend_floor = method.index('"MATHEMATICAL_TREND_FLOOR"')

    assert "if stage is not None:" not in method
    assert hard_exit < trend_floor
