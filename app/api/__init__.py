from __future__ import annotations

from fastapi.responses import HTMLResponse

from . import panel as _panel
from .panel_display_names import enrich_universe_display_names
from .panel_manual_paper import register_manual_paper_routes
from .panel_universe import universe_panel_payload


@_panel.app.middleware("http")
async def canonical_panel_shell(request, call_next):
    if request.url.path != "/":
        return await call_next(request)

    return HTMLResponse(
        content=_panel.INDEX_FILE.read_text(encoding="utf-8"),
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


@_panel.app.get("/api/universe-panel")
def api_universe_panel():
    payload = universe_panel_payload(_panel.CACHE_DB)
    return enrich_universe_display_names(payload, _panel.CACHE_DB)


register_manual_paper_routes(
    _panel.app,
    paper_db=_panel.PAPER_DB,
    cache_db=_panel.CACHE_DB,
)
