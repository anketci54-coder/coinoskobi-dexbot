from app.cache.analyzer_cache import AnalyzerCache
from app.config.scanner import (
    PAIR_ANALYZER_CACHE_TTL_SECONDS,
    RISK_ANALYZER_CACHE_TTL_SECONDS,
    TOKEN_ANALYZER_CACHE_TTL_SECONDS,
)
from app.pipeline.candidate_queue import CandidateAdmissionQueue


CACHE_WARM = "WARM"
CACHE_PARTIAL = "PARTIAL"
CACHE_COLD = "COLD"


class ConveyorLabeler:
    """
    Ray ustu lightweight labeling.

    Bu katman:
    - RPC yapmaz
    - HTTP yapmaz
    - strategy calistirmaz
    - trade karari vermez

    Yalniz mevcut analyzer cache durumunu etiketler.
    """

    def __init__(self, cache=None):
        self.cache = cache or AnalyzerCache()

    @staticmethod
    def _cache_key(row):
        token = CandidateAdmissionQueue.normalize_token(
            row.get("token")
        )

        if not token:
            return None

        chain = str(
            row.get("chain") or "bsc"
        ).strip().lower()

        return f"{chain}:{token.lower()}"

    def _hit(self, namespace, key, ttl):
        if not key:
            return False

        try:
            return (
                self.cache.get(
                    namespace,
                    key,
                    ttl_seconds=ttl,
                )
                is not None
            )
        except Exception:
            return False

    def label(self, row):
        key = self._cache_key(row)

        token_hit = self._hit(
            "token",
            key,
            TOKEN_ANALYZER_CACHE_TTL_SECONDS,
        )

        pair_hit = self._hit(
            "pair",
            key,
            PAIR_ANALYZER_CACHE_TTL_SECONDS,
        )

        risk_hit = self._hit(
            "risk",
            key,
            RISK_ANALYZER_CACHE_TTL_SECONDS,
        )

        missing = []

        if not token_hit:
            missing.append("token")

        if not pair_hit:
            missing.append("pair")

        if not risk_hit:
            missing.append("risk")

        hit_count = 3 - len(missing)

        if hit_count == 3:
            state = CACHE_WARM
        elif hit_count == 0:
            state = CACHE_COLD
        else:
            state = CACHE_PARTIAL

        labeled = dict(row)

        labeled["conveyor"] = {
            "ingress_lane": "ACTIVE",
            "cache_state": state,
            "token_cache": (
                "HIT" if token_hit else "MISS"
            ),
            "pair_cache": (
                "HIT" if pair_hit else "MISS"
            ),
            "risk_cache": (
                "HIT" if risk_hit else "MISS"
            ),
            "missing_analyzers": missing,
        }

        return labeled

    def label_many(self, rows):
        labeled = []

        warm = 0
        partial = 0
        cold = 0

        for row in rows:
            item = self.label(row)
            labeled.append(item)

            state = item["conveyor"]["cache_state"]

            if state == CACHE_WARM:
                warm += 1
            elif state == CACHE_PARTIAL:
                partial += 1
            else:
                cold += 1

        return {
            "rows": labeled,
            "stats": {
                "input": len(rows),
                "warm": warm,
                "partial": partial,
                "cold": cold,
            },
        }

    def close(self):
        try:
            self.cache.close()
        except Exception:
            pass
