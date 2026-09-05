from __future__ import annotations

from typing import Any, Iterable

from app.dex.wallet_candidate_discovery import ingest_wallet_candidates


TRADER_HINTS = (
    "trader",
    "smart money",
    "smart-money",
    "high pnl",
    "high-pnl",
    "profitable",
)


def _walk(value: Any) -> Iterable[Any]:
    yield value
    if isinstance(value, dict):
        for child in value.values():
            yield from _walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk(child)


def _address(row: dict[str, Any]) -> str:
    for key in ("address", "wallet", "walletAddress", "wallet_address"):
        value = row.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _chain(row: dict[str, Any]) -> str:
    for key in ("chain", "chainType", "chain_type", "network"):
        value = row.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip().lower()
    return "bsc"


def _texts(row: dict[str, Any]) -> list[str]:
    values: list[str] = []
    for node in _walk(row):
        if isinstance(node, str):
            values.append(node.strip().lower())
    return values


def _is_trader_candidate(row: dict[str, Any]) -> bool:
    texts = _texts(row)
    return any(hint in text for hint in TRADER_HINTS for text in texts)


def normalize_arkham_update_candidates(rows: Iterable[Any]) -> tuple[list[dict[str, Any]], int]:
    candidates: list[dict[str, Any]] = []
    rejected = 0
    seen: set[tuple[str, str]] = set()
    for row in rows:
        if not isinstance(row, dict):
            rejected += 1
            continue
        address = _address(row)
        chain = _chain(row)
        if not address or chain != "bsc" or not _is_trader_candidate(row):
            rejected += 1
            continue
        key = (chain, address.lower())
        if key in seen:
            continue
        seen.add(key)
        candidates.append(
            {
                "chain": chain,
                "address": address,
                "metadata": {
                    "arkham_update": row,
                    "candidate_reason": "TRADER_INTELLIGENCE_HINT",
                },
            }
        )
    return candidates, rejected


def ingest_arkham_intelligence_updates(
    db_path,
    provider_result: dict[str, Any],
    *,
    source_key: str,
) -> dict[str, Any]:
    """Convert Arkham intelligence updates into OBSERVED BSC candidates only."""
    if not isinstance(provider_result, dict) or provider_result.get("available") is not True:
        return {
            "state": "PROVIDER_NOT_READY",
            "accepted": 0,
            "rejected": 0,
            "success_authority": False,
            "trade_authority": False,
            "decision_authority": False,
            "paper_authority": False,
            "live_authority": False,
            "wallet_authority": False,
            "signing_authority": False,
            "execution_authority": False,
        }

    kind = str(provider_result.get("kind") or "").strip().upper()
    source = "ARKHAM_ADDRESS_TAG_UPDATE" if kind == "ADDRESS_TAGS" else "ARKHAM_TRADER_TAG"
    candidates, rejected = normalize_arkham_update_candidates(provider_result.get("rows") or [])
    out = ingest_wallet_candidates(
        db_path,
        candidates,
        source=source,
        source_key=source_key,
        provider="ARKHAM",
        observed_at=provider_result.get("fetched_at"),
    )
    out["adapter_rejected"] = rejected
    out["provider_kind"] = kind
    return out
