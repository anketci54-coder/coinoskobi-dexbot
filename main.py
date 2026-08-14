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

    def application_scan_job():
        result = pipeline.run_cycle()

        if not services:
            return result

        target_loader = getattr(
            pipeline,
            "native_wss_targets",
            None,
        )

        if target_loader is None:
            return result

        refreshed_targets = target_loader()

        if not refreshed_targets:
            return result

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

            if registered.get("state") != "REGISTERED":
                continue

            if confirm is not None:
                confirmation = confirm(
                    target["pair"],
                    target["token"],
                    target["quote_token"],
                )

                if confirmation.get("state") != "VERIFIED":
                    continue

            verified_addresses.append(
                target["pair"]
            )

        replace_pairs = getattr(
            services[0],
            "replace_pairs",
            None,
        )

        if verified_addresses and replace_pairs is not None:
            pair_filter = (
                verified_addresses[0]
                if len(verified_addresses) == 1
                else verified_addresses
            )

            replace_pairs(pair_filter)

        return result

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
