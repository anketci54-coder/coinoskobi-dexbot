from datetime import datetime, timezone

import requests

from app.universe.schema import canonical_address, canonical_dex


DEXSCREENER_PAIRS_URL = (
    "https://api.dexscreener.com/latest/dex/pairs/bsc"
)
DEXSCREENER_MAX_BATCH = 30
DEXSCREENER_TIMEOUT_SECONDS = 10
SNAPSHOT_SOURCE = "dexscreener"


def _number(value):
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _integer(value):
    number = _number(value)
    return int(number) if number is not None else None


def _window(mapping, name):
    value = mapping.get(name)
    return value if isinstance(value, dict) else {}


def _pancake_response(row):
    dex_id = str(row.get("dexId") or "").strip().lower()
    return dex_id == "pancakeswap" or dex_id.startswith("pancakeswap_")


class DexScreenerSnapshotClient:
    """Bounded, read-only market snapshots for registered BSC Pancake pools."""

    def __init__(self, *, session=None, timeout=DEXSCREENER_TIMEOUT_SECONDS,
                 now_func=None):
        self.session = session or requests.Session()
        self.timeout = float(timeout)
        if self.timeout <= 0:
            raise ValueError("positive timeout required")
        self.now_func = now_func or (
            lambda: datetime.now(timezone.utc).isoformat()
        )

    @staticmethod
    def _requested(pools):
        requested = {}
        for row in pools or []:
            if not isinstance(row, dict):
                raise ValueError("pool identity mapping required")
            pool = canonical_address(row.get("pool"))
            dex = canonical_dex(row.get("dex"))
            previous = requested.get(pool)
            if previous is not None and previous != dex:
                raise ValueError("conflicting pool DEX identity")
            requested[pool] = dex
        if len(requested) > DEXSCREENER_MAX_BATCH:
            raise ValueError("DexScreener batch exceeds 30 pools")
        return requested

    def fetch(self, pools):
        requested = self._requested(pools)
        if not requested:
            return []

        response = self.session.get(
            DEXSCREENER_PAIRS_URL + "/" + ",".join(requested),
            headers={"Accept": "application/json"},
            timeout=self.timeout,
        )
        response.raise_for_status()
        payload = response.json()
        raw_pairs = payload.get("pairs") or []
        if not isinstance(raw_pairs, list):
            raise ValueError("invalid DexScreener pairs payload")

        observed_at = self.now_func()
        snapshots = []
        seen = set()
        for raw in raw_pairs:
            if not isinstance(raw, dict):
                continue
            try:
                pool = canonical_address(raw.get("pairAddress"))
            except ValueError:
                continue
            if (pool not in requested or pool in seen
                    or str(raw.get("chainId") or "").lower() != "bsc"
                    or not _pancake_response(raw)):
                continue

            txns = raw.get("txns") if isinstance(raw.get("txns"), dict) else {}
            volume = raw.get("volume") if isinstance(raw.get("volume"), dict) else {}
            change = raw.get("priceChange") if isinstance(raw.get("priceChange"), dict) else {}
            liquidity = raw.get("liquidity") if isinstance(raw.get("liquidity"), dict) else {}
            base = raw.get("baseToken") if isinstance(raw.get("baseToken"), dict) else {}
            quote = raw.get("quoteToken") if isinstance(raw.get("quoteToken"), dict) else {}

            snapshot = {
                "schema_version": "DEXSCREENER_SNAPSHOT_V1",
                "chain": "bsc",
                "source": SNAPSHOT_SOURCE,
                "dex": requested[pool],
                "pool": pool,
                "base_token": canonical_address(base.get("address"), required=False),
                "quote_token": canonical_address(quote.get("address"), required=False),
                "price_usd": _number(raw.get("priceUsd")),
                "liquidity_usd": _number(liquidity.get("usd")),
                "fdv_usd": _number(raw.get("fdv")),
                "market_cap_usd": _number(raw.get("marketCap")),
                "pair_created_at_ms": _integer(raw.get("pairCreatedAt")),
                "observed_at": observed_at,
            }
            for window in ("m5", "h1", "h6", "h24"):
                window_txns = _window(txns, window)
                buys = _integer(window_txns.get("buys"))
                sells = _integer(window_txns.get("sells"))
                snapshot[f"buys_{window}"] = buys
                snapshot[f"sells_{window}"] = sells
                snapshot[f"txns_{window}"] = (
                    buys + sells if buys is not None and sells is not None else None
                )
                snapshot[f"volume_{window}_usd"] = _number(volume.get(window))
                snapshot[f"change_{window}"] = _number(change.get(window))

            snapshots.append(snapshot)
            seen.add(pool)

        return snapshots


__all__ = ["DEXSCREENER_MAX_BATCH", "DexScreenerSnapshotClient"]
