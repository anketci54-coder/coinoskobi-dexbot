(() => {
  const nativeFetch = window.fetch.bind(window);
  const jsonResponse = (payload, original) => new Response(
    JSON.stringify(payload),
    {
      status: original.status,
      statusText: original.statusText,
      headers: {'Content-Type': 'application/json', 'Cache-Control': 'no-store'}
    }
  );
  const safeJson = async response => {
    try { return await response.json(); } catch (_) { return {}; }
  };
  const get = async url => {
    const response = await nativeFetch(url, {cache: 'no-store'});
    if (!response.ok) throw new Error(`${url} ${response.status}`);
    return safeJson(response);
  };

  window.fetch = async (input, init = {}) => {
    const url = typeof input === 'string' ? input : String(input?.url || input || '');

    if (url === '/api/vezir/ask') {
      return nativeFetch('/api/vezir/chat-v2', init);
    }

    if (url === '/api/dashboard') {
      const original = await nativeFetch(input, init);
      if (!original.ok) return original;
      const dashboard = await safeJson(original.clone());

      const [news, calendar, wallet] = await Promise.allSettled([
        get('/api/live-news-v2'),
        get('/api/economic-calendar-v2'),
        get('/api/wallet-intelligence-v2')
      ]);

      if (news.status === 'fulfilled' || calendar.status === 'fulfilled') {
        const newsValue = news.status === 'fulfilled' ? news.value : {};
        const calendarValue = calendar.status === 'fulfilled' ? calendar.value : {};
        dashboard.news = {
          items: Array.isArray(newsValue.items) ? newsValue.items : [],
          calendar: Array.isArray(calendarValue.items) ? calendarValue.items : [],
          source: [
            ...(Array.isArray(newsValue.sources) ? newsValue.sources.filter(x => x.available).map(x => x.source) : []),
            calendarValue.available ? 'EKONOMİK TAKVİM' : null
          ].filter(Boolean).join(' · ') || 'VERİ YOK'
        };
      }

      if (wallet.status === 'fulfilled') {
        const w = wallet.value || {};
        dashboard.intelligence = {
          ...(dashboard.intelligence || {}),
          tracked_wallets: w.tracked_wallets ?? dashboard.intelligence?.tracked_wallets ?? 0,
          active_whales: w.active_whales ?? dashboard.intelligence?.active_whales ?? 0,
          successful_wallets: w.successful_wallets ?? dashboard.intelligence?.successful_wallets ?? 0,
          summary: {
            ...(dashboard.intelligence?.summary || {}),
            wallet_details_json: JSON.stringify(Array.isArray(w.rows) ? w.rows : [])
          },
          generated_at: w.generated_at ?? null,
          stale: Boolean(w.stale)
        };
      }

      return jsonResponse(dashboard, original);
    }

    return nativeFetch(input, init);
  };

  const esc = value => String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');
  const short = value => {
    const s = String(value || '').trim();
    return s.length > 22 ? `${s.slice(0, 10)}…${s.slice(-8)}` : (s || '—');
  };
  const num = value => {
    const n = Number(value);
    return Number.isFinite(n) ? n : null;
  };
  const money = value => {
    const n = num(value);
    return n === null ? '—' : `${n < 0 ? '-' : ''}$${Math.abs(n).toLocaleString('tr-TR', {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
  };
  const pct = value => {
    const n = num(value);
    return n === null ? '—' : `${n > 0 ? '+' : ''}${n.toFixed(2)}%`;
  };

  function modal(title, bodyHtml) {
    let shell = document.getElementById('acceptanceModal');
    if (!shell) {
      shell = document.createElement('div');
      shell.id = 'acceptanceModal';
      shell.className = 'acceptance-modal';
      shell.innerHTML = '<div class="acceptance-card"><button class="acceptance-close" type="button">×</button><h3 id="acceptanceTitle"></h3><div id="acceptanceBody"></div></div>';
      document.body.appendChild(shell);
      shell.querySelector('.acceptance-close').onclick = () => shell.classList.remove('open');
      shell.onclick = event => { if (event.target === shell) shell.classList.remove('open'); };
    }
    document.getElementById('acceptanceTitle').textContent = title;
    document.getElementById('acceptanceBody').innerHTML = bodyHtml;
    shell.classList.add('open');
  }

  async function showWatchDetails() {
    try {
      const data = await get('/api/watch-probes-detail-v2?limit=100');
      const rows = Array.isArray(data.rows) ? data.rows : [];
      const html = rows.length ? `
        <div class="acceptance-scroll"><table class="acceptance-table">
          <thead><tr><th>ID</th><th>TOKEN</th><th>GİRİŞ</th><th>SON</th><th>MARK</th><th>EXIT</th><th>DURUM</th></tr></thead>
          <tbody>${rows.map(r => `<tr>
            <td>${esc(r.id)}</td><td title="${esc(r.token)}">${esc(short(r.token))}</td>
            <td>${money(r.entry_usdt)} @ ${esc(r.entry_price ?? '—')}</td>
            <td>${esc(r.last_price ?? '—')}</td><td>${pct(r.mark_return_pct)}</td>
            <td>${money(r.realizable_exit_usdt)} ${pct(r.realizable_return_pct)}</td>
            <td>${esc(r.status || '—')} · ${esc(r.exit_state || '—')}<br><span class="acceptance-muted">${esc(r.exit_reason || r.exit_quality || '—')}</span></td>
          </tr>`).join('')}</tbody>
        </table></div>` : '<div class="acceptance-empty">WATCH detay kaydı yok.</div>';
      modal(`1 USDT TEST DETAYI · ${rows.length} KAYIT`, html);
    } catch (error) {
      modal('1 USDT TEST DETAYI', `<div class="acceptance-error">${esc(error.message)}</div>`);
    }
  }

  async function showAccounting() {
    try {
      const dashboard = await get('/api/dashboard');
      const positions = Array.isArray(dashboard.positions) ? dashboard.positions : [];
      const exits = Array.isArray(dashboard.exits) ? dashboard.exits : [];
      const rows = [...positions.map(x => ({...x, _kind: 'AÇIK'})), ...exits.map(x => ({...x, _kind: 'KAPALI'}))];
      const summary = dashboard.summary || {};
      const html = `
        <div class="acceptance-kpis">
          <div><small>BAKİYE</small><b>${money(summary.equity)}</b></div>
          <div><small>TOPLAM PNL</small><b>${money(summary.total_pnl)}</b></div>
          <div><small>AÇIK</small><b>${esc(summary.open_count ?? positions.length)}</b></div>
          <div><small>YATIRIM</small><b>${money(summary.open_investment)}</b></div>
        </div>
        <div class="acceptance-scroll"><table class="acceptance-table">
          <thead><tr><th>DURUM</th><th>TOKEN</th><th>GİRİŞ</th><th>ÇIKIŞ/SON</th><th>NET PNL</th><th>ROI</th></tr></thead>
          <tbody>${rows.length ? rows.map(r => `<tr>
            <td>${esc(r._kind)}</td><td>${esc(r.symbol || short(r.token))}</td>
            <td>${esc(r.entry_price ?? '—')}</td><td>${esc(r.exit_price ?? r.current_price ?? '—')}</td>
            <td>${money(r.net_pnl_usdt ?? r.net_pnl)}</td><td>${pct(num(r.roi_pct) ?? (num(r.roi) === null ? null : num(r.roi) * 100))}</td>
          </tr>`).join('') : '<tr><td colspan="6">Muhasebe kaydı yok.</td></tr>'}</tbody>
        </table></div>`;
      modal('MUHASEBE · PAPER_10K', html);
    } catch (error) {
      modal('MUHASEBE', `<div class="acceptance-error">${esc(error.message)}</div>`);
    }
  }

  async function refreshAutoHealth() {
    const target = document.getElementById('autoTradeState');
    if (!target) return;
    try {
      const data = await get('/api/auto-trade-health-v2');
      const topReason = Array.isArray(data.reasons) && data.reasons.length ? data.reasons[0] : null;
      const age = num(data.latest_age_seconds);
      const ageText = age === null ? 'karar yok' : age < 60 ? `${Math.round(age)} sn` : `${Math.round(age / 60)} dk`;
      target.textContent = `AUTO: ${data.decision_count ?? 0} karar · ${topReason ? `${topReason.reason} (${topReason.count})` : 'blocker yok'} · son ${ageText}`;
      target.className = topReason ? 'sub warn' : 'sub';
    } catch (error) {
      target.textContent = 'AUTO DURUMU ALINAMADI';
      target.className = 'sub warn';
    }
  }

  document.addEventListener('DOMContentLoaded', () => {
    document.getElementById('watchDetailButton')?.addEventListener('click', showWatchDetails);
    document.getElementById('accountingButton')?.addEventListener('click', showAccounting);
    refreshAutoHealth();
    setInterval(refreshAutoHealth, 15000);
  });
})();
