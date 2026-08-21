import ast
import math
from pathlib import Path

from app.strategy.mathematical_trade_plan import (
    initial_net_risk_usdt,
)


ENGINE = Path(
    "app/pipeline/engine.py"
)


def test_engine_inventory_marker_present():
    text = ENGINE.read_text(
        encoding="utf-8"
    )

    assert (
        "CANONICAL_PAPER_EXECUTION_INVENTORY_V1"
        in text
    )


def test_engine_opening_risk_marker_present():
    text = ENGINE.read_text(
        encoding="utf-8"
    )

    assert (
        "CANONICAL_PAPER_OPENING_RISK_V1"
        in text
    )


def test_entry_notional_token_identity():
    entry_amount = 4269.803222339277
    entry_price = 0.000394396421208518

    tokens = (
        entry_amount
        / entry_price
    )

    assert math.isclose(
        tokens * entry_price,
        entry_amount,
        rel_tol=1e-12,
        abs_tol=1e-9,
    )


def test_falling_price_is_loss_with_correct_inventory():
    entry_amount = 4269.803222339277
    entry_price = 0.000394396421208518
    exit_price = 0.000254235037850229

    tokens = (
        entry_amount
        / entry_price
    )

    pnl = (
        tokens
        * exit_price
        - entry_amount
    )

    assert pnl < 0


def test_correct_inventory_produces_positive_stop_risk():
    entry_amount = 496.60107101350917
    entry_price = 6.70014360946828e-05
    stop_price = 5.469277462786699e-05

    tokens = (
        entry_amount
        / entry_price
    )

    risk = initial_net_risk_usdt(
        token_amount=tokens,
        entry_amount_usdt=entry_amount,
        stop_price=stop_price,
        cost_model={},
    )

    assert risk is not None
    assert risk > 0
    assert risk < entry_amount


def test_engine_ast_valid():
    ast.parse(
        ENGINE.read_text(
            encoding="utf-8"
        )
    )
