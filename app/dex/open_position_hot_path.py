import json
import math
import threading

from app.dex.native_ingestion import SYNC_TOPIC


def _address(value):
    value = str(value or "").strip().lower()

    if value.startswith("bsc_"):
        value = value[4:]

    return value or None


def _positive_number(value):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None

    if not math.isfinite(value) or value <= 0:
        return None

    return value


def _decode_words(data, count):
    if not isinstance(data, str):
        return None

    raw = data[2:] if data.startswith("0x") else data

    if len(raw) < 64 * count:
        return None

    try:
        return [
            int(
                raw[
                    index * 64:
                    (index + 1) * 64
                ],
                16,
            )
            for index in range(count)
        ]
    except ValueError:
        return None


def decode_v2_sync(event):
    event = event or {}
    topics = event.get("topics") or []

    if (
        not topics
        or str(topics[0]).lower() != SYNC_TOPIC
    ):
        return {
            "state": "IGNORED",
            "reason": "NOT_SYNC",
        }

    words = _decode_words(
        event.get("data"),
        2,
    )

    if words is None:
        return {
            "state": "IGNORED",
            "reason": "INVALID_SYNC_DATA",
        }

    reserve0, reserve1 = words

    if reserve0 <= 0 or reserve1 <= 0:
        return {
            "state": "IGNORED",
            "reason": "NON_POSITIVE_RESERVE",
        }

    pair = _address(
        event.get("address")
    )

    if not pair:
        return {
            "state": "IGNORED",
            "reason": "PAIR_MISSING",
        }

    return {
        "state": "DECODED",
        "pair": pair,
        "reserve0": reserve0,
        "reserve1": reserve1,
        "decision_authority": False,
        "paper_authority": False,
        "live_authority": False,
        "wallet_authority": False,
        "execution_authority": False,
    }


def _opening_context(position):
    raw = (position or {}).get(
        "opening_context_json"
    )

    if not raw:
        return {}

    if isinstance(raw, dict):
        return dict(raw)

    try:
        value = json.loads(raw)
    except (
        TypeError,
        ValueError,
        json.JSONDecodeError,
    ):
        return {}

    return (
        value
        if isinstance(value, dict)
        else {}
    )


def _open_positions(pipeline):
    manager = getattr(
        pipeline,
        "manager",
        None,
    )

    db = getattr(
        manager,
        "db",
        None,
    )

    reader = getattr(
        db,
        "open_positions",
        None,
    )

    if not callable(reader):
        return []

    try:
        return list(reader() or [])
    except Exception:
        return []


def _cache_rows(pipeline):
    cache = getattr(
        pipeline,
        "cache",
        None,
    )

    reader = getattr(
        cache,
        "all",
        None,
    )

    if not callable(reader):
        return []

    try:
        return list(reader() or [])
    except Exception:
        return []


def _position_pool(
    pipeline,
    position,
    *,
    cache_by_token=None,
):
    position = position or {}
    context = _opening_context(
        position
    )
    raw_signals = context.get(
        "raw_signals"
    ) or {}

    pool = _address(
        position.get("pool")
        or raw_signals.get("pool")
    )

    if pool:
        return pool

    token = _address(
        position.get("token")
        or raw_signals.get("token")
    )

    if not token:
        return None

    if cache_by_token:
        cached = cache_by_token.get(
            token
        )

        if cached:
            return _address(
                cached.get("pool")
            )

    cache = getattr(
        pipeline,
        "cache",
        None,
    )

    finder = getattr(
        cache,
        "pool_for_token",
        None,
    )

    if not callable(finder):
        return None

    try:
        return _address(
            finder(token)
        )
    except Exception:
        return None


def open_position_signature(
    pipeline,
):
    pools = []
    unresolved = []

    for position in _open_positions(
        pipeline
    ):
        pool = _position_pool(
            pipeline,
            position,
        )

        if pool:
            pools.append(pool)
        else:
            unresolved.append(
                _address(
                    position.get("token")
                )
                or "UNKNOWN"
            )

    return (
        tuple(sorted(set(pools))),
        tuple(sorted(set(unresolved))),
    )


def open_position_targets(
    pipeline,
    *,
    max_pairs=30,
):
    limit = max(
        1,
        int(max_pairs),
    )

    cache_rows = _cache_rows(
        pipeline
    )

    cache_by_pool = {}
    cache_by_token = {}

    for row in cache_rows:
        pool = _address(
            row.get("pool")
        )
        token = _address(
            row.get("token")
            or row.get("base_token")
        )

        if pool:
            cache_by_pool[pool] = row

        if token:
            cache_by_token[token] = row

    verifier = getattr(
        pipeline,
        "pair_membership_verifier",
        None,
    )

    targets = []
    seen = set()

    for position in _open_positions(
        pipeline
    ):
        context = _opening_context(
            position
        )

        raw_signals = context.get(
            "raw_signals"
        ) or {}

        token = _address(
            position.get("token")
            or raw_signals.get("token")
        )

        pool = _position_pool(
            pipeline,
            position,
            cache_by_token=cache_by_token,
        )

        cached = cache_by_pool.get(
            pool
        ) or {}

        quote = _address(
            raw_signals.get("quote_token")
            or cached.get("quote_token")
        )

        dex = str(
            position.get("dex")
            or raw_signals.get("dex")
            or cached.get("dex")
            or "pancakeswap_v2"
        ).strip().lower()

        if dex not in {
            "pancakeswap_v2",
            "pancakeswap-v2",
        }:
            continue

        if (
            not pool
            or not token
            or not quote
            or pool in seen
        ):
            continue

        if callable(verifier):
            try:
                membership = verifier(
                    pool,
                    token,
                    quote,
                )
            except Exception:
                continue

            if (
                not isinstance(membership, dict)
                or membership.get("state")
                != "VERIFIED"
            ):
                continue

        seen.add(pool)
        targets.append({
            "pair": pool,
            "token": token,
            "quote_token": quote,
            "membership_verified": True,
            "target_source": "OPEN_POSITION",
        })

        if len(targets) >= limit:
            break

    return targets


def merge_wss_targets(
    pipeline,
    scanner_targets,
    *,
    max_pairs=256,
):
    limit = max(
        1,
        int(max_pairs),
    )

    open_targets = open_position_targets(
        pipeline,
        max_pairs=min(
            30,
            limit,
        ),
    )

    open_pairs = {
        target["pair"]
        for target in open_targets
    }

    merged = []
    seen = set()

    for target in [
        *open_targets,
        *(scanner_targets or []),
    ]:
        pair = _address(
            target.get("pair")
        )
        token = _address(
            target.get("token")
        )
        quote = _address(
            target.get("quote_token")
        )

        if (
            not pair
            or not token
            or not quote
            or pair in seen
        ):
            continue

        normalized = dict(target)
        normalized.update({
            "pair": pair,
            "token": token,
            "quote_token": quote,
            "hot_open_position": (
                pair in open_pairs
            ),
        })

        seen.add(pair)
        merged.append(normalized)

        if len(merged) >= limit:
            break

    retained_open = (
        open_pairs.intersection(seen)
    )

    return {
        "state": "READY",
        "targets": merged,
        "open_pairs": sorted(
            retained_open
        ),
        "open_target_count": len(
            retained_open
        ),
        "address_count": len(merged),
        "bounded": True,
        "decision_authority": False,
        "paper_authority": False,
        "live_authority": False,
        "wallet_authority": False,
        "execution_authority": False,
    }


class HotPositionWSSBridge:
    """
    Thread-safe bridge between WSS Sync observations and the main-thread
    paper lifecycle.

    The WSS thread never touches SQLite. It stores only the latest exact
    Pancake V2 reserve ratio for bounded tracked pairs. The main thread
    anchors that ratio to the current exact-pool cached USD price and can
    then derive subsequent relative USD price movement without provider
    polling or fabricated stop fills.
    """

    def __init__(
        self,
        max_pairs=256,
    ):
        self.max_pairs = max(
            1,
            int(max_pairs),
        )

        self._lock = threading.Lock()
        self._targets = {}
        self._open_pairs = set()
        self._latest_ratio = {}
        self._anchor_ratio = {}
        self._anchor_price = {}
        self._dirty = set()

        self.sync_count = 0
        self.baseline_count = 0
        self.queued_count = 0
        self.retraction_count = 0
        self.dropped_count = 0
        self.anchor_count = 0

    def replace_targets(
        self,
        targets,
        *,
        open_pairs=None,
    ):
        normalized = {}

        for target in targets or []:
            if len(normalized) >= self.max_pairs:
                break

            pair = _address(
                target.get("pair")
            )
            token = _address(
                target.get("token")
            )
            quote = _address(
                target.get("quote_token")
            )

            if (
                not pair
                or not token
                or not quote
                or token == quote
            ):
                continue

            try:
                token_is_0 = (
                    int(token, 16)
                    < int(quote, 16)
                )
            except ValueError:
                continue

            normalized[pair] = {
                "pair": pair,
                "token": token,
                "quote_token": quote,
                "token_is_0": token_is_0,
            }

        requested_open = {
            _address(pair)
            for pair in (
                open_pairs
                or []
            )
        }

        requested_open.discard(None)

        with self._lock:
            old_targets = self._targets

            reset = set(
                old_targets
            ) - set(normalized)

            for pair, meta in normalized.items():
                previous = old_targets.get(
                    pair
                )

                if (
                    previous is not None
                    and previous.get("token_is_0")
                    != meta.get("token_is_0")
                ):
                    reset.add(pair)

            for pair in reset:
                self._latest_ratio.pop(
                    pair,
                    None,
                )
                self._anchor_ratio.pop(
                    pair,
                    None,
                )
                self._anchor_price.pop(
                    pair,
                    None,
                )
                self._dirty.discard(pair)

            self._targets = normalized
            self._open_pairs = (
                requested_open
                .intersection(normalized)
            )

            for pair in list(
                self._dirty
            ):
                if pair not in self._open_pairs:
                    self._dirty.discard(pair)

            return {
                "state": "READY",
                "target_count": len(
                    self._targets
                ),
                "open_pair_count": len(
                    self._open_pairs
                ),
                "bounded": True,
                "decision_authority": False,
                "execution_authority": False,
            }

    def observe_event(
        self,
        event,
    ):
        decoded = decode_v2_sync(
            event
        )

        if decoded.get("state") != "DECODED":
            return decoded

        pair = decoded["pair"]

        with self._lock:
            meta = self._targets.get(
                pair
            )

            if meta is None:
                self.dropped_count += 1
                return {
                    "state": "IGNORED",
                    "reason": "PAIR_NOT_TRACKED",
                }

            reserve0 = decoded[
                "reserve0"
            ]
            reserve1 = decoded[
                "reserve1"
            ]

            ratio = (
                reserve1 / reserve0
                if meta["token_is_0"]
                else reserve0 / reserve1
            )

            if (
                not math.isfinite(ratio)
                or ratio <= 0
            ):
                self.dropped_count += 1
                return {
                    "state": "IGNORED",
                    "reason": "PRICE_RATIO_INVALID",
                }

            self.sync_count += 1
            first = pair not in self._latest_ratio
            self._latest_ratio[pair] = ratio

            if first:
                self.baseline_count += 1

            if pair in self._open_pairs:
                self._dirty.add(pair)
                self.queued_count += 1

                return {
                    "state": (
                        "BASELINED"
                        if first
                        else "HOT_PRICE_QUEUED"
                    ),
                    "pair": pair,
                    "open_position": True,
                    "decision_authority": False,
                    "paper_authority": False,
                    "live_authority": False,
                    "wallet_authority": False,
                    "execution_authority": False,
                }

            return {
                "state": (
                    "BASELINED"
                    if first
                    else "TRACKED"
                ),
                "pair": pair,
                "open_position": False,
                "decision_authority": False,
                "execution_authority": False,
            }

    def observe_retraction(
        self,
        event,
    ):
        pair = _address(
            (event or {}).get(
                "address"
            )
        )

        if not pair:
            return {
                "state": "IGNORED",
                "reason": "PAIR_MISSING",
            }

        with self._lock:
            self._latest_ratio.pop(
                pair,
                None,
            )
            self._anchor_ratio.pop(
                pair,
                None,
            )
            self._anchor_price.pop(
                pair,
                None,
            )
            self._dirty.discard(pair)
            self.retraction_count += 1

        return {
            "state": "RESET",
            "pair": pair,
            "decision_authority": False,
            "execution_authority": False,
        }

    def anchor_from_cache(
        self,
        pipeline,
    ):
        rows = _cache_rows(
            pipeline
        )

        cache_by_pool = {
            _address(row.get("pool")): row
            for row in rows
            if _address(row.get("pool"))
        }

        anchored = []

        with self._lock:
            for pair in self._open_pairs:
                ratio = self._latest_ratio.get(
                    pair
                )
                price = _positive_number(
                    (
                        cache_by_pool.get(pair)
                        or {}
                    ).get("price_usd")
                )

                if ratio is None or price is None:
                    continue

                self._anchor_ratio[pair] = ratio
                self._anchor_price[pair] = price
                self._dirty.discard(pair)
                anchored.append(pair)

            self.anchor_count += len(
                anchored
            )

        return {
            "state": (
                "ANCHORED"
                if anchored
                else "NO_ANCHOR"
            ),
            "anchored": len(anchored),
            "anchored_pools": anchored,
            "decision_authority": False,
            "execution_authority": False,
        }

    def drain_price_updates(
        self,
        pipeline,
    ):
        with self._lock:
            dirty = list(
                self._dirty
            )
            open_pairs = set(
                self._open_pairs
            )
            latest = {
                pair: self._latest_ratio.get(pair)
                for pair in dirty
            }
            anchors = {
                pair: (
                    self._anchor_ratio.get(pair),
                    self._anchor_price.get(pair),
                )
                for pair in dirty
            }

        if not dirty:
            return {
                "state": "IDLE",
                "pending": 0,
                "updated": 0,
                "anchored": 0,
                "failed": 0,
                "updated_pools": [],
                "bounded": True,
                "decision_authority": False,
                "execution_authority": False,
            }

        cache = getattr(
            pipeline,
            "cache",
            None,
        )

        reader = getattr(
            cache,
            "all",
            None,
        )

        updater = getattr(
            cache,
            "update_pool_price",
            None,
        )

        if (
            not callable(reader)
            or not callable(updater)
        ):
            return {
                "state": "CACHE_UNAVAILABLE",
                "pending": len(dirty),
                "updated": 0,
                "anchored": 0,
                "failed": len(dirty),
                "updated_pools": [],
                "bounded": True,
                "decision_authority": False,
                "execution_authority": False,
            }

        rows = list(
            reader()
            or []
        )

        cache_by_pool = {
            _address(row.get("pool")): row
            for row in rows
            if _address(row.get("pool"))
        }

        updated_pools = []
        anchored_pools = []
        failed = 0

        for pair in dirty:
            if pair not in open_pairs:
                continue

            ratio = latest.get(pair)
            anchor_ratio, anchor_price = (
                anchors.get(pair)
                or (None, None)
            )

            current = _positive_number(
                (
                    cache_by_pool.get(pair)
                    or {}
                ).get("price_usd")
            )

            if ratio is None or current is None:
                failed += 1
                continue

            if (
                anchor_ratio is None
                or anchor_price is None
            ):
                with self._lock:
                    self._anchor_ratio[pair] = ratio
                    self._anchor_price[pair] = current
                    self._dirty.discard(pair)
                    self.anchor_count += 1

                anchored_pools.append(pair)
                continue

            updated_price = (
                anchor_price
                * ratio
                / anchor_ratio
            )

            if (
                not math.isfinite(
                    updated_price
                )
                or updated_price <= 0
            ):
                failed += 1
                continue

            try:
                changed = updater(
                    pair,
                    updated_price,
                )
            except Exception:
                failed += 1
                continue

            if changed:
                updated_pools.append(
                    pair
                )

                with self._lock:
                    if (
                        self._latest_ratio.get(pair)
                        == ratio
                    ):
                        self._dirty.discard(pair)
            else:
                failed += 1

        return {
            "state": (
                "UPDATED"
                if updated_pools
                else (
                    "ANCHORED"
                    if anchored_pools
                    else "NO_UPDATE"
                )
            ),
            "pending": len(dirty),
            "updated": len(
                updated_pools
            ),
            "anchored": len(
                anchored_pools
            ),
            "failed": failed,
            "updated_pools": updated_pools,
            "anchored_pools": anchored_pools,
            "bounded": True,
            "decision_authority": False,
            "paper_authority": False,
            "live_authority": False,
            "wallet_authority": False,
            "execution_authority": False,
        }

    def status(self):
        with self._lock:
            return {
                "state": "READY",
                "target_count": len(
                    self._targets
                ),
                "open_pair_count": len(
                    self._open_pairs
                ),
                "baseline_count": (
                    self.baseline_count
                ),
                "sync_count": self.sync_count,
                "queued_count": (
                    self.queued_count
                ),
                "pending_count": len(
                    self._dirty
                ),
                "retraction_count": (
                    self.retraction_count
                ),
                "dropped_count": (
                    self.dropped_count
                ),
                "anchor_count": (
                    self.anchor_count
                ),
                "max_pairs": self.max_pairs,
                "bounded": True,
                "sqlite_from_wss_thread": False,
                "decision_authority": False,
                "paper_authority": False,
                "live_authority": False,
                "wallet_authority": False,
                "execution_authority": False,
            }


class _ExactOpenPoolPrice:
    def __init__(
        self,
        token_prices,
        fallback,
    ):
        self.token_prices = dict(
            token_prices
        )
        self.fallback = fallback

    def get_price(self, token):
        key = _address(token)
        price = self.token_prices.get(
            key
        )

        if price is not None:
            return price

        return self.fallback.get_price(
            token
        )


def process_hot_positions(
    pipeline,
):
    manager = getattr(
        pipeline,
        "manager",
        None,
    )

    processor = getattr(
        manager,
        "process",
        None,
    )

    if not callable(processor):
        return []

    cache_rows = _cache_rows(
        pipeline
    )

    cache_by_pool = {
        _address(row.get("pool")): row
        for row in cache_rows
        if _address(row.get("pool"))
    }

    token_prices = {}

    for position in _open_positions(
        pipeline
    ):
        token = _address(
            position.get("token")
        )
        pool = _position_pool(
            pipeline,
            position,
        )
        row = cache_by_pool.get(
            pool
        ) or {}
        price = _positive_number(
            row.get("price_usd")
        )

        if token and price is not None:
            token_prices[token] = price

    previous_evidence = getattr(
        manager,
        "hybrid_exit_evidence",
        None,
    )

    previous_price = getattr(
        manager,
        "price",
        None,
    )

    runtime_evidence = getattr(
        pipeline,
        "_hybrid_exit_runtime_evidence",
        None,
    )

    if callable(runtime_evidence):
        manager.hybrid_exit_evidence = (
            runtime_evidence
        )

    if (
        previous_price is not None
        and token_prices
    ):
        manager.price = _ExactOpenPoolPrice(
            token_prices,
            previous_price,
        )

    try:
        return processor()
    finally:
        manager.hybrid_exit_evidence = (
            previous_evidence
        )

        if previous_price is not None:
            manager.price = previous_price
