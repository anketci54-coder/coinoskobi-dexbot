from dataclasses import dataclass, asdict
from datetime import datetime, timezone


@dataclass(frozen=True)
class Candidate:
    chain: str
    chain_id: int
    dex: str
    pool: str
    token: str
    quote_token: str | None
    source: str
    liquidity: float
    volume_24h: float
    buys_24h: int
    fdv: float
    price_usd: float
    created_at: str | None
    observed_at: str

    @staticmethod
    def normalize_chain(value):
        if value is None:
            raise ValueError("chain is required")

        chain = str(value).strip().lower()

        if not chain:
            raise ValueError("chain is required")

        return chain

    @staticmethod
    def normalize_address(value):
        if value is None:
            raise ValueError("address is required")

        address = str(value).strip().lower()

        if not address:
            raise ValueError("address is required")

        return address

    @classmethod
    def from_row(
        cls,
        row,
        *,
        chain,
        chain_id,
        source,
    ):
        normalized_chain = cls.normalize_chain(chain)

        token = cls.normalize_address(
            row.get("token")
            or row.get("base_token")
        )

        pool = cls.normalize_address(
            row.get("pool")
        )

        quote_token = row.get("quote_token")

        if quote_token:
            quote_token = cls.normalize_address(
                quote_token
            )

        observed_at = row.get("observed_at")

        if not observed_at:
            observed_at = datetime.now(
                timezone.utc
            ).isoformat()

        return cls(
            chain=normalized_chain,
            chain_id=int(chain_id),
            dex=str(
                row.get("dex") or ""
            ).strip().lower(),
            pool=pool,
            token=token,
            quote_token=quote_token,
            source=str(source).strip().lower(),
            liquidity=float(
                row.get("liquidity") or 0
            ),
            volume_24h=float(
                row.get(
                    "volume_24h",
                    row.get("volume24") or 0,
                )
                or 0
            ),
            buys_24h=int(
                row.get(
                    "buys_24h",
                    row.get("buys24") or 0,
                )
                or 0
            ),
            fdv=float(
                row.get("fdv") or 0
            ),
            price_usd=float(
                row.get("price_usd") or 0
            ),
            created_at=row.get("created_at"),
            observed_at=observed_at,
        )

    @property
    def token_identity(self):
        return (
            self.chain,
            self.token,
        )

    @property
    def token_identity_key(self):
        return (
            f"{self.chain}:{self.token}"
        )

    @property
    def pool_identity(self):
        return (
            self.chain,
            self.dex,
            self.pool,
        )

    @property
    def pool_identity_key(self):
        return (
            f"{self.chain}:"
            f"{self.dex}:"
            f"{self.pool}"
        )

    def to_dict(self):
        data = asdict(self)

        data["token_identity"] = (
            self.token_identity_key
        )

        data["pool_identity"] = (
            self.pool_identity_key
        )

        return data
