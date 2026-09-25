import copy

import pytest

import app.risk.paper_position_sizing as sizing


def plan():
    return {
        'paper_eligible': True, 'sellability_status': 'SELLABILITY_OK',
        'capital': {'available_usdt': 10000., 'entry_amount_usdt': 1000.,
                    'safe_quote_reserve_usd': 1000000.,
                    'liquidity_capacity_source': 'VERIFIED_LP_PROTECTION',
                    'reserve_observation_count': 4,
                    'observed_min_quote_reserve_usd': 1000000.},
        'statistics': {'risk_log_distance': .2, 'second_moment': .04,
                       'tail_risk_fraction': .2},
        'expected': {'known_net_edge_fraction': .1, 'full_net_edge_fraction': .1},
        'cost_model': {'cost_complete': True},
        'market_context': {'opportunity': {'state': 'HOT'}},
    }


@pytest.fixture
def calibrated(monkeypatch):
    monkeypatch.setattr(sizing, '_empirical_outcome_calibration', lambda **kw: {
        'gap_multiplier': 2., 'account_risk_budget_fraction': .01,
        'cost_uncertainty_fraction': .01, 'reason': 'EMPIRICAL_OUTCOME_CALIBRATION',
    })


def test_verified_lp_total_loss_and_capital_scaling(calibrated):
    p = plan()
    p["statistics"]["tail_risk_fraction"] = 1.0
    results = [sizing.calculate_paper_position_size(mathematical_plan=p,
               available_capital_usdt=c) for c in (100., 10000.)]
    for r, capital in zip(results, (100., 10000.)):
        assert 0 < r['entry_amount_usdt'] <= capital * .01
        assert r['tail_loss_fraction'] == 1
        assert r['risk_amount_usdt'] == r['entry_amount_usdt']
        assert r['liquidity_protection_unverified'] is False
    assert results[1]['entry_amount_usdt'] == pytest.approx(100 * results[0]['entry_amount_usdt'])


def test_slots_and_raw_notional_do_not_set_amount(calibrated, monkeypatch):
    amounts = []
    for slots, raw in ((1, 1.), (1000, 9000.)):
        monkeypatch.setattr(sizing, 'MAX_OPEN_PAPER_POSITIONS', slots, raising=False)
        p = plan()
        p['capital']['entry_amount_usdt'] = raw
        amounts.append(sizing.calculate_paper_position_size(mathematical_plan=p)['entry_amount_usdt'])
    assert amounts[0] > 0
    assert amounts[0] == amounts[1]


@pytest.mark.parametrize('change', ['exit', 'hard', 'collapse', 'edge', 'risk', 'precision', 'gas'])
def test_fail_closed(calibrated, change):
    p = plan()
    if change == 'exit': p['capital']['safe_quote_reserve_usd'] = None
    if change == 'hard': p['hard_block'] = True
    if change == 'collapse': p['market_context']['opportunity']['catastrophic_reserve_collapse'] = True
    if change == 'edge': p['expected']['full_net_edge_fraction'] = 0
    if change == 'risk': p['statistics']['second_moment'] = None
    if change == 'precision': p['capital']['safe_quote_reserve_usd'] = 1e-30
    if change == 'gas': p['cost_model']['sell_gas_usd'] = 100
    assert sizing.calculate_paper_position_size(mathematical_plan=p)['entry_amount_usdt'] == 0


def historical_db(path, capital):
    import json
    import sqlite3
    db = sqlite3.connect(path)
    db.execute('''CREATE TABLE paper_trades (
        id INTEGER, created_at TEXT, closed_at TEXT, status TEXT,
        entry_price REAL, entry_amount_usdt REAL, gross_pnl_usdt REAL,
        net_pnl_usdt REAL, mathematical_plan_json TEXT, math_state_json TEXT)''')
    db.execute('INSERT INTO paper_trades VALUES (?,?,?,?,?,?,?,?,?,?)', (
        1, '2026-09-20T00:00:00+00:00', '2026-09-20T01:00:00+00:00',
        'CLOSED', 1., capital / 10, -capital / 100, -capital / 90,
        json.dumps({'capital': {'available_usdt': capital}, 'entry': {'band_low': .95}}), '{}'))
    db.commit()
    db.close()


def test_historical_calibration_is_capital_normalized(tmp_path):
    fractions = []
    amounts = []
    for capital in (100., 10000.):
        path = tmp_path / f'{capital}.db'
        historical_db(path, capital)
        fractions.append(sizing._empirical_outcome_calibration(path)['account_risk_budget_fraction'])
        amounts.append(sizing.calculate_paper_position_size(
            mathematical_plan=plan(), available_capital_usdt=100., db_path=path)['entry_amount_usdt'])
    assert fractions == pytest.approx([1 / 90, 1 / 90])
    assert amounts[0] > 0
    assert amounts[0] == pytest.approx(amounts[1])


@pytest.mark.parametrize('capital_data', [{}, {'available_usdt': 0}, {'available_usdt': 'bad'}, []])
def test_invalid_historical_capital_never_bootstraps(tmp_path, capital_data):
    import json
    import sqlite3
    path = tmp_path / 'invalid.db'
    historical_db(path, 10000.)
    with sqlite3.connect(path) as db:
        db.execute('UPDATE paper_trades SET mathematical_plan_json=?',
                   (json.dumps({'capital': capital_data}),))
    r = sizing.calculate_paper_position_size(mathematical_plan=plan(), db_path=path)
    assert r['entry_amount_usdt'] == 0
    assert 'OUTCOME_CAPITAL_PROVENANCE_INVALID' in r['blockers']


def test_final_costs_charge_uncertainty_on_final_notional(calibrated):
    p = plan()
    p['statistics']['tail_risk_fraction'] = 1.0
    p['cost_model'] = {'cost_complete': False, 'buy_gas_usd': 8.22}
    # Final amount=100, known edge=.1, residual=.01:
    # (100-8.22)*1.1 -100 -100*.01 = -.042.
    r = sizing.calculate_paper_position_size(mathematical_plan=p)
    assert r['entry_amount_usdt'] == 0
    assert 'FIXED_COST_NET_EDGE_NOT_POSITIVE' in r['blockers']


def test_lp_warning_cannot_be_bypassed_by_empirical_exit(calibrated):
    p = plan()
    p['capital']['liquidity_capacity_source'] = 'EMPIRICAL_RESERVE_FLOOR'
    p['blockers'] = ['LP_WITHDRAWAL_PROTECTION_UNVERIFIED']
    result = sizing.calculate_paper_position_size(mathematical_plan=p)
    assert result['entry_amount_usdt'] == 0
    assert 'LP_WITHDRAWAL_PROTECTION_UNVERIFIED' in result['blockers']


@pytest.mark.parametrize('field,value', [('second_moment', .4), ('tail_risk_fraction', .8)])
def test_measured_risk_reduces_bootstrap_size(tmp_path, field, value):
    p = plan()
    before = sizing.calculate_paper_position_size(mathematical_plan=copy.deepcopy(p), db_path=tmp_path / 'missing.db')
    p['statistics'][field] = value
    after = sizing.calculate_paper_position_size(mathematical_plan=p, db_path=tmp_path / 'missing.db')
    assert 0 < after['entry_amount_usdt'] < before['entry_amount_usdt']


def test_hot_observation_never_exceeds_empirical_account_risk_budget(monkeypatch):
    p = plan()
    p["capital"]["entry_amount_usdt"] = 9000.0
    p["statistics"]["prices"] = [1.0, 1.5]
    p["capital"]["liquidity_capacity_source"] = "EMPIRICAL_RESERVE_FLOOR"
    p["blockers"] = ["LP_WITHDRAWAL_PROTECTION_UNVERIFIED"]

    monkeypatch.setattr(sizing, "_empirical_outcome_calibration", lambda **kw: {
        "gap_multiplier": None,
        "account_risk_budget_fraction": .01,
        "cost_uncertainty_fraction": .01,
        "reason": "EMPIRICAL_OUTCOME_CALIBRATION",
        "gap_samples": 0,
        "cost_samples": 1,
        "account_risk_samples": 1,
    })

    result = sizing.calculate_paper_position_size(
        mathematical_plan=p,
        available_capital_usdt=10000.0,
    )

    assert result["sizing_reason"] == "PAPER_HOT_OBSERVATION_BOOTSTRAP"
    assert 0 < result["entry_amount_usdt"] <= 100.0
    assert result["risk_amount_usdt"] == result["entry_amount_usdt"]


def test_hot_observation_without_calibration_is_bounded_discovery(monkeypatch):
    p = plan()
    p["statistics"]["prices"] = [1.0, 1.5]
    p["expected"]["known_net_edge_fraction"] = 0.0
    p["expected"]["full_net_edge_fraction"] = 0.0
    p["cost_model"]["cost_complete"] = False

    monkeypatch.setattr(sizing, "_empirical_outcome_calibration", lambda **kw: {
        "gap_multiplier": None,
        "account_risk_budget_fraction": None,
        "cost_uncertainty_fraction": None,
        "reason": "INSUFFICIENT_HISTORY",
        "gap_samples": 0,
        "cost_samples": 0,
        "account_risk_samples": 0,
    })

    result = sizing.calculate_paper_position_size(
        mathematical_plan=p,
        available_capital_usdt=10000.0,
    )

    assert result["sizing_reason"] == "PAPER_HOT_OBSERVATION_BOOTSTRAP"
    assert 0 < result["entry_amount_usdt"] <= 100.0
    assert result["risk_amount_usdt"] == result["entry_amount_usdt"]
