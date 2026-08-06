import time
import requests

from app.scanner.gecko_scanner import GeckoScanner
from app.cache.gecko_cache import GeckoCache


def main():

    scanner = GeckoScanner()
    cache = GeckoCache()

    retries = 3

    for attempt in range(retries):

        try:

            pools = scanner.scan()

            print(f"{len(pools)} pool bulundu.")

            for pool in pools:
                cache.replace(pool)

            print("Cache güncellendi.")

            rows = cache.all()

            print(f"SQLite kayıt : {len(rows)}")

            return

        except requests.exceptions.HTTPError as e:

            if getattr(e.response, "status_code", None) == 429:

                wait = (attempt + 1) * 30

                print(f"429 Rate Limit. {wait} sn bekleniyor...")

                time.sleep(wait)

                continue

            raise

    print("Gecko güncellenemedi.")


if __name__ == "__main__":

    main()
