from __future__ import annotations

from fastapi.responses import HTMLResponse

# Package bootstrap intentionally registers display-only panel extensions on the
# canonical FastAPI app without changing paper/runtime/execution authority.
from . import panel as _panel
from .panel_display_names import enrich_universe_display_names
from .panel_universe import universe_panel_payload


# Phase 14 display-only desktop closure. The canonical panel remains a single
# index.html and all backend/readmodel/authority contracts stay unchanged.
PHASE14_DESKTOP_RESPONSIVE_STYLE = """
<style id="phase14-desktop-responsive-closure">
:root{
  --phase14-glow:0 0 0 1px rgba(43,178,226,.03),0 8px 24px rgba(0,0,0,.18);
}
html,body{
  text-rendering:geometricPrecision;
  -webkit-font-smoothing:antialiased;
  -moz-osx-font-smoothing:grayscale;
}
.panel{
  border-color:#14506a;
  background:linear-gradient(180deg,rgba(5,19,29,.99),rgba(3,13,21,.995));
  box-shadow:var(--phase14-glow);
}
.title{font-size:13px;letter-spacing:.025em}
.label{font-size:9px;letter-spacing:.045em;color:#c7d8e1}
.meta{font-size:8.5px}
.sub{font-size:9px;color:#9bb0bb}
.small{font-size:9px;color:#d0dde3}
.token{font-size:11px;letter-spacing:.01em}
.table{font-size:9px}
.table th{font-size:8px;color:#9cb2bd}
.empty{font-size:9.5px;color:#9db0ba}
.kv{font-size:9px}
.flow-row{font-size:9px}
.timeline-title{font-size:9px}
.step b{font-size:8px}
.step small{font-size:8px}
.footer{font-size:8.5px}
.quick button,.ctrl,.chatbar input,.chatbar button{font-size:8.5px}
.box small{font-size:8px}
.box b{font-size:12px}

/* Keep scrolling available to wheel/touch while removing chrome scrollbars. */
.radar-body,.flow-body,.ledger-body,.wallet-body,.edge-body,.health-body,
.intel-body,.mini-body,.chat,.drawer-card{
  scrollbar-width:none;
  -ms-overflow-style:none;
}
.radar-body::-webkit-scrollbar,.flow-body::-webkit-scrollbar,
.ledger-body::-webkit-scrollbar,.wallet-body::-webkit-scrollbar,
.edge-body::-webkit-scrollbar,.health-body::-webkit-scrollbar,
.intel-body::-webkit-scrollbar,.mini-body::-webkit-scrollbar,
.chat::-webkit-scrollbar,.drawer-card::-webkit-scrollbar{display:none}

/* Premium reference proportions for full desktop. */
@media (min-width:1451px) {
  .app{padding:7px;gap:7px;grid-template-rows:74px 1fr 44px}
  .topbar{gap:6px;grid-template-columns:195px 150px 150px repeat(5,minmax(112px,1fr)) 295px}
  .brand,.ticker,.metric,.controls{padding:9px 12px}
  .brand-mark{font-size:40px}
  .brand-title{font-size:18px}
  .brand-sub{font-size:9px}
  .ticker-value,.metric-value{font-size:15px}
  .content{grid-template-columns:minmax(0,1fr) 440px;gap:7px}
  .left,.right,.middle,.lower,.healthintel{gap:7px}
  .left{grid-template-rows:minmax(310px,1.10fr) minmax(150px,.55fr) minmax(118px,.40fr) 92px}
  .right{grid-template-rows:minmax(255px,.90fr) minmax(215px,.78fr) minmax(135px,.50fr)}
  .middle{grid-template-columns:315px minmax(0,1fr) minmax(300px,.84fr)}
  .radar-grid,.radar-row{grid-template-columns:68px minmax(135px,1.18fr) 64px 78px 76px 70px 76px 84px minmax(160px,1fr);gap:7px}
  .radar-row{min-height:32px}
  .state{font-size:8px}
  .vezir-name{font-size:20px}
  .vezir-sub{font-size:9px}
  .bubble{font-size:10px;line-height:1.5}
  .edge-big{font-size:29px}
  .edge-caption{font-size:14px}
}

/* 1366-class laptop: readable but still one-screen, no visible scrollbars. */
@media (max-width:1450px) and (min-width:1220px) {
  .app{min-width:0;padding:5px;gap:5px;grid-template-rows:62px 1fr 31px}
  .topbar{gap:5px;grid-template-columns:158px 118px 118px repeat(5,minmax(87px,1fr)) 228px}
  .brand,.ticker,.metric,.controls{padding:6px 8px}
  .brand-mark{font-size:31px}
  .brand-title{font-size:15px}
  .brand-sub{font-size:8px;margin-top:3px}
  .ticker-value,.metric-value{font-size:13px;margin-top:5px}
  .label{font-size:8px}
  .sub{font-size:8px;margin-top:3px}
  .controls{gap:4px}
  .ctrl{height:22px;font-size:8px}
  .content{grid-template-columns:minmax(0,1fr) 380px;gap:5px}
  .left,.right,.middle,.lower,.healthintel{gap:5px}
  .left{grid-template-rows:minmax(210px,1fr) 112px 80px 58px}
  .right{grid-template-rows:minmax(176px,.78fr) minmax(146px,.62fr) 92px}
  .middle{grid-template-columns:268px minmax(0,1fr) minmax(250px,.82fr)}
  .head{height:30px;padding:0 9px}
  .title{font-size:11.5px}
  .meta{font-size:7.5px}
  .radar{grid-template-rows:30px 28px minmax(0,1fr) 22px}
  .radar-head,.radar-grid,.radar-row,.distribution{padding-left:8px;padding-right:8px}
  .radar-grid,.radar-row{grid-template-columns:60px minmax(115px,1.15fr) 55px 66px 67px 57px 67px 69px minmax(126px,1fr);gap:5px}
  .radar-grid{font-size:7.5px}
  .radar-row{min-height:26px}
  .token{font-size:9.5px}
  .small{font-size:8px}
  .state{width:50px;height:19px;font-size:7.5px}
  .tab{height:22px;padding:0 9px;font-size:8px}
  .distribution{font-size:7.5px}
  .dist-chip{padding:3px 10px}
  .flow-body,.ledger-body,.wallet-body,.edge-body,.health-body,.intel-body,.mini-body{padding:7px}
  .flow-row{margin:5px 0;font-size:8px}
  .table{font-size:8px}
  .table th{font-size:7px;padding-bottom:5px}
  .table td{padding:5px 4px}
  .mini{grid-template-rows:28px 1fr}
  .mini .head{height:28px}
  .timeline{padding:3px 7px;grid-template-rows:14px 1fr}
  .timeline-title{font-size:7.5px}
  .step{height:28px;padding:2px}
  .step b,.step small{font-size:7px}
  .step small{margin-top:2px}
  .vezir{grid-template-rows:58px 28px 1fr 34px}
  .vezir-head{grid-template-columns:48px 1fr;padding:4px 8px}
  .vezir-img{width:44px;height:44px}
  .vezir-name{font-size:16px}
  .vezir-sub{font-size:7.5px}
  .quick{padding:4px 7px}
  .quick button{font-size:7.5px}
  .chat{padding:7px}
  .bubble{padding:6px;font-size:8px;line-height:1.4}
  .chatbar{padding:5px 7px}
  .healthintel{grid-template-columns:minmax(0,1fr) minmax(0,1fr)}
  .healthintel>.panel{grid-template-rows:30px 1fr;min-width:0}
  .grid6{grid-template-columns:repeat(3,minmax(0,1fr));gap:4px;min-width:0}
  .box{padding:5px;min-height:42px;min-width:0;overflow:hidden}
  .box small{font-size:7px}
  .box b{font-size:10px}
  .edge-big{font-size:22px}
  .edge-caption{font-size:11px}
  .kv{padding:4px 0;font-size:8px}
  .footer{padding:0 8px;font-size:7.5px}
  .footer-left{gap:11px}
}

/* Short laptop viewport needs a slightly tighter vertical rhythm only. */
@media (max-height:700px) and (min-width:1220px) {
  .app{grid-template-rows:60px 1fr 29px}
  .left{grid-template-rows:minmax(205px,1fr) 108px 77px 56px}
  .right{grid-template-rows:minmax(170px,.78fr) minmax(142px,.62fr) 88px}
  .radar-row{min-height:25px}
  .flow-body,.ledger-body,.wallet-body,.edge-body,.health-body,.intel-body,.mini-body{padding:6px}
  .table td{padding:4px}
  .bubble{padding:5px}
}

@media(max-width:1219px){
  body{overflow:auto}
  .app{height:auto;min-width:0;display:block}
  .topbar,.content,.middle,.lower,.healthintel{display:grid;grid-template-columns:1fr;gap:6px}
  .topbar{grid-template-columns:repeat(2,1fr)}
  .brand,.controls{grid-column:1/-1}
  .content{margin-top:6px}
  .left,.right{display:grid;grid-template-rows:auto}
  .radar{min-height:520px}
  .timeline-track{grid-template-columns:repeat(4,1fr)}
  .footer{margin-top:6px;min-height:42px}
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

    html = html.replace(
        "shortToken(r.token0)||'POOL'",
        "r.display_name||shortToken(r.token0)||'POOL'",
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
    return enrich_universe_display_names(
        payload,
        _panel.CACHE_DB,
    )
