from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from pathlib import Path
from typing import Any
import json
import re
import shutil
import sqlite3
import subprocess

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles


BASE_DIR = Path(__file__).resolve().parents[2]
PAPER_DB = BASE_DIR / "data" / "paper_trades.db"
CACHE_DB = BASE_DIR / "data" / "cache" / "cache.db"
STATIC_DIR = BASE_DIR / "app" / "api" / "static"

PANEL_TIMEZONE_NAME = "Asia/Nicosia"
PANEL_TIMEZONE = ZoneInfo(PANEL_TIMEZONE_NAME)
INDEX_FILE = STATIC_DIR / "index.html"

PAPER_STARTING_CAPITAL_USDT = 10_000.0

# Active dashboard epoch. Historical paper trades are archived outside
# the active paper_trades table; the clean runtime generation starts at ID 1.
PANEL_ACTIVE_PERIOD_MIN_TRADE_ID = 1
PANEL_ACTIVE_PERIOD_LABEL = "PAPER_ACTIVE_ID_1_PLUS"


app = FastAPI(
    title="Coinoskobi İşlem Merkezi",
    version="1.0",
)

app.mount(
    "/static",
    StaticFiles(directory=str(STATIC_DIR)),
    name="static",
)


def connect_readonly() -> sqlite3.Connection:
    uri = f"file:{PAPER_DB}?mode=ro"

    connection = sqlite3.connect(
        uri,
        uri=True,
        timeout=5,
    )
    connection.row_factory = sqlite3.Row

    return connection


def query(
    sql: str,
    params: tuple[Any, ...] = (),
) -> list[dict[str, Any]]:
    connection = connect_readonly()

    try:
        return [
            dict(row)
            for row in connection.execute(
                sql,
                params,
            ).fetchall()
        ]
    finally:
        connection.close()


def query_one(
    sql: str,
    params: tuple[Any, ...] = (),
) -> dict[str, Any]:
    rows = query(sql, params)
    return rows[0] if rows else {}


def table_exists(table_name: str) -> bool:
    row = query_one(
        """
        SELECT COUNT(*) AS count
        FROM sqlite_master
        WHERE type IN ('table', 'view')
          AND name = ?
        """,
        (table_name,),
    )

    return bool(row.get("count"))


def table_count(table_name: str) -> int:
    allowed = {
        "wallet_discovery_registry",
        "wallet_success_score",
        "wallet_outcome_evidence",
        "whale_activity_snapshot",
        "wallet_activity_bucket",
        "intelligence_summary_readmodel",
    }

    if table_name not in allowed:
        return 0

    if not table_exists(table_name):
        return 0

    row = query_one(
        f'SELECT COUNT(*) AS count FROM "{table_name}"'
    )

    return int(row.get("count") or 0)



def runtime_cache_snapshot() -> dict[str, dict[str, dict[str, Any]]]:
    """
    Read-only projection of the current Gecko scanner cache.

    The panel never creates or updates cache rows.
    """

    snapshot: dict[str, dict[str, dict[str, Any]]] = {
        "by_pool": {},
        "by_token": {},
    }

    if not CACHE_DB.exists():
        return snapshot

    connection = None

    try:
        connection = sqlite3.connect(
            f"file:{CACHE_DB}?mode=ro",
            uri=True,
            timeout=2,
        )
        connection.row_factory = sqlite3.Row

        rows = connection.execute(
            """
            SELECT
                pool,
                token,
                quote_token,
                name,
                dex,
                liquidity,
                volume24 AS volume_24h,
                buys24 AS buys_24h,
                fdv,
                price_usd,
                created_at,
                updated_at
            FROM gecko_pool_cache
            """
        ).fetchall()

    except Exception:
        return snapshot

    finally:
        if connection is not None:
            connection.close()

    for raw in rows:
        row = dict(raw)

        pool = str(
            row.get("pool") or ""
        ).strip().lower()

        token = str(
            row.get("token") or ""
        ).strip().lower()

        if token.startswith("bsc_"):
            token = token[4:]

        if pool:
            snapshot["by_pool"][pool] = row

        if token:
            snapshot["by_token"][token] = row

    return snapshot


def parse_json_object(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)

    if not value:
        return {}

    try:
        parsed = json.loads(value)
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}

    return dict(parsed) if isinstance(parsed, dict) else {}


def first_value(
    sources: list[dict[str, Any]],
    *keys: str,
) -> Any:
    for source in sources:
        if not isinstance(source, dict):
            continue

        for key in keys:
            value = source.get(key)

            if value is not None:
                return value

    return None


def number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def service_state(service_name: str) -> str:
    try:
        result = subprocess.run(
            [
                "systemctl",
                "is-active",
                service_name,
            ],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )

        state = result.stdout.strip()

        return state or "unknown"

    except Exception:
        return "unknown"


def extract_entry_evidence(
    opening_context_json: Any,
) -> dict[str, Any]:
    context = parse_json_object(opening_context_json)

    raw_signals = parse_json_object(
        context.get("raw_signals")
    )
    attribution = parse_json_object(
        context.get("signal_attribution")
    )
    baseline = parse_json_object(
        context.get("exit_baseline")
    )
    market_context = parse_json_object(
        raw_signals.get("market_context")
        or context.get("market_context")
    )

    sources = [
        raw_signals,
        attribution,
        market_context,
        baseline,
        context,
    ]

    hard_block_value = first_value(
        sources,
        "hard_block",
    )

    return {
        "captured_at_entry": bool(
            context.get("captured_at_entry")
        ),
        "hindsight_reconstructed": bool(
            context.get("hindsight_reconstructed")
        ),
        "strategy_decision": first_value(
            sources,
            "strategy_decision",
            "historical_action",
        ),
        "unified_decision": first_value(
            sources,
            "unified_decision",
            "paper_admission_decision",
        ),
        "score": first_value(
            sources,
            "unified_score",
            "score",
        ),
        "confidence": first_value(
            sources,
            "unified_confidence",
            "confidence",
        ),
        "coverage": first_value(
            sources,
            "unified_coverage",
            "coverage",
        ),
        "hard_block": (
            bool(hard_block_value)
            if hard_block_value is not None
            else None
        ),
        "sellability": first_value(
            sources,
            "sellability_status",
            "sellability",
        ),
        "liquidity": first_value(
            sources,
            "liquidity_health",
            "liquidity_state",
            "liquidity",
        ),
        "range_state": first_value(
            sources,
            "shooting_range",
            "atis_poligonu",
            "range_state",
            "simulation_state",
        ),
        "trend": first_value(
            sources,
            "trend",
            "trend_health",
            "reserve_trend",
        ),
        "timing": first_value(
            sources,
            "timing",
            "entry_timing",
            "timing_state",
        ),
        "market_state": first_value(
            sources,
            "market_state",
            "market_structure",
            "market_regime",
        ),
        "entry_price": baseline.get("entry_price"),
        "stop_loss_price": baseline.get(
            "stop_loss_price"
        ),
        "take_profit_price": baseline.get(
            "take_profit_price"
        ),
        "signal_attribution": attribution,
    }



def paper_rows(
    limit: int = 100,
    *,
    active_only: bool = False,
) -> list[dict[str, Any]]:
    where_clause = (
        "WHERE paper_account_version = "
        "'PAPER_10K_V2'"
    )

    params: list[Any] = []

    if active_only:
        where_clause += (
            " AND id >= ?"
        )
        params.append(
            PANEL_ACTIVE_PERIOD_MIN_TRADE_ID
        )

    params.append(limit)

    rows = query(
        f"""
        SELECT
            id,
            created_at,
            closed_at,
            token,
            symbol,
            entry_price,
            current_price,
            exit_price,
            highest_price,
            lowest_price,
            tp_price,
            sl_price,
            amount_bnb,
            gross_pnl,
            net_pnl,
            roi,
            gas_buy,
            gas_sell,
            swap_fee,
            buy_tax,
            sell_tax,
            slippage,
            mev,
            close_reason,
            status,
            token_amount,
            pool,
            dex,
            opening_context_json,
            paper_account_version,
            trade_policy,
            cost_model_complete,
            entry_amount_usdt,
            risk_amount_usdt,
            capital_before_usdt,
            capital_after_entry_usdt,
            position_size_pct,
            sizing_reason,
            gross_pnl_usdt,
            net_pnl_usdt
        FROM paper_trades
        {where_clause}
        ORDER BY id DESC
        LIMIT ?
        """,
        tuple(params),
    )

    result: list[dict[str, Any]] = []

    for row in rows:
        item = dict(row)

        roi = number(
            item.get("roi")
        )

        item["roi_pct"] = (
            roi * 100.0
        )

        item["entry_evidence"] = (
            extract_entry_evidence(
                item.pop(
                    "opening_context_json",
                    None,
                )
            )
        )

        result.append(item)

    return result




def performance_payload(
    *,
    active_only: bool = False,
) -> dict[str, Any]:
    active_filter = ""
    params: tuple[Any, ...] = ()

    if active_only:
        active_filter = (
            " AND id >= ?"
        )
        params = (
            PANEL_ACTIVE_PERIOD_MIN_TRADE_ID,
        )

    row = query_one(
        f"""
        SELECT
            COUNT(*) AS closed,
            SUM(
                CASE
                WHEN COALESCE(
                    net_pnl_usdt,
                    net_pnl,
                    0
                ) > 0
                THEN 1 ELSE 0
                END
            ) AS wins,
            SUM(
                CASE
                WHEN COALESCE(
                    net_pnl_usdt,
                    net_pnl,
                    0
                ) < 0
                THEN 1 ELSE 0
                END
            ) AS losses,
            AVG(roi) AS avg_roi,
            COALESCE(
                SUM(
                    COALESCE(
                        net_pnl_usdt,
                        net_pnl,
                        0
                    )
                ),
                0
            ) AS realized_net,
            COALESCE(
                SUM(
                    CASE
                    WHEN COALESCE(
                        net_pnl_usdt,
                        net_pnl,
                        0
                    ) > 0
                    THEN COALESCE(
                        net_pnl_usdt,
                        net_pnl,
                        0
                    )
                    ELSE 0
                    END
                ),
                0
            ) AS gross_profit,
            COALESCE(
                SUM(
                    CASE
                    WHEN COALESCE(
                        net_pnl_usdt,
                        net_pnl,
                        0
                    ) < 0
                    THEN ABS(
                        COALESCE(
                            net_pnl_usdt,
                            net_pnl,
                            0
                        )
                    )
                    ELSE 0
                    END
                ),
                0
            ) AS gross_loss,
            SUM(
                CASE
                WHEN COALESCE(
                    cost_model_complete,
                    0
                ) = 1
                THEN 1 ELSE 0
                END
            ) AS cost_complete
        FROM paper_trades
        WHERE paper_account_version = 'PAPER_10K_V2'
          AND UPPER(
                COALESCE(
                    status,
                    ''
                )
              ) = 'CLOSED'
          {active_filter}
        """,
        params,
    )

    closed = int(
        row.get("closed") or 0
    )

    wins = int(
        row.get("wins") or 0
    )

    losses = int(
        row.get("losses") or 0
    )

    avg_roi = row.get(
        "avg_roi"
    )

    avg_roi_pct = (
        number(avg_roi) * 100.0
        if avg_roi is not None
        else None
    )

    gross_profit = number(
        row.get("gross_profit")
    )

    gross_loss = number(
        row.get("gross_loss")
    )

    profit_factor = (
        gross_profit / gross_loss
        if gross_loss > 0
        else None
    )

    cost_complete = int(
        row.get("cost_complete") or 0
    )

    return {
        "closed": closed,
        "wins": (
            wins
            if closed
            else None
        ),
        "losses": (
            losses
            if closed
            else None
        ),
        "win_rate_pct": (
            wins / closed * 100.0
            if closed
            else None
        ),
        "avg_roi_pct": avg_roi_pct,
        "net_total": number(
            row.get("realized_net")
        ),
        "gross_profit": gross_profit,
        "gross_loss": gross_loss,
        "profit_factor": profit_factor,
        "cost_complete": cost_complete,
        "cost_incomplete": max(
            0,
            closed - cost_complete,
        ),
    }





def policy_performance_payload(
    *,
    active_only: bool = False,
) -> list[dict[str, Any]]:
    active_filter = ""
    params: tuple[Any, ...] = ()

    if active_only:
        active_filter = " AND id >= ?"
        params = (
            PANEL_ACTIVE_PERIOD_MIN_TRADE_ID,
        )

    rows = query(
        f"""
        SELECT
            COALESCE(
                NULLIF(
                    UPPER(TRIM(trade_policy)),
                    ''
                ),
                'LEGACY'
            ) AS trade_policy,

            COUNT(*) AS closed,

            SUM(
                CASE
                WHEN COALESCE(
                    net_pnl_usdt,
                    net_pnl,
                    0
                ) > 0
                THEN 1 ELSE 0
                END
            ) AS wins,

            SUM(
                CASE
                WHEN COALESCE(
                    net_pnl_usdt,
                    net_pnl,
                    0
                ) < 0
                THEN 1 ELSE 0
                END
            ) AS losses,

            AVG(roi) * 100.0 AS avg_roi_pct,

            COALESCE(
                SUM(
                    COALESCE(
                        net_pnl_usdt,
                        net_pnl,
                        0
                    )
                ),
                0
            ) AS net_total,

            SUM(
                CASE
                WHEN COALESCE(
                    cost_model_complete,
                    0
                ) = 1
                THEN 1 ELSE 0
                END
            ) AS cost_complete

        FROM paper_trades

        WHERE paper_account_version = 'PAPER_10K_V2'
          AND UPPER(
                COALESCE(status, '')
              ) = 'CLOSED'
          {active_filter}

        GROUP BY
            COALESCE(
                NULLIF(
                    UPPER(TRIM(trade_policy)),
                    ''
                ),
                'LEGACY'
            )

        ORDER BY closed DESC
        """,
        params,
    )

    result = []

    for row in rows:
        closed = int(
            row.get("closed") or 0
        )

        cost_complete = int(
            row.get("cost_complete") or 0
        )

        result.append({
            "trade_policy": row.get(
                "trade_policy"
            ),
            "closed": closed,
            "wins": int(
                row.get("wins") or 0
            ),
            "losses": int(
                row.get("losses") or 0
            ),
            "avg_roi_pct": (
                number(
                    row.get("avg_roi_pct")
                )
                if row.get("avg_roi_pct")
                is not None
                else None
            ),
            "net_total": number(
                row.get("net_total")
            ),
            "cost_complete": cost_complete,
            "cost_incomplete": max(
                0,
                closed - cost_complete,
            ),
        })

    return result


def performance_series(
    *,
    active_only: bool = False,
) -> list[dict[str, Any]]:
    active_filter = ""
    params: tuple[Any, ...] = ()

    if active_only:
        active_filter = (
            " AND id >= ?"
        )
        params = (
            PANEL_ACTIVE_PERIOD_MIN_TRADE_ID,
        )

    rows = query(
        f"""
        SELECT
            id,
            COALESCE(
                closed_at,
                created_at
            ) AS timestamp,
            COALESCE(
                net_pnl_usdt,
                net_pnl,
                0
            ) AS pnl
        FROM paper_trades
        WHERE paper_account_version = 'PAPER_10K_V2'
          AND UPPER(
                COALESCE(
                    status,
                    ''
                )
              ) = 'CLOSED'
          {active_filter}
        ORDER BY
            COALESCE(
                closed_at,
                created_at
            ) ASC,
            id ASC
        LIMIT 500
        """,
        params,
    )

    cumulative = 0.0
    result = []

    for row in rows:
        cumulative += number(
            row.get("pnl")
        )

        result.append({
            "id": row.get("id"),
            "timestamp": row.get(
                "timestamp"
            ),
            "pnl": number(
                row.get("pnl")
            ),
            "cumulative": cumulative,
        })

    return result



def intelligence_payload() -> dict[str, Any]:
    latest_summary: dict[str, Any] = {}

    if table_exists("intelligence_summary_readmodel"):
        latest_summary = query_one(
            """
            SELECT *
            FROM intelligence_summary_readmodel
            ORDER BY generated_at DESC
            LIMIT 1
            """
        )

    return {
        "summary": latest_summary,
        "tracked_wallets": table_count(
            "wallet_discovery_registry"
        ),
        "successful_wallets": table_count(
            "wallet_success_score"
        ),
        "outcome_evidence": table_count(
            "wallet_outcome_evidence"
        ),
        "active_whales": table_count(
            "whale_activity_snapshot"
        ),
        "activity_buckets": table_count(
            "wallet_activity_bucket"
        ),
    }



# PANEL_MOBILE_LIVE_BACKEND_V2


def _runtime_number(value: Any) -> float | None:
    if value is None:
        return None

    try:
        return float(value)

    except (TypeError, ValueError):
        return None


def _runtime_bool(value: Any) -> bool | None:
    normalized = str(
        value or ""
    ).strip().lower()

    if normalized == "true":
        return True

    if normalized == "false":
        return False

    return None


def _runtime_candidate_cycle_lines(
    lines: list[str],
) -> list[str]:
    """
    Return one coherent scanner-cycle snapshot.

    The scheduler runs scanner synchronously before
    paper_manager.  Therefore a paper_manager job marker
    after the latest scanner marker means that scanner
    cycle has completed.

    While the latest scanner cycle is still running,
    preserve the previous completed scanner snapshot
    instead of exposing a transient empty/partial list.
    """

    scanner_indices = [
        index
        for index, line in enumerate(lines)
        if "[JOB] scanner" in line
    ]

    if not scanner_indices:
        return lines

    latest_index = scanner_indices[-1]

    latest_lines = lines[
        latest_index + 1:
    ]

    latest_complete = any(
        "[JOB] paper_manager" in line
        for line in latest_lines
    )

    if latest_complete:
        return latest_lines

    if len(scanner_indices) < 2:
        return latest_lines

    previous_index = scanner_indices[-2]

    return lines[
        previous_index + 1:
        latest_index
    ]


def _runtime_candidate_fields(
    payload: str,
) -> dict[str, str]:
    """
    Parse one Candidate runtime payload while
    preserving values that contain spaces, such as
    blocker lists.

    Read-only parsing only.
    """
    text = str(payload or "").strip()

    if not text:
        return {}

    head = text.split(None, 1)

    fields = {
        "token": head[0],
    }

    if len(head) < 2:
        return fields

    remainder = head[1]

    matches = list(
        re.finditer(
            r"(?<!\S)"
            r"([A-Za-z_][A-Za-z0-9_]*)=",
            remainder,
        )
    )

    for index, match in enumerate(matches):
        key = match.group(1)

        start = match.end()

        end = (
            matches[index + 1].start()
            if index + 1 < len(matches)
            else len(remainder)
        )

        fields[key] = (
            remainder[start:end].strip()
        )

    return fields


def _runtime_blocker_list(
    value: Any,
) -> list[str]:
    text = str(value or "").strip()

    if text in {
        "",
        "[]",
        "None",
        "null",
    }:
        return []

    return [
        item.strip()
        for item in re.findall(
            r"""['"]([^'"]+)['"]""",
            text,
        )
        if item.strip()
    ]


def runtime_candidate_rows(
    limit: int = 20,
) -> list[dict[str, Any]]:
    """
    Latest scanner candidates from runtime journal.

    Read-only panel projection only.
    No trade / DB / wallet / execution authority.
    """

    cache_snapshot = runtime_cache_snapshot()

    try:
        result = subprocess.run(
            [
                "journalctl",
                "-u",
                "coinoskobi-paper-runtime.service",
                "--since",
                "-20 minutes",
                "-n",
                "400",
                "--no-pager",
                "-o",
                "short-iso",
            ],
            capture_output=True,
            text=True,
            timeout=4,
            check=False,
        )

    except Exception:
        return []

    if result.returncode != 0:
        return []

    lines = _runtime_candidate_cycle_lines(
        result.stdout.splitlines()
    )

    rows = []
    seen = set()

    for line in reversed(lines):

        marker = "Candidate token="

        if marker not in line:
            continue

        prefix, payload = line.split(
            marker,
            1,
        )

        fields = (
            _runtime_candidate_fields(
                payload
            )
        )

        if not fields:
            continue

        token = str(
            fields.get("token") or ""
        ).strip()

        pool = str(
            fields.get("pool") or ""
        ).strip()

        cache_row = (
            cache_snapshot["by_pool"].get(
                pool.lower()
            )
            or cache_snapshot["by_token"].get(
                token.lower()
            )
            or {}
        )

        if not token:
            continue

        identity = (
            token.lower(),
            pool.lower(),
        )

        if identity in seen:
            continue

        seen.add(identity)

        timestamp = None

        prefix_parts = prefix.strip().split()

        if prefix_parts:
            timestamp = prefix_parts[0]

        reason = fields.get("reason")

        if reason in {
            "",
            "None",
            "null",
        }:
            reason = None

        rows.append({
            "token": token,
            "pool": pool or None,
            "observed_at": timestamp,
            "strategy": fields.get(
                "strategy"
            ),
            "unified": fields.get(
                "unified"
            ),
            "paper_action": fields.get(
                "paper"
            ),
            "reason": reason,
            "hard_block": (
                _runtime_bool(
                    fields.get(
                        "hard_block"
                    )
                )
            ),
            "evidence_coverage": (
                _runtime_number(
                    fields.get(
                        "evidence_coverage"
                    )
                )
            ),
            "coverage_confidence": (
                _runtime_number(
                    fields.get(
                        "coverage_confidence"
                    )
                )
            ),
            "sellability": fields.get(
                "sellability"
            ),

            "sizing_reason": fields.get(
                "sizing_reason"
            ),

            "plan_blockers": (
                _runtime_blocker_list(
                    fields.get(
                        "plan_blockers"
                    )
                )
            ),

            "sizing_blockers": (
                _runtime_blocker_list(
                    fields.get(
                        "sizing_blockers"
                    )
                )
            ),

            "entry_amount_usdt": (
                _runtime_number(
                    fields.get(
                        "entry_amount_usdt"
                    )
                )
            ),

            "name": cache_row.get(
                "name"
            ),

            "dex": cache_row.get(
                "dex"
            ),

            "liquidity": (
                _runtime_number(
                    cache_row.get(
                        "liquidity"
                    )
                )
            ),

            "volume_24h": (
                _runtime_number(
                    cache_row.get(
                        "volume_24h"
                    )
                )
            ),

            "buys_24h": (
                _runtime_number(
                    cache_row.get(
                        "buys_24h"
                    )
                )
            ),

            "fdv": (
                _runtime_number(
                    cache_row.get(
                        "fdv"
                    )
                )
            ),

            "price_usd": (
                _runtime_number(
                    cache_row.get(
                        "price_usd"
                    )
                )
            ),

            "cache_updated_at": (
                cache_row.get(
                    "updated_at"
                )
            ),

            "source": (
                "PAPER_RUNTIME_JOURNAL"
            ),
            "panel_display_only": True,
            "decision_authority": False,
            "paper_authority": False,
            "live_authority": False,
            "wallet_authority": False,
            "execution_authority": False,
        })

        if len(rows) >= max(
            1,
            int(limit),
        ):
            break

    return rows


@app.middleware("http")
async def panel_no_cache(
    request,
    call_next,
):
    response = await call_next(
        request
    )

    if request.url.path == "/":
        response.headers[
            "Cache-Control"
        ] = (
            "no-store, no-cache, "
            "must-revalidate, max-age=0"
        )

        response.headers[
            "Pragma"
        ] = "no-cache"

        response.headers[
            "Expires"
        ] = "0"

    elif request.url.path.startswith(
        "/static/"
    ):
        response.headers[
            "Cache-Control"
        ] = (
            "public, max-age=86400"
        )

    return response


@app.get("/api/runtime-candidates")
def api_runtime_candidates() -> list[dict[str, Any]]:
    return runtime_candidate_rows()


def health_payload() -> dict[str, Any]:
    database_ok = False

    try:
        row = query_one(
            "PRAGMA quick_check"
        )

        database_ok = (
            "ok" in {
                str(value).lower()
                for value in row.values()
            }
        )

    except Exception:
        database_ok = False

    disk = shutil.disk_usage(BASE_DIR)

    return {
        "status": (
            "ok"
            if database_ok
            else "error"
        ),
        "database": database_ok,
        "mode": "READ_ONLY",
        "paper_runtime": service_state(
            "coinoskobi-paper-runtime.service"
        ),
        "panel_api": service_state(
            "coinoskobi-panel-api.service"
        ),
        "disk_usage_pct": (
            disk.used / disk.total * 100.0
            if disk.total
            else 0.0
        ),
        "live_execution": False,
        "wallet_authority": False,
    }


def authority_payload() -> dict[str, Any]:
    return {
        "panel_mode": "READ_ONLY",
        "paper_runtime": True,
        "manual_order_authority": False,
        "autopilot_authority": False,
        "live_execution_authority": False,
        "wallet_authority": False,
        "signing_authority": False,
        "message": (
            "Panel read-only çalışıyor. Manuel emir, "
            "otomatik pilot, live execution, wallet ve "
            "signing authority açık değil."
        ),
    }


def recent_signals(
    rows: list[dict[str, Any]],
    intelligence: dict[str, Any],
) -> list[dict[str, Any]]:
    signals: list[dict[str, Any]] = []

    for row in rows[:15]:
        status = str(
            row.get("status") or "OPEN"
        ).upper()

        timestamp = (
            row.get("closed_at")
            if status == "CLOSED"
            else row.get("created_at")
        )

        token = (
            row.get("symbol")
            or str(row.get("token") or "TOKEN")[:12]
        )

        if status == "CLOSED":
            message = (
                f"{token} kapandı · "
                f"{row.get('close_reason') or 'CLOSED'}"
            )
        else:
            message = f"{token} paper pozisyonu açık"

        signals.append({
            "timestamp": timestamp,
            "source": "PAPER",
            "message": message,
            "state": status,
            "pnl": number(
                row.get("net_pnl_usdt")
                if row.get("net_pnl_usdt") is not None
                else row.get("net_pnl")
            ),
        })

    summary = intelligence.get("summary") or {}
    vezir_summary = summary.get("vezir_summary")

    if vezir_summary:
        signals.append({
            "timestamp": summary.get("generated_at"),
            "source": "VEZIR",
            "message": vezir_summary,
            "state": "INTELLIGENCE",
            "pnl": None,
        })

    signals.sort(
        key=lambda item: str(
            item.get("timestamp") or ""
        ),
        reverse=True,
    )

    return signals[:10]


def status() -> dict[str, Any]:
    rows = paper_rows()

    open_count = sum(
        1
        for row in rows
        if str(
            row.get("status") or "OPEN"
        ).upper() != "CLOSED"
    )

    closed_count = sum(
        1
        for row in rows
        if str(
            row.get("status") or ""
        ).upper() == "CLOSED"
    )

    return {
        "total": len(rows),
        "new_generation": len(rows),
        "open_positions": open_count,
        "closed_positions": closed_count,
    }


def performance() -> dict[str, Any]:
    return performance_payload()


def exits() -> list[dict[str, Any]]:
    return query(
        """
        SELECT
            close_reason,
            COUNT(*) AS trades,
            AVG(roi) * 100.0 AS avg_roi_pct,
            COALESCE(
                SUM(net_pnl_usdt),
                0
            ) AS net_total
        FROM paper_trades
        WHERE paper_account_version = 'PAPER_10K_V2'
          AND UPPER(
                COALESCE(status, '')
              ) = 'CLOSED'
        GROUP BY close_reason
        ORDER BY trades DESC
        """
    )


@app.get("/", include_in_schema=False)
def panel_home() -> FileResponse:
    return FileResponse(INDEX_FILE)


@app.get("/healthz")
def healthz() -> dict[str, Any]:
    return health_payload()


@app.get("/api/status")
def api_status() -> dict[str, Any]:
    rows = paper_rows(active_only=True)

    open_count = sum(
        1
        for row in rows
        if str(
            row.get("status") or "OPEN"
        ).upper() != "CLOSED"
    )

    closed_count = sum(
        1
        for row in rows
        if str(
            row.get("status") or ""
        ).upper() == "CLOSED"
    )

    return {
        "total": len(rows),
        "new_generation": len(rows),
        "open_positions": open_count,
        "closed_positions": closed_count,
    }


@app.get("/api/positions")
def api_positions() -> list[dict[str, Any]]:
    return paper_rows(active_only=True)


@app.get("/api/positions-v2")
def api_positions_v2() -> list[dict[str, Any]]:
    return paper_rows(active_only=True)


@app.get("/api/performance")
def api_performance() -> dict[str, Any]:
    return performance_payload(active_only=True)


@app.get("/api/performance-series")
def api_performance_series() -> list[dict[str, Any]]:
    return performance_series(active_only=True)


@app.get("/api/exits")
def api_exits() -> list[dict[str, Any]]:
    return [
        row
        for row in paper_rows(active_only=True)
        if str(
            row.get("status") or ""
        ).upper() == "CLOSED"
    ][:20]


@app.get("/api/intelligence")
def api_intelligence() -> dict[str, Any]:
    return intelligence_payload()


@app.get("/api/authority")
def api_authority() -> dict[str, Any]:
    return authority_payload()


@app.get("/api/position/{position_id}/evidence")
def api_position_evidence(
    position_id: int,
) -> dict[str, Any]:
    row = query_one(
        """
        SELECT
            id,
            token,
            symbol,
            status,
            trade_policy,
            opening_context_json
        FROM paper_trades
        WHERE id = ?
        LIMIT 1
        """,
        (position_id,),
    )

    if not row:
        raise HTTPException(
            status_code=404,
            detail="Position not found",
        )

    context = parse_json_object(
        row.get("opening_context_json")
    )

    return {
        "id": row.get("id"),
        "token": row.get("token"),
        "symbol": row.get("symbol"),
        "status": row.get("status"),
        "trade_policy": row.get("trade_policy"),
        "entry_evidence": extract_entry_evidence(
            row.get("opening_context_json")
        ),
        "opening_context": context,
    }


@app.get("/api/dashboard")
def api_dashboard() -> dict[str, Any]:
    rows = paper_rows(active_only=True)
    performance = performance_payload(active_only=True)
    intelligence = intelligence_payload()
    health = health_payload()
    authority = authority_payload()

    open_positions = [
        row
        for row in rows
        if str(
            row.get("status") or "OPEN"
        ).upper() != "CLOSED"
    ]

    closed_positions = [
        row
        for row in rows
        if str(
            row.get("status") or ""
        ).upper() == "CLOSED"
    ]

    open_investment = sum(
        number(row.get("entry_amount_usdt"))
        for row in open_positions
    )

    open_pnl = sum(
        number(
            row.get("net_pnl_usdt")
            if row.get("net_pnl_usdt") is not None
            else row.get("net_pnl")
        )
        for row in open_positions
    )

    open_risk = sum(
        number(row.get("risk_amount_usdt"))
        for row in open_positions
    )

    realized_net = number(
        performance.get("net_total")
    )

    total_pnl = realized_net + open_pnl
    equity = PAPER_STARTING_CAPITAL_USDT + total_pnl

    now_local = datetime.now(
        PANEL_TIMEZONE
    )

    day_start_local = now_local.replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )

    day_end_local = (
        day_start_local
        + timedelta(days=1)
    )

    day_start_utc = (
        day_start_local
        .astimezone(timezone.utc)
        .isoformat()
    )

    day_end_utc = (
        day_end_local
        .astimezone(timezone.utc)
        .isoformat()
    )

    local_date = (
        day_start_local
        .date()
        .isoformat()
    )

    daily_row = query_one(
        """
        SELECT
            COALESCE(
                SUM(
                    COALESCE(
                        net_pnl_usdt,
                        net_pnl,
                        0
                    )
                ),
                0
            ) AS daily_net
        FROM paper_trades
        WHERE paper_account_version = 'PAPER_10K_V2'
          AND UPPER(COALESCE(status, '')) = 'CLOSED'
          AND id >= ?
          AND COALESCE(
                closed_at,
                created_at
              ) >= ?
          AND COALESCE(
                closed_at,
                created_at
              ) < ?
        """,
        (
            PANEL_ACTIVE_PERIOD_MIN_TRADE_ID,
            day_start_utc,
            day_end_utc,
        ),
    )

    daily_pnl = (
        number(daily_row.get("daily_net"))
        + open_pnl
    )

    risk_used_pct = (
        open_risk / equity * 100.0
        if equity > 0
        else 0.0
    )

    open_roi_pct = (
        open_pnl / open_investment * 100.0
        if open_investment > 0
        else None
    )

    def best_key(row: dict[str, Any]) -> tuple[float, float]:
        evidence = row.get("entry_evidence") or {}

        score = number(
            evidence.get("score"),
            default=-1.0,
        )
        roi_pct = number(
            row.get("roi_pct"),
            default=-999.0,
        )

        return score, roi_pct

    best = (
        max(open_positions, key=best_key)
        if open_positions
        else None
    )

    candidates = sorted(
        rows,
        key=best_key,
        reverse=True,
    )[:5]

    return {
        "generated_at": datetime.now(
            timezone.utc
        ).isoformat(),
        "summary": {
            "starting_capital": PAPER_STARTING_CAPITAL_USDT,
            "panel_timezone": PANEL_TIMEZONE_NAME,
            "local_date": local_date,
            "equity": equity,
            "daily_pnl": daily_pnl,
            "total_pnl": total_pnl,
            "realized_net": realized_net,
            "open_pnl": open_pnl,
            "open_count": len(open_positions),
            "closed_count": len(closed_positions),
            "open_investment": open_investment,
            "open_risk": open_risk,
            "risk_used_pct": risk_used_pct,
            "open_roi_pct": open_roi_pct,
            "win_rate_pct": performance.get(
                "win_rate_pct"
            ),
            "wins": performance.get("wins"),
            "losses": performance.get("losses"),
            "avg_roi_pct": performance.get(
                "avg_roi_pct"
            ),
            "profit_factor": performance.get(
                "profit_factor"
            ),
        },
        "market": {
            "btc": None,
            "eth": None,
            "source": "UNBOUND",
        },
        "best": best,
        "positions": open_positions,
        "candidates": candidates,
        "exits": closed_positions[:10],
        "series": performance_series(active_only=True),
        "performance": performance,
        "policy_performance": (
            policy_performance_payload(
                active_only=True
            )
        ),
        "intelligence": intelligence,
        "signals": recent_signals(
            rows,
            intelligence,
        ),
        "health": health,
        "authority": authority,
    }
