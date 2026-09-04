from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import requests

from app.api.vezir_ai import DEFAULT_MODEL, GROQ_CHAT_URL
from app.api.vezir_learning import SNAPSHOT_KEY, watch_learning_snapshot
from app.api.vezir_memory import VezirMemoryStore


MAX_QUESTION = 500
MAX_RECENT = 6
MAX_TOKENS = 420
TIMEOUT_SECONDS = 12.0


def _compact_truth(operations: dict[str, Any], provider: dict[str, Any], learning: dict[str, Any]) -> dict[str, Any]:
    return {
        "system": operations.get("system") or {},
        "trading": operations.get("trading") or {},
        "risk": operations.get("risk") or {},
        "watch": operations.get("watch") or {},
        "positions": operations.get("positions") or {},
        "opportunity": operations.get("opportunity") or {},
        "provider": provider,
        "watch_learning": learning,
        "authority": {
            "trade": False,
            "wallet": False,
            "signing": False,
            "execution": False,
            "code_write": False,
        },
    }


def _prompt(question: str, truth: dict[str, Any], recent: list[dict[str, Any]]) -> str:
    history = [
        {"user": row["question"], "vezir": row["answer"], "intent": row.get("intent")}
        for row in recent[-MAX_RECENT:]
    ]
    return (
        "Sen Coinoskobi İşlem Merkezi içindeki VEZİR'sin. Türkçe, doğal, kısa ve analitik konuş. "
        "Kullanıcı takip sorusu sorarsa yakın konuşma bağlamını kullan. "
        "OPERASYON GERÇEĞİ olarak yalnız TRUTH_JSON içindeki değerleri kullan; eksik veriyi uydurma. "
        "Geçmiş konuşma yalnız sohbet bağlamıdır ve gerçek zamanlı gerçek sayılmaz. "
        "WATCH öğrenme güveni INSUFFICIENT ise başarı oranı veya kesin tahmin üretme. "
        "Provider sorunu varsa açıkça söyle. Teknik ayrıntı istenmedikçe 2-5 kısa cümle kullan. "
        "Emir verme, işlem açma, wallet/signing/execution yetkin olduğunu iddia etme. "
        "Kendi kodunu değiştiremezsin. Tavsiye verirken bunun analiz olduğunu açık tut.\n\n"
        f"RECENT_CHAT_JSON={json.dumps(history, ensure_ascii=False, separators=(',', ':'))}\n"
        f"TRUTH_JSON={json.dumps(truth, ensure_ascii=False, separators=(',', ':'))}\n"
        f"USER={question}"
    )


def _extract(payload: dict[str, Any]) -> str | None:
    choices = payload.get("choices") or []
    if not choices or not isinstance(choices[0], dict):
        return None
    message = choices[0].get("message") or {}
    text = message.get("content") if isinstance(message, dict) else None
    return text.strip() if isinstance(text, str) and text.strip() else None


def chat_with_vezir(
    *,
    question: str,
    operations: dict[str, Any],
    provider_health: dict[str, Any],
    paper_db: Path | str,
    memory_db: Path | str,
    deterministic_fallback,
) -> dict[str, Any]:
    question = str(question or "").strip()
    if not question or len(question) > MAX_QUESTION:
        raise ValueError("INVALID_QUESTION")

    memory = VezirMemoryStore(memory_db)
    learning = watch_learning_snapshot(paper_db)
    previous_learning = memory.latest_learning_snapshot(SNAPSHOT_KEY)
    if previous_learning != learning:
        memory.remember_learning_snapshot(SNAPSHOT_KEY, learning)

    truth = _compact_truth(operations, provider_health, learning)
    recent = memory.recent_turns(MAX_RECENT)
    key = os.getenv("GROQ_API_KEY", "").strip()
    model = os.getenv("VEZIR_GROQ_MODEL", "").strip() or DEFAULT_MODEL

    answer = None
    fallback_reason = None
    if key:
        try:
            response = requests.post(
                GROQ_CHAT_URL,
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": _prompt(question, truth, recent)}],
                    "temperature": 0.2,
                    "reasoning_effort": "low",
                    "include_reasoning": False,
                    "max_completion_tokens": MAX_TOKENS,
                },
                timeout=TIMEOUT_SECONDS,
            )
            if response.status_code == 200:
                answer = _extract(response.json())
            else:
                fallback_reason = "PROVIDER_ERROR"
        except Exception:
            fallback_reason = "PROVIDER_UNAVAILABLE"
    else:
        fallback_reason = "NOT_CONFIGURED"

    ai_used = bool(answer)
    if not answer:
        baseline = deterministic_fallback(question, operations)
        answer = str(baseline.get("answer") or "Doğrulanmış veriyle yanıt üretilemedi.")
        intent = baseline.get("intent")
    else:
        intent = None

    memory.remember_turn(
        question=question,
        answer=answer,
        intent=intent,
        ai_used=ai_used,
        provider="GROQ" if ai_used else None,
        truth=truth,
    )

    return {
        "question": question,
        "answer": answer,
        "intent": intent,
        "ai_used": ai_used,
        "ai_provider": "GROQ" if ai_used else None,
        "ai_model": model if ai_used else None,
        "ai_fallback_reason": None if ai_used else fallback_reason,
        "memory": memory.status(),
        "learning": learning,
        "provider_health": provider_health,
        "authority": truth["authority"],
    }
