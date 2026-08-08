def test_imports():
    modules = [
        "main",
        "app.pipeline.engine",
        "app.core.runner",
        "app.core.scheduler",
        "app.scanner.gecko_scanner",
        "app.cache.gecko_cache",
        "app.filter.cache_filter",
        "app.analyzer.token",
        "app.analyzer.pair",
        "app.risk.bytecode",
        "app.strategy.engine",
        "app.paper.database",
        "app.paper.manager",
    ]

    for m in modules:
        __import__(m)
