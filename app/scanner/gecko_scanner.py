import logging
import time

import requests

from app.config.scanner import (
    HTTP_429_BACKOFF_SECONDS,
    HTTP_429_MAX_RETRIES,
    HTTP_TIMEOUT,
    MARKET_PROVIDER_COOLDOWN_SECONDS,
    NETWORK,
)
from app.scanner.followup_snapshot_cache import (
    persist_registered_followup_snapshots,
)

logger = logging.getLogger(__name__)

URL = (
    f"https://api.geckoterminal.com/api/v2/"
    f"networks/{NETWORK}/new_pools"
)

DEXSCREENER_URL = (
    "https://api.dexscreener.com/latest/dex/pairs/"
    f"{NETWORK}"
)

# Process-local provider state is deliberate: a restart should recover a
# healthy provider immediately, while a hot provider must stay out of the
# 20-second fast-watch loop after a rate-limit response.
class GeckoScanner:

    def __init__(self):
        # Provider cooldown is scanner-instance state.
        # A fresh scanner starts healthy; the long-lived production
        # scanner still preserves cooldown across its own scan cycles.
        self._provider_cooldown_until = {
            "geckoterminal": 0.0,
            "dexscreener": 0.0,
        }
        self._market_data_broker = None

    def bind_market_data_broker(self, broker):
        if broker is None:
            raise ValueError("market-data broker required")
        self._market_data_broker = broker

    def _provider_available(self, provider):
        return time.monotonic() >= float(
            self._provider_cooldown_until.get(provider, 0.0)
        )

    def _cooldown_provider(self, provider):
        until = time.monotonic() + float(
            MARKET_PROVIDER_COOLDOWN_SECONDS
        )
        self._provider_cooldown_until[provider] = until
        logger.warning(
            "Market provider rate-limited; cooling down provider=%s seconds=%s",
            provider,
            MARKET_PROVIDER_COOLDOWN_SECONDS,
        )

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

    @staticmethod
    def _dex_row_to_candidate(row):
        base = row.get("baseToken") or {}
        quote = row.get("quoteToken") or {}
        liquidity = row.get("liquidity") or {}
        txns = row.get("txns") or {}
        volume = row.get("volume") or {}
        labels = {
            str(value).strip().lower()
            for value in (row.get("labels") or [])
        }
        dex_id = str(row.get("dexId") or "").strip().lower()

        if dex_id == "pancakeswap" and "v3" in labels:
            dex = "pancakeswap_v3"
        elif dex_id == "pancakeswap" and "v2" in labels:
            dex = "pancakeswap_v2"
        else:
            dex = dex_id

        h24 = txns.get("h24") or {}

        return {
            "pool": row.get("pairAddress"),
            "base_token": base.get("address"),
            "quote_token": quote.get("address"),
            "name": (
                f"{base.get('symbol') or ''} / "
                f"{quote.get('symbol') or ''}"
            ).strip(" /"),
            "dex": dex,
            "price_usd": float(row.get("priceUsd") or 0),
            "fdv": float(row.get("fdv") or 0),
            "market_cap": float(row.get("marketCap") or 0),
            "liquidity": float(liquidity.get("usd") or 0),
            "volume_24h": float(volume.get("h24") or 0),
            "buys_24h": int(h24.get("buys") or 0),
            "created_at": None,
            "provider": "dexscreener",
        }

    def _request_multi(self, addresses):
        if not self._provider_available("geckoterminal"):
            raise RuntimeError("geckoterminal provider cooling down")

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
                self._cooldown_provider("geckoterminal")
                response.raise_for_status()

            time.sleep(
                HTTP_429_BACKOFF_SECONDS
                * (2 ** attempt)
            )

        raise RuntimeError(
            "multi-pool request unavailable"
        )

    def _request_dexscreener(self, addresses):
        if not self._provider_available("dexscreener"):
            raise RuntimeError("dexscreener provider cooling down")

        response = requests.get(
            DEXSCREENER_URL + "/" + ",".join(addresses),
            headers={"Accept": "application/json"},
            timeout=HTTP_TIMEOUT,
        )

        if response.status_code == 429:
            self._cooldown_provider("dexscreener")

        response.raise_for_status()
        return response

    def _fetch(self):
        if not self._provider_available("geckoterminal"):
            raise RuntimeError("geckoterminal provider cooling down")

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
                self._cooldown_provider("geckoterminal")
                response.raise_for_status()

            time.sleep(
                HTTP_429_BACKOFF_SECONDS
                * (2 ** attempt)
            )

        raise RuntimeError(
            "unexpected GeckoTerminal retry state"
        )

    def _pool_snapshots_gecko(self, addresses):
        response = self._request_multi(addresses)
        snapshots = []

        for raw in response.json().get("data", []):
            snapshot = self._row_to_candidate(raw)
            pool = str(
                snapshot.get("pool") or ""
            ).strip().lower()

            if pool in addresses:
                snapshots.append(snapshot)

        return snapshots

    def _pool_snapshots_dexscreener(self, addresses):
        response = self._request_dexscreener(addresses)
        snapshots = []

        for raw in response.json().get("pairs", []):
            if not isinstance(raw, dict):
                continue
            if str(raw.get("chainId") or "").strip().lower() != NETWORK:
                continue

            snapshot = self._dex_row_to_candidate(raw)
            pool = str(
                snapshot.get("pool") or ""
            ).strip().lower()

            if pool in addresses:
                snapshots.append(snapshot)

        return snapshots

    def pool_snapshots(
        self,
        pools,
        max_pools=30,
        *,
        persist_followups=True,
    ):
        """Return exact-pool market facts through the canonical broker."""
        if self._market_data_broker is not None:
            return self._market_data_broker.pool_snapshots(
                pools,
                max_pools=max_pools,
                persist_followups=persist_followups,
            )

        addresses = self._normalized_addresses(
            pools,
            max_pools,
        )

        snapshots = []
        try:
            snapshots = self._pool_snapshots_gecko(addresses)
        except Exception as exc:
            logger.warning(
                "GeckoTerminal snapshot unavailable; trying DexScreener: %s",
                exc,
            )

        if not snapshots:
            try:
                snapshots = self._pool_snapshots_dexscreener(addresses)
            except Exception as exc:
                logger.warning(
                    "DexScreener snapshot fallback unavailable: %s",
                    exc,
                )
                snapshots = []

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
            .strip()
            .lower(): float(
                row.get("price_usd") or 0
            )
            for row in snapshots
            if (
                str(row.get("pool") or "")
                .strip()
                .lower()
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
