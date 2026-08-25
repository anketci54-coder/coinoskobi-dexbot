from app.config.contracts import BASE_TOKENS
from app.universe.schema import DEX_PANCAKESWAP_V2


BASE_TOKEN_SET = frozenset(str(value).strip().lower() for value in BASE_TOKENS)
BOOTSTRAP_NATIVE_WSS_LIMIT = 16


class HotDeepPathRouter:
    """Converts audited universe rows into bounded deep-path candidates."""

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
            "market_state": str(row.get("market_state") or "COLD").upper(),
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

    def _bootstrap_candidates(self, *, limit):
        """Bounded WARM/COLD V2 coverage while no verified HOT V2 target exists."""
        limit = min(int(limit), BOOTSTRAP_NATIVE_WSS_LIMIT)
        if limit < 1:
            raise ValueError("positive bootstrap candidate limit required")
        db = getattr(self.registry, "db", None)
        if db is None:
            return []

        bases = sorted(BASE_TOKEN_SET)
        placeholders = ",".join("?" for _ in bases)
        rows = db.execute(f"""
            SELECT registry.*, 0 AS seismic_score
            FROM universe_pool_registry AS registry
            WHERE dex=?
              AND market_state IN ('WARM','COLD')
              AND (
                    (LOWER(token0) IN ({placeholders})
                     AND LOWER(token1) NOT IN ({placeholders}))
                 OR (LOWER(token1) IN ({placeholders})
                     AND LOWER(token0) NOT IN ({placeholders}))
              )
            ORDER BY
                CASE market_state WHEN 'WARM' THEN 0 ELSE 1 END,
                COALESCE(latest_txns_5m, -1) DESC,
                ABS(COALESCE(latest_change_5m, 0)) DESC,
                COALESCE(latest_volume_24h, -1) DESC,
                CASE WHEN latest_snapshot_at IS NULL THEN 1 ELSE 0 END,
                latest_snapshot_at DESC,
                creation_block DESC
            LIMIT ?
        """, (
            DEX_PANCAKESWAP_V2,
            *bases, *bases, *bases, *bases,
            limit,
        )).fetchall()
        return [candidate for row in rows
                if (candidate := self._candidate(dict(row))) is not None]

    def _verified_native_targets(self, candidates, *, limit, selection_reason):
        targets = []
        for candidate in candidates:
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
                "market_state": candidate["market_state"],
                "seismic_score": candidate["seismic_score"],
                "membership_verified": True,
                "selection_reason": selection_reason,
            })
            if len(targets) >= limit:
                break
        return targets

    def native_wss_targets(self, *, limit):
        limit = int(limit)
        if limit < 1:
            raise ValueError("positive native WSS target limit required")

        hot_targets = self._verified_native_targets(
            self.candidates(limit=limit),
            limit=limit,
            selection_reason="HOT_SEISMIC",
        )
        if hot_targets:
            return hot_targets

        # Bootstrap/restart guard: the registry can contain many COLD rows
        # before the robust classifier has its minimum history. Keep a small,
        # ranked native V2 radar alive without turning bootstrap membership
        # verification into an unbounded synchronous RPC burst.
        bootstrap_limit = min(limit, BOOTSTRAP_NATIVE_WSS_LIMIT)
        return self._verified_native_targets(
            self._bootstrap_candidates(limit=bootstrap_limit),
            limit=bootstrap_limit,
            selection_reason="UNIVERSE_BOOTSTRAP",
        )

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
            "bootstrap_native_limit": BOOTSTRAP_NATIVE_WSS_LIMIT,
            "bounded": True, "decision_authority": False,
            "paper_authority": False, "live_authority": False,
            "wallet_authority": False, "execution_authority": False,
        }


__all__ = [
    "BOOTSTRAP_NATIVE_WSS_LIMIT",
    "HotDeepPathRouter",
]
