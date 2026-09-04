from __future__ import annotations

from . import panel as _panel
from .panel_acceptance import register_panel_acceptance_routes
from .panel_display_names import enrich_universe_display_names
from .panel_manual_paper_v2 import register_manual_paper_routes_v2
from .panel_provider_health import provider_health_snapshot, register_provider_health_route
from .panel_universe import universe_panel_payload
from .panel_watch_summary import register_watch_summary_route


@_panel.app.get("/api/universe-panel")
def api_universe_panel():
    payload = universe_panel_payload(_panel.CACHE_DB)
    return enrich_universe_display_names(payload, _panel.CACHE_DB)


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
