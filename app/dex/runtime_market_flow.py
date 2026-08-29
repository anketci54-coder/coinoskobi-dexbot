from collections import Counter, OrderedDict
import threading
import time

from app.dex.native_ingestion import SWAP_TOPIC
from app.risk.stream_stats import (
    cusum_step,
    ewma_variance_step,
    log_change,
)


STREAM_MATH_VERSION = "STREAM_MATH_V1"


def _address(value):
    if value is None:
        return None

    value = str(value).strip().lower()

    if not value:
        return None

    return value


def _number(value):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None

    if value < 0:
        return None

    return value


def _text(value):
    if value is None:
        return None

    value = str(value).strip().lower()

    if not value:
        return None

    return value


def _integer(value):
    try:
        value = int(value)
    except (TypeError, ValueError):
        return None

    if value < 0:
        return None

    return value


def _topic_address(value):
    if not value:
        return None

    raw = str(value).lower()

    if raw.startswith("0x"):
        raw = raw[2:]

    if len(raw) < 40:
        return None

    return "0x" + raw[-40:]


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
                    i * 64:
                    (i + 1) * 64
                ],
                16,
            )
            for i in range(count)
        ]
    except ValueError:
        return None


def decode_v2_swap(event):
    event = event or {}

    topics = event.get("topics") or []

    if not topics:
        return {
            "state": "UNKNOWN",
            "reason": "TOPIC_MISSING",
        }

    if str(topics[0]).lower() != SWAP_TOPIC:
        return {
            "state": "UNKNOWN",
            "reason": "NOT_SWAP",
        }

    words = _decode_words(
        event.get("data"),
        4,
    )

    if words is None:
        return {
            "state": "UNKNOWN",
            "reason": "INVALID_SWAP_DATA",
        }

    (
        amount0_in,
        amount1_in,
        amount0_out,
        amount1_out,
    ) = words

    sender = (
        _topic_address(topics[1])
        if len(topics) > 1
        else None
    )

    recipient = (
        _topic_address(topics[2])
        if len(topics) > 2
        else None
    )

    return {
        "state": "DECODED",
        "amount0_in": amount0_in,
        "amount1_in": amount1_in,
        "amount0_out": amount0_out,
        "amount1_out": amount1_out,
        "sender": sender,
        "recipient": recipient,
        "decision_authority": False,
        "execution_authority": False,
    }


class RuntimeMarketFlowStore:
    """
    Bounded operational market/flow observation store.

    Scanner candidate data supplies:
    - USD volume
    - USD liquidity
    - price

    Native V2 Swap logs supply:
    - directional swap count
    - unique directional actors
    - real event provenance

    Raw token amounts are NOT labelled as USD.
    Missing evidence remains UNKNOWN.
    """

    def __init__(
        self,
        # WSS active target set is capped at 256. Keep bounded
        # state headroom so target rotation cannot evict still-active
        # pair history before the next observation cycle.
        max_pairs=512,
        max_events_per_pair=2048,
        require_membership_confirmation=False,
        stream_math_calibration=None,
    ):
        self.max_pairs = max(
            1,
            int(max_pairs),
        )

        self.max_events_per_pair = max(
            1,
            int(max_events_per_pair),
        )

        self.require_membership_confirmation = bool(
            require_membership_confirmation
        )

        self.stream_math_calibration = dict(
            stream_math_calibration
            or {}
        )

        self._pairs = OrderedDict()
        self._events = {}
        self._snapshot_state = {}

        self._stream_math_state = {}

        self._event_condition = threading.Condition()

        self.accepted_events = 0
        self.retracted_events = 0
        self.unknown_events = 0
        self.dropped_events = 0

    @property
    def pair_count(self):
        return len(self._pairs)

    @property
    def event_count(self):
        return sum(
            len(events)
            for events in self._events.values()
        )

    def register_pair(
        self,
        pair,
        token,
        quote_token,
    ):
        pair = _address(pair)
        token = _address(token)
        quote = _address(quote_token)

        if not pair or not token or not quote:
            return {
                "state": "INVALID",
            }

        if token == quote:
            return {
                "state": "INVALID",
            }

        try:
            token_int = int(token, 16)
            quote_int = int(quote, 16)
        except ValueError:
            return {
                "state": "INVALID",
            }

        if (
            pair not in self._pairs
            and len(self._pairs)
            >= self.max_pairs
        ):
            oldest, _ = self._pairs.popitem(
                last=False
            )

            self._events.pop(
                oldest,
                None,
            )

            self._snapshot_state.pop(
                oldest,
                None,
            )

            for key in list(
                self._stream_math_state
            ):
                if (
                    isinstance(key, tuple)
                    and len(key) >= 3
                    and key[2] == oldest
                ):
                    self._stream_math_state.pop(
                        key,
                        None,
                    )

        self._pairs.pop(
            pair,
            None,
        )

        self._pairs[pair] = {
            "pair": pair,
            "token": token,
            "quote_token": quote,
            "token_is_0": (
                token_int < quote_int
            ),
            "membership_verified": (
                not self.require_membership_confirmation
            ),
        }

        self._events.setdefault(
            pair,
            OrderedDict(),
        )

        return {
            "state": "REGISTERED",
            "pair": pair,
            "token": token,
            "quote_token": quote,
            "token_is_0": (
                token_int < quote_int
            ),
            "decision_authority": False,
            "execution_authority": False,
        }

    def confirm_pair_membership(
        self,
        pair,
        token,
        quote_token,
    ):
        pair = _address(pair)
        token = _address(token)
        quote = _address(quote_token)

        meta = self._pairs.get(pair)

        if meta is None:
            return {
                "state": "UNKNOWN_PAIR",
                "membership_verified": False,
            }

        configured = {
            meta["token"],
            meta["quote_token"],
        }

        observed = {
            token,
            quote,
        }

        if (
            None in observed
            or configured != observed
        ):
            meta["membership_verified"] = False

            return {
                "state": "MISMATCH",
                "membership_verified": False,
                "decision_authority": False,
                "execution_authority": False,
            }

        meta["membership_verified"] = True

        return {
            "state": "VERIFIED",
            "membership_verified": True,
            "decision_authority": False,
            "execution_authority": False,
        }

    def observe_event(self, event):
        event = dict(event or {})

        pair = _address(
            event.get("address")
        )

        identity = event.get(
            "event_identity"
        )

        if (
            not pair
            or pair not in self._pairs
            or not identity
        ):
            self.unknown_events += 1

            return {
                "state": "IGNORED",
                "reason": "PAIR_OR_IDENTITY_UNKNOWN",
            }

        decoded = decode_v2_swap(
            event
        )

        if decoded.get("state") != "DECODED":
            self.unknown_events += 1

            return {
                "state": "IGNORED",
                "reason": decoded.get(
                    "reason",
                    "DECODE_FAILED",
                ),
            }

        meta = self._pairs[pair]

        direction = self._direction(
            meta,
            decoded,
        )

        row = {
            "event_identity": identity,
            "direction": direction,
            "sender": decoded.get(
                "sender"
            ),
            "transaction_hash": (
                event.get(
                    "transaction_hash"
                )
            ),
            "block_number": (
                event.get(
                    "block_number"
                )
            ),
            "log_index": (
                event.get(
                    "log_index"
                )
            ),
        }

        with self._event_condition:
            events = self._events[
                pair
            ]

            if identity in events:
                events.pop(
                    identity,
                    None,
                )

            events[
                identity
            ] = row

            while (
                len(events)
                > self.max_events_per_pair
            ):
                events.popitem(
                    last=False
                )

                self.dropped_events += 1

            self.accepted_events += 1
            self._event_condition.notify_all()

        return {
            "state": "OBSERVED",
            "pair": pair,
            "direction": direction,
            "event_identity": identity,
            "decision_authority": False,
            "execution_authority": False,
        }

    def wait_for_market_evidence(
        self,
        pairs,
        *,
        timeout=10.0,
    ):
        if isinstance(pairs, str):
            requested = [
                _address(pairs)
            ]
        else:
            requested = [
                _address(pair)
                for pair in (pairs or [])
            ]

        requested = [
            pair
            for pair in dict.fromkeys(
                requested
            )
            if pair
        ]

        timeout = max(
            0.0,
            float(timeout),
        )

        if not requested:
            return {
                "state": "NO_TARGETS",
                "requested": 0,
                "ready": 0,
                "pending": 0,
                "timeout": timeout,
                "decision_authority": False,
                "execution_authority": False,
            }

        def ready_pairs():
            ready = []

            for pair in requested:
                events = self._events.get(
                    pair,
                    OrderedDict(),
                )

                bull_actors = {
                    row.get("sender")
                    for row in events.values()
                    if (
                        row.get("direction")
                        == "BULL"
                        and row.get("sender")
                    )
                }

                bear_actors = {
                    row.get("sender")
                    for row in events.values()
                    if (
                        row.get("direction")
                        == "BEAR"
                        and row.get("sender")
                    )
                }

                if bull_actors and bear_actors:
                    ready.append(pair)

            return ready

        deadline = (
            time.monotonic()
            + timeout
        )

        with self._event_condition:
            while True:
                ready = ready_pairs()

                if len(ready) == len(
                    requested
                ):
                    state = "READY"
                    break

                remaining = (
                    deadline
                    - time.monotonic()
                )

                if remaining <= 0:
                    state = (
                        "PARTIAL"
                        if ready
                        else "TIMEOUT"
                    )
                    break

                self._event_condition.wait(
                    timeout=remaining
                )

        return {
            "state": state,
            "requested": len(requested),
            "ready": len(ready),
            "pending": (
                len(requested)
                - len(ready)
            ),
            "ready_pairs": list(ready),
            "timeout": timeout,
            "decision_authority": False,
            "execution_authority": False,
        }

    def observe_retraction(
        self,
        event,
    ):
        event = dict(event or {})

        pair = _address(
            event.get("address")
        )

        identity = (
            event.get(
                "retracts_event_identity"
            )
            or event.get(
                "event_identity"
            )
        )

        if (
            not pair
            or pair not in self._events
            or not identity
        ):
            return {
                "state": "IGNORED",
            }

        removed = self._events[
            pair
        ].pop(
            identity,
            None,
        )

        if removed is not None:
            self.retracted_events += 1

            return {
                "state": "RETRACTED",
                "event_identity": identity,
            }

        return {
            "state": "NOT_FOUND",
            "event_identity": identity,
        }

    def snapshot(
        self,
        pair,
        candidate=None,
    ):
        pair = _address(pair)
        candidate = dict(
            candidate or {}
        )

        meta = self._pairs.get(
            pair
        )

        events = (
            self._events.get(
                pair,
                OrderedDict(),
            )
            if pair
            else OrderedDict()
        )

        real_market = self._market_input(
            candidate,
            events,
        )

        real_flow = self._flow_input(
            pair,
            candidate,
            events,
        )

        stream_math = self._stream_math_input(
            pair,
            candidate,
        )

        state = (
            "READY"
            if (
                real_market.get(
                    "evidence_ready"
                )
                or real_flow.get(
                    "evidence_ready"
                )
            )
            else "UNKNOWN"
        )

        return {
            "state": state,
            "pair_registered": (
                meta is not None
            ),
            "pair": pair,
            "market_intelligence": (
                real_market
            ),
            "flow_intelligence": (
                real_flow
            ),
            "stream_math": (
                stream_math
            ),
            "native_event_count": (
                len(events)
            ),
            "source": (
                "SCANNER_PLUS_NATIVE_WSS"
            ),
            "synthetic": False,
            "decision_authority": False,
            "paper_authority": False,
            "live_authority": False,
            "wallet_authority": False,
            "execution_authority": False,
        }

    def _stream_math_input(
        self,
        pair,
        candidate,
    ):
        candidate = dict(
            candidate or {}
        )

        chain = _text(
            candidate.get("chain")
        )
        dex = _text(
            candidate.get("dex")
        )
        source = _text(
            candidate.get("source")
        )
        pair = _address(pair)

        identity = {
            "chain": chain,
            "dex": dex,
            "pair": pair,
            "source": source,
            "model_version": (
                STREAM_MATH_VERSION
            ),
        }

        if not all(
            (
                chain,
                dex,
                pair,
                source,
            )
        ):
            return {
                "state": "UNKNOWN",
                "reason": (
                    "STREAM_IDENTITY_INCOMPLETE"
                ),
                "identity": identity,
                "price_log_return": None,
                "liquidity_log_change": None,
                "ewma": {
                    "state": "UNKNOWN",
                },
                "liquidity_cusum": {
                    "state": "UNKNOWN",
                },
                "decision_authority": False,
                "paper_authority": False,
                "live_authority": False,
                "wallet_authority": False,
                "execution_authority": False,
            }

        key = (
            chain,
            dex,
            pair,
            source,
            STREAM_MATH_VERSION,
        )

        for existing_key in list(
            self._stream_math_state
        ):
            if (
                existing_key != key
                and existing_key[0] == chain
                and existing_key[1] == dex
                and existing_key[2] == pair
                and existing_key[4]
                    == STREAM_MATH_VERSION
            ):
                self._stream_math_state.pop(
                    existing_key,
                    None,
                )

        previous = (
            self._stream_math_state.get(
                key
            )
            or {}
        )

        price = _number(
            candidate.get("price_usd")
        )
        liquidity = _number(
            candidate.get("liquidity")
        )

        if price is not None and price <= 0:
            price = None

        if (
            liquidity is not None
            and liquidity <= 0
        ):
            liquidity = None

        price_log_return = log_change(
            price,
            previous.get("price_usd"),
        )

        liquidity_log_change = log_change(
            liquidity,
            previous.get(
                "liquidity_usd"
            ),
        )

        ewma = ewma_variance_step(
            price_log_return,
            previous_variance=(
                previous.get(
                    "ewma_variance"
                )
            ),
            decay=(
                self.stream_math_calibration
                .get("ewma_decay")
            ),
        )

        liquidity_cusum = cusum_step(
            liquidity_log_change,
            previous_up=(
                previous.get(
                    "liquidity_cusum_up",
                    0.0,
                )
            ),
            previous_down=(
                previous.get(
                    "liquidity_cusum_down",
                    0.0,
                )
            ),
            reference=(
                self.stream_math_calibration
                .get("cusum_reference")
            ),
            threshold=(
                self.stream_math_calibration
                .get("cusum_threshold")
            ),
        )

        if not previous:
            state = "WARMING"

        elif (
            ewma.get("state") == "READY"
            or liquidity_cusum.get(
                "state"
            ) == "READY"
        ):
            state = "READY"

        elif (
            ewma.get("state")
            == "UNCALIBRATED"
            or liquidity_cusum.get(
                "state"
            ) == "UNCALIBRATED"
        ):
            state = "UNCALIBRATED"

        else:
            state = "WARMING"

        ewma_variance = previous.get(
            "ewma_variance"
        )

        if ewma.get("state") == "READY":
            ewma_variance = ewma.get(
                "ewma_variance"
            )

        cusum_up = previous.get(
            "liquidity_cusum_up",
            0.0,
        )
        cusum_down = previous.get(
            "liquidity_cusum_down",
            0.0,
        )

        if (
            liquidity_cusum.get("state")
            == "READY"
        ):
            cusum_up = liquidity_cusum.get(
                "up_cusum"
            )
            cusum_down = (
                liquidity_cusum.get(
                    "down_cusum"
                )
            )

        self._stream_math_state[
            key
        ] = {
            "price_usd": price,
            "liquidity_usd": liquidity,
            "ewma_variance": ewma_variance,
            "liquidity_cusum_up": cusum_up,
            "liquidity_cusum_down": (
                cusum_down
            ),
        }

        return {
            "state": state,
            "reason": None,
            "identity": identity,
            "price_log_return": (
                price_log_return
            ),
            "liquidity_log_change": (
                liquidity_log_change
            ),
            "ewma": ewma,
            "liquidity_cusum": (
                liquidity_cusum
            ),
            "decision_authority": False,
            "paper_authority": False,
            "live_authority": False,
            "wallet_authority": False,
            "execution_authority": False,
        }

    def _market_input(
        self,
        candidate,
        events,
    ):
        liquidity = _number(
            candidate.get("liquidity")
        )

        volume = _number(
            candidate.get(
                "volume_24h",
                candidate.get(
                    "volume24"
                ),
            )
        )

        buys_scanner = _integer(
            candidate.get(
                "buys_24h",
                candidate.get(
                    "buys24"
                ),
            )
        )

        directions = Counter(
            row.get("direction")
            for row in events.values()
        )

        buyers = {
            row.get("sender")
            for row in events.values()
            if (
                row.get("direction")
                == "BULL"
                and row.get("sender")
            )
        }

        sellers = {
            row.get("sender")
            for row in events.values()
            if (
                row.get("direction")
                == "BEAR"
                and row.get("sender")
            )
        }

        evidence_ready = any(
            value is not None
            for value in (
                liquidity,
                volume,
                buys_scanner,
            )
        ) or bool(events)

        result = {
            "evidence_ready": (
                evidence_ready
            ),
            "source": (
                "REAL_RUNTIME"
            ),
            "synthetic": False,
        }

        if liquidity is not None:
            result[
                "liquidity_usd"
            ] = liquidity

        if volume is not None:
            result[
                "volume_usd"
            ] = volume

        # Native directional counters override
        # scanner buy-only counter when native evidence exists.
        if events:
            result[
                "buys"
            ] = directions["BULL"]

            result[
                "sells"
            ] = directions["BEAR"]

            result[
                "buyers"
            ] = len(buyers)

            result[
                "sellers"
            ] = len(sellers)

        elif buys_scanner is not None:
            result[
                "buys"
            ] = buys_scanner

        previous = self._snapshot_state.get(
            _address(
                candidate.get("pool")
            )
        ) or {}

        previous_liquidity = (
            previous.get(
                "liquidity_usd"
            )
        )

        if previous_liquidity is not None:
            result[
                "previous_liquidity_usd"
            ] = previous_liquidity

        return result

    def _flow_input(
        self,
        pair,
        candidate,
        events,
    ):
        bull = [
            row
            for row in events.values()
            if row.get("direction")
            == "BULL"
        ]

        bear = [
            row
            for row in events.values()
            if row.get("direction")
            == "BEAR"
        ]

        directional_count = (
            len(bull)
            + len(bear)
        )

        total = len(events)

        if directional_count == 0:
            return {
                "evidence_ready": False,
                "freshness": "UNKNOWN",
                "coverage": 0.0,
                "source": "NATIVE_WSS",
                "synthetic": False,
            }

        spread = (
            len(bull)
            - len(bear)
        )

        previous = (
            self._snapshot_state.get(
                pair
            )
            or {}
        )

        prev_spread = previous.get(
            "spread"
        )

        prev_velocity = previous.get(
            "velocity"
        )

        velocity = (
            spread - prev_spread
            if prev_spread is not None
            else None
        )

        price = _number(
            candidate.get(
                "price_usd"
            )
        )

        previous_price = previous.get(
            "price_usd"
        )

        if (
            price is not None
            and previous_price is not None
        ):
            if price > previous_price:
                price_direction = "BULL"
            elif price < previous_price:
                price_direction = "BEAR"
            else:
                price_direction = "UNKNOWN"
        else:
            price_direction = "UNKNOWN"

        if len(bull) > len(bear):
            direction = "BULL"
        elif len(bear) > len(bull):
            direction = "BEAR"
        else:
            direction = "UNKNOWN"

        actor_counts = Counter(
            row.get("sender")
            for row in events.values()
            if row.get("sender")
        )

        unique_wallets = len(
            actor_counts
        )

        largest_actor_share = (
            max(
                actor_counts.values()
            ) / total
            if (
                actor_counts
                and total > 0
            )
            else None
        )

        coverage = (
            directional_count / total
            if total > 0
            else 0.0
        )

        self._snapshot_state[
            pair
        ] = {
            "spread": spread,
            "velocity": velocity,
            "price_usd": price,
            "liquidity_usd": (
                _number(
                    candidate.get(
                        "liquidity"
                    )
                )
            ),
        }

        return {
            "evidence_ready": True,
            "buy_flow": len(bull),
            "sell_flow": len(bear),
            "prev_spread": prev_spread,
            "prev_velocity": prev_velocity,
            "direction": direction,
            "price_direction": (
                price_direction
            ),
            "unique_wallets": (
                unique_wallets
            ),
            "tx_count": total,
            "largest_actor_share": (
                largest_actor_share
            ),
            "freshness": "FRESH",
            "coverage": coverage,
            "source": "NATIVE_WSS",
            "synthetic": False,
        }

    @staticmethod
    def _direction(
        meta,
        decoded,
    ):
        if not meta.get(
            "membership_verified",
            True,
        ):
            return "UNKNOWN"

        token_is_0 = meta[
            "token_is_0"
        ]

        if token_is_0:
            target_in = decoded[
                "amount0_in"
            ]
            target_out = decoded[
                "amount0_out"
            ]

            quote_in = decoded[
                "amount1_in"
            ]
            quote_out = decoded[
                "amount1_out"
            ]

        else:
            target_in = decoded[
                "amount1_in"
            ]
            target_out = decoded[
                "amount1_out"
            ]

            quote_in = decoded[
                "amount0_in"
            ]
            quote_out = decoded[
                "amount0_out"
            ]

        # Target token leaves pool while quote enters:
        # user acquired target token -> BULL.
        if (
            target_out > 0
            and quote_in > 0
            and target_in == 0
        ):
            return "BULL"

        # Target token enters pool while quote leaves:
        # user sold target token -> BEAR.
        if (
            target_in > 0
            and quote_out > 0
            and target_out == 0
        ):
            return "BEAR"

        return "UNKNOWN"

    def status(self):
        return {
            "state": "READY",
            "pair_count": (
                self.pair_count
            ),
            "event_count": (
                self.event_count
            ),
            "max_pairs": (
                self.max_pairs
            ),
            "max_events_per_pair": (
                self.max_events_per_pair
            ),
            "accepted_events": (
                self.accepted_events
            ),
            "retracted_events": (
                self.retracted_events
            ),
            "unknown_events": (
                self.unknown_events
            ),
            "dropped_events": (
                self.dropped_events
            ),
            "bounded": True,
            "synthetic": False,
            "decision_authority": False,
            "paper_authority": False,
            "live_authority": False,
            "wallet_authority": False,
            "execution_authority": False,
        }
