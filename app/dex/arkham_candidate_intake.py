from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Callable

from app.dex.arkham_candidate_provider import fetch_address_tag_candidate_updates
from app.dex.wallet_candidate_discovery import ingest_wallet_candidates


def run_arkham_candidate_intake(
    db_path: str | Path,
    *,
    fetcher: Callable[..., dict[str, Any]] = fetch_address_tag_candidate_updates,
    limit: int = 200,
    observed_at: float | None = None,
) -> dict[str, Any]:
    """Fetch read-only Arkham trader-tag updates and ingest them as OBSERVED candidates."""
    fetched = fetcher(limit=limit)
    fetched = fetched if isinstance(fetched, dict) else {}
    if fetched.get("available") is not True:
        return {
            "state": "PROVIDER_UNAVAILABLE",
            "reason": str(fetched.get("reason") or "ARKHAM_UNAVAILABLE"),
            "fetched_candidates": 0,
            "accepted": 0,
            "success_authority": False,
            "trade_authority": False,
            "decision_authority": False,
            "paper_authority": False,
            "live_authority": False,
            "wallet_authority": False,
            "signing_authority": False,
            "execution_authority": False,
        }

    candidates = fetched.get("candidates")
    candidates = candidates if isinstance(candidates, list) else []
    seen = float(observed_at if observed_at is not None else fetched.get("fetched_at") or time.time())
    result = ingest_wallet_candidates(
        db_path,
        candidates,
        source="ARKHAM_ADDRESS_TAG_UPDATE",
        source_key="address_tags:trader-signals",
        provider="ARKHAM",
        observed_at=seen,
    )
    return {
        "state": "READY",
        "fetched_candidates": len(candidates),
        "accepted": result["accepted"],
        "rejected": result["rejected"],
        "active_candidates": result["active_candidates"],
        "candidate_state": "OBSERVED",
        "success_authority": False,
        "trade_authority": False,
        "decision_authority": False,
        "paper_authority": False,
        "live_authority": False,
        "wallet_authority": False,
        "signing_authority": False,
        "execution_authority": False,
    }
