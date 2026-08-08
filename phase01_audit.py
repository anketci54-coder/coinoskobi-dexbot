import time
import json
import inspect

from app.scanner.gecko_scanner import GeckoScanner
from app.filter.cache_filter import CacheFilter
from app.pipeline.engine import PipelineEngine

print("="*70)
print("COINOSKOBI PHASE0 -> PHASE1 CONTRACT AUDIT")
print("="*70)

scanner = GeckoScanner()
flt = CacheFilter()
pipe = PipelineEngine()

# ------------------------------------------------------------------
# Scanner
# ------------------------------------------------------------------

t0 = time.perf_counter()
rows = scanner.scan()
t1 = time.perf_counter()

scan_ms = (t1-t0)*1000

print()
print("SCANNER")
print("Rows :", len(rows))
print("Time :", round(scan_ms,2),"ms")

assert isinstance(rows,list)

assert len(rows)>0

required = [
    "pool",
    "base_token",
    "quote_token",
    "name",
    "dex",
    "price_usd",
    "fdv",
    "market_cap",
    "liquidity",
    "volume_24h",
    "buys_24h",
    "created_at",
]

missing=[]

for k in required:
    if k not in rows[0]:
        missing.append(k)

print("Missing :", missing)

# ------------------------------------------------------------------
# Filter
# ------------------------------------------------------------------

t0=time.perf_counter()
filtered=flt.filter(rows)
t1=time.perf_counter()

filter_ms=(t1-t0)*1000

print()
print("FILTER")
print("Rows :",len(filtered))
print("Time :",round(filter_ms,2),"ms")

if filtered:

    x=filtered[0]

    print()

    for k in required:
        print(f"{k:15}",k in x)

# ------------------------------------------------------------------
# Pipeline API
# ------------------------------------------------------------------

print()
print("PIPELINE")

print("run()      :",hasattr(pipe,"run"))
print("run_cycle():",hasattr(pipe,"run_cycle"))

sig=inspect.signature(pipe.run)
print("Signature :",sig)

# ------------------------------------------------------------------
# E2E latency
# ------------------------------------------------------------------

e2e=[]

for row in filtered[:5]:

    token=row["base_token"].split("_",1)[1]

    s=time.perf_counter()

    try:
        pipe.run(token)
    except Exception:
        pass

    e=time.perf_counter()

    e2e.append((e-s)*1000)

print()
print("LATENCY")

print("Scanner :",round(scan_ms,2),"ms")
print("Filter  :",round(filter_ms,2),"ms")

if e2e:
    print("Pipeline avg :",round(sum(e2e)/len(e2e),2),"ms")
    print("Pipeline min :",round(min(e2e),2),"ms")
    print("Pipeline max :",round(max(e2e),2),"ms")

print()
print("="*70)
print("PHASE0 -> PHASE1 AUDIT COMPLETE")
print("="*70)
