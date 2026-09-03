(() => {
  const norm = value => String(value || '').trim().toLowerCase();

  function openPositions() {
    const rows = state?.dashboard?.positions;
    return Array.isArray(rows) ? rows : [];
  }

  function openPositionForRadar(row) {
    const pool = norm(row?.pool);
    const token0 = norm(row?.token0);
    const token1 = norm(row?.token1);

    return openPositions().find(position => {
      const positionPool = norm(position?.pool);
      const positionToken = norm(position?.token);
      const status = String(position?.status || 'OPEN').toUpperCase();

      if (status === 'CLOSED') return false;
      if (pool && positionPool && pool === positionPool) return true;
      if (!positionToken) return false;
      return positionToken === token0 || positionToken === token1;
    }) || null;
  }

  function activeRadarRows(source) {
    const rows = [];
    const used = new Set();

    for (const position of openPositions()) {
      const positionPool = norm(position?.pool);
      const positionToken = norm(position?.token);

      const match = source.find(row => {
        const rowPool = norm(row?.pool);
        const token0 = norm(row?.token0);
        const token1 = norm(row?.token1);
        return (
          (positionPool && rowPool && positionPool === rowPool) ||
          (positionToken && (positionToken === token0 || positionToken === token1))
        );
      });

      if (match) {
        const identity = norm(match.pool) || norm(match.token0) || String(position.id || '');
        if (!used.has(identity)) {
          used.add(identity);
          rows.push({...match, _activePosition: position});
        }
        continue;
      }

      const synthetic = {
        chain: 'bsc',
        dex: position?.dex || null,
        pool: position?.pool || null,
        token0: position?.token || null,
        token1: null,
        display_name: position?.symbol || null,
        state: 'ACTIVE',
        liquidity_usd: null,
        volume_24h_usd: null,
        price_usd: position?.current_price ?? position?.entry_price ?? null,
        txns_5m: null,
        change_5m_pct: null,
        snapshot_at: null,
        state_changed_at: null,
        seismic: {
          score: position?.entry_evidence?.score ?? null,
          evidence_count: null,
          reason: 'OPEN_PAPER_POSITION',
        },
        _activePosition: position,
        _activeSynthetic: true,
      };

      const identity = norm(synthetic.pool) || norm(synthetic.token0) || String(position.id || '');
      if (!used.has(identity)) {
        used.add(identity);
        rows.push(synthetic);
      }
    }

    return rows.sort((a, b) => n(b?.seismic?.score) - n(a?.seismic?.score));
  }

  function premiumUniverseRows() {
    const source = state?.universe?.available && Array.isArray(state.universe.rows)
      ? state.universe.rows
      : [];

    if (state.filter === 'ACTIVE') {
      return activeRadarRows(source);
    }

    return source
      .filter(row => finite(row?.seismic?.score) && n(row.seismic.score) > 0)
      .filter(row => state.filter === 'ALL' || String(row.state || '').toUpperCase() === state.filter)
      .sort((a, b) => n(b?.seismic?.score) - n(a?.seismic?.score));
  }

  function premiumSetMode(mode) {
    state.operatingMode = mode === 'MANUAL' ? 'MANUAL' : 'AUTO';

    const autoButton = el('autoModeButton');
    const manualButton = el('manualModeButton');
    if (autoButton) autoButton.classList.toggle('active', state.operatingMode === 'AUTO');
    if (manualButton) manualButton.classList.toggle('active', state.operatingMode === 'MANUAL');

    document.body.classList.toggle('manual-mode', state.operatingMode === 'MANUAL');
    state.pendingManual = null;

    const notice = el('manualNotice');
    if (notice) notice.classList.remove('open');

    premiumRenderRadar();
  }

  function premiumPrepareManualAction(side, row) {
    if (state.operatingMode !== 'MANUAL') return;

    const position = openPositionForRadar(row) || row?._activePosition || null;
    const normalizedSide = position ? 'SELL' : 'BUY';
    if (side && side !== normalizedSide) return;

    state.pendingManual = {
      side: normalizedSide,
      pool: row?.pool || position?.pool || null,
      token: row?.token0 || position?.token || null,
      position_id: position?.id || null,
    };

    const notice = el('manualNotice');
    if (!notice) return;

    const tokenLabel = shortToken(row?.display_name || row?.token0 || position?.symbol || position?.token);
    const actionLabel = normalizedSide === 'BUY' ? 'AL' : 'SAT';
    const positionLabel = position?.id ? ` · POZİSYON #${position.id}` : '';

    notice.textContent = (
      `MANUEL ${actionLabel} HAZIRLIĞI · ${tokenLabel}${positionLabel} · ` +
      'execution/signing authority kapalı; emir gönderilmedi.'
    );
    notice.classList.add('open');
  }

  function rowStateClass(row, position) {
    if (position || row?._activePosition) return 'active';
    const stateName = String(row?.state || '').toLowerCase();
    return ['cold', 'warm', 'hot'].includes(stateName) ? stateName : 'active';
  }

  function rowStateLabel(row, position) {
    if (row?._activeSynthetic) return 'AKTİF';
    return String(row?.state || (position ? 'ACTIVE' : '—')).toUpperCase();
  }

  function actionHtml(row, position) {
    if (state.operatingMode !== 'MANUAL') return '';

    const side = position ? 'SELL' : 'BUY';
    const label = side === 'BUY' ? 'AL' : 'SAT';
    const className = side === 'BUY' ? 'buy' : 'sell';

    return (
      `<span class="trade-actions">` +
      `<button class="trade-btn ${className}" type="button" data-side="${side}">${label}</button>` +
      `</span>`
    );
  }

  function premiumRenderRadar() {
    const body = el('radarBody');
    if (!body) return;
    body.innerHTML = '';

    if (!state?.universe?.available && state.filter !== 'ACTIVE') {
      text('candidateCount', 'FEED YOK');
      body.innerHTML = '<div class="empty" style="padding:18px">Radar score feed kullanılamıyor · sahte aday gösterilmiyor</div>';
      updateActiveTab();
      return;
    }

    const rows = premiumUniverseRows();
    const activeCount = openPositions().length;
    text(
      'candidateCount',
      state.filter === 'ACTIVE'
        ? `${activeCount} AÇIK POZİSYON`
        : `${rows.length} HAREKETLİ`
    );

    if (!rows.length) {
      body.innerHTML = (
        state.filter === 'ACTIVE'
          ? '<div class="empty" style="padding:18px">Açık paper pozisyon yok</div>'
          : '<div class="empty" style="padding:18px">Bu filtrede score > 0 hareketli pool yok</div>'
      );
      updateActiveTab();
      return;
    }

    for (const radarItem of rows) {
      const seismic = radarItem.seismic || {};
      const position = openPositionForRadar(radarItem) || radarItem._activePosition || null;
      const stateClass = rowStateClass(radarItem, position);
      const stateLabel = rowStateLabel(radarItem, position);
      const row = document.createElement('div');
      row.className = 'radar-row' + (state.selected?.pool === radarItem.pool ? ' selected' : '') + (position ? ' has-position' : '');

      const display = radarItem.display_name || shortToken(radarItem.token0) || position?.symbol || 'POOL';
      const poolLabel = shortToken(radarItem.pool || position?.pool);
      const positionBadge = position ? '<span class="position-badge">AKTİF</span>' : '';

      row.innerHTML = `
        <span class="state ${escapeHtml(stateClass)}">${escapeHtml(stateLabel)}</span>
        <span class="token-cell">
          <span>
            <div class="token-line"><div class="token">${escapeHtml(display)}</div>${positionBadge}</div>
            <div class="small">${escapeHtml(poolLabel)}</div>
          </span>
          ${actionHtml(radarItem, position)}
        </span>
        <span class="small score-cell ${finite(seismic.score) && n(seismic.score) > 0 ? 'pos' : ''}">${score(seismic.score)}</span>
        <span class="small volume-cell">${compact(radarItem.volume_24h_usd)}</span>
        <span class="small price-cell">${price(radarItem.price_usd ?? position?.current_price)}</span>
        <span class="small change-cell ${cls(radarItem.change_5m_pct)}">${pct(radarItem.change_5m_pct)}</span>
        <span class="small liquidity-cell">${compact(radarItem.liquidity_usd)}</span>
      `;

      row.onclick = () => {
        state.selected = {pool: radarItem.pool, row: radarItem};
        premiumRenderRadar();
      };

      const button = row.querySelector('.trade-btn');
      if (button) {
        button.onclick = event => {
          event.stopPropagation();
          premiumPrepareManualAction(button.dataset.side, radarItem);
        };
      }

      body.appendChild(row);
    }

    updateActiveTab();
  }

  function ensureActiveTab() {
    const tabs = document.querySelector('.radar-head .tabs');
    if (!tabs || tabs.querySelector('[data-filter="ACTIVE"]')) return;

    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'tab active-position-tab';
    button.dataset.filter = 'ACTIVE';
    button.textContent = 'AKTİF';

    button.addEventListener('click', () => {
      state.filter = 'ACTIVE';
      document.querySelectorAll('[data-filter]').forEach(item => {
        item.classList.toggle('active', item === button);
      });
      state.selected = null;
      premiumRenderRadar();
    });

    tabs.appendChild(button);
  }

  function updateActiveTab() {
    const button = document.querySelector('[data-filter="ACTIVE"]');
    if (!button) return;
    const count = openPositions().length;
    button.textContent = count > 0 ? `AKTİF ${count}` : 'AKTİF';
  }

  function premiumRenderNews() {
    const payload = state?.dashboard?.news || {};
    const items = Array.isArray(payload.items) ? payload.items : [];
    const calendar = Array.isArray(payload.calendar) ? payload.calendar : [];
    const count = items.length;
    const title = el('newsTitle');

    if (title) {
      title.textContent = `HABER AKIŞI (${count})`;
      if (state.lastNewsCount !== null && count > state.lastNewsCount) title.classList.add('news-title-new');
      else title.classList.remove('news-title-new');
    }

    state.lastNewsCount = count;
    text('newsMeta', payload.source || 'BAĞLI DEĞİL');

    const newsStream = el('newsStream');
    if (newsStream) {
      newsStream.classList.remove('empty');
      newsStream.innerHTML = items.length
        ? items.map(item => (
          `<div class="news-item ${item.is_new ? 'new' : ''}">` +
          `<span class="news-time">${escapeHtml(String(item.timestamp || '').slice(11,16))}</span>` +
          `${escapeHtml(item.title || item.text || '—')}</div>`
        )).join('')
        : '<div class="news-empty-card">Gerçek haber sağlayıcısı henüz panel backend’ine bağlı değil. Sahte haber gösterilmiyor.</div>';
    }

    const calendarStream = el('calendarStream');
    if (calendarStream) {
      calendarStream.classList.remove('empty');
      calendarStream.innerHTML = calendar.length
        ? calendar.map(item => (
          `<div class="news-item">` +
          `<span class="news-time">${escapeHtml(String(item.timestamp || '').slice(11,16))}</span>` +
          `${escapeHtml(item.title || item.text || '—')}</div>`
        )).join('')
        : '<div class="news-empty-card">Gerçek ekonomik takvim kaynağı henüz bağlı değil. Sahte etkinlik gösterilmiyor.</div>';
    }
  }

  function parseFreshness(value) {
    if (value === null || value === undefined || value === '') return null;
    let timestamp = Number(value);
    if (!Number.isFinite(timestamp)) {
      const parsed = Date.parse(String(value));
      if (!Number.isFinite(parsed)) return null;
      timestamp = parsed / 1000;
    }
    if (timestamp > 10_000_000_000) timestamp /= 1000;
    return timestamp > 0 ? timestamp : null;
  }

  function radarAgeLabel() {
    const rows = Array.isArray(state?.universe?.rows) ? state.universe.rows : [];
    const timestamps = rows
      .map(row => parseFreshness(row.snapshot_at ?? row?.seismic?.observed_at))
      .filter(value => Number.isFinite(value));

    if (!timestamps.length) return 'veri yaşı bilinmiyor';
    const latest = Math.max(...timestamps);
    const ageSeconds = Math.max(0, Date.now() / 1000 - latest);

    if (ageSeconds < 90) return 'radar güncel';
    if (ageSeconds < 3600) return `radar ${Math.floor(ageSeconds / 60)} dk önce`;
    return `radar ${Math.floor(ageSeconds / 3600)} sa önce`;
  }

  function systemTone(stateName) {
    const value = String(stateName || '').toUpperCase();
    if (value === 'HEALTHY') return 'pos';
    if (value === 'DEGRADED') return 'warn';
    return 'ghost';
  }

  async function premiumRefreshOperations() {
    const bubble = el('vezirLiveSummary');
    if (!bubble) return;

    try {
      const response = await fetch('/api/operations-summary', {cache: 'no-store'});
      if (!response.ok) throw new Error('operations');
      const data = await response.json();
      const system = data.system || {};
      const paper = data.paper || {};
      const reason = data.main_reason || null;
      const moving = premiumUniverseRows().filter(row => !row._activeSynthetic).length;
      const active = openPositions().length;
      const reasonText = reason?.label
        ? `${reason.label}${Number(reason.count || 0) > 0 ? ` · ${Number(reason.count).toLocaleString('tr-TR')} karar` : ''}`
        : 'Son 6 saatte baskın karar nedeni yok';

      const signature = JSON.stringify([
        system.state,
        paper.open,
        reason?.label,
        reason?.count,
        moving,
        active,
        radarAgeLabel(),
      ]);

      if (state.premiumOpsSignature === signature) return;
      state.premiumOpsSignature = signature;

      bubble.innerHTML = `
        <div class="vezir-status-grid">
          <div class="vezir-status-card"><small>SİSTEM</small><b class="${systemTone(system.state)}">${escapeHtml(system.label || 'Bilinmiyor')}</b></div>
          <div class="vezir-status-card"><small>PAPER</small><b>${active} açık pozisyon</b></div>
          <div class="vezir-status-card"><small>RADAR</small><b>${moving} hareketli pool</b></div>
          <div class="vezir-status-card"><small>TAZELİK</small><b>${escapeHtml(radarAgeLabel())}</b></div>
        </div>
        <div class="vezir-status-reason"><b>ŞU AN NEDEN İŞLEM YOK?</b><br>${escapeHtml(reasonText)}</div>
      `;
    } catch (error) {
      bubble.textContent = 'Gerçek operasyon özeti şu anda okunamıyor. Sahte durum üretilmiyor.';
    }
  }

  function installVezirStatus() {
    const legacy = el('vezirSummary');
    if (!legacy) return;
    legacy.id = 'vezirLiveSummary';
    legacy.textContent = 'Gerçek operasyon durumu yükleniyor…';
  }

  function install() {
    document.documentElement.classList.add('panel-premium-v2');
    ensureActiveTab();
    installVezirStatus();

    universeRows = premiumUniverseRows;
    renderRadar = premiumRenderRadar;
    setMode = premiumSetMode;
    prepareManualAction = premiumPrepareManualAction;
    renderNews = premiumRenderNews;

    premiumSetMode(state.operatingMode || 'AUTO');
    premiumRenderNews();
    premiumRefreshOperations();

    setInterval(() => {
      if (document.visibilityState === 'visible') premiumRefreshOperations();
    }, 5000);

    window.addEventListener('focus', premiumRefreshOperations);
    document.addEventListener('visibilitychange', () => {
      if (document.visibilityState === 'visible') premiumRefreshOperations();
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', install, {once: true});
  } else {
    install();
  }
})();
