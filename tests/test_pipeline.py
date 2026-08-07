import pytest
from unittest.mock import MagicMock, patch

from app.pipeline.engine import PipelineEngine


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_token_result():
    return {
        "success": True, "source": "token",
        "data": {"name": "TokenX", "symbol": "TKX", "decimals": 18, "supply": 1_000_000},
    }


@pytest.fixture
def mock_pair_result():
    return {
        "success": True, "source": "pair",
        "data": {"exists": True, "quote_ok": True, "pair": "0xPAIR",
                 "token0": "0xA", "token1": "0xB", "reserve0": 1000, "reserve1": 2000},
    }


@pytest.fixture
def mock_risk_result():
    return {
        "success": True, "source": "risk",
        "data": {"code_size": 6000, "owner": False, "renounce_owner": False,
                 "mint": False, "pause": False, "blacklist": False,
                 "max_tx": False, "max_wallet": False},
    }


@pytest.fixture
def pipeline(mock_token_result, mock_pair_result, mock_risk_result):
    """PipelineEngine with all external dependencies mocked."""
    with patch("app.pipeline.engine.token_analyze") as mock_ta, \
         patch("app.pipeline.engine.pair_analyze")  as mock_pa, \
         patch("app.pipeline.engine.risk_analyze")  as mock_ra, \
         patch("app.pipeline.engine.PaperDatabase") as MockDB,  \
         patch("app.pipeline.engine.CachePrice")    as MockPrice:

        mock_ta.return_value = mock_token_result
        mock_pa.return_value = mock_pair_result
        mock_ra.return_value = mock_risk_result

        mock_db    = MagicMock()
        mock_price = MagicMock()
        MockDB.return_value    = mock_db
        MockPrice.return_value = mock_price

        mock_db.has_open_position.return_value = False
        mock_price.get_price.return_value       = 1.0

        p = PipelineEngine()
        p._mock_db    = mock_db
        p._mock_price = mock_price

        yield p


TOKEN = "0x000000000000000000000000000000000000dEaD"


# ---------------------------------------------------------------------------
# Envelope contract
# ---------------------------------------------------------------------------

class TestPipelineEnvelopeContract:

    def test_top_level_keys(self, pipeline):
        result = pipeline.run(TOKEN)
        for key in ("success", "source", "data"):
            assert key in result

    def test_success_is_true(self, pipeline):
        assert pipeline.run(TOKEN)["success"] is True

    def test_source_is_pipeline(self, pipeline):
        assert pipeline.run(TOKEN)["source"] == "pipeline"

    def test_data_keys(self, pipeline):
        data = pipeline.run(TOKEN)["data"]
        for key in ("token", "pair", "risk", "strategy", "paper"):
            assert key in data, f"missing key: {key}"

    def test_strategy_data_keys(self, pipeline):
        strategy = pipeline.run(TOKEN)["data"]["strategy"]
        for key in ("decision", "score", "risk", "paper_trade", "reasons"):
            assert key in strategy

    def test_deterministic(self, pipeline):
        r1 = pipeline.run(TOKEN)
        r2 = pipeline.run(TOKEN)
        assert r1 == r2


# ---------------------------------------------------------------------------
# Paper BUY path
# ---------------------------------------------------------------------------

class TestPipelinePaperBuy:

    def test_paper_buy_inserts_position(self, pipeline):
        pipeline._mock_db.has_open_position.return_value = False
        pipeline._mock_price.get_price.return_value       = 1.0

        result = pipeline.run(TOKEN)

        paper = result["data"]["paper"]
        assert paper["action"] == "PAPER_BUY"
        pipeline._mock_db.insert.assert_called_once()

    def test_paper_buy_skipped_when_open_position_exists(self, pipeline):
        pipeline._mock_db.has_open_position.return_value = True

        result = pipeline.run(TOKEN)

        paper = result["data"]["paper"]
        assert paper["action"]  == "SKIP"
        assert paper["reason"] == "OPEN_POSITION_EXISTS"
        pipeline._mock_db.insert.assert_not_called()

    def test_paper_buy_skipped_when_price_unavailable(self, pipeline):
        pipeline._mock_db.has_open_position.return_value = False
        pipeline._mock_price.get_price.side_effect        = RuntimeError("no price")

        result = pipeline.run(TOKEN)

        paper = result["data"]["paper"]
        assert paper["action"] == "SKIP"
        assert paper["reason"] == "PRICE_UNAVAILABLE"
        pipeline._mock_db.insert.assert_not_called()

    def test_paper_buy_skipped_when_price_zero(self, pipeline):
        pipeline._mock_db.has_open_position.return_value = False
        pipeline._mock_price.get_price.return_value       = 0.0

        result = pipeline.run(TOKEN)

        paper = result["data"]["paper"]
        assert paper["action"] == "SKIP"
        assert paper["reason"] == "PRICE_UNAVAILABLE"

    def test_paper_buy_envelope_fields(self, pipeline):
        pipeline._mock_db.has_open_position.return_value = False
        pipeline._mock_price.get_price.return_value       = 2.0

        paper = pipeline.run(TOKEN)["data"]["paper"]
        assert paper["token"]       == TOKEN
        assert paper["entry_price"] == 2.0
        assert paper["action"]      == "PAPER_BUY"


# ---------------------------------------------------------------------------
# Non-BUY decisions
# ---------------------------------------------------------------------------

class TestPipelineNonBuyDecisions:

    def _pipeline_with_decision(self, decision, mock_token_result,
                                mock_pair_result, mock_risk_result):
        """Build a pipeline that forces a specific strategy decision."""
        strategy_result = {
            "success": True, "source": "strategy",
            "data": {
                "decision": decision,
                "score": 50,
                "risk": "HIGH",
                "paper_trade": False,
                "reasons": [],
            },
        }
        with patch("app.pipeline.engine.token_analyze", return_value=mock_token_result), \
             patch("app.pipeline.engine.pair_analyze",  return_value=mock_pair_result),  \
             patch("app.pipeline.engine.risk_analyze",  return_value=mock_risk_result),  \
             patch("app.pipeline.engine._strategy") as mock_strat,                       \
             patch("app.pipeline.engine.PaperDatabase") as MockDB,                       \
             patch("app.pipeline.engine.CachePrice"):

            mock_strat.evaluate.return_value = strategy_result
            MockDB.return_value = MagicMock()

            p = PipelineEngine()
            return p.run(TOKEN)

    def test_watch_decision_sets_action_watch(self, mock_token_result,
                                               mock_pair_result, mock_risk_result):
        result = self._pipeline_with_decision(
            "WATCH", mock_token_result, mock_pair_result, mock_risk_result
        )
        assert result["data"]["paper"]["action"] == "WATCH"

    def test_reject_decision_sets_action_reject(self, mock_token_result,
                                                 mock_pair_result, mock_risk_result):
        result = self._pipeline_with_decision(
            "REJECT", mock_token_result, mock_pair_result, mock_risk_result
        )
        assert result["data"]["paper"]["action"] == "REJECT"
