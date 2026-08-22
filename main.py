import logging
from app.config.contracts import WBNB
from app.config.settings import (
    WSS_PAIR,
    WSS_TOKEN,
    WSS_URL,
)
from app.core.runner import Runner
from app.dex.wss_service import (
    NativeWSSService,
)
from app.pipeline.engine import (
    PipelineEngine,
)


def build_application(
    *,
    pipeline=None,
    wss_service_factory=None,
):
    pipeline = (
        pipeline
        or PipelineEngine()
    )

    services = []

    market_flow_bound = False

    if WSS_URL and WSS_PAIR:
        startup_refresh = getattr(
            pipeline,
            "refresh_candidate_cache",
            None,
        )

        if startup_refresh is not None:
            try:
                startup_refresh()
            except Exception as exc:
                logging.getLogger(__name__).warning(
                    "Startup scanner refresh failed; using cache: %s",
                    f"{type(exc).__name__}: {exc}",
                )

        factory = (
            wss_service_factory
            or NativeWSSService
        )

        target_loader = getattr(
            pipeline,
            "native_wss_targets",
            None,
        )

        targets = (
            target_loader()
            if target_loader is not None
            else []
        )

        if not targets and WSS_TOKEN:
            targets = [{
                "pair": WSS_PAIR,
                "token": WSS_TOKEN,
                "quote_token": WBNB,
            }]

        pair_addresses = [
            target["pair"]
            for target in targets
        ]

        if len(pair_addresses) == 1:
            pair_filter = pair_addresses[0]
        elif pair_addresses:
            pair_filter = pair_addresses
        else:
            pair_filter = WSS_PAIR

        service = factory(
            WSS_URL,
            pair_filter,
        )

        configure = getattr(
            pipeline,
            "configure_native_market_flow",
            None,
        )

        bind_callbacks = getattr(
            service,
            "bind_callbacks",
            None,
        )

        registered = 0

        if configure is not None:
            for target in targets:
                result = configure(
                    target["pair"],
                    target["token"],
                    target["quote_token"],
                )

                if result.get("state") == "REGISTERED":
                    confirm = getattr(
                        pipeline,
                        "confirm_native_market_flow",
                        None,
                    )

                    if confirm is None:
                        registered += 1
                    else:
                        confirmation = confirm(
                            target["pair"],
                            target["token"],
                            target["quote_token"],
                        )

                        if confirmation.get("state") == "VERIFIED":
                            registered += 1

        if registered and bind_callbacks is not None:
            bind_callbacks(
                on_event=pipeline.on_native_event,
                on_retraction=pipeline.on_native_retraction,
            )
            market_flow_bound = True

        services.append(service)

    def refresh_native_wss_targets():
        if not services:
            return {
                "state": "NO_SERVICE",
                "address_count": 0,
                "addresses": [],
            }

        target_loader = getattr(
            pipeline,
            "native_wss_targets",
            None,
        )

        if target_loader is None:
            return {
                "state": "NO_TARGET_LOADER",
                "address_count": 0,
                "addresses": [],
            }

        refreshed_targets = target_loader()

        if not refreshed_targets:
            return {
                "state": "NO_TARGETS",
                "address_count": 0,
                "addresses": [],
            }

        configure = getattr(
            pipeline,
            "configure_native_market_flow",
            None,
        )

        confirm = getattr(
            pipeline,
            "confirm_native_market_flow",
            None,
        )

        verified_addresses = []

        for target in refreshed_targets:
            if configure is None:
                break

            registered = configure(
                target["pair"],
                target["token"],
                target["quote_token"],
            )

            if (
                registered.get("state")
                != "REGISTERED"
            ):
                continue

            if confirm is not None:
                confirmation = confirm(
                    target["pair"],
                    target["token"],
                    target["quote_token"],
                )

                if (
                    confirmation.get("state")
                    != "VERIFIED"
                ):
                    continue

            verified_addresses.append(
                target["pair"]
            )

        replace_pairs = getattr(
            services[0],
            "replace_pairs",
            None,
        )

        if (
            not verified_addresses
            or replace_pairs is None
        ):
            return {
                "state": "NO_VERIFIED_TARGETS",
                "address_count": 0,
                "addresses": [],
            }

        pair_filter = (
            verified_addresses[0]
            if len(verified_addresses) == 1
            else verified_addresses
        )

        result = replace_pairs(
            pair_filter
        )

        return {
            "state": result.get(
                "state",
                "UPDATED",
            ),
            "address_count": len(
                verified_addresses
            ),
            "addresses": list(
                verified_addresses
            ),
        }

    def prepare_native_market_evidence(
        candidates=None,
    ):
        binding = (
            refresh_native_wss_targets()
        )

        verified = {
            str(pair).strip().lower()
            for pair in (
                binding.get("addresses")
                or []
            )
            if pair
        }

        candidate_pools = list(
            dict.fromkeys(
                str(
                    row.get("pool")
                    or ""
                ).strip().lower()
                for row in (
                    candidates
                    or []
                )
                if row.get("pool")
            )
        )

        wait_pools = [
            pair
            for pair in candidate_pools
            if pair in verified
        ]

        waiter = getattr(
            pipeline,
            "wait_for_native_market_evidence",
            None,
        )

        if (
            waiter is None
            or not wait_pools
        ):
            warmup = {
                "state": "NO_WAIT_TARGETS",
                "requested": len(
                    wait_pools
                ),
                "ready": 0,
                "pending": len(
                    wait_pools
                ),
            }
        else:
            warmup = waiter(
                wait_pools,
                timeout=10.0,
            )

        logging.getLogger(
            __name__
        ).info(
            (
                "Native evidence warm-up "
                "state=%s requested=%s "
                "ready=%s pending=%s"
            ),
            warmup.get("state"),
            warmup.get("requested"),
            warmup.get("ready"),
            warmup.get("pending"),
        )

        return {
            "binding": binding,
            "warmup": warmup,
        }

    def application_scan_job():
        if not services:
            return pipeline.run_cycle()

        return pipeline.run_cycle(
            pre_analysis_hook=(
                prepare_native_market_evidence
            ),
        )

    position_job = getattr(
        pipeline,
        "process_positions",
        None,
    )

    runner = Runner(
        scan_job=application_scan_job,
        position_job=position_job,
        services=services,
    )

    return {
        "pipeline": pipeline,
        "runner": runner,
        "services": services,
        "wss_configured": bool(
            WSS_URL
            and WSS_PAIR
        ),
        "market_flow_bound": (
            market_flow_bound
        ),
        "paper_lifecycle_bound": (
            position_job is not None
        ),
        "decision_authority": False,
        "live_authority": False,
        "execution_authority": False,
    }


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    app = build_application()
    app["runner"].run()


if __name__ == "__main__":
    main()
