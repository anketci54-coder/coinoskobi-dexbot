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
from app.scanner.gecko_scanner import GeckoScanner
from app.strategy.mathematical_trade_plan import (
    buy_token_amount,
    decode_plan,
    exit_net_proceeds,
    initial_net_risk_usdt,
)


MANUAL_QUOTE_MAX_AGE_SECONDS = 300.0
MANUAL_PLAN_MAX_AGE_SECONDS = 300.0


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


def _cache_quotes(
    cache_db: Path,
    *,
    pool: str | None,
    token: str | None,
) -> list[dict[str, Any]]:
    if not cache_db.exists():
        return []

    connection = sqlite3.connect(
        f"file:{cache_db}?mode=ro",
        uri=True,
        timeout=3,
    )
    connection.row_factory = sqlite3.Row

    quotes: list[dict[str, Any]] = []

    try:
        tables = {
            str(row["name"])
            for row in connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type='table'
                """
            ).fetchall()
        }

        if "universe_pool_registry" in tables and pool:
            row = connection.execute(
                """
                SELECT
                    pool,
                    token0 AS token,
                    NULL AS name,
                    dex,
                    latest_price_usd AS price_usd,
                    latest_snapshot_at AS updated_at
                FROM universe_pool_registry
                WHERE lower(pool)=lower(?)
                ORDER BY latest_snapshot_at DESC
                LIMIT 1
                """,
                (pool,),
            ).fetchone()

            if row is not None:
                quote = dict(row)
                quote["quote_source"] = (
                    "UNIVERSE_POOL_REGISTRY"
                )
                quotes.append(quote)

        if "gecko_pool_cache" in tables:
            row = None

            if pool:
                row = connection.execute(
                    """
                    SELECT
                        pool,
                        token,
                        name,
                        dex,
                        price_usd,
                        updated_at
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
                    SELECT
                        pool,
                        token,
                        name,
                        dex,
                        price_usd,
                        updated_at
                    FROM gecko_pool_cache
                    WHERE lower(token)=lower(?)
                       OR lower(
                           replace(token,'bsc_','')
                       )=lower(?)
                    ORDER BY updated_at DESC
                    LIMIT 1
                    """,
                    (token, token),
                ).fetchone()

            if row is not None:
                quote = dict(row)
                quote["quote_source"] = (
                    "GECKO_POOL_CACHE"
                )
                quotes.append(quote)

        return quotes

    finally:
        connection.close()


def _ondemand_pool_quote(
    *,
    pool: str | None,
    token: str | None,
) -> tuple[dict[str, Any], float, float] | None:
    pool_key = str(pool or "").strip().lower()

    if not pool_key:
        return None

    try:
        rows = GeckoScanner().pool_snapshots(
            [pool_key],
            max_pools=1,
            persist_followups=False,
        )
    except Exception:
        return None

    for row in rows or []:
        row_pool = str(
            row.get("pool") or ""
        ).strip().lower()

        price = _num(
            row.get("price_usd")
        )

        if (
            row_pool != pool_key
            or price is None
            or price <= 0
        ):
            continue

        quote = {
            "pool": row.get("pool") or pool,
            "token": (
                row.get("base_token")
                or token
            ),
            "name": row.get("name"),
            "dex": row.get("dex"),
            "price_usd": price,
            "updated_at": time.time(),
            "quote_source": (
                "GECKOTERMINAL_ON_DEMAND"
            ),
        }

        return quote, price, 0.0

    return None


def _fresh_quote(
    cache_db: Path,
    *,
    pool: str | None,
    token: str | None,
) -> tuple[dict[str, Any], float, float]:
    candidates = []

    for quote in _cache_quotes(
        cache_db,
        pool=pool,
        token=token,
    ):
        price = _num(
            quote.get("price_usd")
        )
        observed = _timestamp(
            quote.get("updated_at")
        )

        if (
            price is None
            or price <= 0
            or observed is None
        ):
            continue

        candidates.append(
            (
                observed,
                price,
                quote,
            )
        )

    if candidates:
        observed, price, quote = max(
            candidates,
            key=lambda item: item[0],
        )

        age = max(
            0.0,
            time.time() - observed,
        )

        if age <= MANUAL_QUOTE_MAX_AGE_SECONDS:
            return quote, price, age

    ondemand = _ondemand_pool_quote(
        pool=pool,
        token=token,
    )

    if ondemand is not None:
        return ondemand

    if candidates:
        raise HTTPException(
            status_code=409,
            detail=(
                "Referans fiyat bayat ve "
                "anlık pool fiyatı alınamadı"
            ),
        )

    raise HTTPException(
        status_code=409,
        detail=(
            "Güncel referans fiyat yok ve "
            "anlık pool fiyatı alınamadı"
        ),
    )


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


def _latest_manual_candidate_plan(
    connection: sqlite3.Connection,
    *,
    pool: str,
    token: str,
) -> tuple[int, dict[str, Any], dict[str, Any], float]:
    try:
        row = connection.execute(
            """
            SELECT
                id,
                observed_at,
                context_json
            FROM candidate_decision_history
            WHERE lower(pool)=lower(?)
               OR lower(
                    replace(token,'bsc_','')
                  )=lower(
                    replace(?,'bsc_','')
                  )
            ORDER BY id DESC
            LIMIT 1
            """,
            (
                pool,
                token,
            ),
        ).fetchone()
    except sqlite3.Error as exc:
        raise HTTPException(
            status_code=409,
            detail=(
                "MANUAL plan kaynağı okunamadı"
            ),
        ) from exc

    if row is None:
        raise HTTPException(
            status_code=409,
            detail=(
                "Bu token için güncel matematiksel plan yok"
            ),
        )

    observed = _timestamp(
        row["observed_at"]
    )

    if observed is None:
        raise HTTPException(
            status_code=409,
            detail=(
                "MANUAL plan zaman damgası geçersiz"
            ),
        )

    age = max(
        0.0,
        time.time() - observed,
    )

    if age > MANUAL_PLAN_MAX_AGE_SECONDS:
        raise HTTPException(
            status_code=409,
            detail=(
                "Matematiksel plan bayat; "
                "adayın yeniden değerlendirilmesi gerekli"
            ),
        )

    try:
        context = json.loads(
            row["context_json"] or "{}"
        )
    except Exception as exc:
        raise HTTPException(
            status_code=409,
            detail=(
                "MANUAL plan context verisi geçersiz"
            ),
        ) from exc

    if not isinstance(
        context,
        dict,
    ):
        raise HTTPException(
            status_code=409,
            detail=(
                "MANUAL plan context verisi geçersiz"
            ),
        )

    plan = context.get(
        "mathematical_plan"
    )

    if not isinstance(
        plan,
        dict,
    ):
        raise HTTPException(
            status_code=409,
            detail=(
                "Matematiksel trade plan bulunamadı"
            ),
        )

    hard_block = bool(
        context.get(
            "hard_block"
        )
    ) or bool(
        plan.get(
            "hard_block"
        )
    )

    if hard_block:
        raise HTTPException(
            status_code=409,
            detail=(
                "Risk Gate hard block aktif; "
                "manuel alım yapılamaz"
            ),
        )

    sellability = str(
        context.get(
            "sellability"
        )
        or plan.get(
            "sellability_status"
        )
        or "UNKNOWN"
    ).upper()

    if sellability != "SELLABILITY_OK":
        raise HTTPException(
            status_code=409,
            detail=(
                "Sellability güvenli değil; "
                "manuel alım yapılamaz"
            ),
        )

    return (
        int(row["id"]),
        context,
        plan,
        age,
    )


def _prepare_manual_buy(
    *,
    paper_db: Path,
    cache_db: Path,
    payload: dict[str, Any],
) -> dict[str, Any]:
    token = str(
        payload.get("token")
        or ""
    ).strip()

    pool = str(
        payload.get("pool")
        or ""
    ).strip()

    symbol = str(
        payload.get("symbol")
        or ""
    ).strip()[:80]

    amount = _num(
        payload.get(
            "amount_usdt"
        )
    )

    if not token or not pool:
        raise HTTPException(
            status_code=400,
            detail="Token/pool eksik",
        )

    if amount is None or amount <= 0:
        raise HTTPException(
            status_code=400,
            detail=(
                "Geçerli USDT miktarı gir"
            ),
        )

    quote, price, quote_age = (
        _fresh_quote(
            cache_db,
            pool=pool,
            token=token,
        )
    )

    connection = _connect(
        paper_db
    )

    try:
        (
            candidate_id,
            candidate_context,
            source_plan,
            plan_age,
        ) = _latest_manual_candidate_plan(
            connection,
            pool=pool,
            token=token,
        )

    finally:
        connection.close()

    plan = json.loads(
        json.dumps(
            source_plan
        )
    )

    sl_plan = (
        plan.get("sl")
        if isinstance(
            plan.get("sl"),
            dict,
        )
        else {}
    )

    statistics = (
        plan.get("statistics")
        if isinstance(
            plan.get("statistics"),
            dict,
        )
        else {}
    )

    risk_distance = _num(
        sl_plan.get(
            "risk_log_distance"
        )
    )

    if (
        risk_distance is None
        or risk_distance <= 0
    ):
        risk_distance = _num(
            statistics.get(
                "risk_log_distance"
            )
        )

    if (
        risk_distance is None
        or risk_distance <= 0
    ):
        raise HTTPException(
            status_code=409,
            detail=(
                "Risk mesafesi hazır değil; "
                "manuel NORMAL plan üretilemedi"
            ),
        )

    cost_model = (
        dict(
            plan.get(
                "cost_model"
            )
            or {}
        )
    )

    token_amount = (
        buy_token_amount(
            amount,
            price,
            cost_model,
        )
    )

    if token_amount <= 0:
        raise HTTPException(
            status_code=409,
            detail=(
                "Token miktarı hesaplanamadı"
            ),
        )

    system_sl = (
        price
        * math.exp(
            -risk_distance
        )
    )

    user_sl_raw = payload.get(
        "sl_price"
    )

    user_sl = (
        _num(user_sl_raw)
        if user_sl_raw
        not in (None, "")
        else None
    )

    if user_sl is not None:
        if (
            user_sl <= 0
            or user_sl >= price
        ):
            raise HTTPException(
                status_code=400,
                detail=(
                    "SL, entry fiyatından düşük "
                    "pozitif bir fiyat olmalı"
                ),
            )

        effective_sl = user_sl
        sl_source = (
            "USER_OVERRIDDEN"
        )

    else:
        effective_sl = system_sl
        sl_source = "SYSTEM"

    effective_risk_distance = (
        math.log(
            price / effective_sl
        )
    )

    initial_risk = (
        initial_net_risk_usdt(
            token_amount,
            amount,
            effective_sl,
            cost_model,
        )
    )

    if (
        initial_risk is None
        or not math.isfinite(
            float(initial_risk)
        )
        or float(initial_risk) <= 0
    ):
        raise HTTPException(
            status_code=409,
            detail=(
                "Başlangıç net riski "
                "hesaplanamadı"
            ),
        )

    initial_risk = float(
        initial_risk
    )

    sell_retention = _num(
        cost_model.get(
            "sell_retention_known"
        )
    )

    if (
        sell_retention is None
        or sell_retention <= 0
    ):
        raise HTTPException(
            status_code=409,
            detail=(
                "TP1 için sell retention "
                "verisi hazır değil"
            ),
        )

    sell_gas = max(
        0.0,
        _num(
            cost_model.get(
                "sell_gas_usd"
            )
        )
        or 0.0,
    )

    system_tp1 = (
        amount
        + initial_risk
        + sell_gas
    ) / (
        token_amount
        * sell_retention
    )

    user_tp1_raw = payload.get(
        "tp1_price"
    )

    user_tp1 = (
        _num(user_tp1_raw)
        if user_tp1_raw
        not in (None, "")
        else None
    )

    if user_tp1 is not None:
        if user_tp1 <= price:
            raise HTTPException(
                status_code=400,
                detail=(
                    "TP1 entry fiyatından "
                    "yüksek olmalı"
                ),
            )

        effective_tp1 = user_tp1
        tp1_source = (
            "USER_OVERRIDDEN"
        )

    else:
        effective_tp1 = (
            system_tp1
        )
        tp1_source = "SYSTEM"

    level_source = (
        "USER_OVERRIDDEN"
        if (
            sl_source
            == "USER_OVERRIDDEN"
            or tp1_source
            == "USER_OVERRIDDEN"
        )
        else "SYSTEM"
    )

    entry_plan = (
        plan.setdefault(
            "entry",
            {},
        )
    )

    capital_plan = (
        plan.setdefault(
            "capital",
            {},
        )
    )

    position_plan = (
        plan.setdefault(
            "position",
            {},
        )
    )

    sl_plan = (
        plan.setdefault(
            "sl",
            {},
        )
    )

    tp1_plan = (
        plan.setdefault(
            "tp1",
            {},
        )
    )

    plan["contract"] = (
        "mathematical_trade_plan"
    )

    entry_plan["price"] = price

    capital_plan[
        "entry_amount_usdt"
    ] = amount

    position_plan[
        "token_amount"
    ] = token_amount

    position_plan[
        "initial_risk_usdt"
    ] = initial_risk

    sl_plan[
        "initial_price"
    ] = effective_sl

    sl_plan[
        "risk_log_distance"
    ] = effective_risk_distance

    tp1_plan[
        "activation_price"
    ] = effective_tp1

    plan[
        "manual_control"
    ] = {
        "control_mode": "MANUAL",
        "trade_type": "NORMAL",
        "candidate_decision_id": (
            candidate_id
        ),
        "candidate_plan_age_seconds": (
            plan_age
        ),
        "quote_age_seconds": (
            quote_age
        ),
        "level_source": (
            level_source
        ),
        "sl_source": sl_source,
        "tp1_source": tp1_source,
        "tp2_mode": (
            "DYNAMIC_PRINCIPAL_RECOVERY"
        ),
        "tp3_mode": (
            "TREND_RUNNER"
        ),
        "hard_safety_bypassed": False,
        "sellability_bypassed": False,
        "live_authority": False,
        "wallet_authority": False,
        "signing_authority": False,
        "execution_authority": False,
    }

    return {
        "token": token,
        "pool": pool,
        "symbol": symbol,
        "amount_usdt": amount,
        "quote": quote,
        "entry_price": price,
        "quote_age_seconds": quote_age,
        "candidate_id": candidate_id,
        "candidate_context": (
            candidate_context
        ),
        "plan_age_seconds": plan_age,
        "plan": plan,
        "cost_model": cost_model,
        "token_amount": token_amount,
        "initial_risk_usdt": (
            initial_risk
        ),
        "system_sl_price": system_sl,
        "sl_price": effective_sl,
        "system_tp1_price": (
            system_tp1
        ),
        "tp1_price": effective_tp1,
        "sl_source": sl_source,
        "tp1_source": tp1_source,
        "level_source": level_source,
    }


def _preview_buy(
    *,
    paper_db: Path,
    cache_db: Path,
    payload: dict[str, Any],
) -> dict[str, Any]:
    prepared = (
        _prepare_manual_buy(
            paper_db=paper_db,
            cache_db=cache_db,
            payload=payload,
        )
    )

    return {
        "ok": True,
        "side": "BUY_PREVIEW",
        "preview_only": True,
        "paper_only": True,
        "token": prepared[
            "token"
        ],
        "pool": prepared[
            "pool"
        ],
        "amount_usdt": prepared[
            "amount_usdt"
        ],
        "reference_price": prepared[
            "entry_price"
        ],
        "reference_price_age_seconds": (
            prepared[
                "quote_age_seconds"
            ]
        ),
        "reference_price_source": (
            prepared[
                "quote"
            ].get(
                "quote_source"
            )
        ),
        "candidate_decision_id": (
            prepared[
                "candidate_id"
            ]
        ),
        "candidate_plan_age_seconds": (
            prepared[
                "plan_age_seconds"
            ]
        ),
        "token_amount": prepared[
            "token_amount"
        ],
        "initial_risk_usdt": (
            prepared[
                "initial_risk_usdt"
            ]
        ),
        "system_sl_price": (
            prepared[
                "system_sl_price"
            ]
        ),
        "sl_price": prepared[
            "sl_price"
        ],
        "system_tp1_price": (
            prepared[
                "system_tp1_price"
            ]
        ),
        "tp1_price": prepared[
            "tp1_price"
        ],
        "tp2_mode": (
            "DYNAMIC_PRINCIPAL_RECOVERY"
        ),
        "tp3_mode": (
            "TREND_RUNNER"
        ),
        "control_mode": "MANUAL",
        "trade_type": "NORMAL",
        "level_source": prepared[
            "level_source"
        ],
        "sl_source": prepared[
            "sl_source"
        ],
        "tp1_source": prepared[
            "tp1_source"
        ],
        "risk_gate_bypassed": False,
        "live_execution": False,
        "wallet_authority": False,
        "signing_authority": False,
    }


def _buy(
    *,
    paper_db: Path,
    cache_db: Path,
    payload: dict[str, Any],
) -> dict[str, Any]:
    prepared = (
        _prepare_manual_buy(
            paper_db=paper_db,
            cache_db=cache_db,
            payload=payload,
        )
    )

    token = prepared["token"]
    pool = prepared["pool"]
    symbol = prepared["symbol"]
    amount = prepared[
        "amount_usdt"
    ]
    quote = prepared["quote"]
    price = prepared[
        "entry_price"
    ]
    token_amount = prepared[
        "token_amount"
    ]
    initial_risk = prepared[
        "initial_risk_usdt"
    ]
    sl_price = prepared[
        "sl_price"
    ]
    tp1_price = prepared[
        "tp1_price"
    ]
    plan = prepared["plan"]
    cost_model = prepared[
        "cost_model"
    ]

    connection = _connect(
        paper_db
    )

    try:
        connection.execute(
            "BEGIN IMMEDIATE"
        )

        if _open_position(
            connection,
            pool=pool,
            token=token,
        ) is not None:
            connection.rollback()

            raise HTTPException(
                status_code=409,
                detail=(
                    "Bu varlıkta zaten açık "
                    "paper pozisyon var"
                ),
            )

        available = float(
            paper_available_capital_usdt(
                connection,
                PAPER_CAPITAL_USDT,
            )
        )

        if amount > available + 1e-9:
            connection.rollback()

            raise HTTPException(
                status_code=409,
                detail=(
                    "Yetersiz paper bakiye: "
                    f"{available:.2f} USDT"
                ),
            )

        now = (
            datetime.now(
                timezone.utc
            ).isoformat()
        )

        context = {
            "source": "MANUAL_PANEL",
            "manual_confirmed": True,
            "captured_at_entry": True,
            "reference_price": price,
            "reference_price_age_seconds": (
                prepared[
                    "quote_age_seconds"
                ]
            ),
            "reference_price_source": (
                quote.get(
                    "quote_source"
                )
            ),
            "candidate_decision_id": (
                prepared[
                    "candidate_id"
                ]
            ),
            "candidate_plan_age_seconds": (
                prepared[
                    "plan_age_seconds"
                ]
            ),
            "control_mode": "MANUAL",
            "trade_type": "NORMAL",
            "level_source": prepared[
                "level_source"
            ],
            "level_sources": {
                "sl": prepared[
                    "sl_source"
                ],
                "tp1": prepared[
                    "tp1_source"
                ],
                "tp2": (
                    "SYSTEM_DYNAMIC"
                ),
                "tp3": (
                    "SYSTEM_DYNAMIC"
                ),
            },
            "hard_safety_bypassed": False,
            "sellability_bypassed": False,
            "paper_only": True,
            "live_execution": False,
            "wallet_authority": False,
            "signing_authority": False,
        }

        values = {
            "created_at": now,
            "token": token,
            "symbol": (
                symbol
                or str(
                    quote.get("name")
                    or token
                )[:80]
            ),
            "entry_price": price,
            "current_price": price,
            "highest_price": price,
            "lowest_price": price,
            "tp_price": tp1_price,
            "sl_price": sl_price,
            "amount_bnb": 0.0,
            "status": "OPEN",
            "token_amount": (
                token_amount
            ),
            "initial_token_amount": (
                token_amount
            ),
            "pool": pool,
            "dex": quote.get(
                "dex"
            ),
            "opening_context_json": (
                json.dumps(
                    context,
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
            ),
            "paper_account_version": (
                "PAPER_10K_V2"
            ),
            "trade_policy": (
                "MANUAL_PANEL"
            ),
            "control_mode": (
                "MANUAL"
            ),
            "trade_type": (
                "NORMAL"
            ),
            "level_source": prepared[
                "level_source"
            ],
            "cost_model_complete": (
                int(
                    bool(
                        cost_model.get(
                            "cost_complete"
                        )
                    )
                )
            ),
            "entry_amount_usdt": (
                amount
            ),
            "risk_amount_usdt": (
                initial_risk
            ),
            "capital_before_usdt": (
                available
            ),
            "capital_after_entry_usdt": (
                available - amount
            ),
            "position_size_pct": (
                amount
                / available
                * 100.0
                if available > 0
                else 0.0
            ),
            "sizing_reason": (
                "MANUAL_NORMAL_CONFIRMED"
            ),
            "remaining_cost_basis_usdt": (
                amount
            ),
            "tp1_done": 0,
            "tp2_done": 0,
            "runner_active": 0,
            "mathematical_plan_json": (
                json.dumps(
                    plan,
                    sort_keys=True,
                    separators=(",", ":"),
                )
            ),
            "math_state_json": (
                json.dumps(
                    {
                        "initial_net_risk_usdt": (
                            initial_risk
                        )
                    },
                    sort_keys=True,
                    separators=(",", ":"),
                )
            ),
        }

        columns = ", ".join(
            values
        )

        placeholders = ", ".join(
            "?"
            for _ in values
        )

        connection.execute(
            f"""
            INSERT INTO paper_trades(
                {columns}
            )
            VALUES(
                {placeholders}
            )
            """,
            list(
                values.values()
            ),
        )

        position_id = int(
            connection.execute(
                "SELECT last_insert_rowid()"
            ).fetchone()[0]
        )

        connection.commit()

        return {
            "ok": True,
            "side": "BUY",
            "position_id": (
                position_id
            ),
            "token": token,
            "pool": pool,
            "reference_price": price,
            "reference_price_age_seconds": (
                prepared[
                    "quote_age_seconds"
                ]
            ),
            "reference_price_source": (
                quote.get(
                    "quote_source"
                )
            ),
            "amount_usdt": amount,
            "token_amount": (
                token_amount
            ),
            "initial_risk_usdt": (
                initial_risk
            ),
            "sl_price": sl_price,
            "tp1_price": tp1_price,
            "tp2_mode": (
                "DYNAMIC_PRINCIPAL_RECOVERY"
            ),
            "tp3_mode": (
                "TREND_RUNNER"
            ),
            "control_mode": (
                "MANUAL"
            ),
            "trade_type": (
                "NORMAL"
            ),
            "level_source": (
                prepared[
                    "level_source"
                ]
            ),
            "paper_balance_after": (
                available - amount
            ),
            "paper_only": True,
            "live_execution": False,
            "wallet_authority": False,
            "signing_authority": False,
        }

    except HTTPException:
        raise

    except sqlite3.Error as exc:
        connection.rollback()

        raise HTTPException(
            status_code=500,
            detail=(
                "Paper DB hatası: "
                f"{type(exc).__name__}"
            ),
        ) from exc

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



def _latest_m5_change(
    cache_db: Path,
    *,
    pool: str | None,
) -> float | None:
    if not cache_db.exists() or not pool:
        return None

    connection = None

    try:
        connection = sqlite3.connect(
            f"file:{cache_db}?mode=ro",
            uri=True,
            timeout=3,
        )
        connection.row_factory = sqlite3.Row

        table = connection.execute(
            """
            SELECT 1
            FROM sqlite_master
            WHERE type='table'
              AND name='universe_pool_registry'
            """
        ).fetchone()

        if table is None:
            return None

        columns = {
            str(row[1])
            for row in connection.execute(
                "PRAGMA table_info(universe_pool_registry)"
            ).fetchall()
        }

        if "latest_change_5m" not in columns:
            return None

        row = connection.execute(
            """
            SELECT latest_change_5m
            FROM universe_pool_registry
            WHERE lower(pool)=lower(?)
            ORDER BY latest_snapshot_at DESC
            LIMIT 1
            """,
            (pool,),
        ).fetchone()

        return (
            _num(row["latest_change_5m"])
            if row is not None
            else None
        )

    except sqlite3.Error:
        return None

    finally:
        if connection is not None:
            connection.close()


def _manual_sell_guidance(
    *,
    roi_pct: float,
    change_5m_pct: float | None,
) -> tuple[str, str, str]:
    if change_5m_pct is None:
        if roi_pct > 0:
            return (
                "PROFIT_M5_UNKNOWN",
                "KÂR VAR · M5 TEYİDİ YOK",
                (
                    "Pozisyon kârda fakat kısa hareket verisi eksik. "
                    "Kârı koruma açısından güncel satış fiyatını değerlendir."
                ),
            )

        return (
            "M5_UNKNOWN",
            "TEYİT EKSİK",
            (
                "Kısa hareket verisi eksik. "
                "Karar vermeden önce güncel fiyat hareketini izle."
            ),
        )

    if roi_pct > 0 and change_5m_pct < 0:
        return (
            "PROFIT_MOMENTUM_WEAKENING",
            "KÂRI KORU",
            (
                "Pozisyon kârda fakat 5 dakikalık hareket zayıflıyor. "
                "Satışı değerlendir; kârın geri verilmesini izle."
            ),
        )

    if roi_pct > 0 and change_5m_pct > 0:
        return (
            "PROFIT_MOMENTUM_POSITIVE",
            "MOMENTUM SÜRÜYOR",
            (
                "Pozisyon kârda ve kısa hareket pozitif. "
                "Momentum sürerken izle; zayıflama halinde satışı değerlendir."
            ),
        )

    if roi_pct <= 0 and change_5m_pct < 0:
        return (
            "LOSS_PRESSURE",
            "ZARAR BASKISI",
            (
                "Pozisyon zararda ve kısa hareket de negatif. "
                "Zararın büyümesine karşı satışı değerlendir."
            ),
        )

    return (
        "RECOVERY_OR_FLAT",
        "TOPARLANMAYI İZLE",
        (
            "Pozisyon henüz kârda değil fakat kısa hareket negatif değil. "
            "Toparlanmanın devam edip etmediğini izle."
        ),
    )


def _preview_sell(
    *,
    paper_db: Path,
    cache_db: Path,
    payload: dict[str, Any],
) -> dict[str, Any]:
    token = str(payload.get("token") or "").strip()
    pool = str(payload.get("pool") or "").strip()

    connection = _connect(paper_db)

    try:
        row = _open_position(
            connection,
            position_id=payload.get("position_id"),
            pool=pool or None,
            token=token or None,
        )

        if row is None:
            raise HTTPException(
                status_code=404,
                detail="Açık paper pozisyon bulunamadı",
            )

        position = dict(row)

    finally:
        connection.close()

    quote, price, age = _fresh_quote(
        cache_db,
        pool=str(position.get("pool") or pool or ""),
        token=str(position.get("token") or token or ""),
    )

    accounting = _sell_accounting(
        position,
        price,
    )

    entry_price = float(
        position.get("entry_price")
        or 0.0
    )

    entry_amount = float(
        position.get("entry_amount_usdt")
        or 0.0
    )

    token_amount = float(
        position.get("token_amount")
        or 0.0
    )

    roi_pct = float(
        accounting["roi"]
    ) * 100.0

    change_5m_pct = _latest_m5_change(
        cache_db,
        pool=str(position.get("pool") or ""),
    )

    code, label, guidance = (
        _manual_sell_guidance(
            roi_pct=roi_pct,
            change_5m_pct=change_5m_pct,
        )
    )

    break_even_price = None

    if (
        entry_price > 0
        and entry_amount > 0
        and token_amount > 0
    ):
        try:
            at_entry = _sell_accounting(
                position,
                entry_price,
            )

            friction_at_entry = max(
                0.0,
                -float(at_entry["net"]),
            )

            break_even_price = (
                entry_amount
                + friction_at_entry
            ) / token_amount

        except Exception:
            break_even_price = None

    high = max(
        float(
            position.get("highest_price")
            or entry_price
            or price
        ),
        price,
    )

    low = min(
        float(
            position.get("lowest_price")
            or entry_price
            or price
        ),
        price,
    )

    return {
        "ok": True,
        "side": "SELL_PREVIEW",
        "position_id": int(position["id"]),
        "symbol": position.get("symbol"),
        "token": position.get("token"),
        "pool": position.get("pool"),

        "entry_price": entry_price,
        "reference_price": price,
        "reference_price_age_seconds": age,
        "reference_price_source": (
            quote.get("quote_source")
        ),

        "break_even_price": break_even_price,
        "highest_price": high,
        "lowest_price": low,
        "change_5m_pct": change_5m_pct,

        "proceeds_usdt": float(
            accounting["proceeds"]
        ),
        "net_pnl_usdt": float(
            accounting["net"]
        ),
        "roi_pct": roi_pct,

        "guidance_code": code,
        "guidance_label": label,
        "guidance_text": guidance,

        "paper_only": True,
        "preview_only": True,
        "decision_authority": False,
        "live_execution": False,
        "wallet_authority": False,
        "signing_authority": False,
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

        expected_net_raw = payload.get("expected_net_pnl_usdt")
        if expected_net_raw is not None:
            try:
                expected_net = float(expected_net_raw)
            except (TypeError, ValueError):
                expected_net = None

            if expected_net is not None:
                sign_flipped = (
                    (expected_net > 0.0 and net < 0.0)
                    or
                    (expected_net < 0.0 and net > 0.0)
                )

                if sign_flipped:
                    connection.rollback()
                    raise HTTPException(
                        status_code=409,
                        detail=(
                            "Fiyat ve PNL önizlemeden sonra yön değiştirdi; "
                            "satış yapılmadı. Pozisyonu yeniden inceleyin."
                        ),
                    )

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
    @app.post("/api/manual-paper/preview-v2")
    def manual_paper_preview_v2(payload: dict[str, Any]) -> dict[str, Any]:
        side = str(
            payload.get("side")
            or "SELL"
        ).strip().upper()

        if side == "BUY":
            return _preview_buy(
                paper_db=paper_db,
                cache_db=cache_db,
                payload=payload,
            )

        return _preview_sell(
            paper_db=paper_db,
            cache_db=cache_db,
            payload=payload,
        )

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
