from app.scanner.bsc_scanner import latest_bsc
from app.analyzer.token import analyze as token_analyze
from app.analyzer.pair import analyze as pair_analyze
from app.risk.bytecode import analyze as risk_analyze

def main():

    print("=" * 60)
    print("Coinoskobi DEX Bot v0.3")
    print("=" * 60)

    tokens = latest_bsc()

    if not tokens:
        print("Aday bulunamadı.")
        return

    print(f"{len(tokens)} aday bulundu.")

    for i, item in enumerate(tokens, start=1):

        token = item["tokenAddress"]

        print()
        print("=" * 60)
        print(f"Aday #{i}")
        print(token)
        print("=" * 60)

        try:
            print("\\n[1] ERC20")
            token_analyze(token)

            print("\\n[2] Pair")
            pair_analyze(token)

            print("\\n[3] Risk")
            risk_analyze(token)

            print("\\nAnaliz tamamlandı.")

        except Exception as e:
            print("Analiz hatası:", e)

if __name__ == "__main__":
    main()
