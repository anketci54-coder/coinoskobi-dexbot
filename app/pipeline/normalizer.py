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

        return Candidate.from_row(
            normalized,
            chain="bsc",
            chain_id=56,
            source="geckoterminal",
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
