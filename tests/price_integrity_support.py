"""Contract-shaped HTTP fake; the real integrity gate performs all checks."""
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

from app.config.contracts import PANCAKE_FACTORY, USDT

TOKEN = '0x' + '11' * 20
POOL = '0x' + '22' * 20
HASH = '0x' + 'ab' * 32


def position(**kwargs):
    return dict(dict(id=1, pool=POOL, token=TOKEN, dex='pancakeswap_v2',
                     entry_price=1, current_price=1, highest_price=1,
                     lowest_price=1, token_amount=1), **kwargs)


def evidence(price=1, **kwargs):
    return dict(dict(chain='bsc', pool=POOL, base_token=TOKEN, quote_token=USDT,
                     dex='pancakeswap_v2', source='dexscreener', price_usd=price,
                     observed_at=datetime.now(timezone.utc).isoformat()), **kwargs)


class V2RPC:
    def __init__(self, price=1, *, token=TOKEN, pool=POOL, reverse=False,
                 token_decimals=9, usdt_decimals=6):
        self.eth = self
        self.chain_id = 56
        self.token, self.pool = token.lower(), pool.lower()
        self.canonical = pool
        self.token0, self.token1 = (USDT.lower(), self.token) if reverse else (self.token, USDT.lower())
        self.token_decimals, self.usdt_decimals = token_decimals, usdt_decimals
        self.price = Decimal(str(price))
        self.calls = []
        self.fail = False
        self.zero = False
        self.block = dict(hash=HASH, number=123, timestamp=int(datetime.now(timezone.utc).timestamp()))

    def get_block(self, identifier):
        if self.fail:
            raise ConnectionError('offline')
        self.calls.append(('block', identifier))
        return dict(self.block)

    def contract(self, address, abi):
        address = address.lower()
        rpc = self

        def call(name, value):
            def read(**kwargs):
                assert kwargs == {'block_identifier': HASH}
                rpc.calls.append((name, address))
                return value()
            return SimpleNamespace(call=read)

        def reserves():
            token_raw = 10**24
            usdt_raw = int(Decimal(token_raw) * rpc.price * Decimal(10)**(rpc.usdt_decimals-rpc.token_decimals))
            values = (token_raw, usdt_raw if not rpc.zero else 0)
            return (*((values[::-1]) if rpc.token0 == USDT.lower() else values), 123)

        functions = SimpleNamespace(
            getPair=lambda *args: call('getPair', lambda: rpc.canonical),
            token0=lambda: call('token0', lambda: rpc.token0),
            token1=lambda: call('token1', lambda: rpc.token1),
            decimals=lambda: call('decimals', lambda: rpc.usdt_decimals if address == USDT.lower() else rpc.token_decimals),
            getReserves=lambda: call('getReserves', reserves),
        )
        return SimpleNamespace(functions=functions)
