from app.paper.manager import PaperManager


class FakePrice:
    def __init__(self, price):
        self.price = price

    def get_price(self, token):
        return self.price


class FakeDB:
    def __init__(self, position):
        self.position = position
        self.updated = []
        self.closed = []

    def open_positions(self):
        return [dict(self.position)]

    def update_position(
        self,
        trade_id,
        values,
    ):
        self.updated.append(
            (
                trade_id,
                dict(values),
            )
        )

    def close_position(
        self,
        trade_id,
        values=None,
    ):
        self.closed.append(
            (
                trade_id,
                dict(values or {}),
            )
        )
        return True


def position(
    *,
    highest=1.0,
    sl_price=0.90,
):
    return {
        "id": 1,
        "token": "0xtoken",
        "entry_price": 1.0,
        "current_price": 1.0,
        "highest_price": highest,
        "lowest_price": 1.0,
        "tp_price": 1.20,
        "sl_price": sl_price,
        "amount_bnb": 1.0,
        "token_amount": 1.0,
        "gas_buy": 0.0,
        "gas_sell": 0.0,
        "swap_fee": 0.0,
        "buy_tax": 0.0,
        "sell_tax": 0.0,
        "slippage": 0.0,
        "mev": 0.0,
        "created_at": (
            "2026-08-17T00:00:00+00:00"
        ),
        "closed_at": None,
    }


def evidence(
    **signal_overrides,
):
    signal = {
        "freshness": "FRESH",
        "coverage": 1.0,
        "liquidity_health": "HEALTHY",
        "flow_momentum": 0.80,
        "flow_acceleration": 0.50,
        "price_impact_health": "HEALTHY",
    }

    signal.update(
        signal_overrides
    )

    return {
        "signal_bundle": signal,
        "trend_health": "STRONG",
        "exit_pressure": "NONE",
        "hard_block": False,
        "sellability": "SELLABILITY_OK",
    }


def manager(
    *,
    price,
    pos=None,
    runtime_evidence=None,
):
    m = PaperManager.__new__(
        PaperManager
    )

    m.db = FakeDB(
        pos or position()
    )

    m.price = FakePrice(
        price
    )

    m.learning_feed = None
    m._learning_replay_after_id = 0
    m.hybrid_exit_evidence = (
        runtime_evidence
    )

    return m


def test_no_evidence_runs_always_on_adaptive_protection():
    m = manager(
        price=1.30,
        runtime_evidence=None,
    )

    result = m.process()

    assert m.db.closed == []

    data = result[0]["data"]

    assert data["action"] == "HOLD"

    assert (
        data["hybrid_exit"]["bound"]
        is True
    )

    assert (
        data["hybrid_exit"][
            "protection_price"
        ]
        is not None
    )

    assert (
        data["hybrid_exit"][
            "protection_price"
        ]
        > 0.90
    )


def test_hybrid_runner_replaces_fixed_take_profit_when_bound():
    m = manager(
        price=1.30,
        pos=position(
            highest=1.30,
        ),
        runtime_evidence=evidence(),
    )

    result = m.process()

    assert m.db.closed == []

    data = result[0]["data"]

    assert data["action"] == "HOLD"

    assert (
        data["reason"]
        == "POSITIVE_EDGE_HEALTHY"
    )

    assert (
        data["hybrid_exit"]["bound"]
        is True
    )

    assert (
        data["hybrid_exit"]["action"]
        == "RUNNER"
    )

    assert (
        data["hybrid_exit"][
            "runner_active"
        ]
        is True
    )


def test_hybrid_static_sl_still_closes():
    m = manager(
        price=0.89,
        pos=position(
            highest=1.20,
            sl_price=0.90,
        ),
        runtime_evidence=evidence(),
    )

    result = m.process()

    assert len(m.db.closed) == 1

    assert (
        m.db.closed[0][1][
            "close_reason"
        ]
        == "PERSISTED_STOP_LOSS"
    )

    assert (
        result[0]["data"][
            "reason"
        ]
        == "PERSISTED_STOP_LOSS"
    )

    assert (
        result[0]["data"][
            "hybrid_exit"
        ]["bound"]
        is False
    )


def test_hybrid_hard_block_dominates_health():
    runtime = evidence()
    runtime["hard_block"] = True

    m = manager(
        price=1.30,
        pos=position(
            highest=1.30,
        ),
        runtime_evidence=runtime,
    )

    result = m.process()

    assert len(m.db.closed) == 1

    assert (
        m.db.closed[0][1][
            "close_reason"
        ]
        == "HARD_BLOCK"
    )

    assert (
        result[0]["data"][
            "hybrid_exit"
        ]["action"]
        == "EMERGENCY_EXIT"
    )


def test_stale_bad_intelligence_is_neutral_not_fake_exit():
    runtime = evidence(
        freshness="STALE",
        liquidity_health="CRITICAL",
        flow_momentum=-1.0,
        flow_acceleration=-1.0,
        price_impact_health="CRITICAL",
    )

    runtime[
        "trend_health"
    ] = "BREAK"

    runtime[
        "exit_pressure"
    ] = "HIGH"

    m = manager(
        price=1.02,
        pos=position(
            highest=1.02,
        ),
        runtime_evidence=runtime,
    )

    result = m.process()

    assert m.db.closed == []

    assert (
        result[0]["data"]["reason"]
        != "SEVERE_MARKET_DETERIORATION"
    )


def test_hybrid_runtime_binding_has_zero_live_authority():
    m = manager(
        price=1.10,
        pos=position(
            highest=1.10,
        ),
        runtime_evidence=evidence(),
    )

    result = m.process()

    hybrid = result[0][
        "data"
    ]["hybrid_exit"]

    assert (
        hybrid["decision_authority"]
        is False
    )

    assert (
        hybrid["live_authority"]
        is False
    )

    assert (
        hybrid["wallet_authority"]
        is False
    )

    assert (
        hybrid["execution_authority"]
        is False
    )
