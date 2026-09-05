from app.dex.arkham_discovery_provider import (
    MAX_UPDATE_ROWS,
    fetch_intelligence_updates,
)


class _Response:
    def __init__(self, status_code=200, payload=None, json_error=False):
        self.status_code = status_code
        self._payload = payload
        self._json_error = json_error

    def json(self):
        if self._json_error:
            raise ValueError("bad json")
        return self._payload


class _Session:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.response


def test_provider_is_inactive_without_api_key(monkeypatch):
    monkeypatch.delenv("ARKHAM_API_KEY", raising=False)
    out = fetch_intelligence_updates("ADDRESS_TAGS", session=_Session(None))
    assert out["available"] is False
    assert out["state"] == "ARKHAM_NOT_CONFIGURED"
    assert out["success_authority"] is False
    assert out["execution_authority"] is False


def test_provider_uses_only_caller_supplied_params(monkeypatch):
    monkeypatch.setenv("ARKHAM_API_KEY", "secret")
    session = _Session(_Response(payload={"updates": [{"id": 1}]}))
    out = fetch_intelligence_updates(
        "ADDRESS_TAGS",
        params={"cursor": "abc"},
        session=session,
    )
    assert out["available"] is True
    assert out["row_count"] == 1
    url, kwargs = session.calls[0]
    assert url.endswith("/intelligence/address_tags/updates")
    assert kwargs["params"] == {"cursor": "abc"}
    assert kwargs["headers"]["API-Key"] == "secret"


def test_provider_caps_update_rows(monkeypatch):
    monkeypatch.setenv("ARKHAM_API_KEY", "secret")
    rows = [{"id": i} for i in range(MAX_UPDATE_ROWS + 20)]
    out = fetch_intelligence_updates(
        "ADDRESSES",
        session=_Session(_Response(payload={"data": rows})),
    )
    assert out["row_count"] == MAX_UPDATE_ROWS
    assert len(out["rows"]) == MAX_UPDATE_ROWS
    assert out["capped"] is True


def test_provider_fail_soft_http_and_json(monkeypatch):
    monkeypatch.setenv("ARKHAM_API_KEY", "secret")
    http = fetch_intelligence_updates(
        "ADDRESSES",
        session=_Session(_Response(status_code=429, payload={})),
    )
    bad_json = fetch_intelligence_updates(
        "ADDRESSES",
        session=_Session(_Response(json_error=True)),
    )
    assert http["state"] == "ARKHAM_HTTP_429"
    assert bad_json["state"] == "ARKHAM_INVALID_JSON"
    assert http["trade_authority"] is False
    assert bad_json["decision_authority"] is False
