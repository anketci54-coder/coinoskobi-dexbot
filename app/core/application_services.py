from __future__ import annotations

from app.dex.arkham_candidate_discovery_service import ArkhamCandidateDiscoveryService
from app.dex.arkham_provider import arkham_config_status
from app.dex.arkham_successful_wallet_service import ArkhamSuccessfulWalletService
from app.paper.database import DB as PAPER_DB


def build_application_auxiliary_services(*, intelligence=None):
    """Return optional application-owned slow-path services.

    These services share Runner lifecycle but never enter scanner scheduling or
    native-WSS target composition. Missing provider configuration yields no
    service and no network call.
    """
    services = []

    if arkham_config_status().get("configured") is True:
        services.append(
            ArkhamCandidateDiscoveryService(PAPER_DB)
        )
        services.append(
            ArkhamSuccessfulWalletService(
                PAPER_DB,
                intelligence=intelligence,
            )
        )

    return services
