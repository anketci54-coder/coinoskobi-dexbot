import app.cache.gecko_cache as module


def row(
    *,
    pool="0xPOOL1",
    token="bsc_0xTOKEN1",
    source=None,
    observed_at=None,
    price=1.0,
    liquidity=10000.0,
):
    result = {
        "pool": pool,
        "base_token": token,
        "quote_token": "bsc_0xQUOTE",
        "name": "TOKEN/WBNB",
        "dex": "pancakeswap_v2",
        "liquidity": liquidity,
        "volume_24h": 5000.0,
        "buys_24h": 20,
        "fdv": 50000.0,
        "market_cap": 45000.0,
        "price_usd": price,
        "created_at": "2026-08-25T00:00:00Z",
    }

    if source is not None:
        result["source"] = source

    if observed_at is not None:
        result["observed_at"] = observed_at

    return result


def test_replace_preserves_latest_snapshot_and_appends_history(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(
        module,
        "DB",
        tmp_path / "cache.db",
    )

    cache = module.GeckoCache()

    cache.replace(
        row(
            observed_at="2026-08-25T10:00:00Z",
            price=1.0,
        )
    )

    cache.replace(
        row(
            observed_at="2026-08-25T10:01:00Z",
            price=1.2,
        )
    )

    latest = cache.all()

    assert len(latest) == 1
    assert latest[0]["price_usd"] == 1.2

    history = cache.history_for_pool(
        "0xpool1"
    )

    assert len(history) == 2

    assert [
        item["price_usd"]
        for item in history
    ] == [1.0, 1.2]

    assert [
        item["observed_at"]
        for item in history
    ] == [
        "2026-08-25T10:00:00Z",
        "2026-08-25T10:01:00Z",
    ]


def test_history_keeps_canonical_identity_and_raw_fields(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(
        module,
        "DB",
        tmp_path / "cache.db",
    )

    cache = module.GeckoCache()

    cache.replace(
        row(
            source="geckoterminal",
            observed_at="2026-08-25T10:00:00Z",
            price=2.0,
            liquidity=12345.0,
        )
    )

    item = cache.history_for_pool(
        "0xpool1",
        source="geckoterminal",
    )[0]

    assert (
        item["schema_version"]
        == "MARKET_OBSERVATION_V1"
    )
    assert item["chain"] == "bsc"
    assert item["source"] == "geckoterminal"
    assert item["dex"] == "pancakeswap_v2"

    assert item["pool"] == "0xpool1"
    assert item["token"] == "0xtoken1"
    assert item["quote_token"] == "0xquote"

    assert item["price_usd"] == 2.0
    assert item["liquidity_usd"] == 12345.0
    assert item["volume_24h"] == 5000.0
    assert item["buys_24h"] == 20
    assert item["fdv_usd"] == 50000.0
    assert item["market_cap_usd"] == 45000.0


def test_prune_only_removes_latest_cache_not_training_history(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(
        module,
        "DB",
        tmp_path / "cache.db",
    )

    cache = module.GeckoCache()

    cache.replace(
        row(
            pool="0xpool1",
            token="bsc_0xtoken1",
        )
    )

    cache.replace(
        row(
            pool="0xpool2",
            token="bsc_0xtoken2",
        )
    )

    assert cache.observation_count() == 2

    removed = cache.prune_except(
        ["0xpool1"]
    )

    assert removed == 1

    latest_pools = {
        item["pool"]
        for item in cache.all()
    }

    assert latest_pools == {"0xpool1"}

    # Raw historical evidence is intentionally durable.
    assert cache.observation_count() == 2

    assert len(
        cache.history_for_pool(
            "0xpool2"
        )
    ) == 1


def test_source_filter_prevents_cross_source_history_mix(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(
        module,
        "DB",
        tmp_path / "cache.db",
    )

    cache = module.GeckoCache()

    cache.replace(
        row(
            source="geckoterminal",
            observed_at="2026-08-25T10:00:00Z",
            price=1.0,
        )
    )

    cache.replace(
        row(
            source="dexscreener",
            observed_at="2026-08-25T10:01:00Z",
            price=2.0,
        )
    )

    gecko = cache.history_for_pool(
        "0xpool1",
        source="geckoterminal",
    )

    dex = cache.history_for_pool(
        "0xpool1",
        source="dexscreener",
    )

    assert len(gecko) == 1
    assert len(dex) == 1
    assert gecko[0]["price_usd"] == 1.0
    assert dex[0]["price_usd"] == 2.0


def test_cache_builds_pool_source_calibration_from_raw_history(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(
        module,
        "DB",
        tmp_path / "cache.db",
    )

    cache = module.GeckoCache()

    samples = (
        (1.00, 10000.0),
        (1.03, 9800.0),
        (1.01, 10100.0),
        (1.06, 9500.0),
        (1.04, 9700.0),
        (1.10, 9000.0),
    )

    for index, (
        price,
        liquidity,
    ) in enumerate(samples):
        cache.replace(
            row(
                source="geckoterminal",
                observed_at=(
                    "2026-08-25T10:"
                    f"{index:02d}:00Z"
                ),
                price=price,
                liquidity=liquidity,
            )
        )

    result = (
        cache.stream_math_calibration_for_pool(
            "0xpool1",
            source="geckoterminal",
        )
    )

    assert result["state"] == "READY"

    assert (
        result["identity"]["pool"]
        == "0xpool1"
    )

    assert (
        result["identity"]["source"]
        == "geckoterminal"
    )

    calibration = result[
        "calibration"
    ]

    assert 0 < calibration[
        "ewma_decay"
    ] < 1

    assert calibration[
        "cusum_reference"
    ] >= 0

    assert calibration[
        "cusum_threshold"
    ] > 0

    assert result[
        "decision_authority"
    ] is False
