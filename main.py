import logging

from app.cache.gecko_cache import GeckoCache
from app.filter.cache_filter import CacheFilter
from app.pipeline.engine import PipelineEngine
from app.paper.manager import PaperManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s : %(message)s",
)

logger = logging.getLogger(__name__)


def main():

    print("=" * 60)
    print("Coinoskobi Pipeline v6")
    print("=" * 60)

    cache    = GeckoCache()
    flt      = CacheFilter()
    pipeline = PipelineEngine()
    manager  = PaperManager()

    rows       = cache.all()
    candidates = flt.filter(rows)

    print(f"Cache      : {len(rows)}")
    print(f"Candidates : {len(candidates)}")

    paper_buy = 0
    watch     = 0
    reject    = 0
    skip      = 0

    for i, row in enumerate(candidates, start=1):

        token_address = row["token"].split("_", 1)[1]

        print()
        print("=" * 60)
        print(f"Aday #{i}  {token_address}")
        print("=" * 60)

        result = pipeline.run(token_address)

        if not result.get("success"):
            logger.warning("Pipeline failed for token: %s", token_address)
            reject += 1
            continue

        data     = result["data"]
        strategy = data.get("strategy", {})
        paper    = data.get("paper", {})

        decision = strategy.get("decision", "REJECT")
        action   = paper.get("action", "")

        print(f"Decision : {decision}")
        print(f"Score    : {strategy.get('score', 0)}")
        print(f"Risk     : {strategy.get('risk', '-')}")
        print(f"Action   : {action}")

        if decision == "PAPER_BUY":

            if action == "SKIP":
                reason = paper.get("reason", "")
                print(f">>> SKIP ({reason})")
                skip += 1

            else:
                print(">>> PAPER BUY")
                paper_buy += 1

        elif decision == "WATCH":
            print(">>> WATCH")
            watch += 1

        else:
            print(">>> REJECT")
            reject += 1

    print()
    print("=" * 60)
    print("ÖZET")
    print("=" * 60)
    print(f"Cache      : {len(rows)}")
    print(f"Candidates : {len(candidates)}")
    print(f"Paper Buy  : {paper_buy}")
    print(f"Watch      : {watch}")
    print(f"Reject     : {reject}")
    print(f"Skip       : {skip}")
    print("=" * 60)

    print()
    print("Pozisyon kontrolü")
    manager.process()


if __name__ == "__main__":
    main()
