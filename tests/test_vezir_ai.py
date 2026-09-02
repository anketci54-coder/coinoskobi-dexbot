import app.api.vezir_ai as ai


BASE = {
    "answer": "Şu anda 0 açık paper işlem var.",
    "intent": "POSITIONS",
    "authority": "READ_ONLY",
    "technical": None,
    "evidence": {
        "paper_open": 0,
    },
    "permissions": {
        "trade": False,
        "wallet": False,
        "signing": False,
        "database_write": False,
        "runtime_control": False,
        "deployment": False,
    },
}


def test_ai_falls_back_when_key_missing(monkeypatch):
    monkeypatch.delenv(
        "GROQ_API_KEY",
        raising=False,
    )

    r = ai.enhance_vezir_answer(
        question="İşlemleri özetle",
        deterministic=BASE,
    )

    assert r["answer"] == BASE["answer"]
    assert r["ai_used"] is False
    assert r["ai_fallback_reason"] == "NOT_CONFIGURED"


def test_ai_success_preserves_authority(monkeypatch):
    monkeypatch.setenv(
        "GROQ_API_KEY",
        "test-key",
    )
    monkeypatch.setenv(
        "VEZIR_GROQ_MODEL",
        "openai/gpt-oss-120b",
    )

    captured = {}

    class Response:
        status_code = 200

        def json(self):
            return {
                "choices": [
                    {
                        "message": {
                            "content": (
                                "Açık paper işlem bulunmuyor."
                            )
                        }
                    }
                ]
            }

    def fake_post(*args, **kwargs):
        captured.update(kwargs)
        return Response()

    monkeypatch.setattr(
        ai.requests,
        "post",
        fake_post,
    )

    r = ai.enhance_vezir_answer(
        question="İşlemleri özetle",
        deterministic=BASE,
    )

    assert r["answer"] == "Açık paper işlem bulunmuyor."
    assert r["ai_used"] is True
    assert r["ai_provider"] == "GROQ"
    assert r["ai_model"] == "openai/gpt-oss-120b"

    assert r["authority"] == "READ_ONLY"

    assert all(
        value is False
        for value in r["permissions"].values()
    )

    assert captured["json"]["model"] == "openai/gpt-oss-120b"

    prompt = captured["json"]["messages"][0]["content"]

    assert "GERCEKLIK BLOĞU" in prompt
    assert "paper_open" in prompt


def test_ai_provider_error_falls_back(monkeypatch):
    monkeypatch.setenv(
        "GROQ_API_KEY",
        "test-key",
    )

    class Response:
        status_code = 429

        def json(self):
            return {}

    monkeypatch.setattr(
        ai.requests,
        "post",
        lambda *a, **k: Response(),
    )

    r = ai.enhance_vezir_answer(
        question="Risk ne?",
        deterministic=BASE,
    )

    assert r["answer"] == BASE["answer"]
    assert r["ai_used"] is False
    assert r["ai_fallback_reason"] == "PROVIDER_ERROR"


def test_ai_empty_output_falls_back(monkeypatch):
    monkeypatch.setenv(
        "GROQ_API_KEY",
        "test-key",
    )

    class Response:
        status_code = 200

        def json(self):
            return {
                "choices": [
                    {
                        "message": {
                            "content": ""
                        }
                    }
                ]
            }

    monkeypatch.setattr(
        ai.requests,
        "post",
        lambda *a, **k: Response(),
    )

    r = ai.enhance_vezir_answer(
        question="Durum nedir?",
        deterministic=BASE,
    )

    assert r["answer"] == BASE["answer"]
    assert r["ai_used"] is False
    assert r["ai_fallback_reason"] == "EMPTY_OUTPUT"


def test_ai_exception_falls_back(monkeypatch):
    monkeypatch.setenv(
        "GROQ_API_KEY",
        "test-key",
    )

    def fail(*args, **kwargs):
        raise RuntimeError("provider unavailable")

    monkeypatch.setattr(
        ai.requests,
        "post",
        fail,
    )

    r = ai.enhance_vezir_answer(
        question="Durum nedir?",
        deterministic=BASE,
    )

    assert r["answer"] == BASE["answer"]
    assert r["ai_used"] is False
    assert r["ai_fallback_reason"] == "PROVIDER_UNAVAILABLE"
