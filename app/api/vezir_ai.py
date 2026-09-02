from __future__ import annotations

import json
import os
from typing import Any

import requests


GROQ_CHAT_URL = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_MODEL = "openai/gpt-oss-120b"
DEFAULT_TIMEOUT_SECONDS = 12.0


def _extract_output_text(
    payload: dict[str, Any],
) -> str | None:
    choices = payload.get("choices") or []

    if not choices:
        return None

    first = choices[0]

    if not isinstance(first, dict):
        return None

    message = first.get("message")

    if not isinstance(message, dict):
        return None

    text = message.get("content")

    if isinstance(text, str) and text.strip():
        return text.strip()

    return None


def _build_prompt(
    *,
    question: str,
    deterministic: dict[str, Any],
) -> str:
    truth = {
        "answer": deterministic.get("answer"),
        "intent": deterministic.get("intent"),
        "technical": deterministic.get("technical"),
        "evidence": deterministic.get("evidence"),
    }

    return (
        "Sen Coinoskobi panelindeki VEZIR isimli "
        "read-only operasyon analistisin.\n"
        "Sana verilen GERCEKLIK BLOĞU tek kaynak gerçektir.\n"
        "Yeni sayı, olay, neden, token, fırsat veya sistem "
        "durumu UYDURMA.\n"
        "GERCEKLIK BLOĞU ile çelişme.\n"
        "Trade emri verme, wallet/signing/runtime/deployment "
        "işlemi önerme veya yürütme.\n"
        "Teknik ayrıntıyı yalnız gerçeklik bloğunda varsa kullan.\n"
        "Kısa, net, doğal Türkçe konuş.\n"
        "Gereksiz teknik jargon ve tekrar kullanma.\n\n"
        f"KULLANICI SORUSU:\n{question}\n\n"
        "GERCEKLIK BLOĞU:\n"
        f"{json.dumps(truth, ensure_ascii=False, separators=(',', ':'))}\n\n"
        "Sadece kullanıcıya gösterilecek cevabı yaz."
    )


def enhance_vezir_answer(
    *,
    question: str,
    deterministic: dict[str, Any],
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """
    Optional Groq language layer over deterministic Vezir truth.

    Groq receives only the bounded deterministic truth projection
    and the user's question.

    It has no trade, wallet, signing, database-write, runtime-control
    or deployment authority.

    Any configuration, provider or output failure returns the
    deterministic answer unchanged.
    """

    fallback = dict(deterministic)
    fallback["ai_used"] = False
    fallback["ai_provider"] = None

    key = os.getenv("GROQ_API_KEY", "").strip()

    if not key:
        fallback["ai_fallback_reason"] = "NOT_CONFIGURED"
        return fallback

    model = (
        os.getenv("VEZIR_GROQ_MODEL", "").strip()
        or DEFAULT_MODEL
    )

    try:
        response = requests.post(
            GROQ_CHAT_URL,
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": [
                    {
                        "role": "user",
                        "content": _build_prompt(
                            question=question,
                            deterministic=deterministic,
                        ),
                    }
                ],
                "temperature": 0,
            },
            timeout=timeout_seconds,
        )

        if response.status_code != 200:
            fallback["ai_fallback_reason"] = "PROVIDER_ERROR"
            return fallback

        payload = response.json()
        text = _extract_output_text(payload)

        if not text:
            fallback["ai_fallback_reason"] = "EMPTY_OUTPUT"
            return fallback

        result = dict(deterministic)
        result["answer"] = text
        result["ai_used"] = True
        result["ai_provider"] = "GROQ"
        result["ai_model"] = model
        result["ai_fallback_reason"] = None

        return result

    except Exception:
        fallback["ai_fallback_reason"] = "PROVIDER_UNAVAILABLE"
        return fallback
