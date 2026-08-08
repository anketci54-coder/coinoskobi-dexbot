import time

from app.pipeline.engine import PipelineEngine
from app.scanner.gecko_scanner import GeckoScanner
from app.filter.cache_filter import CacheFilter

engine = PipelineEngine()

rows = GeckoScanner().scan()
rows = CacheFilter().filter(rows)

if not rows:
    raise SystemExit("No candidate")

token = rows[0]["base_token"].split("_",1)[1]

t0 = time.perf_counter()
engine.run(token)
t1 = time.perf_counter()

print("="*60)
print("REAL PIPELINE")
print("="*60)
print(f"Pipeline : {(t1-t0)*1000:.2f} ms")
