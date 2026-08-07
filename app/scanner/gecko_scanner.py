import requests

from app.config.scanner import (
    HTTP_TIMEOUT,
    NETWORK,
    MIN_LIQUIDITY_USD,
    MIN_VOLUME_24H_USD,
    MIN_BUYS_24H,
    MIN_FDV_USD,
    MAX_FDV_USD,
)

URL = f"https://api.geckoterminal.com/api/v2/networks/{NETWORK}/new_pools"


class GeckoScanner:

    def scan(self):

        r = requests.get(
            URL,
            headers={
                "Accept": "application/json;version=20230302"
            },
            timeout=HTTP_TIMEOUT
        )

        r.raise_for_status()

        candidates = []

        for row in r.json().get("data", []):

            attr = row.get("attributes", {})
            rel = row.get("relationships", {})

            liquidity = float(attr.get("reserve_in_usd") or 0)
            volume_24h = float(attr.get("volume_usd", {}).get("h24") or 0)
            buys_24h = int(attr.get("transactions", {}).get("h24", {}).get("buys", 0))
            fdv = float(attr.get("fdv_usd") or 0)

            if liquidity < MIN_LIQUIDITY_USD:
                continue

            if volume_24h < MIN_VOLUME_24H_USD:
                continue

            if buys_24h < MIN_BUYS_24H:
                continue

            if fdv < MIN_FDV_USD:
                continue

            if fdv > MAX_FDV_USD:
                continue

            candidates.append({

                "pool": pool,

                "name": attr.get("name"),

                "price_usd": price_usd,

                "fdv": fdv,

                "market_cap": float(attr.get("market_cap_usd") or 0)
                if attr.get("market_cap_usd")
                else 0,

                "liquidity": liquidity,

                "volume_24h": volume_24h,

                "buys_24h": buys_24h,

                "created_at": created_at,

                "dex": rel.get("dex", {})
                         .get("data", {})
                         .get("id"),

                "base_token": rel.get("base_token", {})
                                 .get("data", {})
                                 .get("id"),

                "quote_token": rel.get("quote_token", {})
                                  .get("data", {})
                                  .get("id")

            })

        candidates.sort(
            key=lambda x: (
                x["liquidity"],
                x["volume_24h"],
                x["buys_24h"]
            ),
            reverse=True
        )

        return candidates


if __name__ == "__main__":

    scanner = GeckoScanner()

    pools = scanner.scan()

    print()
    print("=" * 60)
    print("COINOSKOBI GECKO SCANNER")
    print("=" * 60)
    print("Geçen Aday :", len(pools))
    print()

    for i, p in enumerate(pools, start=1):

        print("-" * 60)
        print(f"Aday #{i}")
        print("Name      :", p["name"])
        print("DEX       :", p["dex"])
        print("Liquidity :", p["liquidity"])
        print("Volume24H :", p["volume_24h"])
        print("Buys24H   :", p["buys_24h"])
        print("FDV       :", p["fdv"])
        print("Pool      :", p["pool"])
