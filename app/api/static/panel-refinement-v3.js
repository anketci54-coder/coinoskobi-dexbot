(() => {
  window.__COINOSKOBI_REFINEMENT_V3_OWNS_INTEL = true;
  const $ = id => document.getElementById(id);
  const esc = value => String(value ?? '')
    .replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;').replaceAll("'", '&#039;');
  const num = value => { const n = Number(value); return Number.isFinite(n) ? n : null; };
  const money = value => { const n = num(value); return n === null ? '—' : `${n < 0 ? '-' : ''}$${Math.abs(n).toLocaleString('tr-TR',{minimumFractionDigits:2,maximumFractionDigits:2})}`; };
  const pct = value => { const n = num(value); return n === null ? '—' : `${n > 0 ? '+' : ''}${n.toFixed(2)}%`; };
  const short = value => { const s = String(value || '').trim(); return !s ? '—' : s.length > 20 ? `${s.slice(0,9)}…${s.slice(-7)}` : s; };
  const get = async url => {
    const response = await fetch(url, {cache:'no-store'});
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || `${url} ${response.status}`);
    return data;
  };

  let marketCache = null;
  let calendarCache = null;
  let walletCache = null;
  let rendering = false;

  function openModal(title, bodyHtml) {
    let shell = $('acceptanceModal');
    if (!shell) {
      shell = document.createElement('div');
      shell.id = 'acceptanceModal';
      shell.className = 'acceptance-modal';
      shell.innerHTML = '<div class="acceptance-card"><button class="acceptance-close" type="button">×</button><h3 id="acceptanceTitle"></h3><div id="acceptanceBody"></div></div>';
      document.body.appendChild(shell);
      shell.querySelector('.acceptance-close').onclick = () => shell.classList.remove('open');
      shell.onclick = event => { if (event.target === shell) shell.classList.remove('open'); };
    }
    $('acceptanceTitle').textContent = title;
    $('acceptanceBody').innerHTML = bodyHtml;
    shell.classList.add('open');
  }

  function stateClass(value) {
    const state = String(value || 'COLD').toLowerCase();
    return ['cold','warm','hot'].includes(state) ? state : 'cold';
  }

  function renderIntelRows(targetId, rows, emptyText) {
    const target = $(targetId);
    if (!target) return;
    rendering = true;
    try {
      const html = rows.length ? rows.map((row, index) => `
        <div class="intel-item">
          <span class="intel-state ${stateClass(row.state)}">${esc(row.state)}</span>
          <span class="intel-main">
            <div class="intel-title">${esc(row.title_tr || 'PİYASA')}</div>
            <div class="intel-summary">${esc(row.summary_tr || 'Detay için aç.')}</div>
          </span>
          <span class="intel-score">${esc(row.importance_score ?? '—')}</span>
          <button class="intel-detail" type="button" data-detail-index="${index}" data-detail-target="${targetId}">DETAY</button>
        </div>`).join('') : `<div class="news-empty">${esc(emptyText)}</div>`;
      if (target.innerHTML !== html) {
        target.innerHTML = html;
      }
    } finally {
      setTimeout(() => {
        rendering = false;
      }, 0);
    }
  }

  function renderMarket() {
    const news = Array.isArray(marketCache?.items) ? marketCache.items : [];
    const launches = Array.isArray(marketCache?.launch_items) ? marketCache.launch_items : [];
    const calendar = Array.isArray(calendarCache?.items) ? calendarCache.items : [];
    renderIntelRows('newsStream', news, 'Şu anda önem filtresini geçen güncel piyasa haberi yok.');
    renderIntelRows('calendarStream', calendar, 'Şu anda WARM/HOT ekonomik takvim olayı yok.');
    renderIntelRows('launchStream', launches, 'Şu anda doğrulanmış Airdrop / IDO / ICO / TGE / Listing başlığı yok.');
    if ($('newsTitle')) $('newsTitle').textContent = `PİYASA HABERLERİ · ${news.length}`;
    if ($('newsMeta')) $('newsMeta').textContent = launches.length ? `${launches.length} DROP/LANSMAN` : 'ÖNEME GÖRE';
  }

  function detailRow(targetId, index) {
    const source = targetId === 'calendarStream'
      ? (calendarCache?.items || [])
      : targetId === 'launchStream'
        ? (marketCache?.launch_items || [])
        : (marketCache?.items || []);

    const row = source[index];

    if (!row) return;

    const sourceLine = row.source
      ? `<div class="acceptance-muted" style="margin-top:8px">KAYNAK: ${esc(row.source)}</div>`
      : '';

    const dateLine = row.date || row.published_at
      ? `<div class="acceptance-muted" style="margin-top:5px">ZAMAN: ${esc(row.date || row.published_at)}</div>`
      : '';

    const originalTitle = row.source_title
      ? `<div class="mini" style="margin-top:8px">
           <small>ORİJİNAL KAYNAK BAŞLIĞI</small>
           <b style="white-space:normal;line-height:1.45">${esc(row.source_title)}</b>
         </div>`
      : '';

    const sourceUrl = String(
      row.url || ''
    ).trim();

    const sourceLink =
      /^https?:\/\//i.test(sourceUrl)
        ? `<div style="margin-top:10px"><a href="${esc(sourceUrl)}" target="_blank" rel="noopener noreferrer" style="color:var(--cyan);font-weight:900;text-decoration:none">KAYNAĞI AÇ ↗</a></div>`
        : '';

    openModal(
      `${row.state || 'COLD'} · ÖNEM ${row.importance_score ?? '—'}/100`,
      `<div class="mini">
         <small>OLAY</small>
         <b>${esc(row.title_tr || 'PİYASA')}</b>
       </div>

       <div class="mini" style="margin-top:8px">
         <small>BİZİM PİYASAYA ETKİ ALANI</small>
         <b>${esc(row.market_scope_tr || 'GENEL KRİPTO')}</b>
       </div>

       <div class="mini" style="margin-top:8px">
         <small>OLASI ETKİ</small>
         <b style="white-space:normal;line-height:1.45">${esc(row.summary_tr || '—')}</b>
       </div>

       <div class="mini" style="margin-top:8px">
         <small>NE YAPMALI?</small>
         <b style="white-space:normal;line-height:1.45">${esc(row.recommendation_tr || 'Teyit bekle; haberi tek başına işlem sinyali olarak kullanma.')}</b>
       </div>

       ${originalTitle}
       ${sourceLine}
       ${dateLine}
       ${sourceLink}`
    );
  }

  async function refreshMarket() {
    try {
      const [market, calendar] = await Promise.allSettled([
        get('/api/market-brief-v3'),
        get('/api/calendar-brief-v3')
      ]);
      if (market.status === 'fulfilled') marketCache = market.value;
      if (calendar.status === 'fulfilled') calendarCache = calendar.value;
      renderMarket();
    } catch (_) {}
  }

  function ageText(seconds) {
    const value = num(seconds);
    if (value === null) return '—';
    if (value < 60) return `${Math.round(value)} sn`;
    if (value < 3600) return `${Math.round(value / 60)} dk`;
    return `${Math.round(value / 3600)} sa`;
  }

  function renderWallet() {
    const data = walletCache || {};
    if ($('walletCount')) $('walletCount').textContent = String(data.candidates ?? 0);
    if ($('successCount')) $('successCount').textContent = String(data.successful ?? 0);
    if ($('whaleCount')) $('whaleCount').textContent = String(data.holdings_wallets ?? 0);
    const body = $('walletRows');
    if (!body) return;
    const rows = Array.isArray(data.rows) ? data.rows : [];
    rendering = true;
    try {
      body.innerHTML = rows.length ? rows.map(row => `<tr>
        <td title="${esc(row.wallet_uid)}">${esc(short(row.wallet_uid))}</td>
        <td>${esc(String(row.source || row.provider || '—').replaceAll('_',' '))}</td>
        <td>${esc(row.candidate_state || 'OBSERVED')} · ${esc(ageText(row.age_seconds))}</td>
      </tr>`).join('') : '<tr><td colspan="3">Güncel aday cüzdan kaydı yok.</td></tr>';
    } finally {
      setTimeout(() => {
        rendering = false;
      }, 0);
    }
  }

  async function refreshWallet() {
    try {
      walletCache = await get('/api/wallet-brief-v3');
      renderWallet();
    } catch (_) {}
  }

  async function showWalletDetail() {
    try {
      const data = await get(
        '/api/wallet-intelligence-v2'
      );

      const holdings =
        data.arkham_holdings || {};

      const wallets =
        Array.isArray(holdings.wallets)
          ? holdings.wallets
          : [];

      const changes =
        Array.isArray(holdings.changes)
          ? holdings.changes
          : [];

      const candidates =
        Array.isArray(data.rows)
          ? data.rows
          : [];

      const candidateRows =
        candidates.length
          ? candidates.map(row => {
              const source = String(
                row.discovery_source
                || row.source
                || 'GÖZLEM'
              ).toUpperCase();

              const reason =
                source === 'TRANSACTION_FROM_ONLY'
                  ? 'BSC işlem akışında gönderen cüzdan olarak gözlendi'
                  : source.replaceAll('_',' ');

              const success =
                String(
                  row.success_state
                  || 'UNKNOWN'
                ).toUpperCase();

              const sample =
                row.success_sample_depth
                ?? '—';

              const whale =
                String(
                  row.whale_state
                  || 'UNKNOWN'
                ).toUpperCase();

              const direction =
                String(
                  row.whale_direction
                  || 'UNKNOWN'
                ).toUpperCase();

              return `<tr>
                <td title="${esc(row.wallet_uid)}">${esc(short(row.wallet_uid))}</td>
                <td>${esc(reason)}</td>
                <td>${esc(success)} · örnek ${esc(sample)}</td>
                <td>${esc(whale)} · ${esc(direction)}</td>
              </tr>`;
            }).join('')
          : '<tr><td colspan="4">Aday cüzdan ayrıntısı henüz oluşmadı.</td></tr>';

      const html = `
        <div class="acceptance-kpis">
          <div>
            <small>ADAY CÜZDAN</small>
            <b>${esc(walletCache?.candidates ?? data.tracked_wallets ?? '—')}</b>
          </div>
          <div>
            <small>BAŞARILI</small>
            <b>${esc(walletCache?.successful ?? data.successful_wallets ?? '—')}</b>
          </div>
          <div>
            <small>HOLDINGS</small>
            <b>${esc(wallets.length)}</b>
          </div>
          <div>
            <small>DEĞİŞİM</small>
            <b>${esc(changes.length)}</b>
          </div>
        </div>

        <div class="acceptance-muted" style="margin:10px 0">
          ADAY CÜZDAN sayısı bir başarı skoru değildir.
          Sistem tarafından izlemeye alınmış farklı cüzdanların sayısıdır.
          Aşağıda neden aday oldukları ve başarı/balina durumu gösterilir.
        </div>

        <div class="meta" style="margin:8px 0 5px">
          ADAYLAR · NEDEN İZLENİYOR?
        </div>

        <div class="acceptance-scroll" style="max-height:230px">
          <table class="acceptance-table">
            <thead>
              <tr>
                <th>CÜZDAN</th>
                <th>NEDEN ADAY?</th>
                <th>BAŞARI</th>
                <th>BALİNA / YÖN</th>
              </tr>
            </thead>
            <tbody>${candidateRows}</tbody>
          </table>
        </div>

        <div class="meta" style="margin:14px 0 5px">
          DOĞRULANMIŞ HOLDINGS
        </div>

        <div class="acceptance-scroll">
          <table class="acceptance-table">
            <thead>
              <tr>
                <th>CÜZDAN</th>
                <th>PORTFÖY</th>
                <th>VARLIK</th>
                <th>SON TARAMA</th>
              </tr>
            </thead>
            <tbody>
              ${
                wallets.length
                  ? wallets.map(wallet => `<tr>
                      <td title="${esc(wallet.address || wallet.wallet_uid)}">${esc(short(wallet.address || wallet.wallet_uid))}</td>
                      <td>${money(wallet.total_value_usd)}</td>
                      <td>${esc(wallet.asset_count ?? 0)}</td>
                      <td>${esc(
                        ageText(
                          num(wallet.last_success_at) === null
                            ? null
                            : Date.now()/1000 - num(wallet.last_success_at)
                        )
                      )}</td>
                    </tr>`).join('')
                  : '<tr><td colspan="4">Henüz başarılı cüzdan holdings kaydı yok.</td></tr>'
              }
            </tbody>
          </table>
        </div>`;

      openModal(
        'CÜZDAN / BALİNA TAKİP',
        html
      );

    } catch (error) {
      openModal(
        'CÜZDAN / BALİNA TAKİP',
        `<div class="acceptance-error">${esc(error.message)}</div>`
      );
    }
  }

  function watchStatus(row) {
    const status = String(row?.status || '').toUpperCase();
    if (status === 'CLOSED' || row?.closed_at) return 'KAPANDI';
    return 'AÇIK';
  }

  async function showAccountingRefined() {
    try {
      const [dashboard, ledger, watch] = await Promise.all([
        get('/api/dashboard'),
        get('/api/accounting-ledger-v2?limit=100'),
        get('/api/watch-probes-detail-v2?limit=100')
      ]);
      const rows = Array.isArray(ledger.rows) ? ledger.rows : [];
      const watchRows = Array.isArray(watch.rows) ? watch.rows : [];
      const summary = dashboard.summary || {};
      const watchOpen = watchRows.filter(row => watchStatus(row) === 'AÇIK').length;
      const watchClosed = watchRows.filter(row => watchStatus(row) === 'KAPANDI').length;
      const html = `
        <div class="acceptance-kpis">
          <div><small>BAKİYE</small><b>${money(summary.equity)}</b></div>
          <div><small>TOPLAM PNL</small><b>${money(summary.total_pnl)}</b></div>
          <div><small>AÇIK PAPER</small><b>${esc(summary.open_count ?? 0)}</b></div>
          <div><small>1 USDT TEST</small><b>${esc(watchOpen)} AÇIK · ${esc(watchClosed)} KAPANDI</b></div>
        </div>
        <div class="meta" style="margin:8px 0 5px">PAPER İŞLEMLER</div>
        <div class="acceptance-scroll" style="max-height:230px"><table class="acceptance-table">
          <thead><tr><th>DURUM</th><th>TOKEN</th><th>GİRİŞ</th><th>ÇIKIŞ/SON</th><th>NET PNL</th><th>ROI</th></tr></thead>
          <tbody>${rows.length ? rows.map(row => `<tr>
            <td>${esc(String(row.status || '—').toUpperCase())}</td><td>${esc(row.symbol || short(row.token))}</td>
            <td>${esc(row.entry_price ?? '—')}</td><td>${esc(row.exit_price ?? row.current_price ?? '—')}</td>
            <td>${money(row.net_pnl_usdt ?? row.net_pnl)}</td><td>${pct(num(row.roi_pct) ?? (num(row.roi) === null ? null : num(row.roi)*100))}</td>
          </tr>`).join('') : '<tr><td colspan="6">Paper işlem kaydı yok.</td></tr>'}</tbody>
        </table></div>
        <div class="meta" style="margin:14px 0 5px">1 USDT TESTLER</div>
        <div class="acceptance-scroll" style="max-height:230px"><table class="acceptance-table">
          <thead><tr><th>DURUM</th><th>TOKEN</th><th>GİRİŞ</th><th>SON</th><th>MARK</th><th>REALİZE ÇIKIŞ</th></tr></thead>
          <tbody>${watchRows.length ? watchRows.map(row => `<tr>
            <td>${watchStatus(row)}</td><td title="${esc(row.token)}">${esc(short(row.token))}</td>
            <td>${money(row.entry_usdt)} @ ${esc(row.entry_price ?? '—')}</td><td>${esc(row.last_price ?? '—')}</td>
            <td>${pct(row.mark_return_pct)}</td><td>${money(row.realizable_exit_usdt)} ${pct(row.realizable_return_pct)}</td>
          </tr>`).join('') : '<tr><td colspan="6">1 USDT test kaydı yok.</td></tr>'}</tbody>
        </table></div>`;
      openModal('MUHASEBE', html);
    } catch (error) {
      openModal('MUHASEBE', `<div class="acceptance-error">${esc(error.message)}</div>`);
    }
  }

  async function refreshProviderState() {
    try {
      const data = await get('/api/provider-health-v2');
      const system = $('systemState');
      const provider = $('providerState');
      if (!system || !provider) return;
      if (data.state === 'HEALTHY') {
        system.textContent = 'SİSTEM ÇALIŞIYOR';
        system.className = 'sub pos';
      } else if (data.state === 'DEGRADED') {
        system.textContent = 'RPC FALLBACK DEVREDE';
        system.className = 'sub warn';
      } else {
        system.textContent = 'RPC ERİŞİMİ YOK';
        system.className = 'sub neg';
      }
      provider.textContent = data.label || 'Provider durumu bilinmiyor';
    } catch (_) {}
  }

  function bindTabs() {
    document.querySelectorAll('[data-intel]').forEach(button => {
      button.addEventListener('click', () => {
        document.querySelectorAll('[data-intel]').forEach(node => node.classList.toggle('active', node === button));
        const target = button.dataset.intel;
        $('newsPane')?.classList.toggle('active', target === 'NEWS');
        $('calendarPane')?.classList.toggle('active', target === 'CALENDAR');
        $('launchPane')?.classList.toggle('active', target === 'LAUNCH');
      });
    });
  }

  function bindDetails() {
    document.addEventListener('click', event => {
      const button = event.target.closest('[data-detail-index]');
      if (!button) return;
      detailRow(button.dataset.detailTarget, Number(button.dataset.detailIndex));
    });
  }



  document.addEventListener('DOMContentLoaded', () => {
    bindTabs();
    bindDetails();

    $('walletDetailButton')?.addEventListener('click', event => {
      event.stopImmediatePropagation();
      showWalletDetail();
    }, true);
    $('accountingButton')?.addEventListener('click', event => {
      event.stopImmediatePropagation();
      showAccountingRefined();
    }, true);

    refreshMarket();
    refreshWallet();
    refreshProviderState();
    setInterval(refreshMarket, 30000);
    setInterval(refreshWallet, 15000);
    setInterval(refreshProviderState, 30000);
  });
})();
