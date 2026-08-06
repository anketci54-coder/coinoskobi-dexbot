from app.cache.gecko_cache import GeckoCache
from app.filter.cache_filter import CacheFilter
from app.analyzer.token import analyze as token_analyze
from app.analyzer.pair import analyze as pair_analyze
from app.risk.bytecode import analyze as risk_analyze
from app.strategy.engine import StrategyEngine
from app.paper.database import PaperDatabase
from app.paper.manager import PaperManager

print("=" * 60)
print("Coinoskobi Pipeline v5")
print("=" * 60)

cache = GeckoCache()
flt = CacheFilter()
strategy = StrategyEngine()
paper = PaperDatabase()
manager = PaperManager()

rows = cache.all()

print(f"Cache      : {len(rows)}")

candidates = flt.filter(rows)

print(f"Candidates : {len(candidates)}")

paper_buy = 0
watch = 0
reject = 0

for i, row in enumerate(candidates, start=1):

    print()
    print("=" * 60)
    print(f"Aday #{i}")
    print("=" * 60)

    token_address = row["token"].split("_",1)[1]

    token = token_analyze(token_address)
    pair = pair_analyze(token_address)
    risk = risk_analyze(token_address)

    decision = strategy.evaluate(
        token,
        pair,
        risk
    )

    print("TOKEN")
    print(token)
    print()

    print("PAIR")
    print(pair)
    print()

    print("RISK")
    print(risk)
    print()

    print("STRATEGY")
    print(decision)
    print()

    if decision["decision"] == "PAPER_BUY":

        if paper.has_open_position(token_address):
            print(">>> OPEN POSITION EXISTS")
            watch += 1
            continue

        try:
            price = manager.price.get_price(token_address)
        except Exception:
            price = 0.0

        if price <= 0:
            print(f">>> SKIP (price unavailable): {token_address}")
            reject += 1
            continue

        amount_bnb = 0.01
        token_amount = amount_bnb / price

        paper.insert({

            "token": token_address,
            "symbol": token.get("symbol", "?"),

            "entry_price": price,
            "current_price": price,
            "highest_price": price,
            "lowest_price": price,

            "tp_price": price * 1.20 if price else 0,
            "sl_price": price * 0.90 if price else 0,

            "amount_bnb": amount_bnb,
            "token_amount": token_amount,

            "gas_buy": 0.00018,
            "gas_sell": 0.00018,

            "swap_fee": 0.25,
            "buy_tax": 0,
            "sell_tax": 0,
            "slippage": 0.5,
            "mev": 0.2,

            "status": "OPEN"

        })

        paper_buy += 1
        print(">>> PAPER BUY")

    elif decision["decision"] == "WATCH":

        watch += 1
        print(">>> WATCH")

    else:

        reject += 1
        print(">>> REJECT")

print()
print("=" * 60)
print("ÖZET")
print("=" * 60)
print("Cache      :", len(rows))
print("Candidates :", len(candidates))
print("Paper Buy  :", paper_buy)
print("Watch      :", watch)
print("Reject     :", reject)
print("=" * 60)

print()
print("Pozisyon kontrolü")
manager.process()
