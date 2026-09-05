import pytest

from app.dex import arkham_discovery_provider as provider


def _addr(index: int) -> str:
    return "0x" + f"{index:040x}"


class Response:
    status_code = 200

    def __init__(self, payload):
        self.payload = payload

    def json(self):
        return self.payload


def test_provider_is_inactive_without_api_key(monkeypatch):
    monkeypatch.delenv("ARKHAM_API_KEY", raising=False)
    called = []
    monkeypatch.setattr(provider.requests, "get", lambda *a, **k: called.append(1))

    out = provider.fetch_discovery_updates(
        feed="ADDRESS_UPDATES",
        since=100.0,
    )

    assert out["available"] is False
    assert out["reason"] == "ARKHAM_NOT_CONFIGURED"
    assert called == []


def test_address_updates_keep_only_performance_relevant_bsc_candidates_and_dedupe(monkeypatch):
    monkeypatch.setenv("ARKHAM_API_KEY", "configured-not-printed")
    calls = []
    payload = {
        "updates": [
            {"address": _addr(1), "chain": "bsc", "label": "Trader"},
            {"address": _addr(1), "chain": "bsc", "label": "Trader"},
            {"address": _addr(2), "chain": "ethereum", "label": "Trader"},
            {"address": {"address": _addr(3), "chain": "bnb"}, "label": "Whale"},
            {"address": _addr(4), "chain": "bsc", "label": "Exchange Deposit"},
            {"address": _addr(5), "chain": "bsc", "labels": [{"name": "Smart Money"}]},
            {"address": _addr(6), "chain": "bsc", "label": "High PnL Wallet"},
            {"address": _addr(7), "chain": "bsc", "label": "Profitable Trader"},
            {"address": "0xabc", "chain": "bsc", "label": "Trader"},
        ]
    }

    def fake_get(url, *, params, headers, timeout):
        calls.append((url, params, headers, timeout))
        return Response(payload)

    monkeypatch.setattr(provider.requests, "get", fake_get)
    out = provider.fetch_discovery_updates(
        feed="ADDRESS_UPDATES",
        since=100.0,
    )

    assert out["available"] is True
    assert [row["address"] for row in out["candidates"]] == [
        _addr(1),
        _addr(5),
        _addr(6),
        _addr(7),
    ]
    assert [row["metadata"]["arkham_signal"] for row in out["candidates"]] == [
        "TRADER",
        "SMART_MONEY",
        "HIGH_PNL",
        "TRADER",
    ]
    assert out["success_authority"] is False
    assert out["execution_authority"] is False
    assert calls[0][0].endswith("/intelligence/addresses/updates")
    assert calls[0][1]["since"].endswith("Z")
    assert "API-Key" in calls[0][2]


def test_tag_id_only_association_update_is_not_guessed_as_candidate(monkeypatch):
    monkeypatch.setenv("ARKHAM_API_KEY", "configured-not-printed")
    payload = {
        "updates": [
            {"address": _addr(8), "chain": "bsc", "tagId": "tag-123", "time": "2026-09-05T12:00:00Z"}
        ]
    }
    monkeypatch.setattr(provider.requests, "get", lambda *a, **k: Response(payload))

    out = provider.fetch_discovery_updates(
        feed="ADDRESS_TAG_UPDATES",
        since=100.0,
    )

    assert out["available"] is True
    assert out["candidates"] == []
    assert out["returned_candidates"] == 0


def test_address_updates_support_nested_data_shape_with_performance_label(monkeypatch):
    monkeypatch.setenv("ARKHAM_API_KEY", "configured-not-printed")
    payload = {
        "data": {
            "items": [
                {
                    "addressInfo": {"address": _addr(9), "chainType": "bsc"},
                    "label": "Smart Money Trader",
                    "time": "2026-09-05T12:00:00Z",
                }
            ]
        }
    }
    monkeypatch.setattr(provider.requests, "get", lambda *a, **k: Response(payload))

    out = provider.fetch_discovery_updates(
        feed="ADDRESS_UPDATES",
        since="2026-09-05T12:00:00Z",
    )

    assert out["available"] is True
    assert out["returned_candidates"] == 1
    assert out["candidates"][0]["address"] == _addr(9)
    assert out["candidates"][0]["metadata"]["arkham_signal"] == "TRADER"
    assert out["candidates"][0]["metadata"]["updated_at"] == "2026-09-05T12:00:00Z"


def test_valid_empty_update_page_is_successful(monkeypatch):
    monkeypatch.setenv("ARKHAM_API_KEY", "configured-not-printed")
    monkeypatch.setattr(provider.requests, "get", lambda *a, **k: Response({"updates": []}))

    out = provider.fetch_discovery_updates(feed="ADDRESS_UPDATES", since=100.0)

    assert out["available"] is True
    assert out["candidates"] == []
    assert out["returned_candidates"] == 0


def test_unknown_update_payload_is_provider_failure(monkeypatch):
    monkeypatch.setenv("ARKHAM_API_KEY", "configured-not-printed")
    monkeypatch.setattr(
        provider.requests,
        "get",
        lambda *a, **k: Response({"unexpected": {"shape": True}}),
    )

    out = provider.fetch_discovery_updates(feed="ADDRESS_UPDATES", since=100.0)

    assert out["available"] is False
    assert out["reason"] == "ARKHAM_INVALID_UPDATES_PAYLOAD"
    assert out["candidates"] == []


def test_normalizer_is_bounded_and_rejects_unknown_feed():
    rows = [
        {"address": _addr(i), "chain": "bsc", "label": "Trader"}
        for i in range(1, 10)
    ]
    out = provider.normalize_discovery_updates(
        rows,
        feed="ADDRESS_UPDATES",
        limit=3,
    )
    assert len(out) == 3

    with pytest.raises(ValueError, match="UNSUPPORTED_ARKHAM_DISCOVERY_FEED"):
        provider.normalize_discovery_updates(rows, feed="UNKNOWN")
