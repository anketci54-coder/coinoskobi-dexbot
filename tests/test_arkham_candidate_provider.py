import os

from app.dex import arkham_candidate_provider as provider


def _addr(index: int) -> str:
    return "0x" + f"{index:040x}"


def test_normalize_address_tag_candidates_accepts_only_bsc_candidate_signals():
    payload = {
        "updates": [
            {
                "address": _addr(1),
                "chain": "bsc",
                "tag": {"name": "Smart Money Trader"},
            },
            {
                "address": _addr(2),
                "chainType": "BNB Chain",
                "tags": [{"name": "Whale"}],
            },
            {
                "address": _addr(3),
                "chain": "bsc",
                "tag": {"name": "Exchange Deposit"},
            },
            {
                "address": _addr(4),
                "chain": "ethereum",
                "tag": {"name": "Trader"},
            },
        ]
    }

    out = provider.normalize_address_tag_candidates(payload)

    assert out["available"] is True
    assert out["source"] == "ARKHAM_ADDRESS_TAG_UPDATE"
    assert out["candidate_count"] == 2
    assert [row["address"] for row in out["candidates"]] == [_addr(1), _addr(2)]
    assert out["ignored_rows"] == 1
    assert out["rejected_rows"] == 1
    assert out["success_authority"] is False
    assert out["trade_authority"] is False
    assert out["execution_authority"] is False


def test_normalize_nested_identity_and_deduplicates_wallets():
    address = _addr(11)
    payload = {
        "data": {
            "items": [
                {
                    "address": {"address": address, "chainType": "bsc"},
                    "tagName": "Trader",
                },
                {
                    "walletAddress": address.upper().replace("0X", "0x"),
                    "network": "BSC",
                    "label": "Smart Money",
                },
            ]
        }
    }

    out = provider.normalize_address_tag_candidates(payload)
    assert out["candidate_count"] == 1
    assert out["candidates"][0]["address"] == address


def test_normalize_is_bounded_and_fail_soft_on_unknown_payload():
    payload = [
        {"address": _addr(index), "chain": "bsc", "tag": "Trader"}
        for index in range(1, 220)
    ]
    out = provider.normalize_address_tag_candidates(payload, limit=25)
    assert out["candidate_count"] == 25

    bad = provider.normalize_address_tag_candidates({"unexpected": {"shape": True}})
    assert bad["available"] is True
    assert bad["candidate_count"] == 0
    assert bad["candidates"] == []


def test_fetch_does_not_call_network_without_api_key(monkeypatch):
    monkeypatch.delenv("ARKHAM_API_KEY", raising=False)

    def fail(*args, **kwargs):
        raise AssertionError("network must not be called")

    monkeypatch.setattr(provider.requests, "get", fail)
    out = provider.fetch_address_tag_updates()
    assert out == {
        "available": False,
        "reason": "ARKHAM_NOT_CONFIGURED",
        "candidates": [],
    }


def test_fetch_uses_only_supplied_params_and_normalizes(monkeypatch):
    monkeypatch.setenv("ARKHAM_API_KEY", "secret-test-key")
    calls = []

    class Response:
        status_code = 200

        def json(self):
            return {
                "results": [
                    {"address": _addr(9), "chain": "bsc", "tag": "Trader"}
                ]
            }

    def fake_get(url, *, params, headers, timeout):
        calls.append((url, params, headers, timeout))
        return Response()

    monkeypatch.setattr(provider.requests, "get", fake_get)
    out = provider.fetch_address_tag_updates(params={"cursor": "verified-cursor"})

    assert out["candidate_count"] == 1
    assert calls[0][0].endswith("/intelligence/address_tags/updates")
    assert calls[0][1] == {"cursor": "verified-cursor"}
    assert calls[0][2]["API-Key"] == "secret-test-key"
    assert out["success_authority"] is False


def test_fetch_fail_soft_http_and_invalid_json(monkeypatch):
    monkeypatch.setenv("ARKHAM_API_KEY", "secret-test-key")

    class HttpError:
        status_code = 429

    monkeypatch.setattr(provider.requests, "get", lambda *a, **k: HttpError())
    out = provider.fetch_address_tag_updates()
    assert out["available"] is False
    assert out["reason"] == "ARKHAM_HTTP_429"

    class BadJson:
        status_code = 200

        def json(self):
            raise ValueError("bad json")

    monkeypatch.setattr(provider.requests, "get", lambda *a, **k: BadJson())
    out = provider.fetch_address_tag_updates()
    assert out["available"] is False
    assert out["reason"] == "ARKHAM_INVALID_JSON"
