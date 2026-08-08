from app.config.scanner import (
    ALLOWED_DEX,
    MIN_LIQUIDITY_USD,
    MIN_VOLUME_24H_USD,
    MIN_BUYS_24H,
    MIN_FDV_USD,
    MAX_FDV_USD,
)


class CacheFilter:

    def filter(self, rows):

        accepted = []

        for row in rows:

            if row["dex"] not in ALLOWED_DEX:
                continue

            if row["liquidity"] < MIN_LIQUIDITY_USD:
                continue

            if row["volume_24h"] < MIN_VOLUME_24H_USD:
                continue

            if row["buys_24h"] < MIN_BUYS_24H:
                continue

            if row["fdv"] < MIN_FDV_USD:
                continue

            if row["fdv"] > MAX_FDV_USD:
                continue

            accepted.append(row)

        accepted.sort(
            key=lambda x: (
                x["liquidity"],
                x["volume_24h"],
                x["buys_24h"],
            ),
            reverse=True,
        )

        return accepted
