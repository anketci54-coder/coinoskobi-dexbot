from __future__ import annotations

from fastapi.responses import HTMLResponse

# Package bootstrap intentionally registers display-only panel extensions on the
# canonical FastAPI app without changing paper/runtime/execution authority.
from . import panel as _panel
from .panel_universe import universe_panel_payload


# Phase 14 maintenance closure for laptop-class viewports. The canonical panel
# remains a single index.html; this display-only response shim only adds bounded
# responsive CSS at the root route so 1366x768 and 1600x900 remain usable without
# creating a second panel or changing any data/decision/execution authority.
PHASE14_DESKTOP_RESPONSIVE_STYLE = """
<style id="phase14-desktop-responsive-closure">
@media (max-width:1450px) and (min-width:1220px) {
  .app{min-width:0}
  .topbar{grid-template-columns:160px 118px 118px repeat(5,minmax(88px,1fr)) 230px}
  .brand,.ticker,.metric,.controls{padding:7px 8px}
  .brand-mark{font-size:32px}
  .brand-title{font-size:15px}
  .ticker-value,.metric-value{font-size:13px}
  .content{grid-template-columns:minmax(0,1fr) 380px}
  .middle{grid-template-columns:270px minmax(0,1fr) minmax(250px,.82fr)}
  .radar-grid,.radar-row{grid-template-columns:60px minmax(115px,1.15fr) 56px 68px 68px 58px 68px 70px minmax(125px,1fr);gap:5px}
  .tab{padding:0 9px}
}
@media (max-height:820px) and (min-width:1220px) {
  .app{grid-template-rows:64px 1fr 36px}
  .left{grid-template-rows:minmax(252px,1.05fr) minmax(126px,.50fr) minmax(88px,.30fr) 68px}
  .right{grid-template-rows:minmax(210px,.82fr) minmax(168px,.66fr) minmax(100px,.40fr)}
  .head{height:34px}
  .radar{grid-template-rows:34px 30px minmax(0,1fr) 24px}
  .radar-row{min-height:28px}
  .timeline{padding:5px 8px;grid-template-rows:16px 1fr}
  .step{height:32px;padding:3px}
  .vezir{grid-template-rows:68px 30px 1fr 38px}
  .vezir-head{grid-template-columns:56px 1fr;padding:6px 9px}
  .vezir-img{width:52px;height:52px}
  .edge-big{font-size:22px}
  .edge-caption{font-size:11px}
  .kv{padding:5px 0}
}
</style>
""".strip()


@_panel.app.middleware("http")
async def phase14_desktop_responsive_shell(request, call_next):
    if request.url.path != "/":
        return await call_next(request)

    html = _panel.INDEX_FILE.read_text(encoding="utf-8")

    if "phase14-desktop-responsive-closure" not in html:
        html = html.replace(
            "</head>",
            PHASE14_DESKTOP_RESPONSIVE_STYLE + "\n</head>",
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
    return universe_panel_payload(_panel.CACHE_DB)
