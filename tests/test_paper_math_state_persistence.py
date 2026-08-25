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
        '"trade_policy": "VUR_KAC"'
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
            "PAIR_ONCHAIN",
        ) in engine_module._RUNTIME_PRICE_HISTORY

        assert (
            "0xabc",
            "0xpool2",
            "PAIR_ONCHAIN",
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
        "PAIR_ONCHAIN",
    ) in keys



def test_new_paper_positions_default_to_vur_kac_policy():
    source = Path(
        "app/pipeline/engine.py"
    ).read_text(
        encoding="utf-8"
    )

    # One value is persisted in opening context,
    # the other is the canonical paper trade row.
    assert (
        source.count(
            '"trade_policy": "VUR_KAC"'
        )
        == 2
    )

    assert (
        '"trade_policy": "NORMAL"'
        not in source
    )
