from collections import deque

from app.dex.wallet_readmodel import (
    WalletReadModel,
    hot_path_contract as wallet_contract,
)
from app.dex.adversary_readmodel import (
    AdversaryReadModel,
    hot_path_contract as adversary_contract,
)


def test_wallet_uses_deque():
    r = WalletReadModel(2)

    assert isinstance(r._order, deque)


def test_adversary_uses_deque():
    r = AdversaryReadModel(2)

    assert isinstance(r._order, deque)


def test_wallet_fifo_eviction():
    r = WalletReadModel(2)

    r.put("a", {"x": 1})
    r.put("b", {"x": 2})
    r.put("c", {"x": 3})

    assert r.size == 2
    assert r.get("a")["state"] == "UNKNOWN"
    assert r.get("b")["state"] == "READY"
    assert r.get("c")["state"] == "READY"


def test_adversary_fifo_eviction():
    r = AdversaryReadModel(2)

    r.put("a", {"x": 1})
    r.put("b", {"x": 2})
    r.put("c", {"x": 3})

    assert r.size == 2
    assert r.get("a")["state"] == "UNKNOWN"
    assert r.get("b")["state"] == "READY"
    assert r.get("c")["state"] == "READY"


def test_update_does_not_duplicate_wallet_order():
    r = WalletReadModel(2)

    r.put("a", {"x": 1})
    r.put("a", {"x": 2})
    r.put("b", {"x": 3})

    assert r.size == 2
    assert list(r._order) == ["a", "b"]


def test_update_does_not_duplicate_adversary_order():
    r = AdversaryReadModel(2)

    r.put("a", {"x": 1})
    r.put("a", {"x": 2})
    r.put("b", {"x": 3})

    assert r.size == 2
    assert list(r._order) == ["a", "b"]


def test_hotpath_contract_o1_eviction():
    assert wallet_contract()["o1_eviction"] is True
    assert adversary_contract()["o1_eviction"] is True
