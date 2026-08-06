from datetime import datetime, UTC

from app.scanner.bsc_scanner import latest_bsc
from app.analyzer.token import analyze as token_analyze
from app.analyzer.pair import analyze as pair_analyze
from app.risk.bytecode import analyze as risk_analyze
from app.filter.candidate import CandidateFilter
from app.strategy.engine import StrategyEngine
from app.paper.database import PaperDatabase

print("=" * 60)
print("Coinoskobi DEX Bot v1.0")
print("=" * 60)

scanner = latest_bsc()
flt = CandidateFilter()
strategy = StrategyEngine()
paper = PaperDatabase()

print(f"Scanner {len(scanner)} aday buldu.")

accepted = 0
rejected = 0

for item in scanner:

    address = item["tokenAddress"]

    print()
    print("=" * 60)
    print(address)
    print("=" * 60)

    try:

        token = token_analyze(address)
        pair = pair_analyze(address)
        risk = risk_analyze(address)

        result = flt.accept(
            token,
            pair,
            risk
        )

        print()
        print("TOKEN")
        print(token)

        print()
        print("PAIR")
        print(pair)

        print()
        print("RISK")
        print(risk)

        print()
        print("FILTER")
        print(result)

        if not result["accepted"]:
            rejected += 1
            continue

        accepted += 1

        decision = strategy.evaluate(
            token,
            pair,
            risk
        )

        print()
        print("STRATEGY")
        print(decision)

        if decision["decision"] != "BUY":
            continue

        paper.insert({

            "created_at": datetime.now(UTC).isoformat(),

            "token": address,

            "symbol": token["symbol"],

            "entry_price": 0,

            "exit_price": 0,

            "amount_bnb": 0.01,

            "gross_pnl": 0,

            "net_pnl": 0,

            "gas_buy": 0.00018,

            "gas_sell": 0.00018,

            "swap_fee": 0.25,

            "buy_tax": 0,

            "sell_tax": 0,

            "slippage": 0.5,

            "mev": 0.2,

            "status": "OPEN"

        })

        print()
        print(">>> PAPER BUY <<<")

    except Exception as e:

        print("HATA :", e)

print()
print("=" * 60)
print("ÖZET")
print("=" * 60)
print("Toplam :", len(scanner))
print("Accepted :", accepted)
print("Rejected :", rejected)
print("=" * 60)

