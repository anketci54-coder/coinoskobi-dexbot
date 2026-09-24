"""Historical 52/58 magnitudes, with isolated SQLite and contract-shaped RPC.

The verified cases use the currently supported USDT quote, not the historical
WBNB pair. Only external RPC is faked; price validation, stops and accounting
execute production code. No historical database or network is accessed.
"""
import copy
import json
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.config.contracts import WBNB
from app.paper.cache_price import CachePrice
from app.paper.database import PaperDatabase
from app.paper.manager import PaperManager
from app.paper.schema import (
    OBSERVATIONS_SCHEMA, PAPER_TRADES_SCHEMA, REALIZATIONS_SCHEMA,
)
from app.risk.price_integrity import PriceIntegrityGate
from price_integrity_support import HASH, POOL, TOKEN, V2RPC, evidence


INCIDENTS = [
    dict(id=52, entry=7.035693661886157e-05, peak=0.00011231836126677397,
         stop=0.00010021074615143754, collapse=1.7334020867540104e-10,
         initial_tokens=561303.6424480883, sold_tokens=546588.5751577705,
         entry_amount=39.59477565436379, sold_basis=38.55676388312736,
         tp1_price=9.321915811191217e-05, fraction=0.9737841229282979,
         gross=50.952526809797, net=50.821068996171064),
    dict(id=58, entry=0.0003049977227800851, peak=0.0004619291872889031,
         stop=0.00043376231807124884, collapse=2.8430679874075983e-09,
         initial_tokens=83950.25121807908, sold_tokens=81085.98889066507,
         entry_amount=25.672933022197785, sold_basis=24.797009319495768,
         tp1_price=0.0004205, fraction=0.9658814323262301,
         gross=34.09665832852466, net=34.00739871525899),
]


@pytest.fixture(params=INCIDENTS, ids=['trade52', 'trade58'])
def replay(request, monkeypatch):
    incident = request.param
    conn = sqlite3.connect(':memory:')
    conn.row_factory = sqlite3.Row
    for schema in (PAPER_TRADES_SCHEMA, OBSERVATIONS_SCHEMA, REALIZATIONS_SCHEMA):
        conn.execute(schema)
    db = object.__new__(PaperDatabase)  # Do not initialize the production singleton.
    db.conn = conn
    db._db_lock = threading.RLock()
    pos = dict(
        id=incident['id'], token=TOKEN, pool=POOL, dex='pancakeswap_v2',
        status='OPEN', trade_type='NORMAL', trade_policy='NORMAL',
        entry_price=incident['entry'], current_price=incident['peak'],
        highest_price=incident['peak'], lowest_price=incident['entry'],
        sl_price=incident['stop'], tp_price=incident['tp1_price'],
        entry_amount_usdt=incident['entry_amount'],
        initial_token_amount=incident['initial_tokens'],
        token_amount=incident['initial_tokens'] - incident['sold_tokens'],
        remaining_cost_basis_usdt=incident['entry_amount'] - incident['sold_basis'],
        realized_gross_proceeds_usdt=incident['gross'],
        realized_proceeds_usdt=incident['net'],
        realized_pnl_usdt=incident['net'] - incident['sold_basis'],
        tp1_done=1, tp2_done=1, runner_active=1,
        mathematical_plan_json=json.dumps(dict(
            contract='mathematical_trade_plan',
            cost_model=dict(sell_retention_known=0.9975, sell_gas_usd=0.004),
        )),
        math_state_json=json.dumps(dict(tp3_runner_stop=incident['stop'])),
    )
    conn.execute(
        f"INSERT INTO paper_trades ({','.join(pos)}) VALUES ({','.join('?' for _ in pos)})",
        list(pos.values()),
    )
    conn.execute(
        'INSERT INTO paper_realizations (position_id, stage, observed_at, price, '
        'token_amount, close_fraction, gross_proceeds_usdt, net_proceeds_usdt, '
        'sold_cost_basis_usdt, realized_pnl_usdt) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
        (pos['id'], 'TP1', '2026-09-20T00:00:00+00:00', incident['tp1_price'],
         incident['sold_tokens'], incident['fraction'], incident['gross'],
         incident['net'], incident['sold_basis'], pos['realized_pnl_usdt']),
    )
    db.record_price_observation(pos['id'], incident['peak'])
    cache = CachePrice(':memory:')
    cache.db.execute('CREATE TABLE gecko_pool_cache '
                     '(pool TEXT, price_usd REAL, price_evidence_json TEXT)')
    cache.db.execute('INSERT INTO gecko_pool_cache VALUES (?, ?, ?)',
                     (POOL, incident['peak'], json.dumps(evidence(incident['peak']))))
    manager = PaperManager.__new__(PaperManager)
    manager.db, manager.price = db, cache
    manager.hybrid_exit_evidence = None
    # Isolate post-close telemetry; keep observation, stop and realization real.
    monkeypatch.setattr(manager, '_observe_learning_outcome', lambda *a: None)
    monkeypatch.setattr(manager, '_runtime_phase15h_sell_evidence', lambda **kw: None)
    yield incident, manager
    cache.db.close()
    conn.close()


def publish(manager, incident, **changes):
    value = evidence(incident['collapse'], **changes)
    manager.price.db.execute(
        'UPDATE gecko_pool_cache SET price_usd=?, price_evidence_json=?',
        (incident['collapse'], json.dumps(value)),
    )


@pytest.mark.parametrize('warm', [False, True], ids=['restart', 'accepted_reference'])
@pytest.mark.parametrize('failure', ['rpc', 'conflict', 'stale', 'missing', 'wss_rpc', 'historical_quote'])
def test_unverified_collapse_never_mutates_paper(replay, monkeypatch, warm, failure):
    incident, manager = replay
    pos = manager.db.open_positions()[0]
    rpc = V2RPC(incident['peak'])
    gate = manager.price_integrity = PriceIntegrityGate(rpc)
    if warm:
        verified = gate.evaluate(pos, evidence(incident['peak']))
        assert verified['state'] == 'VERIFIED_EXTREME'
        gate.accept(verified)
    before_refs = copy.deepcopy(gate.accepted)
    before_pos = copy.deepcopy(pos)
    before_db = list(manager.db.conn.iterdump())
    changes_before = manager.db.conn.total_changes
    changes = {}
    if failure in {'rpc', 'wss_rpc'}:
        rpc.fail = True
    if failure == 'wss_rpc':
        changes.update(source='pancakeswap_v2_sync', block_number=123, block_hash=HASH)
    if failure == 'stale':
        changes['observed_at'] = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    if failure == 'historical_quote':
        changes['quote_token'] = WBNB
    # Prove neither static nor runner stop evaluation can even be entered.
    monkeypatch.setattr(manager, '_process_normal_math_position',
                        lambda *a: pytest.fail('unverified tick reached stop evaluation'))
    for _ in range(3):
        publish(manager, incident, **changes)
        if failure == 'missing':
            manager.price.db.execute('UPDATE gecko_pool_cache SET price_evidence_json=NULL')
        result = manager._process_position(pos)
        assert result['state'] == ('PRICE_CONFLICT' if failure == 'conflict' else 'PRICE_UNVERIFIED')
        assert pos == before_pos
        assert gate.accepted == before_refs
        assert manager.db.conn.total_changes == changes_before
        assert list(manager.db.conn.iterdump()) == before_db


@pytest.mark.parametrize('reverse', [False, True], ids=['token0', 'token1'])
@pytest.mark.parametrize('decimals', [(18, 6), (6, 18), (9, 8)])
@pytest.mark.parametrize('source', ['dexscreener', 'pancakeswap_v2_sync'])
def test_independently_verified_collapse_closes_only_residual(replay, reverse, decimals, source):
    incident, manager = replay
    pos = manager.db.open_positions()[0]
    rpc = V2RPC(incident['peak'], reverse=reverse,
                token_decimals=decimals[0], usdt_decimals=decimals[1])
    gate = manager.price_integrity = PriceIntegrityGate(rpc)
    baseline = gate.evaluate(pos, evidence(incident['peak']))
    assert baseline['state'] == 'VERIFIED_EXTREME'
    gate.accept(baseline)
    rpc.price = Decimal(str(incident['collapse']))
    publish(manager, incident, source=source, block_number=123, block_hash=HASH)
    tp1_before = [tuple(r) for r in manager.db.conn.execute('SELECT * FROM paper_realizations')]
    result = manager._process_position(pos)
    assert result['data']['action'] == 'CLOSE'
    row = dict(manager.db.conn.execute('SELECT * FROM paper_trades').fetchone())
    assert row['status'] == 'CLOSED'
    assert row['close_reason'] == 'NORMAL_STOP_LOSS'
    assert row['current_price'] == row['exit_price'] == row['lowest_price'] == incident['collapse']
    assert row['highest_price'] == incident['peak']
    assert row['token_amount'] == row['remaining_cost_basis_usdt'] == 0
    assert row['realized_proceeds_usdt'] == pytest.approx(incident['net'])
    expected_pnl = incident['net'] - incident['entry_amount']
    assert row['net_pnl_usdt'] == row['net_pnl'] == row['realized_pnl_usdt'] == pytest.approx(expected_pnl)
    assert row['roi'] == pytest.approx(expected_pnl / incident['entry_amount'])
    assert row['realized_gross_proceeds_usdt'] == pytest.approx(
        incident['gross'] + pos['token_amount'] * incident['collapse'])
    assert [tuple(r) for r in manager.db.conn.execute('SELECT * FROM paper_realizations')] == tp1_before
    assert manager.db.price_observations(pos['id']) == [incident['peak'], incident['collapse']]
    accepted = next(iter(gate.accepted.values()))
    assert accepted['state'] == 'VERIFIED_EXTREME'
    # The fake uses 10**24 raw token units and floors the quote reserve to an
    # integer. Assert that exact quantized price, including at tiny magnitudes.
    quantum = Decimal(10) ** (decimals[0] - decimals[1] - 24)
    expected_chain_price = (Decimal(str(incident['collapse'])) // quantum) * quantum
    assert accepted['chain_price'] == expected_chain_price
