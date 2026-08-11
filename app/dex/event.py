from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class DexEvent:
    chain: str
    chain_id: int
    dex: str
    event_type: str
    block_number: int
    tx_hash: str
    log_index: int
    pool: str
    observed_at: float
    data: dict[str, Any]

    @property
    def identity(self):
        return (
            self.chain,
            self.tx_hash,
            self.log_index,
        )


def normalize_event(
    *,
    chain,
    chain_id,
    dex,
    event_type,
    block_number,
    tx_hash,
    log_index,
    pool,
    observed_at,
    data=None,
):
    if not event_type:
        raise ValueError("event_type is required")

    if block_number < 0:
        raise ValueError("block_number must be >= 0")

    if log_index < 0:
        raise ValueError("log_index must be >= 0")

    return DexEvent(
        chain=str(chain).strip().lower(),
        chain_id=int(chain_id),
        dex=str(dex).strip().lower(),
        event_type=str(event_type).strip().upper(),
        block_number=int(block_number),
        tx_hash=str(tx_hash).strip().lower(),
        log_index=int(log_index),
        pool=str(pool).strip().lower(),
        observed_at=float(observed_at),
        data=dict(data or {}),
    )
