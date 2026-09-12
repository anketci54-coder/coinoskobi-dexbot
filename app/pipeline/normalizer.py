from app.pipeline.candidate import Candidate


class CandidateNormalizer:
    """
    Source-specific row -> common Candidate.

    Bu katman:
    - RPC yapmaz
    - HTTP yapmaz
    - filtre / strategy çalıştırmaz
    - yalnız veri formatını normalize eder
    """

    @staticmethod
    def gecko_bsc(row):
        normalized = dict(row)

        # Exact-pool snapshot clients use the canonical universe contract,
        # while legacy scanner rows use Candidate field names. Preserve
        # real measured values when crossing that boundary.
        canonical_aliases = {
            "liquidity": "liquidity_usd",
            "volume_24h": "volume_h24_usd",
            "buys_24h": "buys_h24",
            "fdv": "fdv_usd",
        }

        for target, source in canonical_aliases.items():
            if (
                normalized.get(target) is None
                and normalized.get(source) is not None
            ):
                normalized[target] = normalized[source]

        token = (
            normalized.get("token")
            or normalized.get("base_token")
        )

        if token:
            token = str(token).strip()

            if token.lower().startswith("bsc_"):
                token = token[4:]

            normalized["token"] = token

        quote_token = normalized.get("quote_token")

        if quote_token:
            quote_token = str(quote_token).strip()

            if quote_token.lower().startswith("bsc_"):
                quote_token = quote_token[4:]

            normalized["quote_token"] = quote_token

        provider = str(
            normalized.get("provider")
            or normalized.get("source")
            or "geckoterminal"
        ).strip().lower()
        if provider not in {"geckoterminal", "dexscreener"}:
            provider = "geckoterminal"

        return Candidate.from_row(
            normalized,
            chain="bsc",
            chain_id=56,
            source=provider,
        )

    @classmethod
    def gecko_bsc_many(cls, rows):
        candidates = []
        rejected = 0

        for row in rows:
            try:
                candidates.append(
                    cls.gecko_bsc(row)
                )
            except (
                TypeError,
                ValueError,
                KeyError,
            ):
                rejected += 1

        return {
            "candidates": candidates,
            "rejected": rejected,
        }