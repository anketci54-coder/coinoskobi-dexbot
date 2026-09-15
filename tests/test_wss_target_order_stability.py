from app.dex.wss_service import NativeWSSService


class DummyRuntime:
    def __init__(self, *args, **kwargs):
        pass


class AliveThread:
    def is_alive(self):
        return True


def test_same_membership_different_order_does_not_restart():
    service = NativeWSSService(
        "wss://example.invalid",
        ["0x1", "0x2", "0x3"],
        runtime_factory=DummyRuntime,
    )

    service._started = True
    service._thread = AliveThread()

    calls = {"start": 0, "stop": 0}

    def start():
        calls["start"] += 1
        return True

    def stop():
        calls["stop"] += 1
        return True

    service.start = start
    service.stop = stop

    result = service.replace_pairs([
        "0x3",
        "0x1",
        "0x2",
    ])

    assert result["state"] == "UNCHANGED"
    assert result["restarted"] is False
    assert calls == {"start": 0, "stop": 0}


def test_same_membership_restarts_if_service_was_started_but_stopped():
    service = NativeWSSService(
        "wss://example.invalid",
        ["0x1", "0x2"],
        runtime_factory=DummyRuntime,
    )

    service._started = True

    calls = {"start": 0}

    def start():
        calls["start"] += 1
        return True

    service.start = start

    result = service.replace_pairs([
        "0x2",
        "0x1",
    ])

    assert result["state"] == "RESTARTED"
    assert result["restarted"] is True
    assert calls["start"] == 1
