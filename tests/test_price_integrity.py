from types import SimpleNamespace

from app.paper.manager import PaperManager


def test_numeric_only_price_cannot_mutate_paper():
    manager = PaperManager.__new__(PaperManager)
    manager.price = SimpleNamespace(get_price=lambda token: 1 / 770000)
    mutations = []
    manager._process_legacy_position = lambda *args: mutations.append(args)
    position = dict(id=1, token='0x' + '11' * 20, entry_price=1,
                    token_amount=1, current_price=1)
    manager._process_position(position)
    assert mutations == []

import copy
import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.config.contracts import USDT, WBNB
from app.risk.price_integrity import PriceIntegrityGate, observation
from price_integrity_support import V2RPC, TOKEN, POOL, HASH, position, evidence


@pytest.mark.parametrize('reverse', [False, True])
@pytest.mark.parametrize('decimals', [(18, 6), (6, 18), (9, 8)])
def test_oriented_price_reads_both_decimals_at_one_block(reverse, decimals):
    rpc = V2RPC('0.0025', reverse=reverse, token_decimals=decimals[0], usdt_decimals=decimals[1])
    result = PriceIntegrityGate(rpc).evaluate(position(), evidence('0.0025'))
    assert result['state'] == 'VERIFIED_EXTREME'
    assert result['chain_price'] == Decimal('0.0025')
    assert ('decimals', TOKEN) in rpc.calls
    assert ('decimals', USDT.lower()) in rpc.calls
    assert ('getReserves', POOL) in rpc.calls


@pytest.mark.parametrize('price,extreme', [('2', True), ('0.5', True), ('1.999999', False), ('0.500001', False)])
def test_symmetric_trigger_boundary(price, extreme):
    rpc = V2RPC(1)
    gate = PriceIntegrityGate(rpc)
    gate.accept(gate.evaluate(position(), evidence(1)))
    rpc.calls.clear()
    rpc.price = Decimal(price)
    result = gate.evaluate(position(), evidence(price))
    assert result['state'] == ('VERIFIED_EXTREME' if extreme else 'VERIFIED_NORMAL')
    assert bool(rpc.calls) == extreme


@pytest.mark.parametrize('candidate,chain,state', [
    ('1.1', '1', 'VERIFIED_EXTREME'), ('1', '1.1', 'VERIFIED_EXTREME'),
    ('1.100001', '1', 'PRICE_CONFLICT'), ('1', '1.100001', 'PRICE_CONFLICT'),
])
def test_tolerance(candidate, chain, state):
    assert PriceIntegrityGate(V2RPC(chain)).evaluate(position(), evidence(candidate))['state'] == state


@pytest.mark.parametrize('quote', [WBNB, '0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d', '0x'+'ff'*20, None])
def test_unsupported_quotes_never_call_rpc(quote):
    rpc = V2RPC()
    result = PriceIntegrityGate(rpc).evaluate(position(), evidence(quote_token=quote))
    assert result == {'state': 'PRICE_UNVERIFIED', 'reason': 'UNSUPPORTED_QUOTE'}
    assert not rpc.calls


def test_v3_never_calls_rpc():
    rpc = V2RPC()
    result = PriceIntegrityGate(rpc).evaluate(position(dex='pancakeswap_v3'), evidence(dex='pancakeswap_v3'))
    assert result['reason'] == 'UNSUPPORTED_DEX'
    assert not rpc.calls


@pytest.mark.parametrize('failure', ['factory', 'token', 'rpc', 'decimals_none', 'decimals_string', 'decimals_negative', 'zero', 'chain'])
def test_independent_evidence_failures(failure):
    rpc = V2RPC()
    if failure == 'factory': rpc.canonical = '0x'+'99'*20
    if failure == 'token': rpc.token1 = WBNB
    if failure == 'rpc': rpc.fail = True
    if failure == 'decimals_none': rpc.usdt_decimals = None
    if failure == 'decimals_string': rpc.token_decimals = '18'
    if failure == 'decimals_negative': rpc.token_decimals = -1
    if failure == 'zero': rpc.zero = True
    if failure == 'chain': rpc.chain_id = 1
    state = PriceIntegrityGate(rpc).evaluate(position(), evidence())['state']
    assert state == ('PRICE_CONFLICT' if failure in {'factory', 'token', 'chain'} else 'PRICE_UNVERIFIED')


def test_same_token_different_pool_never_reuses_reference():
    rpc = V2RPC()
    gate = PriceIntegrityGate(rpc)
    gate.accept(gate.evaluate(position(), evidence()))
    wrong_pool = '0x'+'99'*20
    result = gate.evaluate(position(pool=wrong_pool), evidence())
    assert result['state'] == 'PRICE_CONFLICT'
    result = gate.evaluate(position(pool=wrong_pool), evidence(pool=wrong_pool))
    assert result['state'] == 'PRICE_CONFLICT'  # factory mismatch, not ordinary movement
    assert len(gate.accepted) == 1


@pytest.mark.parametrize('factor', [300000, 770000])
def test_incident_scale_mismatch_has_zero_mutation(factor):
    rpc = V2RPC()
    gate = PriceIntegrityGate(rpc)
    gate.accept(gate.evaluate(position(), evidence()))
    original_references = copy.deepcopy(gate.accepted)
    pos = position()
    before = copy.deepcopy(pos)
    manager = PaperManager.__new__(PaperManager)
    manager.price_integrity = gate
    manager.price = SimpleNamespace(get_observation=lambda _: evidence(1/factor))
    manager._process_legacy_position = lambda *args: pytest.fail('strategy mutation reached')
    result = manager._process_position(pos)
    assert result['state'] == 'PRICE_CONFLICT'
    assert pos == before
    assert gate.accepted == original_references


def test_rejected_cache_price_cannot_rebase_anchor(monkeypatch):
    import app.risk.price_integrity as integrity
    from app.dex.open_position_hot_path import HotPositionWSSBridge
    monkeypatch.setattr(integrity, 'w3', V2RPC(1))
    row = evidence(1/770000)
    pipeline = SimpleNamespace(cache=SimpleNamespace(all=lambda: [row]),
                               manager=SimpleNamespace(db=SimpleNamespace(open_positions=lambda: [position()])))
    bridge = HotPositionWSSBridge()
    bridge._open_pairs = {POOL}
    bridge._latest_ratio[POOL] = 1
    bridge._anchor_ratio[POOL] = 2
    bridge._anchor_price[POOL] = 1
    assert bridge.anchor_from_cache(pipeline)['anchored'] == 0
    assert bridge._anchor_ratio[POOL] == 2
    assert bridge._anchor_price[POOL] == 1


def test_confirmed_real_collapse_preserves_existing_stop_loss():
    from test_paper_manager import make_manager, make_position
    pos = make_position()
    pos.update(pool=POOL, dex='pancakeswap_v2')
    rpc = V2RPC(1, token=pos['token'])
    gate = PriceIntegrityGate(rpc)
    gate.accept(gate.evaluate(pos, evidence(1, base_token=pos['token'])))
    price = 0.0000013
    rpc.price = Decimal(str(price))
    manager = make_manager(price, pos)
    manager.price_integrity = gate
    manager.price = SimpleNamespace(get_observation=lambda _: evidence(price, base_token=pos['token']))
    manager.process()
    assert manager.db.closed[0][1]['exit_price'] == price
    assert manager.db.closed[0][1]['close_reason'] == 'PERSISTED_STOP_LOSS'


def test_stale_unknown_and_wrong_identity_fail_closed():
    for changes in [dict(source='unknown'), dict(observed_at=None),
                    dict(observed_at=(datetime.now(timezone.utc)-timedelta(minutes=1)).isoformat()),
                    dict(base_token='0x'+'99'*20), dict(pool='0x'+'99'*20)]:
        assert PriceIntegrityGate(V2RPC()).evaluate(position(), evidence(**changes))['state'].startswith('PRICE_')


def test_old_evidence_cannot_bless_new_numeric_write():
    assert observation(dict(pool=POOL, price_usd=2, price_evidence_json=json.dumps(evidence(1)))) == {}


def test_wss_cannot_verify_itself_without_http():
    rpc = V2RPC()
    rpc.fail = True
    result = PriceIntegrityGate(rpc).evaluate(position(), evidence(source='pancakeswap_v2_sync', block_hash=HASH, block_number=123))
    assert result['state'] == 'PRICE_UNVERIFIED'


@pytest.mark.parametrize("trade_type", ["NORMAL", "VUR_KAC"])
def test_price_conflict_cannot_reach_any_paper_strategy_or_mutate_pnl(trade_type):
    """A conflicting market price is observation-only: no close, PnL, or extrema mutation."""
    rpc = V2RPC(1)
    gate = PriceIntegrityGate(rpc)
    pos = position()
    pos["trade_type"] = trade_type

    # Establish an accepted baseline that agrees across both sources.
    gate.accept(gate.evaluate(pos, evidence(1)))

    # Keep the trusted on-chain source at 1.0 while the runtime observation
    # jumps by >10%; this must be rejected before any strategy handler runs.
    rpc.price = Decimal("1")
    before = copy.deepcopy(pos)
    manager = PaperManager.__new__(PaperManager)
    manager.price_integrity = gate
    manager.price = SimpleNamespace(
        get_observation=lambda _: evidence("1.100001")
    )
    manager._process_normal_math_position = (
        lambda *args: pytest.fail("NORMAL strategy mutation reached")
    )
    manager._process_vur_kac_position = (
        lambda *args: pytest.fail("VUR_KAC strategy mutation reached")
    )
    manager._process_legacy_position = (
        lambda *args: pytest.fail("legacy strategy mutation reached")
    )

    result = manager._process_position(pos)

    assert result["state"] == "PRICE_CONFLICT"
    assert result["reason"] == "ONCHAIN_PRICE_DISAGREEMENT"
    assert pos == before
    assert gate.accepted

