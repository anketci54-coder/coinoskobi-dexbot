from app.dex.event_buffer import EventBuffer, buffer_health


def test_push():
    b = EventBuffer(3)
    r = b.push({"id": 1})
    assert r["accepted"] is True
    assert b.size == 1


def test_bounded():
    b = EventBuffer(2)

    b.push({"id": 1})
    b.push({"id": 2})
    r = b.push({"id": 3})

    assert b.size == 2
    assert r["overflowed"] is True
    assert r["dropped"]["id"] == 1
    assert b.dropped == 1


def test_fifo():
    b = EventBuffer(3)

    b.push({"id": 1})
    b.push({"id": 2})

    assert b.pop()["id"] == 1
    assert b.pop()["id"] == 2


def test_drain_limit():
    b = EventBuffer(5)

    for i in range(5):
        b.push({"id": i})

    rows = b.drain(2)

    assert len(rows) == 2
    assert b.size == 3


def test_health():
    b = EventBuffer(10)

    for i in range(8):
        b.push({"id": i})

    assert buffer_health(b)["state"] == "PRESSURED"


def test_full():
    b = EventBuffer(2)
    b.push(1)
    b.push(2)

    assert buffer_health(b)["state"] == "FULL"


def test_bounded_flag():
    b = EventBuffer(2)
    r = buffer_health(b)

    assert r["bounded"] is True
    assert r["decision_authority"] is False
    assert r["execution_authority"] is False
