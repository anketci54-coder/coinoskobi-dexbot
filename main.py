from app.scanner.bsc_scanner import latest_bsc
from app.analyzer.token import analyze as token_analyze
from app.analyzer.pair import analyze as pair_analyze
from app.risk.bytecode import analyze as risk_analyze
from app.filter.candidate import CandidateFilter

flt = CandidateFilter()

print("=" * 60)
print("Coinoskobi Pipeline v2")
print("=" * 60)

tokens = latest_bsc()

print(f"Scanner : {len(tokens)} aday")

for item in tokens:

    address = item["tokenAddress"]

    print()
    print("=" * 60)
    print(address)
    print("=" * 60)

    try:
        token_info = token_analyze(address)
        pair_info = pair_analyze(address)
        risk_info = risk_analyze(address)

        result = flt.accept(
            token_info,
            pair_info,
            risk_info
        )

        print()

        print("Token :", token_info)

        print()

        print("Pair :", pair_info)

        print()

        print("Risk :", risk_info)

        print()

        print("Filter :", result)

    except Exception as e:

        print("HATA :", e)
