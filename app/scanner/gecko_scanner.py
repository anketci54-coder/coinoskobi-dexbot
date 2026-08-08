import requests

from app.config.scanner import (
    HTTP_TIMEOUT,
    NETWORK,
)

URL = (
    f"https://api.geckoterminal.com/api/v2/"
    f"networks/{NETWORK}/new_pools"
)


class GeckoScanner:

    def scan(self):

        response = requests.get(
            URL,
            headers={
                "Accept": "application/json;version=20230302",
            },
            timeout=HTTP_TIMEOUT,
        )

        response.raise_for_status()

        candidates = []

        for row in response.json().get("data", []):

            attr = row.get("attributes", {})
            rel = row.get("relationships", {})

            candidates.append(
                {
                    "pool": attr.get("address"),
                    "base_token": (
                        rel.get("base_token", {})
                        .get("data", {})
                        .get("id")
                    ),
                    "quote_token": (
                        rel.get("quote_token", {})
                        .get("data", {})
                        .get("id")
                    ),
                    "name": attr.get("name"),
                    "dex": (
                        rel.get("dex", {})
                        .get("data", {})
                        .get("id")
                    ),
                    "price_usd": float(
                        attr.get("base_token_price_usd") or 0
                    ),
                    "fdv": float(attr.get("fdv_usd") or 0),
                    "market_cap": float(
                        attr.get("market_cap_usd") or 0
                    ),
                    "liquidity": float(
                        attr.get("reserve_in_usd") or 0
                    ),
                    "volume_24h": float(
                        attr.get("volume_usd", {}).get("h24") or 0
                    ),
                    "buys_24h": int(
                        attr.get("transactions", {})
                        .get("h24", {})
                        .get("buys", 0)
                    ),
                    "created_at": attr.get("pool_created_at"),
                }
            )

        return candidates


if __name__ == "__main__":

    pools = GeckoScanner().scan()

    print("=" * 60)
    print("POOLS :", len(pools))
    print("=" * 60)

    for pool in pools[:10]:
        print(pool)
