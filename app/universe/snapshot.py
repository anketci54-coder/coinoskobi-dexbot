from datetime import datetime, timezone

import requests

from app.universe.schema import canonical_address, canonical_dex


DEXSCREENER_PAIRS_URL = (
    "https://api.dexscreener.com/latest/dex/pairs/bsc"
)
DEXSCREENER_MAX_BATCH = 30
DEXSCREENER_TIMEOUT_SECONDS = 10
SNAPSHOT_SOURCE = "dexscreener"

GECKOTERMINAL_POOLS_URL = (
    "https://api.geckoterminal.com/api/v2/networks/bsc/pools/multi"
)
GECKOTERMINAL_TIMEOUT_SECONDS = 10
GECKOTERMINAL_SOURCE = "geckoterminal"


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


def _text(value):
    value = str(value or "").strip()
    return value or None


def _window(mapping, name):
    value = mapping.get(name)
    return value if isinstance(value, dict) else {}


def _pancake_response(row):
    dex_id = str(row.get("dexId") or "").strip().lower()
    return dex_id == "pancakeswap" or dex_id.startswith("pancakeswap_")


def _gecko_pancake_response(row):
    relationships = (
        row.get("relationships")
        if isinstance(row.get("relationships"), dict)
        else {}
    )
    dex_data = (
        relationships.get("dex", {}).get("data", {})
        if isinstance(relationships.get("dex"), dict)
        else {}
    )
    dex_id = str(dex_data.get("id") or "").strip().lower()
    return dex_id == "pancakeswap" or dex_id.startswith("pancakeswap_")


def _gecko_relationship_address(row, name):
    relationships = (
        row.get("relationships")
        if isinstance(row.get("relationships"), dict)
        else {}
    )
    relationship = relationships.get(name)
    relationship = relationship if isinstance(relationship, dict) else {}
    data = relationship.get("data")
    data = data if isinstance(data, dict) else {}
    value = str(data.get("id") or "").strip().lower()
    if value.startswith("bsc_"):
        value = value[4:]
    return canonical_address(value, required=False)


def _timestamp_ms(value):
    value = str(value or "").strip()
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return int(parsed.timestamp() * 1000)


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
            base_symbol = _text(base.get("symbol"))
            quote_symbol = _text(quote.get("symbol"))

            snapshot = {
                "schema_version": "DEXSCREENER_SNAPSHOT_V1",
                "chain": "bsc",
                "source": SNAPSHOT_SOURCE,
                "dex": requested[pool],
                "pool": pool,
                "base_token": canonical_address(base.get("address"), required=False),
                "quote_token": canonical_address(quote.get("address"), required=False),
                "base_symbol": base_symbol,
                "quote_symbol": quote_symbol,
                "base_name": _text(base.get("name")),
                "quote_name": _text(quote.get("name")),
                "display_name": (
                    f"{base_symbol} / {quote_symbol}"
                    if base_symbol and quote_symbol
                    else base_symbol or quote_symbol
                ),
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


class GeckoTerminalSnapshotClient:
    """Exact-pool GeckoTerminal snapshots normalized to the universe contract."""

    def __init__(self, *, session=None, timeout=GECKOTERMINAL_TIMEOUT_SECONDS,
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
            raise ValueError("GeckoTerminal batch exceeds 30 pools")
        return requested

    def fetch(self, pools):
        requested = self._requested(pools)
        if not requested:
            return []

        response = self.session.get(
            GECKOTERMINAL_POOLS_URL + "/" + ",".join(requested),
            headers={"Accept": "application/json;version=20230302"},
            timeout=self.timeout,
        )
        response.raise_for_status()
        payload = response.json()
        raw_pools = payload.get("data") or []
        if not isinstance(raw_pools, list):
            raise ValueError("invalid GeckoTerminal pools payload")

        observed_at = self.now_func()
        snapshots = []
        seen = set()
        for raw in raw_pools:
            if not isinstance(raw, dict):
                continue
            attributes = (
                raw.get("attributes")
                if isinstance(raw.get("attributes"), dict)
                else {}
            )
            try:
                pool = canonical_address(attributes.get("address"))
            except ValueError:
                continue
            if (pool not in requested or pool in seen
                    or not _gecko_pancake_response(raw)):
                continue

            txns = (
                attributes.get("transactions")
                if isinstance(attributes.get("transactions"), dict)
                else {}
            )
            volume = (
                attributes.get("volume_usd")
                if isinstance(attributes.get("volume_usd"), dict)
                else {}
            )
            change = (
                attributes.get("price_change_percentage")
                if isinstance(attributes.get("price_change_percentage"), dict)
                else {}
            )
            display_name = _text(
                attributes.get("name") or attributes.get("pool_name")
            )

            snapshot = {
                "schema_version": "GECKOTERMINAL_SNAPSHOT_V1",
                "chain": "bsc",
                "source": GECKOTERMINAL_SOURCE,
                "dex": requested[pool],
                "pool": pool,
                "base_token": _gecko_relationship_address(raw, "base_token"),
                "quote_token": _gecko_relationship_address(raw, "quote_token"),
                "base_symbol": None,
                "quote_symbol": None,
                "base_name": None,
                "quote_name": None,
                "display_name": display_name,
                "price_usd": _number(attributes.get("base_token_price_usd")),
                "liquidity_usd": _number(attributes.get("reserve_in_usd")),
                "fdv_usd": _number(attributes.get("fdv_usd")),
                "market_cap_usd": _number(attributes.get("market_cap_usd")),
                "pair_created_at_ms": _timestamp_ms(
                    attributes.get("pool_created_at")
                ),
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


class ProviderStickySnapshotClient:
    """
    Preserve one measurement methodology per pool.

    Unobserved pools try DexScreener first and only provider omissions fall
    through to GeckoTerminal. Once latest_snapshot_source is set, the pool is
    queried only through that provider; a temporary miss never switches source.
    """

    def __init__(self, *, primary=None, fallback=None):
        self.primary = primary or DexScreenerSnapshotClient()
        self.fallback = fallback or GeckoTerminalSnapshotClient()

    @staticmethod
    def _requested(pools):
        requested = {}
        order = []
        for raw in pools or []:
            if not isinstance(raw, dict):
                raise ValueError("pool identity mapping required")
            pool = canonical_address(raw.get("pool"))
            dex = canonical_dex(raw.get("dex"))
            source = str(raw.get("latest_snapshot_source") or "").strip().lower()
            source = source or None
            if source not in {None, SNAPSHOT_SOURCE, GECKOTERMINAL_SOURCE}:
                raise ValueError("unsupported sticky snapshot source")

            previous = requested.get(pool)
            if previous is not None:
                if previous["dex"] != dex:
                    raise ValueError("conflicting pool DEX identity")
                if previous["source"] not in {None, source} and source is not None:
                    raise ValueError("conflicting pool snapshot source")
                if previous["source"] is None and source is not None:
                    previous["source"] = source
                continue

            requested[pool] = {
                "pool": pool,
                "dex": dex,
                "source": source,
            }
            order.append(pool)

        if len(requested) > DEXSCREENER_MAX_BATCH:
            raise ValueError("sticky snapshot batch exceeds 30 pools")
        return requested, order

    @staticmethod
    def _provider_rows(entries):
        return [
            {"pool": row["pool"], "dex": row["dex"]}
            for row in entries
        ]

    def fetch(self, pools):
        requested, order = self._requested(pools)
        if not requested:
            return []

        entries = list(requested.values())
        unbound = [row for row in entries if row["source"] is None]
        primary_sticky = [
            row for row in entries if row["source"] == SNAPSHOT_SOURCE
        ]
        fallback_sticky = [
            row for row in entries if row["source"] == GECKOTERMINAL_SOURCE
        ]

        primary_targets = primary_sticky + unbound
        primary_rows = (
            self.primary.fetch(self._provider_rows(primary_targets))
            if primary_targets else []
        )
        primary_by_pool = {
            canonical_address(row["pool"]): row
            for row in primary_rows
        }

        unbound_missing = [
            row for row in unbound if row["pool"] not in primary_by_pool
        ]
        fallback_targets = fallback_sticky + unbound_missing
        fallback_rows = (
            self.fallback.fetch(self._provider_rows(fallback_targets))
            if fallback_targets else []
        )
        fallback_by_pool = {
            canonical_address(row["pool"]): row
            for row in fallback_rows
        }

        snapshots = []
        for pool in order:
            row = requested[pool]
            snapshot = None
            if row["source"] == SNAPSHOT_SOURCE:
                snapshot = primary_by_pool.get(pool)
            elif row["source"] == GECKOTERMINAL_SOURCE:
                snapshot = fallback_by_pool.get(pool)
            else:
                snapshot = (
                    primary_by_pool.get(pool)
                    or fallback_by_pool.get(pool)
                )
            if snapshot is not None:
                snapshots.append(snapshot)
        return snapshots


__all__ = [
    "DEXSCREENER_MAX_BATCH",
    "DexScreenerSnapshotClient",
    "GECKOTERMINAL_SOURCE",
    "GeckoTerminalSnapshotClient",
    "ProviderStickySnapshotClient",
    "SNAPSHOT_SOURCE",
]
