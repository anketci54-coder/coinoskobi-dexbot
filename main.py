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
        factory = (
            wss_service_factory
            or NativeWSSService
        )

        service = factory(
            WSS_URL,
            WSS_PAIR,
        )

        # Directional Swap semantics require explicit
        # target token identity. We never guess it.
        if WSS_TOKEN:
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

            if (
                configure is not None
                and bind_callbacks is not None
            ):
                result = configure(
                    WSS_PAIR,
                    WSS_TOKEN,
                    WBNB,
                )

                if (
                    result.get("state")
                    == "REGISTERED"
                ):
                    bind_callbacks(
                        on_event=(
                            pipeline.on_native_event
                        ),
                        on_retraction=(
                            pipeline.on_native_retraction
                        ),
                    )

                    market_flow_bound = True

        services.append(
            service
        )

    position_job = getattr(
        pipeline,
        "process_positions",
        None,
    )

    runner = Runner(
        scan_job=pipeline.run_cycle,
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
    app = build_application()

    app["runner"].run()


if __name__ == "__main__":
    main()
