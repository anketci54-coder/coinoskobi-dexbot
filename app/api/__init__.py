from __future__ import annotations

from fastapi.responses import HTMLResponse

from . import panel as _panel
from .panel_display_names import enrich_universe_display_names
from .panel_manual_paper_v2 import register_manual_paper_routes_v2
from .panel_universe import universe_panel_payload


PHASE14_PREMIUM_HEAD = """
<link rel="stylesheet" href="/static/panel-premium-v2.css?v=2">
<link rel="stylesheet" href="/static/panel-radar-trade-v3.css?v=2">
""".strip()

PHASE14_PREMIUM_BODY = """
<script src="/static/panel-premium-v2.js?v=2"></script>
<script src="/static/panel-radar-trade-v3.js?v=2"></script>
""".strip()


@_panel.app.middleware("http")
async def phase14_premium_responsive_shell(request, call_next):
    if request.url.path != "/":
        return await call_next(request)

    html = _panel.INDEX_FILE.read_text(encoding="utf-8")

    if "panel-premium-v2.css" not in html:
        html = html.replace("</head>", PHASE14_PREMIUM_HEAD + "\n</head>", 1)

    if "panel-premium-v2.js" not in html:
        html = html.replace("</body>", PHASE14_PREMIUM_BODY + "\n</body>", 1)

    html = html.replace(
        "shortToken(r.token0)||'POOL'",
        "r.display_name||shortToken(r.token0)||'POOL'",
        1,
    )
    html = html.replace("PHASE 9 · READ ONLY", "CÜZDAN İZLEME")
    html = html.replace("OPERASYON ANALİSTİ · SADECE OKUMA", "OPERASYON ASİSTANI")

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


register_manual_paper_routes_v2(
    _panel.app,
    paper_db=_panel.PAPER_DB,
    cache_db=_panel.CACHE_DB,
)
