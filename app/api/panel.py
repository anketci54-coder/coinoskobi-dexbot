from pathlib import Path
import json
import sqlite3

from fastapi import FastAPI


BASE_DIR = Path(__file__).resolve().parents[2]
PAPER_DB = BASE_DIR / "data" / "paper_trades.db"

app = FastAPI(
    title="Coinoskobi Panel API",
    version="1.0",
)


# SINGLE_PAGE_PANEL_V2
from fastapi.responses import HTMLResponse


@app.get("/", response_class=HTMLResponse)
def panel_home():
    return """<!doctype html>
<html lang="tr">
<head>
<meta charset="utf-8">
<meta name="viewport"
      content="width=device-width,initial-scale=1">
<title>Coinoskobi</title>
<style>
:root{
  color-scheme:dark;
  --bg:#081019;
  --card:#101b27;
  --line:#26384a;
  --text:#edf4fb;
  --muted:#91a4b7;
  --good:#72e69a;
  --warn:#ffd16a;
  --bad:#ff7b86;
}
*{box-sizing:border-box}
body{
  margin:0;
  background:var(--bg);
  color:var(--text);
  font-family:system-ui,-apple-system,sans-serif;
}
main{
  max-width:1180px;
  margin:auto;
  padding:20px;
}
h1{margin:0 0 4px}
.sub{color:var(--muted);margin-bottom:20px}
.grid{
  display:grid;
  grid-template-columns:repeat(4,1fr);
  gap:12px;
}
.card{
  background:var(--card);
  border:1px solid var(--line);
  border-radius:14px;
  padding:16px;
}
.big{
  font-size:25px;
  font-weight:800;
  margin-top:6px;
}
.good{color:var(--good)}
.warn{color:var(--warn)}
.bad{color:var(--bad)}
.muted{color:var(--muted)}
table{
  width:100%;
  border-collapse:collapse;
  margin-top:8px;
}
th,td{
  text-align:left;
  padding:10px 8px;
  border-bottom:1px solid var(--line);
  font-size:14px;
}
th{color:var(--muted)}
.section{margin-top:14px}
.tag{
  display:inline-block;
  border:1px solid var(--line);
  border-radius:999px;
  padding:5px 9px;
  margin:2px;
  font-size:12px;
}
@media(max-width:800px){
  .grid{grid-template-columns:repeat(2,1fr)}
}
@media(max-width:520px){
  .grid{grid-template-columns:1fr}
  main{padding:12px}
}
</style>
</head>
<body>
<main>
<h1>Coinoskobi</h1>
<div class="sub">
Yeni Paper Dönemi · 10.000 USDT · PAPER_10K_V2
</div>

<div class="grid">
  <div class="card">
    <div class="muted">Başlangıç</div>
    <div class="big">10.000 USDT</div>
  </div>
  <div class="card">
    <div class="muted">Açık İşlem</div>
    <div id="open" class="big">—</div>
  </div>
  <div class="card">
    <div class="muted">Başarı Oranı</div>
    <div id="winrate" class="big">—</div>
  </div>
  <div class="card">
    <div class="muted">Net Sonuç</div>
    <div id="net" class="big">—</div>
  </div>
</div>

<div class="card section">
  <b>Yeni Strateji</b>
  <div style="margin-top:10px">
    <span class="tag">Yerel risk önce</span>
    <span class="tag">İki aşamalı giriş</span>
    <span class="tag">Sellability doğrulaması</span>
    <span class="tag">Unified karar</span>
    <span class="tag">Hard risk üstün</span>
  </div>
</div>

<div class="card section">
  <b>İşlemler</b>
  <div style="overflow:auto">
    <table>
      <thead>
        <tr>
          <th>Token</th>
          <th>Durum</th>
          <th>Giriş</th>
          <th>SL</th>
          <th>TP</th>
          <th>ROI</th>
          <th>Sonuç</th>
        </tr>
      </thead>
      <tbody id="positions">
        <tr>
          <td colspan="7" class="muted">
            Veri bekleniyor…
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</div>

<div class="card section">
  <b>Güvenlik</b>
  <div style="margin-top:10px">
    <span class="tag good">Paper only</span>
    <span class="tag">Live kapalı</span>
    <span class="tag">Wallet yetkisi yok</span>
    <span class="tag">Signing yok</span>
  </div>
</div>
</main>

<script>
const fmt = v =>
  (v === null || v === undefined)
    ? "—"
    : Number(v).toLocaleString(
        "tr-TR",
        {maximumFractionDigits:4}
      );

async function load(){
  try{
    const [s,p,r] = await Promise.all([
      fetch("/api/status").then(x=>x.json()),
      fetch("/api/performance").then(x=>x.json()),
      fetch("/api/positions-v2").then(x=>x.json())
    ]);

    document.getElementById("open").textContent =
      s.open_positions ?? 0;

    document.getElementById("winrate").textContent =
      (p.win_rate_pct ?? 0) + "%";

    const net = Number(p.net_total ?? 0);
    const netEl = document.getElementById("net");
    netEl.textContent = fmt(net) + " USDT";
    netEl.className =
      "big " + (net > 0 ? "good" : net < 0 ? "bad" : "");

    const body = document.getElementById("positions");

    if(!Array.isArray(r) || !r.length){
      body.innerHTML =
        '<tr><td colspan="7" class="muted">' +
        'Yeni dönemde henüz işlem yok.' +
        '</td></tr>';
      return;
    }

    body.innerHTML = r.slice(0,30).map(x => `
      <tr>
        <td>${x.symbol || x.token || "—"}</td>
        <td>${x.status || "—"}</td>
        <td>${fmt(x.entry_price)}</td>
        <td>${fmt(x.sl_price)}</td>
        <td>${fmt(x.tp_price)}</td>
        <td>${fmt(
          x.roi == null ? null : Number(x.roi)*100
        )}%</td>
        <td>${x.close_reason || "—"}</td>
      </tr>
    `).join("");
  }catch(e){
    document.getElementById("positions").innerHTML =
      '<tr><td colspan="7" class="bad">' +
      'Panel verisi alınamadı.' +
      '</td></tr>';
  }
}

load();
setInterval(load,5000);
</script>
</body>
</html>"""


def query(sql, params=()):
    # Read-only SQLite connection: panel cannot write.
    uri = f"file:{PAPER_DB}?mode=ro"
    conn = sqlite3.connect(uri, uri=True, timeout=5)
    conn.row_factory = sqlite3.Row
    try:
        return [
            dict(row)
            for row in conn.execute(sql, params).fetchall()
        ]
    finally:
        conn.close()


@app.get("/healthz")
def health():
    rows = query("SELECT 1 AS ok")
    return {
        "status": "ok",
        "database": rows[0]["ok"] == 1,
        "mode": "READ_ONLY",
    }


@app.get("/api/status")
def status():
    rows = query(
        """
        SELECT
            COUNT(*) AS total,
            COUNT(*) AS new_generation,
            SUM(
                CASE
                    WHEN status='OPEN'
                    THEN 1 ELSE 0
                END
            ) AS open_positions,
            SUM(
                CASE
                    WHEN status='CLOSED'
                    THEN 1 ELSE 0
                END
            ) AS closed_positions
        FROM paper_trades
        WHERE paper_account_version='PAPER_10K_V2'
        """
    )
    return rows[0]


@app.get("/api/positions")
def positions():
    return query(
        """
        SELECT
            id,
            symbol,
            token,
            pool,
            status,
            entry_price,
            current_price,
            highest_price,
            tp_price,
            sl_price,
            gross_pnl,
            net_pnl,
            roi,
            close_reason,
            created_at,
            closed_at
        FROM paper_trades
        WHERE id > 250
          AND pool IS NOT NULL
          AND trim(pool) <> ''
        ORDER BY id DESC
        LIMIT 100
        """
    )


@app.get("/api/performance")
def performance():
    rows = query(
        """
        SELECT
            COUNT(*) AS closed,
            SUM(
                CASE
                    WHEN net_pnl_usdt > 0
                    THEN 1 ELSE 0
                END
            ) AS wins,
            SUM(
                CASE
                    WHEN net_pnl_usdt <= 0
                    THEN 1 ELSE 0
                END
            ) AS losses,
            ROUND(
                100.0 *
                SUM(
                    CASE
                        WHEN net_pnl_usdt > 0
                        THEN 1 ELSE 0
                    END
                )
                / NULLIF(COUNT(*), 0),
                2
            ) AS win_rate_pct,
            ROUND(
                AVG(roi) * 100,
                2
            ) AS avg_roi_pct,
            ROUND(
                COALESCE(
                    SUM(net_pnl_usdt),
                    0
                ),
                8
            ) AS net_total
        FROM paper_trades
        WHERE paper_account_version='PAPER_10K_V2'
          AND status='CLOSED'
        """
    )
    return rows[0]


@app.get("/api/exits")
def exits():
    return query(
        """
        SELECT
            close_reason,
            COUNT(*) AS trades,
            ROUND(
                AVG(roi) * 100,
                2
            ) AS avg_roi_pct,
            ROUND(
                COALESCE(
                    SUM(net_pnl_usdt),
                    0
                ),
                8
            ) AS net_total
        FROM paper_trades
        WHERE paper_account_version='PAPER_10K_V2'
          AND status='CLOSED'
        GROUP BY close_reason
        ORDER BY trades DESC
        """
    )


@app.get("/api/positions-v2")
def positions_v2():
    rows = query(
        """
        SELECT
            id,
            symbol,
            token,
            pool,
            status,
            entry_price,
            current_price,
            highest_price,
            tp_price,
            sl_price,
            gross_pnl,
            net_pnl,
            roi,
            close_reason,
            created_at,
            closed_at,

            paper_account_version,
            entry_amount_usdt,
            risk_amount_usdt,
            capital_before_usdt,
            capital_after_entry_usdt,
            position_size_pct,
            sizing_reason,
            gross_pnl_usdt,
            net_pnl_usdt,

            opening_context_json
        FROM paper_trades
        WHERE paper_account_version='PAPER_10K_V2'
            AND pool IS NOT NULL
            AND trim(pool) <> ''
        ORDER BY id DESC
        LIMIT 100
        """
    )

    result = []

    for row in rows:
        item = dict(row)
        raw = item.pop("opening_context_json", None)

        try:
            context = json.loads(raw) if raw else {}
        except (TypeError, ValueError, json.JSONDecodeError):
            context = {}

        signals = dict(context.get("raw_signals") or {})
        attribution = dict(
            context.get("signal_attribution") or {}
        )
        baseline = dict(context.get("exit_baseline") or {})

        item["entry_evidence"] = {
            "captured_at_entry": bool(
                context.get("captured_at_entry")
            ),
            "hindsight_reconstructed": bool(
                context.get("hindsight_reconstructed")
            ),
            "strategy_decision": signals.get(
                "strategy_decision"
            ),
            "unified_decision": signals.get(
                "unified_decision"
            ),
            "score": signals.get("unified_score"),
            "confidence": signals.get(
                "unified_confidence"
            ),
            "hard_block": bool(
                signals.get("hard_block")
            ),
            "sellability": signals.get(
                "sellability_status"
            ),
            "coverage": signals.get(
                "unified_coverage"
            ),
            "signal_attribution": attribution,
            "entry_price": baseline.get(
                "entry_price"
            ),
            "stop_loss_price": baseline.get(
                "stop_loss_price"
            ),
            "take_profit_price": baseline.get(
                "take_profit_price"
            ),
        }

        item["authority"] = {
            "decision": False,
            "execution": False,
            "live": False,
            "wallet": False,
            "read_only": True,
        }

        result.append(item)

    return result
