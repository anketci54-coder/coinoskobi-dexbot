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
  const age = value => {
    const ts = num(value);
    if (ts === null) return '—';
    const seconds = Math.max(0, Date.now() / 1000 - ts);
    if (seconds < 60) return `${Math.round(seconds)} sn`;
    if (seconds < 3600) return `${Math.round(seconds / 60)} dk`;
    return `${Math.round(seconds / 3600)} sa`;
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

  function arkhamStateText(data, holdings) {
    if (data?.provider?.configured !== true) return 'ARKHAM KAPALI · API KEY YOK';
    const state = String(holdings?.state || 'WAITING_FOR_RUNTIME');
    if (state === 'NO_SUCCESSFUL_WALLETS') return 'BAŞARILI CÜZDAN YOK';
    if (state === 'WAITING_FOR_FIRST_SCAN') return 'İLK ARKHAM TARAMASI BEKLENİYOR';
    if (state === 'WAITING_FOR_RUNTIME') return 'ARKHAM RUNTIME BEKLENİYOR';
    if (state === 'READY') return 'ARKHAM AKTİF';
    return state;
  }

  async function showWalletDetails() {
    try {
      const data = await get('/api/wallet-intelligence-v2');
      const holdings = data.arkham_holdings || {};
      const wallets = Array.isArray(holdings.wallets) ? holdings.wallets : [];
      const changes = Array.isArray(holdings.changes) ? holdings.changes : [];
      const providerText = arkhamStateText(data, holdings);

      const walletHtml = wallets.length ? wallets.map(wallet => {
        const assets = Array.isArray(wallet.holdings) ? wallet.holdings : [];
        return `
          <div style="margin-bottom:14px">
            <div class="acceptance-kpis">
              <div><small>CÜZDAN</small><b title="${esc(wallet.address)}">${esc(short(wallet.address || wallet.wallet_uid))}</b></div>
              <div><small>PORTFÖY</small><b>${money(wallet.total_value_usd)}</b></div>
              <div><small>VARLIK</small><b>${esc(wallet.asset_count ?? assets.length)}</b></div>
              <div><small>SON TARAMA</small><b>${esc(age(wallet.last_success_at || wallet.last_scan_at))}</b></div>
            </div>
            <div class="acceptance-scroll"><table class="acceptance-table">
              <thead><tr><th>VARLIK</th><th>BAKİYE</th><th>DEĞER</th><th>FİYAT</th><th>24H</th></tr></thead>
              <tbody>${assets.length ? assets.map(asset => `<tr>
                <td title="${esc(asset.token_id)}">${esc(asset.symbol || asset.name || short(asset.token_id))}</td>
                <td>${esc(asset.balance ?? '—')}</td><td>${money(asset.value_usd)}</td>
                <td>${money(asset.price_usd)}</td><td>${pct(asset.price_change_24h_pct)}</td>
              </tr>`).join('') : '<tr><td colspan="5">Henüz holdings kaydı yok.</td></tr>'}</tbody>
            </table></div>
          </div>`;
      }).join('') : `<div class="acceptance-empty">${esc(providerText)}</div>`;

      const changesHtml = changes.length ? `
        <div class="meta" style="margin:12px 0 6px">SON VARLIK DEĞİŞİMLERİ</div>
        <div class="acceptance-scroll"><table class="acceptance-table">
          <thead><tr><th>CÜZDAN</th><th>VARLIK</th><th>DEĞİŞİM</th><th>ÖNCE</th><th>ŞİMDİ</th><th>ZAMAN</th></tr></thead>
          <tbody>${changes.map(row => `<tr>
            <td title="${esc(row.wallet_uid)}">${esc(short(row.wallet_uid))}</td>
            <td title="${esc(row.token_id)}">${esc(short(row.token_id))}</td>
            <td>${esc(row.change_type || '—')}</td><td>${esc(row.previous_balance ?? '—')}</td>
            <td>${esc(row.current_balance ?? '—')}</td><td>${esc(age(row.observed_at))}</td>
          </tr>`).join('')}</tbody>
        </table></div>` : '';

      const html = `
        <div class="acceptance-kpis">
          <div><small>ARKHAM</small><b>${esc(providerText)}</b></div>
          <div><small>BAŞARILI</small><b>${esc(data.successful_wallets ?? wallets.length)}</b></div>
          <div><small>HOLDINGS CÜZDAN</small><b>${esc(wallets.length)}</b></div>
          <div><small>DEĞİŞİM</small><b>${esc(changes.length)}</b></div>
        </div>
        ${walletHtml}
        ${changesHtml}`;
      modal('CÜZDAN / BALİNA TAKİP · ARKHAM HOLDINGS', html);
    } catch (error) {
      modal('CÜZDAN / BALİNA TAKİP', `<div class="acceptance-error">${esc(error.message)}</div>`);
    }
  }

  function ensureWalletDetailButton() {
    const title = [...document.querySelectorAll('.panel .head .title')]
      .find(node => node.textContent.includes('CÜZDAN / BALİNA TAKİP'));
    const head = title?.closest('.head');
    if (!head || document.getElementById('walletDetailButton')) return;
    const button = document.createElement('button');
    button.className = 'panel-action';
    button.id = 'walletDetailButton';
    button.type = 'button';
    button.textContent = 'DETAY';
    button.addEventListener('click', showWalletDetails);
    head.appendChild(button);
  }

  async function getAccountingLedger() {
    const rows = [];
    const seen = new Set();
    let beforeId = null;

    for (;;) {
      const url = beforeId === null
        ? '/api/accounting-ledger-v2?limit=100'
        : `/api/accounting-ledger-v2?limit=100&before_id=${encodeURIComponent(beforeId)}`;
      const page = await get(url);
      const batch = Array.isArray(page.rows) ? page.rows : [];

      for (const row of batch) {
        const id = Number(row?.id);
        const key = Number.isFinite(id) ? `id:${id}` : JSON.stringify(row);
        if (!seen.has(key)) {
          seen.add(key);
          rows.push(row);
        }
      }

      const next = Number(page.next_before_id);
      if (!batch.length || !Number.isFinite(next)) break;
      if (beforeId !== null && next >= beforeId) {
        throw new Error('MUHASEBE sayfalama ilerlemedi');
      }
      beforeId = next;
    }

    return rows;
  }

  function accountingSummary(rows, dashboardSummary = {}) {
    const statuses = rows.map(row => String(row?.status || '').toUpperCase());
    const statusKnown = statuses.every(status => status === 'OPEN' || status === 'CLOSED');
    const openRows = rows.filter((_, index) => statuses[index] === 'OPEN');
    const openAmounts = openRows.map(row => num(row?.entry_amount_usdt ?? row?.amount_usdt));
    const pnlValues = rows.map(row => num(row?.net_pnl_usdt ?? row?.net_pnl));
    const openCount = statusKnown ? openRows.length : null;
    const openInvestment = statusKnown && openAmounts.every(value => value !== null)
      ? openAmounts.reduce((sum, value) => sum + value, 0)
      : null;
    const totalPnl = pnlValues.every(value => value !== null)
      ? pnlValues.reduce((sum, value) => sum + value, 0)
      : null;
    const startingCapital = num(dashboardSummary.starting_capital);
    const equity = startingCapital !== null && totalPnl !== null
      ? startingCapital + totalPnl
      : null;

    return {
      equity,
      total_pnl: totalPnl,
      open_count: openCount,
      open_investment: openInvestment
    };
  }

  async function showAccounting() {
    try {
      const [dashboard, ledger] = await Promise.all([
        get('/api/dashboard'),
        getAccountingLedger()
      ]);
      const rows = Array.isArray(ledger) ? ledger : [];
      const summary = accountingSummary(rows, dashboard.summary || {});
      const html = `
        <div class="acceptance-kpis">
          <div><small>BAKİYE</small><b>${money(summary.equity)}</b></div>
          <div><small>TOPLAM PNL</small><b>${money(summary.total_pnl)}</b></div>
          <div><small>AÇIK</small><b>${esc(summary.open_count ?? '—')}</b></div>
          <div><small>YATIRIM</small><b>${money(summary.open_investment)}</b></div>
        </div>
        <div class="acceptance-scroll"><table class="acceptance-table">
          <thead><tr><th>DURUM</th><th>TOKEN</th><th>GİRİŞ</th><th>ÇIKIŞ/SON</th><th>NET PNL</th><th>ROI</th></tr></thead>
          <tbody>${rows.length ? rows.map(r => `<tr>
            <td>${esc(String(r.status || '—').toUpperCase())}</td><td>${esc(r.symbol || short(r.token))}</td>
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
      const ageValue = num(data.latest_age_seconds);
      const ageText = ageValue === null ? 'karar yok' : ageValue < 60 ? `${Math.round(ageValue)} sn` : `${Math.round(ageValue / 60)} dk`;
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
    ensureWalletDetailButton();
    refreshAutoHealth();
    setInterval(refreshAutoHealth, 15000);
  });
})();
