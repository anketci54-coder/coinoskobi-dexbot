from pathlib import Path


JS = Path("app/api/static/panel-canonical.js")
PANEL = Path("app/api/panel.py")


def test_panel_bfcache_restore_invalidates_old_refresh_generation():
    js = JS.read_text(encoding="utf-8")

    assert "snapshotGeneration:0" in js
    assert "state.snapshotGeneration+=1" in js
    assert "const generation=state.snapshotGeneration" in js
    assert "if(generation!==state.snapshotGeneration)return" in js
    assert "state.refreshing=false" not in js


def test_panel_bfcache_restore_clears_restored_modals():
    js = JS.read_text(encoding="utf-8")

    assert "function clearRestoredModals()" in js
    assert "acceptanceModal" in js
    assert "shell.classList.remove('open')" in js
    assert "clearRestoredModals();" in js
    assert "window.addEventListener('pageshow'" in js
    assert "event.persisted" in js
    assert "clearLiveSnapshot();refresh()" in js


def test_failed_refresh_sources_remain_unavailable_not_fake_empty():
    js = JS.read_text(encoding="utf-8")

    assert "state.dashboard=d.status==='fulfilled'?d.value:null" in js
    assert "state.universe=u.status==='fulfilled'?u.value:null" in js
    assert "state.watch=w.status==='fulfilled'?w.value:null" in js
    assert "state.watchSummary=ws.status==='fulfilled'?ws.value:null" in js
    assert "state.operations=o.status==='fulfilled'?o.value:null" in js
    assert "text('updatedAt',successCount===5?stamp:successCount>0?`${stamp} · KISMİ`:'VERİ YOK')" in js
    assert "Radar verisi alınamadı." in js
    assert "<tr><td colspan=\"4\">VERİ YOK</td></tr>" in js


def test_panel_document_is_served_no_store():
    source = PANEL.read_text(encoding="utf-8")

    assert '"Cache-Control"' in source
    assert '"no-store, no-cache, "' in source
    assert '"must-revalidate, max-age=0"' in source
    assert '"Pragma"' in source
    assert '"no-cache"' in source
