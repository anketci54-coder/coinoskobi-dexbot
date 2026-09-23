"""Fail-closed PAPER V1: BSC Pancake V2 TOKEN/USDT, USDT=USD policy.

Provider observations never constitute independent extreme-move evidence.
References are process-local; restart deliberately requires a new HTTP proof.
"""
import json
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, localcontext

from app.chains.bsc import w3
from app.config.contracts import USDT
from app.dex.pair_membership import verify_pair_membership
from app.risk.exit_feasibility import PAIR_ABI, ERC20_ABI
from web3 import Web3

EXTREME_RATIO = Decimal('2.0')
MAX_DIVERGENCE = Decimal('1.10')
MAX_AGE_SECONDS = 30
MAX_SKEW_SECONDS = 10
SOURCES = {'geckoterminal', 'dexscreener', 'pancakeswap_v2_sync'}


def address(value):
    value = str(value or '').lower().removeprefix('bsc_')
    return value if Web3.is_address(value) else None


def number(value):
    try:
        result = Decimal(str(value))
        return result if result.is_finite() and result > 0 else None
    except (InvalidOperation, ValueError, TypeError):
        return None


def timestamp(value):
    try:
        result = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        return result.replace(tzinfo=timezone.utc) if result.tzinfo is None else result
    except (ValueError, TypeError):
        return None


def context(position):
    value = position.get('opening_context_json') or {}
    try:
        return json.loads(value) if isinstance(value, str) else dict(value)
    except (TypeError, ValueError):
        return {}


def observation(row):
    """Never let an old evidence envelope bless a later numeric-only write."""
    row = dict(row or {})
    raw = row.get('price_evidence_json')
    if raw:
        try:
            evidence = json.loads(raw)
        except (TypeError, ValueError):
            return {}
        if (number(evidence.get('price_usd')) != number(row.get('price_usd'))
                or address(evidence.get('pool')) != address(row.get('pool'))):
            return {}
        return evidence
    return {key: row.get(key) for key in (
        'chain', 'pool', 'base_token', 'token', 'quote_token', 'dex',
        'source', 'observed_at', 'price_usd', 'block_number', 'block_hash',
    )}


def verdict(state, reason, **kwargs):
    return dict(state=state, reason=reason, **kwargs)


class PriceIntegrityGate:
    def __init__(self, client=None):
        self.client = client if client is not None else w3
        self.accepted = {}

    def evaluate(self, position, evidence):
        try:
            return self._evaluate(position, dict(evidence or {}))
        except Exception:
            # No cached/provider fallback on contract, RPC, or parsing failure.
            return verdict('PRICE_UNVERIFIED', 'INDEPENDENT_EVIDENCE_UNAVAILABLE')

    def _evaluate(self, position, evidence):
        raw = context(position).get('raw_signals') or {}
        pool = address(position.get('pool') or raw.get('pool'))
        token = address(position.get('token'))
        dex = str(position.get('dex') or raw.get('dex') or '').lower()
        if dex not in {'pancakeswap_v2', 'pancakeswap-v2'}:
            return verdict('PRICE_UNVERIFIED', 'UNSUPPORTED_DEX')
        quote = address(evidence.get('quote_token'))
        expected_quote = address(position.get('quote_token') or raw.get('quote_token'))
        if quote != USDT.lower() or (expected_quote and expected_quote != USDT.lower()):
            return verdict('PRICE_UNVERIFIED', 'UNSUPPORTED_QUOTE')
        if (not pool or not token or token == quote
                or address(evidence.get('pool')) != pool
                or address(evidence.get('base_token') or evidence.get('token')) != token
                or str(evidence.get('dex') or '').replace('-', '_').lower() != 'pancakeswap_v2'
                or evidence.get('chain') != 'bsc'):
            return verdict('PRICE_CONFLICT', 'IDENTITY_MISMATCH')
        price = number(evidence.get('price_usd'))
        observed = timestamp(evidence.get('observed_at'))
        now = datetime.now(timezone.utc)
        if (price is None or observed is None
                or not 0 <= (now - observed).total_seconds() <= MAX_AGE_SECONDS
                or evidence.get('source') not in SOURCES):
            return verdict('PRICE_UNVERIFIED', 'INVALID_PROVENANCE_OR_PRICE')
        key = (position.get('id'), pool, token, quote)
        reference = self.accepted.get(key)
        if reference and observed < reference['observed_at']:
            return verdict('PRICE_UNVERIFIED', 'OUT_OF_ORDER')
        if (reference and observed == reference['observed_at']
                and price != reference['price']):
            return verdict('PRICE_CONFLICT', 'OBSERVATION_CHANGED')
        extreme = reference is None or max(price / reference['price'], reference['price'] / price) >= EXTREME_RATIO
        result = dict(key=key, price=price, observed_at=observed)
        if extreme or evidence.get("source") == "pancakeswap_v2_sync":
            proof = self._onchain(pool, token, observed)
            if proof['state'] != 'VERIFIED':
                return proof
            if evidence.get('source') == 'pancakeswap_v2_sync':
                raw_block = evidence.get('block_number')
                event_block = int(raw_block, 16) if isinstance(raw_block, str) and raw_block.startswith('0x') else int(raw_block)
                if (event_block != proof['block_number']
                        or str(evidence.get('block_hash') or '').lower() != proof['block_hash'].lower()):
                    return verdict('PRICE_UNVERIFIED', 'SYNC_BLOCK_INCOMPATIBLE')
            chain_price = proof['chain_price']
            # Multiplication avoids rounding error at the inclusive boundary.
            if max(price, chain_price) > min(price, chain_price) * MAX_DIVERGENCE:
                return verdict('PRICE_CONFLICT', 'ONCHAIN_PRICE_DISAGREEMENT')
            result.update(proof)
        return verdict('VERIFIED_EXTREME' if extreme else 'VERIFIED_NORMAL',
                       'PAPER_USDT_USD_V1', **{k: v for k, v in result.items() if k not in {'state', 'reason'}})

    def _onchain(self, pool, token, observed):
        client = self.client
        if client.eth.chain_id != 56:
            return verdict('PRICE_CONFLICT', 'CHAIN_MISMATCH')
        block = client.eth.get_block('latest')
        block_hash = block['hash']
        block_id = block_hash.hex() if hasattr(block_hash, 'hex') else block_hash
        if isinstance(block_id, str) and not block_id.startswith('0x'):
            block_id = '0x' + block_id
        block_time = datetime.fromtimestamp(int(block['timestamp']), timezone.utc)
        if (not 0 <= (datetime.now(timezone.utc) - block_time).total_seconds() <= MAX_AGE_SECONDS
                or abs((observed - block_time).total_seconds()) > MAX_SKEW_SECONDS):
            return verdict('PRICE_UNVERIFIED', 'BLOCK_TIME_INCOMPATIBLE')
        membership = verify_pair_membership(pool, token, USDT, client=client, block_identifier=block_id)
        if membership['state'] != 'VERIFIED':
            return verdict('PRICE_CONFLICT' if membership['state'] in {'FACTORY_MISMATCH', 'TOKEN_MISMATCH'} else 'PRICE_UNVERIFIED', membership['state'])
        token0, token1 = membership['token0'], membership['token1']
        decimals = []
        for asset in (token, USDT):
            value = client.eth.contract(address=Web3.to_checksum_address(asset), abi=ERC20_ABI).functions.decimals().call(block_identifier=block_id)
            if type(value) is not int or not 0 <= value <= 255:
                return verdict('PRICE_UNVERIFIED', 'INVALID_DECIMALS')
            decimals.append(value)
        reserves = client.eth.contract(address=Web3.to_checksum_address(pool), abi=PAIR_ABI).functions.getReserves().call(block_identifier=block_id)
        r_token, r_usdt = reserves[:2] if token0 == token else reserves[:2][::-1]
        if any(type(r) is not int or not 0 < r < 2**112 for r in (r_token, r_usdt)):
            return verdict('PRICE_UNVERIFIED', 'INVALID_RESERVES')
        # Detect a reorg or inconsistent failover response during the read set.
        if client.eth.get_block(block['number'])['hash'] != block_hash:
            return verdict('PRICE_UNVERIFIED', 'BLOCK_RETRACTED')
        with localcontext() as ctx:
            ctx.prec = 100
            price = Decimal(r_usdt) / Decimal(r_token) * Decimal(10) ** (decimals[0] - decimals[1])
        return verdict('VERIFIED', 'HTTP_PINNED_V2_RESERVES', chain_price=price,
                       token0=token0, token1=token1, block_hash=block_id,
                       block_number=block['number'], ratio_raw=r_usdt / r_token)

    def accept(self, result):
        if result.get('state') in {'VERIFIED_NORMAL', 'VERIFIED_EXTREME'}:
            self.accepted[result['key']] = dict(result)


def admission_check(trade):
    evidence = context(trade).get('price_observation') or {}
    if number(evidence.get('price_usd')) != number(trade.get('entry_price')):
        return verdict('PRICE_UNVERIFIED', 'ENTRY_EVIDENCE_MISSING')
    return PriceIntegrityGate().evaluate(trade, evidence)
