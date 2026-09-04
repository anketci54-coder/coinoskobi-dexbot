from app.learning import watch_probe_exit


def test_watch_exit_canonical_quote_assets_are_bounded():
    assert watch_probe_exit.WBNB.lower() == "0xbb4cdb9cbd36b01bd1cbaebf2de08d9173bc095c"
    assert watch_probe_exit.USDT.lower() == "0x55d398326f99059ff775485246999027b3197955"
    assert watch_probe_exit.USDC.lower() == "0x8ac76a51cc950d9822d68b83fe1ad97b32cd580d"
    assert watch_probe_exit.MAX_PROBES_PER_MINUTE == 4
    assert watch_probe_exit.RETRY_SECONDS == 900.0
