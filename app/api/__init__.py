from __future__ import annotations

from fastapi import HTTPException

from . import panel as _panel
from .panel_acceptance import register_panel_acceptance_routes
from .panel_display_names import enrich_universe_display_names
from .panel_manual_paper_v2 import register_manual_paper_routes_v2
from .panel_provider_health import provider_health_snapshot, register_provider_health_route
from .panel_universe import universe_panel_payload
from .panel_watch_summary import register_watch_summary_route
from .vezir_chat import chat_with_vezir


VEZIR_MEMORY_DB = _panel.BASE_DIR / "data" / "vezir_memory.db"


@_panel.app.get("/api/universe-panel")
def api_universe_panel():
    payload = universe_panel_payload(_panel.CACHE_DB)
    return enrich_universe_display_names(payload, _panel.CACHE_DB)


@_panel.app.post("/api/vezir/chat-v2")
def api_vezir_chat_v2(payload: dict):
    question = str(payload.get("question") or "").strip()
    try:
        return chat_with_vezir(
            question=question,
            operations=_panel._phase14_operations_payload(),
            provider_health=provider_health_snapshot(),
            paper_db=_panel.PAPER_DB,
            memory_db=VEZIR_MEMORY_DB,
            deterministic_fallback=_panel.answer_vezir_query,
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Soru boş veya çok uzun")


register_provider_health_route(_panel.app)

register_manual_paper_routes_v2(
    _panel.app,
    paper_db=_panel.PAPER_DB,
    cache_db=_panel.CACHE_DB,
)

register_watch_summary_route(
    _panel.app,
    paper_db=_panel.PAPER_DB,
)

register_panel_acceptance_routes(
    _panel.app,
    paper_db=_panel.PAPER_DB,
)
