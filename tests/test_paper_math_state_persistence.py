from pathlib import Path


def test_normal_tp_state_is_persisted_before_tp2_or_runner_actions():
    source = Path(
        "app/paper/manager.py"
    ).read_text(
        encoding="utf-8"
    )

    normal_start = source.index(
        "def _process_normal_math_position("
    )

    vur_start = source.index(
        "def _process_vur_kac_position("
    )

    normal_source = source[
        normal_start:vur_start
    ]

    tp1_index = normal_source.index(
        '"tp1_required_fraction"'
    )

    tp2_index = normal_source.index(
        '"tp2_required_fraction"'
    )

    tp2_apply_index = normal_source.index(
        'stage="TP2"'
    )

    runner_index = normal_source.index(
        '"tp3_mode"'
    )

    assert tp1_index < tp2_index
    assert tp2_index < tp2_apply_index
    assert tp2_apply_index < runner_index

    assert (
        '"math_state_json"'
        in normal_source
    )


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
        not in normal_source
    )

    assert (
        '"NORMAL_RISK_NEUTRALIZATION"'
        in normal_source
    )

    assert (
        '"NORMAL_PRINCIPAL_RECOVERY"'
        in normal_source
    )

    assert (
        '"NORMAL_TP3_TREND_EXIT"'
        in normal_source
    )

    assert (
        'lifecycle_trade_type('
        in manager
    )

    assert (
        'trade_type == "VUR_KAC"'
        in manager
    )

    assert (
        '"trade_policy": selected_trade_type'
        in engine
    )

    assert (
        'else "NORMAL"'
        in engine
    )

    assert (
        '"trade_type": ('
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



def test_vur_kac_entry_shadow_uses_existing_momentum_semantics():
    from app.pipeline.engine import (
        _vur_kac_entry_signal,
    )

    ready = _vur_kac_entry_signal(
        price_series=[
            1.0,
            1.01,
            1.03,
        ],
        signal_bundle={
            "freshness": "FRESH",
            "coverage": 1.0,
            "flow_momentum": 0.25,
            "flow_acceleration": 0.10,
        },
    )

    assert ready["ready"] is True
    assert (
        ready["reason"]
        == "VUR_KAC_ENTRY_SIGNAL_READY"
    )
    assert (
        ready["trade_policy_candidate"]
        == "VUR_KAC"
    )
    assert ready["shadow_only"] is True
    assert ready["paper_authority"] is False
    assert ready["live_authority"] is False
    assert ready["wallet_authority"] is False
    assert ready["execution_authority"] is False

    weakening = _vur_kac_entry_signal(
        price_series=[
            1.0,
            1.03,
            1.04,
        ],
        signal_bundle={
            "freshness": "FRESH",
            "coverage": 1.0,
            "flow_momentum": 0.25,
            "flow_acceleration": 0.10,
        },
    )

    assert weakening["ready"] is False
    assert (
        weakening["reason"]
        == "VUR_KAC_PRICE_ACCELERATION_WEAKENING"
    )

    stale = _vur_kac_entry_signal(
        price_series=[
            1.0,
            1.01,
            1.03,
        ],
        signal_bundle={
            "freshness": "STALE",
            "coverage": 1.0,
            "flow_momentum": 0.25,
            "flow_acceleration": 0.10,
        },
    )

    assert stale["ready"] is False
    assert (
        stale["reason"]
        == "VUR_KAC_FLOW_EVIDENCE_NOT_READY"
    )



def test_runtime_math_price_history_isolated_by_pool():
    from app.pipeline import engine as engine_module

    engine_module._RUNTIME_PRICE_HISTORY.clear()

    try:
        first = engine_module._runtime_math_evidence(
            token_address="0xabc",
            pool="0xpool1",
            price=1.1,
            upstream_price_series=[
                1.0,
                1.1,
            ],
            price_series_source="PAIR_RUNTIME_ONCHAIN",
            exit_evidence={},
            lp_evidence={},
            market_context={},
            sellability_data={},
        )

        second = engine_module._runtime_math_evidence(
            token_address="0xabc",
            pool="0xpool2",
            price=11.0,
            upstream_price_series=[
                10.0,
                11.0,
            ],
            price_series_source="PAIR_RUNTIME_ONCHAIN",
            exit_evidence={},
            lp_evidence={},
            market_context={},
            sellability_data={},
        )

        assert first["price_series"] == [
            1.0,
            1.1,
        ]

        assert second["price_series"] == [
            10.0,
            11.0,
        ]

        assert len(
            engine_module._RUNTIME_PRICE_HISTORY
        ) == 2

        assert (
            "0xabc",
            "0xpool1",
            "PAIR_RUNTIME_ONCHAIN",
        ) in engine_module._RUNTIME_PRICE_HISTORY

        assert (
            "0xabc",
            "0xpool2",
            "PAIR_RUNTIME_ONCHAIN",
        ) in engine_module._RUNTIME_PRICE_HISTORY

    finally:
        engine_module._RUNTIME_PRICE_HISTORY.clear()



def test_runtime_math_history_isolates_cache_from_pair_onchain_source():
    from app.pipeline import engine as engine_module

    engine_module._RUNTIME_PRICE_HISTORY.clear()

    common = {
        "token_address": "0xtoken",
        "pool": "0xpool",
        "exit_evidence": {},
        "lp_evidence": {},
        "market_context": {},
        "sellability_data": {},
    }

    cache_result = engine_module._runtime_math_evidence(
        **common,
        price=5.0e-5,
        upstream_price_series=[],
        price_series_source="TOKEN_CACHE",
    )

    assert cache_result["price_series"] == [
        5.0e-5
    ]

    onchain_series = [
        2.40e-9,
        2.41e-9,
        2.42e-9,
    ]

    onchain_result = engine_module._runtime_math_evidence(
        **common,
        price=2.42e-9,
        upstream_price_series=onchain_series,
        price_series_source="PAIR_RUNTIME_ONCHAIN",
    )

    assert onchain_result["price_series"] == (
        onchain_series
    )

    # The earlier token-cache price must never appear
    # inside the pair-specific onchain return history.
    assert 5.0e-5 not in (
        onchain_result["price_series"]
    )

    keys = set(
        engine_module._RUNTIME_PRICE_HISTORY
    )

    assert (
        "0xtoken",
        "0xpool",
        "TOKEN_CACHE",
    ) in keys

    assert (
        "0xtoken",
        "0xpool",
        "PAIR_RUNTIME_ONCHAIN",
    ) in keys



def test_runtime_math_history_separates_block_and_runtime_pair_sources():
    from app.pipeline import engine as engine_module

    engine_module._RUNTIME_PRICE_HISTORY.clear()

    common = {
        "token_address": "0xtoken",
        "pool": "0xpool",
        "exit_evidence": {},
        "lp_evidence": {},
        "market_context": {},
        "sellability_data": {},
    }

    try:
        block = engine_module._runtime_math_evidence(
            **common,
            price=1.1,
            upstream_price_series=[1.0, 1.1],
            price_series_source="PAIR_BLOCK_HISTORY",
        )

        runtime = engine_module._runtime_math_evidence(
            **common,
            price=2.1,
            upstream_price_series=[2.0, 2.1],
            price_series_source="PAIR_RUNTIME_ONCHAIN",
        )

        assert block["price_series"] == [1.0, 1.1]
        assert runtime["price_series"] == [2.0, 2.1]

        keys = set(engine_module._RUNTIME_PRICE_HISTORY)

        assert (
            "0xtoken",
            "0xpool",
            "PAIR_BLOCK_HISTORY",
        ) in keys

        assert (
            "0xtoken",
            "0xpool",
            "PAIR_RUNTIME_ONCHAIN",
        ) in keys
    finally:
        engine_module._RUNTIME_PRICE_HISTORY.clear()


def test_new_auto_paper_positions_use_selected_trade_type():
    source = Path(
        "app/pipeline/engine.py"
    ).read_text(
        encoding="utf-8"
    )

    assert (
        source.count(
            '"trade_policy": selected_trade_type'
        )
        == 2
    )

    assert (
        '"trade_policy": "VUR_KAC"'
        not in source
    )

    assert (
        'selected_trade_type = ('
        in source
    )

    assert (
        'else "NORMAL"'
        in source
    )

    assert (
        '"control_mode": "AUTO"'
        in source
    )

    assert (
        '"trade_type": ('
        in source
    )

    assert (
        '"trade_policy": "NORMAL"'
        not in source
    )
