import asyncio
import json
from collections import deque

from app.dex.connection_health import reconnect_delay
from app.dex.event_buffer import EventBuffer
from app.dex.event_integrity import validate_event_integrity
from app.dex.wss_subscription import (
    normalize_wss_event,
    subscribe_request,
    unsubscribe_request,
)


def default_connect_factory(url, **kwargs):
    from websockets.asyncio.client import connect

    return connect(
        url,
        **kwargs,
    )


class NativeWSSRuntime:
    def __init__(
        self,
        url,
        pair,
        *,
        max_buffer=1024,
        max_seen=4096,
        max_reconnects=5,
        receive_timeout=10.0,
        open_timeout=10.0,
        ping_interval=20.0,
        ping_timeout=20.0,
        close_timeout=5.0,
        connect_factory=None,
        sleep_func=None,
        on_event=None,
        on_retraction=None,
    ):
        if not url:
            raise ValueError("url required")

        if not pair:
            raise ValueError("pair required")

        self.url = url
        self.pair = pair

        self.max_reconnects = max(
            0,
            int(max_reconnects),
        )

        self.receive_timeout = max(
            0.01,
            float(receive_timeout),
        )

        self.open_timeout = max(
            0.01,
            float(open_timeout),
        )

        self.ping_interval = max(
            0.01,
            float(ping_interval),
        )

        self.ping_timeout = max(
            0.01,
            float(ping_timeout),
        )

        self.close_timeout = max(
            0.01,
            float(close_timeout),
        )

        self.connect_factory = (
            connect_factory
            or default_connect_factory
        )

        self.sleep_func = (
            sleep_func
            or asyncio.sleep
        )

        self.on_event = on_event
        self.on_retraction = on_retraction

        self.buffer = EventBuffer(
            max_buffer
        )

        self.max_seen = max(
            1,
            int(max_seen),
        )

        self._seen_order = deque()
        self._seen = set()

        self._stop = False
        self._ws = None

        self.last_block = None
        self.last_log_index = None

        self.connected = False
        self.subscription_id = None
        self.reconnect_count = 0

        self.accepted_count = 0
        self.duplicate_count = 0
        self.removed_count = 0
        self.retraction_count = 0
        self.rejected_count = 0
        self.out_of_order_count = 0
        self.message_count = 0
        self.subscription_mismatch_count = 0
        self.delivery_failure_count = 0

        self.last_error = None

    def request_stop(self):
        self._stop = True

    async def force_close(self):
        """
        Second-stage shutdown.

        Used only when graceful request_stop() cannot
        terminate the transport within the service timeout.
        """
        self.request_stop()

        ws = self._ws

        if ws is None:
            return False

        close = getattr(
            ws,
            "close",
            None,
        )

        if close is None:
            return False

        try:
            result = close()

            if asyncio.iscoroutine(result):
                await asyncio.wait_for(
                    result,
                    timeout=self.close_timeout,
                )

            return True

        except Exception:
            return False

    async def run(
        self,
        max_events=None,
    ):
        accepted_target = (
            None
            if max_events is None
            else max(
                0,
                int(max_events),
            )
        )

        if accepted_target == 0:
            return self.status()

        attempt = 0

        while not self._stop:
            try:
                await self._run_connection(
                    accepted_target
                )

                if (
                    accepted_target is not None
                    and self.accepted_count
                    >= accepted_target
                ):
                    break

                if self._stop:
                    break

                raise ConnectionError(
                    "WSS connection ended"
                )

            except asyncio.CancelledError:
                self.request_stop()
                raise

            except Exception as exc:
                self.connected = False
                self.subscription_id = None
                self.last_error = (
                    f"{type(exc).__name__}: {exc}"
                )

                if (
                    self._stop
                    or attempt
                    >= self.max_reconnects
                ):
                    break

                delay = reconnect_delay(
                    attempt,
                )

                attempt += 1
                self.reconnect_count += 1

                await self.sleep_func(
                    delay
                )

        return self.status()

    async def _run_connection(
        self,
        accepted_target,
    ):
        connect_cm = self.connect_factory(
            self.url,
            open_timeout=self.open_timeout,
            ping_interval=self.ping_interval,
            ping_timeout=self.ping_timeout,
            close_timeout=self.close_timeout,
            max_queue=32,
        )

        async with connect_cm as ws:
            self._ws = ws
            self.connected = True
            self.last_error = None

            subscription_id = await self._subscribe(
                ws
            )

            self.subscription_id = (
                subscription_id
            )

            try:
                while not self._stop:
                    if (
                        accepted_target is not None
                        and self.accepted_count
                        >= accepted_target
                    ):
                        break

                    raw = await asyncio.wait_for(
                        ws.recv(),
                        timeout=self.receive_timeout,
                    )

                    self.message_count += 1

                    message = _decode_message(
                        raw
                    )

                    await self._handle_message(
                        message
                    )

            finally:
                await self._unsubscribe(
                    ws
                )

                self.connected = False
                self.subscription_id = None
                self._ws = None

    async def _subscribe(self, ws):
        contract = subscribe_request(
            self.pair,
            request_id=1,
        )

        if contract.get("state") != "READY":
            raise RuntimeError(
                "subscription contract invalid"
            )

        await ws.send(
            json.dumps(
                contract["request"]
            )
        )

        raw = await asyncio.wait_for(
            ws.recv(),
            timeout=self.receive_timeout,
        )

        response = _decode_message(
            raw
        )

        if response.get("error"):
            raise RuntimeError(
                "subscription error: "
                f"{response['error']}"
            )

        if response.get("id") != 1:
            raise RuntimeError(
                "subscription response id mismatch"
            )

        subscription_id = response.get(
            "result"
        )

        if not subscription_id:
            raise RuntimeError(
                "subscription id missing"
            )

        return subscription_id

    async def _unsubscribe(self, ws):
        subscription_id = (
            self.subscription_id
        )

        if not subscription_id:
            return False

        contract = unsubscribe_request(
            subscription_id,
            request_id=2,
        )

        if contract.get("state") != "READY":
            return False

        try:
            await ws.send(
                json.dumps(
                    contract["request"]
                )
            )
            return True
        except Exception:
            return False

    async def _handle_message(
        self,
        message,
    ):
        normalized = normalize_wss_event(
            message
        )

        if normalized.get(
            "state"
        ) != "NORMALIZED":
            self.rejected_count += 1
            return

        # A notification from another or stale
        # subscription must never enter this runtime.
        if (
            normalized.get(
                "subscription_id"
            )
            != self.subscription_id
        ):
            self.subscription_mismatch_count += 1
            self.rejected_count += 1
            return

        integrity = validate_event_integrity(
            normalized,
            seen=self._seen,
            last_block=self.last_block,
            last_log_index=self.last_log_index,
        )

        state = integrity.get(
            "state"
        )

        if state == "DUPLICATE":
            self.duplicate_count += 1
            return

        if state == "REMOVED":
            await self._deliver_retraction(
                normalized,
                integrity[
                    "event_identity"
                ],
            )
            return

        if state == "OUT_OF_ORDER":
            self.out_of_order_count += 1
            return

        if state != "ACCEPTED":
            self.rejected_count += 1
            return

        identity = integrity[
            "event_identity"
        ]

        delivered = dict(
            normalized
        )

        delivered[
            "delivery_kind"
        ] = "EVENT"

        # IMPORTANT:
        # callback/downstream delivery occurs BEFORE
        # local acknowledgement (_remember / buffer /
        # accepted_count).
        #
        # If callback fails, the event remains unseen
        # and can be replayed after reconnect.
        await self._deliver(
            delivered
        )

        self._remember(
            identity
        )

        self.last_block = normalized.get(
            "block_number"
        )

        self.last_log_index = normalized.get(
            "log_index"
        )

        self.buffer.push(
            delivered
        )

        self.accepted_count += 1

    async def _deliver_retraction(
        self,
        normalized,
        identity,
    ):
        retraction = dict(
            normalized
        )

        retraction[
            "delivery_kind"
        ] = "RETRACTION"

        retraction[
            "retracts_event_identity"
        ] = identity

        # Retraction has a separate callback contract.
        # This preserves the historical on_event contract:
        # on_event receives canonical accepted events only.
        #
        # If a retraction consumer exists it is delivered
        # before local acknowledgement/state correction.
        if self.on_retraction is not None:
            await self._deliver_callback(
                self.on_retraction,
                retraction,
            )

        self._forget(
            identity
        )

        # Reorg invalidates our monotonic ordering
        # watermark. Reset conservatively so canonical
        # replacement logs may be accepted.
        self.last_block = None
        self.last_log_index = None

        self.buffer.push(
            retraction
        )

        self.removed_count += 1
        self.retraction_count += 1

    async def _deliver(
        self,
        event_row,
    ):
        if self.on_event is None:
            return True

        return await self._deliver_callback(
            self.on_event,
            event_row,
        )

    async def _deliver_callback(
        self,
        callback,
        event_row,
    ):
        try:
            result = callback(
                event_row
            )

            if asyncio.iscoroutine(
                result
            ):
                result = await result

            # Explicit False is negative acknowledgement.
            if result is False:
                raise RuntimeError(
                    "event callback rejected"
                )

            return True

        except Exception:
            self.delivery_failure_count += 1
            raise

    def _remember(
        self,
        identity,
    ):
        if identity in self._seen:
            return

        if (
            len(self._seen_order)
            >= self.max_seen
        ):
            oldest = (
                self._seen_order.popleft()
            )

            self._seen.discard(
                oldest
            )

        self._seen_order.append(
            identity
        )

        self._seen.add(
            identity
        )

    def _forget(
        self,
        identity,
    ):
        if identity not in self._seen:
            return

        self._seen.discard(
            identity
        )

        # Reorg is rare and max_seen is bounded.
        # O(n) removal here is acceptable because
        # this is not the normal hot path.
        try:
            self._seen_order.remove(
                identity
            )
        except ValueError:
            pass

    def status(self):
        return {
            "state": (
                "CONNECTED"
                if self.connected
                else "DISCONNECTED"
            ),
            "connected": self.connected,
            "subscription_id": (
                self.subscription_id
            ),
            "accepted_count": (
                self.accepted_count
            ),
            "duplicate_count": (
                self.duplicate_count
            ),
            "removed_count": (
                self.removed_count
            ),
            "retraction_count": (
                self.retraction_count
            ),
            "rejected_count": (
                self.rejected_count
            ),
            "out_of_order_count": (
                self.out_of_order_count
            ),
            "subscription_mismatch_count": (
                self.subscription_mismatch_count
            ),
            "delivery_failure_count": (
                self.delivery_failure_count
            ),
            "message_count": (
                self.message_count
            ),
            "reconnect_count": (
                self.reconnect_count
            ),
            "buffer_size": (
                self.buffer.size
            ),
            "buffer_dropped": (
                self.buffer.dropped
            ),
            "seen_size": len(
                self._seen
            ),
            "last_error": (
                self.last_error
            ),
            "delivery_semantics": (
                "CALLBACK_BEFORE_ACK_AT_LEAST_ONCE"
            ),
            "retraction_supported": True,
            "separate_retraction_callback": True,
            "subscription_validation": True,
            "bounded_buffer": True,
            "bounded_seen": True,
            "decision_authority": False,
            "paper_authority": False,
            "live_authority": False,
            "wallet_authority": False,
            "execution_authority": False,
        }


def _decode_message(raw):
    if isinstance(raw, dict):
        return raw

    if isinstance(raw, bytes):
        raw = raw.decode(
            "utf-8"
        )

    if not isinstance(raw, str):
        raise ValueError(
            "unsupported websocket message"
        )

    value = json.loads(
        raw
    )

    if not isinstance(value, dict):
        raise ValueError(
            "websocket message must be object"
        )

    return value
