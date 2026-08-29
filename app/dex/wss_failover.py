from app.config.settings import WSS_URL_SECONDARY
from app.dex.wss_runtime import NativeWSSRuntime


class FailoverWSSRuntime:
    """Primary WSS runtime with one cold-standby provider fallback."""

    def __init__(
        self,
        url,
        pair,
        *,
        fallback_url=None,
        runtime_factory=NativeWSSRuntime,
        **runtime_kwargs,
    ):
        if not url:
            raise ValueError("url required")

        if not pair:
            raise ValueError("pair required")

        secondary = (
            WSS_URL_SECONDARY
            if fallback_url is None
            else str(fallback_url).strip()
        )

        self.urls = [str(url).strip()]
        if secondary and secondary not in self.urls:
            self.urls.append(secondary)

        self.pair = pair
        self.runtime_factory = runtime_factory
        self.runtime_kwargs = dict(runtime_kwargs)

        self._runtime = None
        self._stop = False
        self.active_provider = "PRIMARY"
        self.failover_count = 0
        self.last_error = None
        self.last_status = None

    def request_stop(self):
        self._stop = True
        runtime = self._runtime
        if runtime is not None:
            runtime.request_stop()

    async def force_close(self):
        self.request_stop()

        runtime = self._runtime
        if runtime is None:
            return False

        close = getattr(runtime, "force_close", None)
        if close is None:
            return False

        return await close()

    async def run(self, max_events=None):
        remaining = max_events

        for index, url in enumerate(self.urls):
            if self._stop:
                break

            self.active_provider = (
                "PRIMARY" if index == 0 else "SECONDARY"
            )

            runtime = self.runtime_factory(
                url,
                self.pair,
                **self.runtime_kwargs,
            )
            self._runtime = runtime

            status = await runtime.run(
                max_events=remaining
            )
            self.last_status = status
            self.last_error = status.get("last_error")

            if self._stop:
                break

            if max_events is not None:
                accepted = int(
                    status.get("accepted_count", 0) or 0
                )
                remaining = max(0, int(remaining) - accepted)
                if remaining == 0:
                    break

            if not self.last_error:
                break

            if index + 1 < len(self.urls):
                self.failover_count += 1
                continue

            break

        self._runtime = None
        return self.status()

    def status(self):
        runtime = self._runtime
        base = (
            runtime.status()
            if runtime is not None
            else dict(self.last_status or {})
        )

        base.update({
            "provider_role": self.active_provider,
            "provider_failover_count": self.failover_count,
            "secondary_configured": len(self.urls) > 1,
            "last_error": self.last_error,
            "decision_authority": False,
            "paper_authority": False,
            "live_authority": False,
            "wallet_authority": False,
            "execution_authority": False,
        })
        return base
