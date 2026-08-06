from app.config.scanner import (
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

            if row["liquidity"] < MIN_LIQUIDITY_USD:
                continue

            if row["volume24"] < MIN_VOLUME_24H_USD:
                continue

            if row["buys24"] < MIN_BUYS_24H:
                continue

            if row["fdv"] < MIN_FDV_USD:
                continue

            if row["fdv"] > MAX_FDV_USD:
                continue

            accepted.append(row)

        accepted.sort(
            key=lambda x: (
                x["liquidity"],
                x["volume24"],
                x["buys24"]
            ),
            reverse=True
        )

        return accepted
