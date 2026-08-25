import time

import requests

from app.config.scanner import (
    HTTP_429_BACKOFF_SECONDS,
    HTTP_429_MAX_RETRIES,
    HTTP_TIMEOUT,
    NETWORK,
)
from app.scanner.followup_snapshot_cache import (
    persist_registered_followup_snapshots,
)

URL = (
    f"https://api.geckoterminal.com/api/v2/"
    f"networks/{NETWORK}/new_pools"
)


class GeckoScanner:

    @staticmethod
    def _normalized_addresses(pools, max_pools):
        addresses = list(dict.fromkeys(
            str(pool or "").strip().lower()
            for pool in pools
            if str(pool or "").strip()
        ))

        if (
            not addresses
            or len(addresses) > int(max_pools)
        ):
            raise ValueError(
                "invalid bounded pool list"
            )

        return addresses

    @staticmethod
    def _row_to_candidate(row):
        attr = row.get("attributes", {})
        rel = row.get("relationships", {})

        return {
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
                attr.get("base_token_price_usd")
                or 0
            ),
            "fdv": float(
                attr.get("fdv_usd")
                or 0
            ),
            "market_cap": float(
                attr.get("market_cap_usd")
                or 0
            ),
            "liquidity": float(
                attr.get("reserve_in_usd")
                or 0
            ),
            "volume_24h": float(
                attr.get("volume_usd", {})
                .get("h24")
                or 0
            ),
            "buys_24h": int(
                attr.get("transactions", {})
                .get("h24", {})
                .get("buys", 0)
            ),
            "created_at": attr.get(
                "pool_created_at"
            ),
        }

    def _request_multi(self, addresses):
        url = (
            "https://api.geckoterminal.com/api/v2/"
            f"networks/{NETWORK}/pools/multi/"
            + ",".join(addresses)
        )

        attempts = HTTP_429_MAX_RETRIES + 1
        response = None

        for attempt in range(attempts):
            response = requests.get(
                url,
                headers={
                    "Accept": (
                        "application/json;"
                        "version=20230302"
                    ),
                },
                timeout=HTTP_TIMEOUT,
            )

            if (
                getattr(
                    response,
                    "status_code",
                    200,
                )
                != 429
            ):
                response.raise_for_status()
                return response

            if attempt >= HTTP_429_MAX_RETRIES:
                response.raise_for_status()

            time.sleep(
                HTTP_429_BACKOFF_SECONDS
                * (2 ** attempt)
            )

        raise RuntimeError(
            "multi-pool request unavailable"
        )

    def _fetch(self):
        attempts = HTTP_429_MAX_RETRIES + 1

        for attempt in range(attempts):
            response = requests.get(
                URL,
                headers={
                    "Accept": (
                        "application/json;"
                        "version=20230302"
                    ),
                },
                timeout=HTTP_TIMEOUT,
            )

            if response.status_code != 429:
                response.raise_for_status()
                return response

            if attempt >= HTTP_429_MAX_RETRIES:
                response.raise_for_status()

            time.sleep(
                HTTP_429_BACKOFF_SECONDS
                * (2 ** attempt)
            )

        raise RuntimeError(
            "unexpected GeckoTerminal retry state"
        )

    def pool_snapshots(
        self,
        pools,
        max_pools=30,
        *,
        persist_followups=True,
    ):
        """
        Return fresh exact-pool market facts using one bounded Gecko
        multi-pool request.

        When a pool is already registered for counterfactual follow-up,
        the same response also refreshes its preserved cache row. This
        keeps later reevaluation on current liquidity/volume/activity
        instead of a stale discovery snapshot.
        """
        addresses = self._normalized_addresses(
            pools,
            max_pools,
        )
        response = self._request_multi(addresses)

        snapshots = []

        for raw in response.json().get("data", []):
            snapshot = self._row_to_candidate(raw)
            pool = str(
                snapshot.get("pool") or ""
            ).strip().lower()

            if pool in addresses:
                snapshots.append(snapshot)

        if persist_followups and snapshots:
            persist_registered_followup_snapshots(
                snapshots
            )

        return snapshots

    def pool_prices(self, pools, max_pools=30):
        addresses = self._normalized_addresses(
            pools,
            max_pools,
        )

        snapshots = self.pool_snapshots(
            addresses,
            max_pools=max_pools,
        )

        return {
            str(row.get("pool") or "")
            .strip().lower(): float(
                row.get("price_usd") or 0
            )
            for row in snapshots
            if (
                str(row.get("pool") or "")
                .strip().lower()
                in addresses
                and float(
                    row.get("price_usd") or 0
                ) > 0
            )
        }

    def pool_price(self, pool):
        pool = str(pool or "").strip().lower()
        prices = self.pool_prices([pool])

        if pool not in prices:
            raise RuntimeError(
                "pool price unavailable"
            )

        return prices[pool]

    def scan(self):
        response = self._fetch()

        return [
            self._row_to_candidate(row)
            for row in response.json().get(
                "data",
                [],
            )
        ]


if __name__ == "__main__":
    pools = GeckoScanner().scan()

    print("=" * 60)
    print("POOLS :", len(pools))
    print("=" * 60)

    for pool in pools[:10]:
        print(pool)
