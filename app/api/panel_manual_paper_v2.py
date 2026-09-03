from __future__ import annotations

import json
import math
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import HTTPException

from app.paper.manager import PaperManager
from app.risk.paper_position_sizing import PAPER_CAPITAL_USDT, paper_available_capital_usdt
from app.strategy.mathematical_trade_plan import decode_plan, exit_net_proceeds


MANUAL_QUOTE_MAX_AGE_SECONDS = 300.0


def _num(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _timestamp(value: Any) -> float | None:
    number = _num(value)
    if number is not None:
        if number > 10_000_000_000:
            number /= 1000.0
        return number if number > 0 else None

    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.timestamp()


def _cache_quote(cache_db: Path, *, pool: str | None, token: str | None) -> dict[str, Any]:
    if not cache_db.exists():
        return {}

    connection = sqlite3.connect(f"file:{cache_db}?mode=ro", uri=True, timeout=3)
    connection.row_factory = sqlite3.Row
    try:
        row = None
        if pool:
            row = connection.execute(
                """
                SELECT pool, token, name, dex, price_usd, updated_at
                FROM gecko_pool_cache
                WHERE lower(pool)=lower(?)
                ORDER BY updated_at DESC
                LIMIT 1
                """,
                (pool,),
            ).fetchone()
        if row is None and token:
            row = connection.execute(
                """
                SELECT pool, token, name, dex, price_usd, updated_at
                FROM gecko_pool_cache
                WHERE lower(token)=lower(?)
                   OR lower(replace(token,'bsc_',''))=lower(?)
                ORDER BY updated_at DESC
                LIMIT 1
                """,
                (token, token),
            ).fetchone()
        return dict(row) if row is not None else {}
    finally:
        connection.close()


def _fresh_quote(cache_db: Path, *, pool: str | None, token: str | None) -> tuple[dict[str, Any], float, float]:
    quote = _cache_quote(cache_db, pool=pool, token=token)
    price = _num(quote.get("price_usd"))
    observed = _timestamp(quote.get("updated_at"))
    if price is None or price <= 0 or observed is None:
        raise HTTPException(status_code=409, detail="Güncel referans fiyat yok")

    age = max(0.0, time.time() - observed)
    if age > MANUAL_QUOTE_MAX_AGE_SECONDS:
        raise HTTPException(
            status_code=409,
            detail="Referans fiyat bayat; provider/cache akışını kontrol et",
        )
    return quote, price, age


def _open_position(connection: sqlite3.Connection, *, position_id=None, pool=None, token=None):
    if position_id not in (None, ""):
        row = connection.execute(
            "SELECT * FROM paper_trades WHERE id=? AND status='OPEN' LIMIT 1",
            (int(position_id),),
        ).fetchone()
        if row is not None:
            return row
    if pool:
        row = connection.execute(
            "SELECT * FROM paper_trades WHERE lower(pool)=lower(?) AND status='OPEN' ORDER BY id DESC LIMIT 1",
            (pool,),
        ).fetchone()
        if row is not None:
            return row
    if token:
        return connection.execute(
            "SELECT * FROM paper_trades WHERE lower(token)=lower(?) AND status='OPEN' ORDER BY id DESC LIMIT 1",
            (token,),
        ).fetchone()
    return None


def _connect(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(path, timeout=30)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA busy_timeout=30000")
    connection.execute("PRAGMA foreign_keys=ON")
    return connection


def _buy(*, paper_db: Path, cache_db: Path, payload: dict[str, Any]) -> dict[str, Any]:
    token = str(payload.get("token") or "").strip()
    pool = str(payload.get("pool") or "").strip()
    symbol = str(payload.get("symbol") or "").strip()[:80]
    amount = _num(payload.get("amount_usdt"))
    if not token or not pool:
        raise HTTPException(status_code=400, detail="Token/pool eksik")
    if amount is None or amount <= 0:
        raise HTTPException(status_code=400, detail="Geçerli USDT miktarı gir")

    quote, price, age = _fresh_quote(cache_db, pool=pool, token=token)
    connection = _connect(paper_db)
    try:
        connection.execute("BEGIN IMMEDIATE")
        if _open_position(connection, pool=pool, token=token) is not None:
            connection.rollback()
            raise HTTPException(status_code=409, detail="Bu varlıkta zaten açık paper pozisyon var")

        available = float(paper_available_capital_usdt(connection, PAPER_CAPITAL_USDT))
        if amount > available + 1e-9:
            connection.rollback()
            raise HTTPException(status_code=409, detail=f"Yetersiz paper bakiye: {available:.2f} USDT")

        token_amount = amount / price
        now = datetime.now(timezone.utc).isoformat()
        context = {
            "source": "MANUAL_PANEL",
            "manual_confirmed": True,
            "captured_at_entry": True,
            "reference_price": price,
            "reference_price_age_seconds": age,
            "cost_model_complete": False,
        }
        connection.execute(
            """
            INSERT INTO paper_trades(
                created_at, token, symbol, entry_price, current_price,
                highest_price, lowest_price, amount_bnb, status,
                token_amount, initial_token_amount, pool, dex,
                opening_context_json, paper_account_version, trade_policy,
                cost_model_complete, entry_amount_usdt, risk_amount_usdt,
                capital_before_usdt, capital_after_entry_usdt,
                position_size_pct, sizing_reason, remaining_cost_basis_usdt
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                now, token, symbol or str(quote.get("name") or token)[:80],
                price, price, price, price, 0.0, "OPEN",
                token_amount, token_amount, pool, quote.get("dex"),
                json.dumps(context, ensure_ascii=False, separators=(",", ":")),
                "PAPER_10K_V2", "MANUAL_PANEL", 0, amount, 0.0,
                available, available - amount,
                amount / available * 100.0 if available > 0 else 0.0,
                "MANUAL_PAPER_ORDER", amount,
            ),
        )
        position_id = int(connection.execute("SELECT last_insert_rowid()").fetchone()[0])
        connection.commit()
        return {
            "ok": True, "side": "BUY", "position_id": position_id,
            "token": token, "pool": pool, "reference_price": price,
            "reference_price_age_seconds": age, "amount_usdt": amount,
            "token_amount": token_amount, "paper_balance_after": available - amount,
            "paper_only": True, "live_execution": False,
            "wallet_authority": False, "signing_authority": False,
        }
    except HTTPException:
        raise
    except sqlite3.Error as exc:
        connection.rollback()
        raise HTTPException(status_code=500, detail=f"Paper DB hatası: {type(exc).__name__}") from exc
    finally:
        connection.close()


def _sell_accounting(position: dict[str, Any], price: float) -> dict[str, float]:
    entry = float(position.get("entry_amount_usdt") or 0.0)
    tokens = float(position.get("token_amount") or 0.0)
    realized_gross = float(position.get("realized_gross_proceeds_usdt") or 0.0)
    realized_net = float(position.get("realized_proceeds_usdt") or 0.0)
    if entry <= 0 or tokens < 0:
        raise HTTPException(status_code=409, detail="Pozisyon muhasebesi eksik")

    gross = realized_gross + tokens * price - entry
    raw_plan = position.get("mathematical_plan_json")
    if raw_plan:
        try:
            plan = decode_plan(raw_plan)
            cost_model = dict(plan.get("cost_model") or {})
        except Exception:
            cost_model = {}
        if cost_model:
            exit_net = exit_net_proceeds(tokens, price, cost_model)
            net = realized_net + exit_net - entry
            return {"gross": gross, "net": net, "roi": net / entry, "proceeds": tokens * price}

    if realized_gross or realized_net:
        raise HTTPException(status_code=409, detail="Kısmi pozisyon maliyet modeli eksik; manuel kapanış güvenli değil")

    accounting = PaperManager._calculate_accounting(position, price)
    return {
        "gross": float(accounting["gross_pnl_usdt"]),
        "net": float(accounting["net_pnl_usdt"]),
        "roi": float(accounting["roi"]),
        "proceeds": tokens * price,
    }


def _sell(*, paper_db: Path, cache_db: Path, payload: dict[str, Any]) -> dict[str, Any]:
    token = str(payload.get("token") or "").strip()
    pool = str(payload.get("pool") or "").strip()
    connection = _connect(paper_db)
    try:
        connection.execute("BEGIN IMMEDIATE")
        row = _open_position(
            connection,
            position_id=payload.get("position_id"),
            pool=pool or None,
            token=token or None,
        )
        if row is None:
            connection.rollback()
            raise HTTPException(status_code=404, detail="Açık paper pozisyon bulunamadı")

        position = dict(row)
        _, price, age = _fresh_quote(
            cache_db,
            pool=str(position.get("pool") or pool or ""),
            token=str(position.get("token") or token or ""),
        )
        accounting = _sell_accounting(position, price)
        gross = accounting["gross"]
        net = accounting["net"]
        roi = accounting["roi"]
        entry = float(position.get("entry_amount_usdt") or 0.0)
        high = max(float(position.get("highest_price") or price), price)
        low = min(float(position.get("lowest_price") or price), price)
        now = datetime.now(timezone.utc).isoformat()

        cursor = connection.execute(
            """
            UPDATE paper_trades
            SET status='CLOSED', closed_at=?, current_price=?, exit_price=?,
                highest_price=?, lowest_price=?, gross_pnl=?, net_pnl=?, roi=?,
                gross_pnl_usdt=?, net_pnl_usdt=?, close_reason=?, token_amount=0,
                remaining_cost_basis_usdt=0,
                realized_gross_proceeds_usdt=?, realized_proceeds_usdt=?, realized_pnl_usdt=?
            WHERE id=? AND status='OPEN'
            """,
            (
                now, price, price, high, low, gross, net, roi, gross, net,
                "MANUAL_PAPER_SELL", entry + gross, entry + net, net,
                int(position["id"]),
            ),
        )
        if cursor.rowcount != 1:
            connection.rollback()
            raise HTTPException(status_code=409, detail="Pozisyon kapanamadı")
        connection.commit()
        return {
            "ok": True, "side": "SELL", "position_id": int(position["id"]),
            "token": position.get("token"), "pool": position.get("pool"),
            "reference_price": price, "reference_price_age_seconds": age,
            "proceeds_usdt": accounting["proceeds"], "net_pnl_usdt": net,
            "roi_pct": roi * 100.0, "paper_only": True,
            "live_execution": False, "wallet_authority": False,
            "signing_authority": False,
        }
    except HTTPException:
        raise
    except sqlite3.Error as exc:
        connection.rollback()
        raise HTTPException(status_code=500, detail=f"Paper DB hatası: {type(exc).__name__}") from exc
    finally:
        connection.close()


def register_manual_paper_routes_v2(app, *, paper_db: Path, cache_db: Path) -> None:
    @app.post("/api/manual-paper/order-v2")
    def manual_paper_order_v2(payload: dict[str, Any]) -> dict[str, Any]:
        if payload.get("confirmed") is not True:
            raise HTTPException(status_code=400, detail="İşlem onayı gerekli")
        side = str(payload.get("side") or "").strip().upper()
        if side == "BUY":
            return _buy(paper_db=paper_db, cache_db=cache_db, payload=payload)
        if side == "SELL":
            return _sell(paper_db=paper_db, cache_db=cache_db, payload=payload)
        raise HTTPException(status_code=400, detail="Geçersiz işlem yönü")
