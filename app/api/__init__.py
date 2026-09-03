from __future__ import annotations

import re

from fastapi.responses import HTMLResponse

from . import panel as _panel
from .panel_display_names import enrich_universe_display_names
from .panel_manual_paper import register_manual_paper_routes
from .panel_universe import universe_panel_payload


@_panel.app.middleware("http")
async def canonical_panel_shell(request, call_next):
    if request.url.path != "/":
        return await call_next(request)

    html = _panel.INDEX_FILE.read_text(encoding="utf-8")

    # index.html remains the canonical structural shell. Runtime behavior and
    # presentation are owned by exactly one JS/CSS pair. The historical inline
    # implementation is stripped before the page is served, so there is no
    # second renderer, refresh loop, or manual-trade path in the browser.
    html = re.sub(r"<style>.*?</style>", "", html, count=1, flags=re.S)
    html = re.sub(r"<script>.*?</script>", "", html, count=1, flags=re.S)
    html = html.replace(
        "</head>",
        '<link rel="stylesheet" href="/static/panel.css?v=1">\n</head>',
        1,
    )
    html = html.replace(
        "</body>",
        '<script src="/static/panel.js?v=1"></script>\n</body>',
        1,
    )

    return HTMLResponse(
        content=html,
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
