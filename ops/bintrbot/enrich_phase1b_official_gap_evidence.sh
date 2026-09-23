#!/usr/bin/env bash
set -euo pipefail

ROOT=/root/bintrbot
PY="$ROOT/.venv/bin/python"

cat > "$ROOT/app/enrich_gap_registry_official_evidence.py" <<'PY'
from __future__ import annotations

import json
import os
import sqlite3
import time
from pathlib import Path

ROOT = Path("/root/bintrbot")
DB = ROOT / "state/phase1b_gap_registry.sqlite3"
OUT = ROOT / "data/quality/gap_registry.json"
STATE = ROOT / "state/phase1b_gap_evidence.json"

def atomic_json(path: Path, obj):
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True))
    os.replace(tmp, path)

if not DB.exists() or not OUT.exists():
    raise SystemExit("gap registry missing")

con = sqlite3.connect(DB)

cols = {r[1] for r in con.execute("PRAGMA table_info(gaps)")}
for name, typ in [
    ("evidence_strength", "TEXT"),
    ("evidence_source", "TEXT"),
    ("evidence_url", "TEXT"),
    ("evidence_note", "TEXT"),
]:
    if name not in cols:
        con.execute(f"ALTER TABLE gaps ADD COLUMN {name} {typ}")

# Exact gap intervals observed in Binance TR historical klines.
# Classification is about correlation with official Binance GLOBAL maintenance/outage evidence,
# not a claim that Binance TR independently published the same outage.
EVIDENCE = {
    ("2020-11-30T06:00:00+00:00", "2020-11-30T06:59:00+00:00"): {
        "classification": "OFFICIAL_BINANCE_GLOBAL_MAINTENANCE_CORRELATED",
        "strength": "STRONG_START_MATCH",
        "source": "BINANCE_OFFICIAL",
        "url": "https://www.binance.com/en/support/announcement/detail/1344e0dd30e843a8801aa58e23d6d82e",
        "note": "Official Binance notice states scheduled spot system upgrade starting 2020-11-30 06:00 UTC; observed Binance TR gap starts exactly 06:00 UTC."
    },
    ("2020-12-21T13:48:00+00:00", "2020-12-21T17:59:00+00:00"): {
        "classification": "OFFICIAL_BINANCE_GLOBAL_MAINTENANCE_CORRELATED",
        "strength": "STRONG_RESUME_MATCH",
        "source": "BINANCE_OFFICIAL",
        "url": "https://www.binance.com/en-ZA/support/announcement/detail/b026ae47a3ab4335990d1c2f92aaeb29",
        "note": "Official Binance completion notice states all trading resumes at 2020-12-21 18:00 UTC; observed Binance TR gap ends at 17:59 UTC."
    },
    ("2021-02-11T03:41:00+00:00", "2021-02-11T04:59:00+00:00"): {
        "classification": "OFFICIAL_BINANCE_GLOBAL_MAINTENANCE_CORRELATED",
        "strength": "STRONG_RESUME_MATCH",
        "source": "BINANCE_OFFICIAL",
        "url": "https://www.binance.com/en/support/announcement/detail/aad7639a0ed9424bad585b508a61a433",
        "note": "Official Binance completion notice states all trading resumes at 2021-02-11 05:00 UTC; observed Binance TR gap ends at 04:59 UTC."
    },
    ("2021-03-06T02:00:00+00:00", "2021-03-06T03:29:00+00:00"): {
        "classification": "OFFICIAL_BINANCE_GLOBAL_MAINTENANCE_CORRELATED",
        "strength": "VERY_STRONG_WINDOW_MATCH",
        "source": "BINANCE_OFFICIAL",
        "url": "https://www.binance.com/en/support/announcement/detail/f02cab4e685b46da803bb0a680546d4b",
        "note": "Official notice starts upgrade 02:00 UTC, estimates 1 hour, then gives a 30-minute pre-resumption window; observed Binance TR gap is exactly 02:00-03:29 UTC."
    },
    ("2021-04-20T02:00:00+00:00", "2021-04-20T04:29:00+00:00"): {
        "classification": "OFFICIAL_BINANCE_GLOBAL_MAINTENANCE_CORRELATED",
        "strength": "VERY_STRONG_WINDOW_MATCH",
        "source": "BINANCE_OFFICIAL",
        "url": "https://www.binance.com/en-PH/support/announcement/detail/69e82a64b2c442b18eb1cf11934b27eb",
        "note": "Official notice starts upgrade 02:00 UTC; official completion states trading resumes 04:30 UTC; observed Binance TR gap is exactly 02:00-04:29 UTC."
    },
    ("2021-04-25T04:01:00+00:00", "2021-04-25T08:44:00+00:00"): {
        "classification": "OFFICIAL_BINANCE_GLOBAL_MAINTENANCE_CORRELATED",
        "strength": "STRONG_WINDOW_OVERLAP",
        "source": "BINANCE_OFFICIAL",
        "url": "https://www.binance.com/kk-KZ/support/announcement/detail/849160fe70214641baa6385619595aa1",
        "note": "Official notice starts scheduled spot upgrade at 04:00 UTC for approximately 4 hours plus a 30-minute pre-resumption window; observed Binance TR gap starts 04:01 UTC and lasts into that maintenance/resumption window."
    },
    ("2021-08-13T02:00:00+00:00", "2021-08-13T06:29:00+00:00"): {
        "classification": "OFFICIAL_BINANCE_GLOBAL_MAINTENANCE_CORRELATED",
        "strength": "VERY_STRONG_WINDOW_MATCH",
        "source": "BINANCE_OFFICIAL",
        "url": "https://www.binance.com/en/support/announcement/detail/92a9a5bc0129427f8e9928c9b7b09836",
        "note": "Official notice starts upgrade 02:00 UTC and official completion resumes trading 06:30 UTC; observed Binance TR gap is exactly 02:00-06:29 UTC."
    },
    ("2021-09-29T07:00:00+00:00", "2021-09-29T08:59:00+00:00"): {
        "classification": "OFFICIAL_BINANCE_GLOBAL_MAINTENANCE_CORRELATED",
        "strength": "VERY_STRONG_WINDOW_MATCH",
        "source": "BINANCE_OFFICIAL",
        "url": "https://www.binance.com/en/support/announcement/detail/e2f674fc961d48af9b28edd82896607c",
        "note": "Official notice starts upgrade 07:00 UTC for approximately 2 hours; observed Binance TR gap is exactly 07:00-08:59 UTC."
    },
    ("2023-03-24T12:40:00+00:00", "2023-03-24T13:59:00+00:00"): {
        "classification": "OFFICIAL_BINANCE_GLOBAL_OUTAGE_CORRELATED",
        "strength": "STRONG_RESUME_MATCH_PARTIAL_WINDOW",
        "source": "BINANCE_OFFICIAL",
        "url": "https://www.binance.com/en/blog/from-our-ceo/6789340645608890113",
        "note": "Binance documents temporary spot halt on 2023-03-24 and recovery around 14:00 UTC; observed Binance TR gap ends at 13:59 UTC but starts later than the global halt, so this remains correlation rather than a Binance TR-specific outage claim."
    },
}

reg = json.loads(OUT.read_text())
entries = reg.get("entries", [])
matched = 0
unmatched_shared = set()

for e in entries:
    key = (e.get("gap_start_utc"), e.get("gap_end_utc"))
    ev = EVIDENCE.get(key)
    if ev is None:
        continue
    matched += 1
    e["classification"] = ev["classification"]
    e["classification_reason"] = ev["note"]
    e["evidence_strength"] = ev["strength"]
    e["evidence_source"] = ev["source"]
    e["evidence_url"] = ev["url"]

    con.execute(
        """
        UPDATE gaps
        SET classification=?, classification_reason=?,
            evidence_strength=?, evidence_source=?, evidence_url=?, evidence_note=?,
            last_seen_at_ms=?
        WHERE symbol=? AND gap_start_ms=? AND gap_end_ms=?
        """,
        (
            ev["classification"], ev["note"],
            ev["strength"], ev["source"], ev["url"], ev["note"],
            time.time_ns() // 1_000_000,
            e["symbol"], e["gap_start_ms"], e["gap_end_ms"],
        ),
    )

shared = reg.get("shared_exact_intervals", [])
for g in shared:
    key = (g.get("gap_start_utc"), g.get("gap_end_utc"))
    ev = EVIDENCE.get(key)
    if ev:
        g["classification"] = ev["classification"]
        g["evidence_strength"] = ev["strength"]
        g["evidence_source"] = ev["source"]
        g["evidence_url"] = ev["url"]
        g["evidence_note"] = ev["note"]
    else:
        unmatched_shared.add(key)

reg["evidence_schema_version"] = 1
reg["official_evidence_enriched_at_ms"] = time.time_ns() // 1_000_000
reg["official_evidence_policy"] = (
    "Official Binance GLOBAL maintenance/outage evidence is correlation evidence for Binance TR historical gaps; "
    "it is not promoted to Binance TR-specific causation without Binance TR-specific evidence or source re-query."
)
atomic_json(OUT, reg)
con.commit()
con.close()

state = {
    "schema_version": 1,
    "status": "PASS",
    "matched_gap_entries": matched,
    "official_intervals_defined": len(EVIDENCE),
    "shared_intervals_without_official_match": [
        {"gap_start_utc": a, "gap_end_utc": b}
        for a, b in sorted(unmatched_shared)
    ],
    "backfill_touched": False,
    "source_requery_performed": False,
}
atomic_json(STATE, state)
print(json.dumps(state, ensure_ascii=False, indent=2))
PY

"$PY" "$ROOT/app/enrich_gap_registry_official_evidence.py"

echo
echo '========== SHARED GAP EVIDENCE =========='
"$PY" - <<'PY'
import json
from pathlib import Path
p=Path("/root/bintrbot/data/quality/gap_registry.json")
x=json.loads(p.read_text())
for g in x.get("shared_exact_intervals", []):
    print(
        g["gap_start_utc"], "->", g["gap_end_utc"],
        "markets=", g["affected_markets"],
        "class=", g.get("classification","UNCLASSIFIED"),
        "strength=", g.get("evidence_strength","NONE"),
    )
PY

echo
echo '========== SERVICES UNAFFECTED =========='
systemctl is-active bintrbot-backfill-klines.service || true
systemctl is-active bintrbot-collector.service || true
echo "PHASE1B_OFFICIAL_EVIDENCE_ENRICHMENT=PASS"
