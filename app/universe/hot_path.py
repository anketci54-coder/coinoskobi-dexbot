from app.config.contracts import BASE_TOKENS
from app.universe.schema import DEX_PANCAKESWAP_V2


BASE_TOKEN_SET = frozenset(str(value).strip().lower() for value in BASE_TOKENS)


class HotDeepPathRouter:
    """Converts audited HOT registry rows into bounded deep-path candidates."""

    def __init__(self, registry, *, pair_membership_verifier):
        self.registry = registry
        self.pair_membership_verifier = pair_membership_verifier

    @staticmethod
    def _candidate(row):
        token0 = str(row.get("token0") or "").strip().lower()
        token1 = str(row.get("token1") or "").strip().lower()
        token0_is_base = token0 in BASE_TOKEN_SET
        token1_is_base = token1 in BASE_TOKEN_SET
        if token0_is_base == token1_is_base:
            return None
        token = token1 if token0_is_base else token0
        quote = token0 if token0_is_base else token1
        return {
            "chain": row["chain"], "dex": row["dex"],
            "pool": row["pool"], "token": token, "quote_token": quote,
            "market_state": "HOT",
            "seismic_score": float(row.get("seismic_score") or 0),
            "price_usd": row.get("latest_price_usd"),
            "liquidity": row.get("latest_liquidity_usd"),
            "volume_24h": row.get("latest_volume_24h"),
            "buys_24h": None,
            "source": row.get("latest_snapshot_source") or "universe_registry",
        }

    def candidates(self, *, limit):
        limit = int(limit)
        if limit < 1:
            raise ValueError("positive HOT candidate limit required")
        rows = self.registry.hot_pools(limit=limit)
        return [candidate for row in rows
                if (candidate := self._candidate(row)) is not None]

    def native_wss_targets(self, *, limit):
        targets = []
        for candidate in self.candidates(limit=limit):
            if candidate["dex"] != DEX_PANCAKESWAP_V2:
                continue
            membership = self.pair_membership_verifier(
                candidate["pool"], candidate["token"],
                candidate["quote_token"],
            )
            if membership.get("state") != "VERIFIED":
                continue
            targets.append({
                "pair": candidate["pool"], "token": candidate["token"],
                "quote_token": candidate["quote_token"],
                "market_state": "HOT",
                "seismic_score": candidate["seismic_score"],
                "membership_verified": True,
            })
        return targets

    def status(self, *, limit=256):
        candidates = self.candidates(limit=limit)
        return {
            "state": "READY", "hot_candidates": len(candidates),
            "native_v2_eligible": sum(
                row["dex"] == DEX_PANCAKESWAP_V2 for row in candidates
            ),
            "v3_snapshot_deep_only": sum(
                row["dex"] != DEX_PANCAKESWAP_V2 for row in candidates
            ),
            "bounded": True, "decision_authority": False,
            "paper_authority": False, "live_authority": False,
            "wallet_authority": False, "execution_authority": False,
        }


__all__ = ["HotDeepPathRouter"]
