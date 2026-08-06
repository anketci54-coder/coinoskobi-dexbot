import requests
import time

TOKEN_URL = "https://api.dexscreener.com/token-profiles/latest/v1"
PAIR_URL = "https://api.dexscreener.com/token-pairs/v1/bsc/{}"

MIN_LIQUIDITY = 20000


class Scanner:

    def scan(self):

        r = requests.get(TOKEN_URL, timeout=20)
        r.raise_for_status()

        result = []

        for token in r.json():

            if token.get("chainId") != "bsc":
                continue

            address = token.get("tokenAddress")

            try:

                p = requests.get(
                    PAIR_URL.format(address),
                    timeout=20
                )

                if p.status_code != 200:
                    continue

                pairs = p.json()

                if not pairs:
                    continue

                best = max(
                    pairs,
                    key=lambda x: (
                        x.get("liquidity", {})
                         .get("usd") or 0
                    )
                )

                liquidity = (
                    best.get("liquidity", {})
                        .get("usd") or 0
                )

                if liquidity < MIN_LIQUIDITY:
                    continue

                result.append({

                    "address": address,

                    "pair": best.get("pairAddress"),

                    "dex": best.get("dexId"),

                    "price": best.get("priceUsd"),

                    "liquidity": liquidity,

                    "fdv": best.get("fdv"),

                    "marketcap": best.get("marketCap"),

                    "created": best.get("pairCreatedAt"),

                    "url": best.get("url")

                })

                time.sleep(0.15)

            except Exception:
                continue

        return result


if __name__ == "__main__":

    scanner = Scanner()

    data = scanner.scan()

    print()
    print("GEÇEN ADAY :", len(data))
    print()

    for item in data:

        print("=" * 60)
        print("Address   :", item["address"])
        print("DEX       :", item["dex"])
        print("Liquidity :", item["liquidity"])
        print("FDV       :", item["fdv"])
        print("MarketCap :", item["marketcap"])
        print("Price     :", item["price"])
        print("URL       :", item["url"])
