import pytest
from unittest.mock import MagicMock, patch

from app.paper.manager import PaperManager
from app.config.trading import TAKE_PROFIT, STOP_LOSS, TRAILING_STOP_FACTOR


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_pos(
    token="0xABCDEF",
    entry_price=1.0,
    current_price=1.0,
    highest_price=1.0,
    lowest_price=1.0,
    amount_bnb=0.01,
    token_amount=100.0,
    gas_buy=0.00018,
    gas_sell=0.00018,
    swap_fee=0.25,
    buy_tax=0.0,
    sell_tax=0.0,
    slippage=0.5,
    mev=0.2,
    created_at="2026-01-01T00:00:00",
    closed_at=None,
    pos_id=1,
):
    return {
        "id":            pos_id,
        "token":         token,
        "entry_price":   entry_price,
        "current_price": current_price,
        "highest_price": highest_price,
        "lowest_price":  lowest_price,
        "amount_bnb":    amount_bnb,
        "token_amount":  token_amount,
        "gas_buy":       gas_buy,
        "gas_sell":      gas_sell,
        "swap_fee":      swap_fee,
        "buy_tax":       buy_tax,
        "sell_tax":      sell_tax,
        "slippage":      slippage,
        "mev":           mev,
        "created_at":    created_at,
        "closed_at":     closed_at,
    }


@pytest.fixture
def manager():
    """PaperManager with PaperDatabase and CachePrice fully mocked."""
    with patch("app.paper.manager.PaperDatabase") as MockDB, \
         patch("app.paper.manager.CachePrice")    as MockPrice:

        mock_db    = MagicMock()
        mock_price = MagicMock()

        MockDB.return_value    = mock_db
        MockPrice.return_value = mock_price

        m = PaperManager()
        m._mock_db    = mock_db
        m._mock_price = mock_price

        yield m


# ---------------------------------------------------------------------------
# Envelope contract
# ---------------------------------------------------------------------------

class TestPaperManagerEnvelopeContract:

    def test_returns_list(self, manager):
        manager._mock_db.open_positions.return_value = []
        result = manager.process()
        assert isinstance(result, list)

    def test_empty_positions_returns_empty_list(self, manager):
        manager._mock_db.open_positions.return_value = []
        assert manager.process() == []

    def test_result_envelope_keys(self, manager):
        pos = _make_pos(entry_price=1.0, token_amount=100.0, amount_bnb=0.01)
        manager._mock_db.open_positions.return_value = [pos]
        manager._mock_price.get_price.return_value   = 1.0

        results = manager.process()
        assert len(results) == 1

        r = results[0]
        assert r["success"] is True
        assert r["source"]  == "paper"

        for key in ("action", "token", "entry_price", "current_price",
                    "roi", "status", "opened_at", "closed_at", "reason"):
            assert key in r["data"], f"missing key: {key}"


# ---------------------------------------------------------------------------
# Exit logic: TAKE_PROFIT
# ---------------------------------------------------------------------------

class TestPaperManagerTakeProfit:

    def test_take_profit_triggers(self, manager):
        # current 1.30, entry 1.0, amount_bnb 0.01, token_amount 100 -> gross = 100*1.30 - 0.01*100... wait
        # token_amount = amount_bnb / entry = 0.01 / 1.0 = 0.01; current_value = 0.01 * 1.30 = 0.013
        # gross = 0.013 - 0.01 = 0.003; fees ~ small; roi > 0.20 -> TAKE_PROFIT
        pos = _make_pos(
            entry_price=1.0,
            highest_price=1.30,
            amount_bnb=0.01,
            token_amount=0.01,  # 0.01 BNB / 1.0 = 0.01 tokens
            gas_buy=0.0, gas_sell=0.0,
            swap_fee=0.0, buy_tax=0.0, sell_tax=0.0, slippage=0.0, mev=0.0,
        )
        manager._mock_db.open_positions.return_value = [pos]
        manager._mock_price.get_price.return_value   = 1.30

        results = manager.process()
        assert results[0]["data"]["reason"] == "TAKE_PROFIT"
        assert results[0]["data"]["action"] == "CLOSE"
        assert results[0]["data"]["status"] == "CLOSED"
        manager._mock_db.close_position.assert_called_once()

    def test_take_profit_not_triggered_below_threshold(self, manager):
        # roi ~0.10, below TAKE_PROFIT 0.20
        pos = _make_pos(
            entry_price=1.0,
            highest_price=1.10,
            amount_bnb=0.01,
            token_amount=0.01,
            gas_buy=0.0, gas_sell=0.0,
            swap_fee=0.0, buy_tax=0.0, sell_tax=0.0, slippage=0.0, mev=0.0,
        )
        manager._mock_db.open_positions.return_value = [pos]
        manager._mock_price.get_price.return_value   = 1.10

        results = manager.process()
        assert results[0]["data"]["action"] == "HOLD"
        manager._mock_db.close_position.assert_not_called()


# ---------------------------------------------------------------------------
# Exit logic: STOP_LOSS
# ---------------------------------------------------------------------------

class TestPaperManagerStopLoss:

    def test_stop_loss_triggers(self, manager):
        # entry 1.0, current 0.85 -> roi = -0.15 < -0.10 -> STOP_LOSS
        pos = _make_pos(
            entry_price=1.0,
            highest_price=1.0,
            amount_bnb=0.01,
            token_amount=0.01,
            gas_buy=0.0, gas_sell=0.0,
            swap_fee=0.0, buy_tax=0.0, sell_tax=0.0, slippage=0.0, mev=0.0,
        )
        manager._mock_db.open_positions.return_value = [pos]
        manager._mock_price.get_price.return_value   = 0.85

        results = manager.process()
        assert results[0]["data"]["reason"] == "STOP_LOSS"
        assert results[0]["data"]["action"] == "CLOSE"
        manager._mock_db.close_position.assert_called_once()

    def test_stop_loss_not_triggered_above_threshold(self, manager):
        # entry 1.0, current 0.95 -> roi = -0.05 > -0.10 -> HOLD
        pos = _make_pos(
            entry_price=1.0,
            highest_price=1.0,
            amount_bnb=0.01,
            token_amount=0.01,
            gas_buy=0.0, gas_sell=0.0,
            swap_fee=0.0, buy_tax=0.0, sell_tax=0.0, slippage=0.0, mev=0.0,
        )
        manager._mock_db.open_positions.return_value = [pos]
        manager._mock_price.get_price.return_value   = 0.95

        results = manager.process()
        assert results[0]["data"]["action"] == "HOLD"
        manager._mock_db.close_position.assert_not_called()


# ---------------------------------------------------------------------------
# Exit logic: TRAILING_STOP
# ---------------------------------------------------------------------------

class TestPaperManagerTrailingStop:

    def test_trailing_stop_triggers(self, manager):
        # highest=1.50, current=1.50*0.90=1.35 (at the trailing boundary), entry=1.0
        # current(1.34) <= trailing_price(1.35) AND highest(1.50) > entry(1.0) -> TRAILING_STOP
        pos = _make_pos(
            entry_price=1.0,
            highest_price=1.50,
            amount_bnb=0.01,
            token_amount=0.01,
            gas_buy=0.0, gas_sell=0.0,
            swap_fee=0.0, buy_tax=0.0, sell_tax=0.0, slippage=0.0, mev=0.0,
        )
        manager._mock_db.open_positions.return_value = [pos]
        manager._mock_price.get_price.return_value   = 1.34  # below 1.50 * 0.90 = 1.35

        results = manager.process()
        assert results[0]["data"]["reason"] == "TRAILING_STOP"
        assert results[0]["data"]["action"] == "CLOSE"
        manager._mock_db.close_position.assert_called_once()

    def test_trailing_stop_not_triggered_when_highest_equals_entry(self, manager):
        # highest == entry -> condition `highest > entry` is False -> no trailing stop
        pos = _make_pos(
            entry_price=1.0,
            highest_price=1.0,
            amount_bnb=0.01,
            token_amount=0.01,
            gas_buy=0.0, gas_sell=0.0,
            swap_fee=0.0, buy_tax=0.0, sell_tax=0.0, slippage=0.0, mev=0.0,
        )
        manager._mock_db.open_positions.return_value = [pos]
        manager._mock_price.get_price.return_value   = 0.85  # would trigger SL, not trailing

        results = manager.process()
        assert results[0]["data"]["reason"] != "TRAILING_STOP"


# ---------------------------------------------------------------------------
# Fee calculation
# ---------------------------------------------------------------------------

class TestPaperManagerFeeCalculation:

    def test_zero_fees_roi_equals_gross_ratio(self, manager):
        # With all fees zero: roi = (current_value - amount_bnb) / amount_bnb
        entry        = 1.0
        token_amount = 0.01  # amount_bnb / entry
        amount_bnb   = 0.01
        current      = 1.20

        expected_gross = token_amount * current - amount_bnb  # 0.012 - 0.01 = 0.002
        expected_roi   = expected_gross / amount_bnb           # 0.20

        pos = _make_pos(
            entry_price=entry,
            amount_bnb=amount_bnb,
            token_amount=token_amount,
            highest_price=current,
            gas_buy=0.0, gas_sell=0.0,
            swap_fee=0.0, buy_tax=0.0, sell_tax=0.0, slippage=0.0, mev=0.0,
        )
        manager._mock_db.open_positions.return_value = [pos]
        manager._mock_price.get_price.return_value   = current

        results = manager.process()
        actual_roi = results[0]["data"]["roi"]
        assert abs(actual_roi - expected_roi) < 1e-10

    def test_skip_position_with_zero_entry(self, manager):
        pos = _make_pos(entry_price=0.0)
        manager._mock_db.open_positions.return_value = [pos]
        manager._mock_price.get_price.return_value   = 1.0
        assert manager.process() == []

    def test_skip_position_with_zero_token_amount(self, manager):
        pos = _make_pos(entry_price=1.0, token_amount=0.0)
        manager._mock_db.open_positions.return_value = [pos]
        manager._mock_price.get_price.return_value   = 1.0
        assert manager.process() == []

    def test_skip_position_when_price_fetch_fails(self, manager):
        pos = _make_pos()
        manager._mock_db.open_positions.return_value = [pos]
        manager._mock_price.get_price.side_effect    = RuntimeError("cache miss")
        assert manager.process() == []
