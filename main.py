import logging
from app.config.contracts import WBNB
from app.config.settings import (
    UNIVERSE_SHADOW_ENABLED,
    UNIVERSE_V2_START_BLOCK,
    UNIVERSE_V3_START_BLOCK,
    WSS_PAIR,
    WSS_TOKEN,
    WSS_URL,
)
from app.universe.runtime import (
    FullUniverseObservationRuntime,
    bind_shadow_runtime,
)
from app.core.runner import Runner
from app.dex.open_position_hot_path import (
    HotPositionWSSBridge,
    merge_wss_targets,
    open_position_signature,
    process_hot_positions,
)
from app.dex.wss_service import (
    NativeWSSService,
)
from app.pipeline.engine import (
    PipelineEngine,
)


SCAN_NATIVE_WSS_LIMIT = 16


def build_application(
    *,
    pipeline=None,
    wss_service_factory=None,
    universe_runtime=None,
):
    pipeline = (
        pipeline
        or PipelineEngine()
    )

    services = []
    market_flow_bound = False
    hot_bridge = HotPositionWSSBridge()
    base_wss_targets = []
    hot_signature = {
        "value": None,
    }

    def merged_targets(
        scanner_targets,
    ):
        return merge_wss_targets(
            pipeline,
            scanner_targets,
            max_pairs=256,
        )

    def candidate_wss_targets(
        candidates,
    ):
        verifier = getattr(
            pipeline,
            "pair_membership_verifier",
            None,
        )

        if not callable(verifier):
            return []

        targets = []
        seen = set()

        for row in candidates or []:
            if len(targets) >= SCAN_NATIVE_WSS_LIMIT:
                break

            if not isinstance(row, dict):
                continue

            chain = str(
                row.get("chain") or ""
            ).strip().lower()
            dex = str(
                row.get("dex") or ""
            ).strip().lower()

            if chain not in {"", "bsc"}:
                continue

            if dex not in {
                "pancakeswap_v2",
                "pancakeswap-v2",
            }:
                continue

            pair = str(
                row.get("pool") or ""
            ).strip().lower()
            token = str(
                row.get("token")
                or row.get("base_token")
                or ""
            ).strip().lower()
            quote = str(
                row.get("quote_token") or ""
            ).strip().lower()

            if pair.startswith("bsc_"):
                pair = pair[4:]
            if token.startswith("bsc_"):
                token = token[4:]
            if quote.startswith("bsc_"):
                quote = quote[4:]

            if (
                not pair
                or not token
                or not quote
                or token == quote
                or pair in seen
            ):
                continue

            try:
                membership = verifier(
                    pair,
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

            seen.add(pair)
            targets.append({
                "pair": pair,
                "token": token,
                "quote_token": quote,
                "membership_verified": True,
                "selection_reason": "SCAN_CANDIDATE",
            })

        return targets

    async def on_native_event(event):
        hot_bridge.observe_event(
            event
        )

        handler = getattr(
            pipeline,
            "on_native_event",
            None,
        )

        if handler is None:
            return True

        return await handler(event)

    async def on_native_retraction(event):
        hot_bridge.observe_retraction(
            event
        )

        handler = getattr(
            pipeline,
            "on_native_retraction",
            None,
        )

        if handler is None:
            return True

        return await handler(event)

    def apply_wss_targets(
        targets,
        *,
        open_pairs=None,
        replace_service=True,
    ):
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

        verified_targets = []

        for target in targets or []:
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

            verified_targets.append(
                target
            )

        verified_addresses = [
            target["pair"]
            for target in verified_targets
        ]

        address_set = set(
            verified_addresses
        )

        verified_open = {
            pair
            for pair in (
                open_pairs or []
            )
            if pair in address_set
        }

        hot_bridge.replace_targets(
            verified_targets,
            open_pairs=verified_open,
        )

        if not services:
            return {
                "state": "NO_SERVICE",
                "address_count": len(
                    verified_addresses
                ),
                "addresses": list(
                    verified_addresses
                ),
                "open_pair_count": len(
                    verified_open
                ),
            }

        if not replace_service:
            return {
                "state": "CONFIGURED",
                "address_count": len(
                    verified_addresses
                ),
                "addresses": list(
                    verified_addresses
                ),
                "open_pair_count": len(
                    verified_open
                ),
            }

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
                "open_pair_count": 0,
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
            "open_pair_count": len(
                verified_open
            ),
        }

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

        base_wss_targets = (
            target_loader()
            if target_loader is not None
            else []
        )

        if not base_wss_targets and WSS_TOKEN:
            base_wss_targets = [{
                "pair": WSS_PAIR,
                "token": WSS_TOKEN,
                "quote_token": WBNB,
            }]

        initial_merge = merged_targets(
            base_wss_targets
        )

        targets = initial_merge[
            "targets"
        ]

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

        services.append(service)

        bind_callbacks = getattr(
            service,
            "bind_callbacks",
            None,
        )

        initial_binding = apply_wss_targets(
            targets,
            open_pairs=(
                initial_merge[
                    "open_pairs"
                ]
            ),
            replace_service=False,
        )

        if (
            initial_binding.get(
                "address_count",
                0,
            )
            and bind_callbacks is not None
        ):
            bind_callbacks(
                on_event=on_native_event,
                on_retraction=on_native_retraction,
            )
            market_flow_bound = True

        hot_signature[
            "value"
        ] = open_position_signature(
            pipeline
        )

    def refresh_native_wss_targets(
        candidates=None,
    ):
        nonlocal base_wss_targets

        if not services:
            return {
                "state": "NO_SERVICE",
                "address_count": 0,
                "addresses": [],
                "open_pair_count": 0,
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
                "open_pair_count": 0,
            }

        refreshed_targets = (
            target_loader()
        )

        if refreshed_targets:
            base_wss_targets = list(
                refreshed_targets
            )

        hot_targets = [
            target
            for target in base_wss_targets
            if str(
                target.get("selection_reason")
                or ""
            ).upper() == "HOT_SEISMIC"
        ]
        background_targets = [
            target
            for target in base_wss_targets
            if target not in hot_targets
        ]
        scan_targets = candidate_wss_targets(
            candidates
        )

        merged = merged_targets([
            *hot_targets,
            *scan_targets,
            *background_targets,
        ])

        return apply_wss_targets(
            merged["targets"],
            open_pairs=merged[
                "open_pairs"
            ],
        )

    def refresh_hot_open_position_targets():
        if not services:
            return {
                "state": "NO_SERVICE",
                "address_count": 0,
                "addresses": [],
                "open_pair_count": 0,
            }

        merged = merged_targets(
            base_wss_targets
        )

        return apply_wss_targets(
            merged["targets"],
            open_pairs=merged[
                "open_pairs"
            ],
        )

    def prepare_native_market_evidence(
        candidates=None,
    ):
        binding = (
            refresh_native_wss_targets(
                candidates
            )
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

    original_position_job = getattr(
        pipeline,
        "process_positions",
        None,
    )

    refresh_open_prices = getattr(
        pipeline,
        "refresh_open_position_prices",
        None,
    )

    manager = getattr(
        pipeline,
        "manager",
        None,
    )

    manager_db = getattr(
        manager,
        "db",
        None,
    )

    open_reader = getattr(
        manager_db,
        "open_positions",
        None,
    )

    hot_position_capable = bool(
        services
        and callable(open_reader)
        and callable(refresh_open_prices)
    )

    def application_position_job():
        if not hot_position_capable:
            if original_position_job is None:
                return []

            return original_position_job()

        refresh = refresh_open_prices()

        open_count = int(
            refresh.get(
                "open_positions",
                0,
            )
            or 0
        )

        if (
            refresh.get("state")
            == "REFRESHED"
            and int(
                refresh.get(
                    "failed",
                    0,
                )
                or 0
            ) == 0
            and int(
                refresh.get(
                    "refreshed",
                    0,
                )
                or 0
            ) == open_count
        ):
            hot_bridge.anchor_from_cache(
                pipeline
            )

        return process_hot_positions(
            pipeline
        )

    def application_hot_position_job():
        current_signature = (
            open_position_signature(
                pipeline
            )
        )

        binding = None

        if (
            current_signature
            != hot_signature[
                "value"
            ]
        ):
            binding = (
                refresh_hot_open_position_targets()
            )

            hot_signature[
                "value"
            ] = current_signature

        drained = (
            hot_bridge.drain_price_updates(
                pipeline
            )
        )

        processed = 0

        if int(
            drained.get(
                "updated",
                0,
            )
            or 0
        ) > 0:
            processed = len(
                process_hot_positions(
                    pipeline
                )
                or []
            )

        return {
            "state": "READY",
            "binding": binding,
            "drain": drained,
            "processed": processed,
            "bridge": hot_bridge.status(),
            "provider_call": False,
            "hot_path_wait": False,
            "decision_authority": False,
            "paper_authority": False,
            "live_authority": False,
            "wallet_authority": False,
            "execution_authority": False,
        }

    position_job = (
        application_position_job
        if original_position_job is not None
        else None
    )

    runner = Runner(
        scan_job=application_scan_job,
        position_job=position_job,
        services=services,
    )

    shadow_runtime = universe_runtime
    if shadow_runtime is None and UNIVERSE_SHADOW_ENABLED:
        if UNIVERSE_V2_START_BLOCK < 1 or UNIVERSE_V3_START_BLOCK < 1:
            raise RuntimeError(
                "verified universe V2/V3 start blocks required"
            )
        shadow_runtime = FullUniverseObservationRuntime(
            start_blocks={
                "pancakeswap_v2": UNIVERSE_V2_START_BLOCK,
                "pancakeswap_v3": UNIVERSE_V3_START_BLOCK,
            },
            registry=getattr(pipeline, "universe_registry", None),
        )

    shadow_binding = None
    if shadow_runtime is not None:
        shadow_binding = bind_shadow_runtime(
            runner, shadow_runtime, interval=1
        )

    if hot_position_capable:
        runner.scheduler.every(
            interval=1,
            func=application_hot_position_job,
            name="paper_hot_manager",
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
        "hot_position_wss": (
            hot_bridge.status()
        ),
        "hot_position_bound": (
            hot_position_capable
        ),
        "universe_shadow_bound": shadow_binding is not None,
        "universe_shadow": shadow_binding,
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
