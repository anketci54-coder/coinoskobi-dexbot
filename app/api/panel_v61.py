from __future__ import annotations

import re
from typing import Any

import requests
from fastapi import HTTPException

from app.dex.arkham_provider import fetch_balances_for_address


BINANCE_TICKER_URL = "https://api.binance.com/api/v3/ticker/24hr"
ADDRESS_RE = re.compile(r"^0x[a-fA-F0-9]{40}$")


def _ticker(symbol: str) -> dict[str, Any]:
    try:
        response = requests.get(
            BINANCE_TICKER_URL,
            params={"symbol": symbol},
            timeout=3,
        )
        if response.status_code != 200:
            return {
                "symbol": symbol,
                "available": False,
                "reason": f"HTTP_{response.status_code}",
            }

        payload = response.json()

        return {
            "symbol": symbol,
            "available": True,
            "price": float(payload["lastPrice"]),
            "change_24h_pct": float(payload["priceChangePercent"]),
            "high_24h": float(payload["highPrice"]),
            "low_24h": float(payload["lowPrice"]),
            "quote_volume_24h": float(payload["quoteVolume"]),
            "source": "BINANCE_PUBLIC_MARKET_DATA",
        }

    except Exception:
        return {
            "symbol": symbol,
            "available": False,
            "reason": "PROVIDER_UNAVAILABLE",
        }


def register_panel_v61_routes(app) -> None:
    @app.get("/api/v61/market-tickers")
    def api_v61_market_tickers() -> dict[str, Any]:
        return {
            "items": [
                _ticker("BTCUSDT"),
                _ticker("ETHUSDT"),
            ],
            "read_only": True,
            "execution_authority": False,
        }

    @app.get("/api/v61/wallet-readonly")
    def api_v61_wallet_readonly(address: str) -> dict[str, Any]:
        address = str(address or "").strip()

        if not ADDRESS_RE.fullmatch(address):
            raise HTTPException(
                status_code=400,
                detail="Geçerli BSC 0x cüzdan adresi gerekli",
            )

        result = fetch_balances_for_address(
            address,
            chain="bsc",
        )

        rows = list(result.get("holdings") or [])

        known_total = sum(
            float(row.get("value_usd") or 0.0)
            for row in rows
        )

        total = result.get("total_value_usd")

        try:
            total = float(total)
        except (TypeError, ValueError):
            total = known_total

        denominator = total if total and total > 0 else known_total

        for row in rows:
            value = float(row.get("value_usd") or 0.0)
            row["portfolio_pct"] = (
                value / denominator * 100.0
                if denominator > 0
                else None
            )

        return {
            **result,
            "holdings": rows,
            "total_value_usd": total,
            "read_only": True,
            "wallet_authority": False,
            "signing_authority": False,
            "execution_authority": False,
        }
