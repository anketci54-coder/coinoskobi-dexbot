import pytest
from app.strategy.engine import StrategyEngine


@pytest.fixture
def engine():
    return StrategyEngine()


# ---------------------------------------------------------------------------
# Helpers: build minimal input dicts
# ---------------------------------------------------------------------------

def _token(name="TokenX", symbol="TKX"):
    return {"name": name, "symbol": symbol, "decimals": 18, "supply": 1_000_000}


def _pair(exists=True, quote_ok=True):
    return {"exists": exists, "quote_ok": quote_ok}


def _risk(
    code_size=6000,
    owner=False,
    renounce_owner=False,
    mint=False,
    pause=False,
    blacklist=False,
    max_tx=False,
    max_wallet=False,
):
    return {
        "code_size": code_size,
        "owner": owner,
        "renounce_owner": renounce_owner,
        "mint": mint,
        "pause": pause,
        "blacklist": blacklist,
        "max_tx": max_tx,
        "max_wallet": max_wallet,
    }


# ---------------------------------------------------------------------------
# Envelope contract
# ---------------------------------------------------------------------------

class TestStrategyEnvelopeContract:

    def test_top_level_keys_present(self, engine):
        result = engine.evaluate(_token(), _pair(), _risk())
        assert "success"  in result
        assert "source"   in result
        assert "data"     in result

    def test_success_is_true(self, engine):
        result = engine.evaluate(_token(), _pair(), _risk())
        assert result["success"] is True

    def test_source_is_strategy(self, engine):
        result = engine.evaluate(_token(), _pair(), _risk())
        assert result["source"] == "strategy"

    def test_data_keys_present(self, engine):
        data = engine.evaluate(_token(), _pair(), _risk())["data"]
        for key in ("decision", "score", "reasons", "risk", "paper_trade"):
            assert key in data, f"missing key: {key}"

    def test_reasons_is_list(self, engine):
        data = engine.evaluate(_token(), _pair(), _risk())["data"]
        assert isinstance(data["reasons"], list)

    def test_score_is_int_or_float(self, engine):
        data = engine.evaluate(_token(), _pair(), _risk())["data"]
        assert isinstance(data["score"], (int, float))

    def test_paper_trade_is_bool(self, engine):
        data = engine.evaluate(_token(), _pair(), _risk())["data"]
        assert isinstance(data["paper_trade"], bool)


# ---------------------------------------------------------------------------
# Decision thresholds
# ---------------------------------------------------------------------------

class TestStrategyDecision:

    def test_paper_buy_when_score_gte_90(self, engine):
        # Max possible score path: name+symbol+pair+quote+large_code+no_owner+no_mint+no_pause+no_blacklist+no_maxtx+no_maxwallet
        # 5+5+20+15+20+10+15+5+5+5+5 = 110
        data = engine.evaluate(
            _token(),
            _pair(exists=True, quote_ok=True),
            _risk(code_size=6000, owner=False, mint=False, pause=False, blacklist=False, max_tx=False, max_wallet=False),
        )["data"]
        assert data["decision"] == "PAPER_BUY"
        assert data["score"] >= 90

    def test_watch_when_score_between_70_and_89(self, engine):
        # Remove pair (lose 20+15=35) from the max 110 -> 75 -> WATCH
        data = engine.evaluate(
            _token(),
            _pair(exists=False, quote_ok=False),
            _risk(code_size=6000, owner=False, mint=False, pause=False, blacklist=False, max_tx=False, max_wallet=False),
        )["data"]
        assert data["decision"] == "WATCH"
        assert 70 <= data["score"] <= 89

    def test_reject_when_score_lt_70(self, engine):
        # Worst case: mint penalty (-30), blacklist (-15), pause (-10), no pair, tiny code
        data = engine.evaluate(
            _token(name="", symbol=""),
            _pair(exists=False, quote_ok=False),
            _risk(code_size=0, owner=True, renounce_owner=False, mint=True, pause=True, blacklist=True),
        )["data"]
        assert data["decision"] == "REJECT"
        assert data["score"] < 70

    def test_paper_trade_true_only_for_paper_buy(self, engine):
        buy = engine.evaluate(
            _token(),
            _pair(exists=True, quote_ok=True),
            _risk(code_size=6000),
        )["data"]
        assert buy["paper_trade"] is True

    def test_paper_trade_false_for_watch(self, engine):
        watch = engine.evaluate(
            _token(),
            _pair(exists=False, quote_ok=False),
            _risk(code_size=6000),
        )["data"]
        assert watch["paper_trade"] is False

    def test_paper_trade_false_for_reject(self, engine):
        reject = engine.evaluate(
            _token(name="", symbol=""),
            _pair(exists=False, quote_ok=False),
            _risk(code_size=0, mint=True, pause=True, blacklist=True),
        )["data"]
        assert reject["paper_trade"] is False


# ---------------------------------------------------------------------------
# Risk level
# ---------------------------------------------------------------------------

class TestStrategyRiskLevel:

    def test_risk_low_when_score_gte_90(self, engine):
        data = engine.evaluate(_token(), _pair(), _risk())["data"]
        assert data["risk"] == "LOW"

    def test_risk_medium_when_score_between_70_89(self, engine):
        data = engine.evaluate(
            _token(),
            _pair(exists=False, quote_ok=False),
            _risk(code_size=6000),
        )["data"]
        assert data["risk"] == "MEDIUM"

    def test_risk_high_when_score_lt_70(self, engine):
        data = engine.evaluate(
            _token(name="", symbol=""),
            _pair(exists=False, quote_ok=False),
            _risk(code_size=0, mint=True, pause=True, blacklist=True),
        )["data"]
        assert data["risk"] == "HIGH"


# ---------------------------------------------------------------------------
# Scoring: individual signal contributions
# ---------------------------------------------------------------------------

class TestStrategyScoringSignals:

    def _score(self, engine, token=None, pair=None, risk=None):
        return engine.evaluate(
            token or _token(name="", symbol=""),
            pair  or _pair(exists=False, quote_ok=False),
            risk  or _risk(code_size=0),
        )["data"]["score"]

    def test_valid_name_adds_5(self, engine):
        base  = self._score(engine, token=_token(name="",    symbol=""))
        named = self._score(engine, token=_token(name="Tok", symbol=""))
        assert named - base == 5

    def test_valid_symbol_adds_5(self, engine):
        base = self._score(engine, token=_token(name="", symbol=""))
        sym  = self._score(engine, token=_token(name="", symbol="TKX"))
        assert sym - base == 5

    def test_pair_exists_adds_20(self, engine):
        base = self._score(engine, pair=_pair(exists=False, quote_ok=False))
        p    = self._score(engine, pair=_pair(exists=True,  quote_ok=False))
        assert p - base == 20

    def test_quote_ok_adds_15(self, engine):
        base = self._score(engine, pair=_pair(exists=False, quote_ok=False))
        q    = self._score(engine, pair=_pair(exists=False, quote_ok=True))
        assert q - base == 15

    def test_large_code_adds_20(self, engine):
        base  = self._score(engine, risk=_risk(code_size=0))
        large = self._score(engine, risk=_risk(code_size=6000))
        assert large - base == 20

    def test_medium_code_adds_15(self, engine):
        base   = self._score(engine, risk=_risk(code_size=0))
        medium = self._score(engine, risk=_risk(code_size=3000))
        assert medium - base == 15

    def test_small_code_adds_10(self, engine):
        base  = self._score(engine, risk=_risk(code_size=0))
        small = self._score(engine, risk=_risk(code_size=1500))
        assert small - base == 10

    def test_no_owner_adds_10(self, engine):
        base     = self._score(engine, risk=_risk(code_size=0, owner=True,  renounce_owner=False))
        no_owner = self._score(engine, risk=_risk(code_size=0, owner=False, renounce_owner=False))
        assert no_owner - base == 10

    def test_renounce_owner_adds_8(self, engine):
        base     = self._score(engine, risk=_risk(code_size=0, owner=True, renounce_owner=False))
        renounce = self._score(engine, risk=_risk(code_size=0, owner=True, renounce_owner=True))
        assert renounce - base == 8

    def test_mint_subtracts_30(self, engine):
        base = self._score(engine, risk=_risk(code_size=0, mint=False))
        mint = self._score(engine, risk=_risk(code_size=0, mint=True))
        assert base - mint == 30 + 15  # no-mint adds 15; mint loses 30 -> diff = 45

    def test_pause_subtracts_10(self, engine):
        base  = self._score(engine, risk=_risk(code_size=0, pause=False))
        pause = self._score(engine, risk=_risk(code_size=0, pause=True))
        assert base - pause == 5 + 10  # no-pause adds 5; pause loses 10 -> diff = 15

    def test_blacklist_subtracts_15(self, engine):
        base = self._score(engine, risk=_risk(code_size=0, blacklist=False))
        bl   = self._score(engine, risk=_risk(code_size=0, blacklist=True))
        assert base - bl == 5 + 15  # no-blacklist adds 5; blacklist loses 15 -> diff = 20

    def test_deterministic_same_input_same_output(self, engine):
        t, p, r = _token(), _pair(), _risk()
        r1 = engine.evaluate(t, p, r)
        r2 = engine.evaluate(t, p, r)
        assert r1 == r2
