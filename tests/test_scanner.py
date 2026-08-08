from app.scanner.gecko_scanner import GeckoScanner
from app.filter.cache_filter import CacheFilter

def test_scanner():
    rows = GeckoScanner().scan()

    assert isinstance(rows, list)

    filtered = CacheFilter().filter(rows)

    assert isinstance(filtered, list)
