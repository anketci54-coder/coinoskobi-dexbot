(() => {
  'use strict';

  const n = value => {
    const x = Number(value);
    return Number.isFinite(x) ? x : null;
  };
  const esc = value => String(value ?? '')
    .replaceAll('&','&amp;')
    .replaceAll('<','&lt;')
    .replaceAll('>','&gt;')
    .replaceAll('"','&quot;')
    .replaceAll("'",'&#039;');
  const money = value => {
    const x = n(value);
    if (x === null) return '—';
    return `${x < 0 ? '-' : ''}$${Math.abs(x).toLocaleString('tr-TR',{minimumFractionDigits:2,maximumFractionDigits:2})}`;
  };
  const price = value => {
    const x = n(value);
    if (x === null) return '—';
    return x.toLocaleString('tr-TR',{maximumFractionDigits:x < 1 ? 10 : 4});
  };
  const pct = value => {
    const x = n(value);
    if (x === null) return '—';
    return `${x > 0 ? '+' : ''}${x.toFixed(2)}%`;
  };
  const short = value => {
    const text = String(value || '').trim();
    return !text ? '—' : text.length > 20 ? `${text.slice(0,9)}…${text.slice(-7)}` : text;
  };
  const get = async url => {
    const response = await fetch(url,{cache:'no-store'});
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || `${url} ${response.status}`);
    return data;
  };

  function openPositions(dashboard){
    return (Array.isArray(dashboard?.positions) ? dashboard.positions : [])
      .filter(row => String(row?.status || 'OPEN').toUpperCase() !== 'CLOSED');
  }

  function marksById(marks){
    const map = new Map();
    (Array.isArray(marks?.rows) ? marks.rows : []).forEach(row => {
      if (row?.id !== null && row?.id !== undefined) map.set(Number(row.id),row);
    });
    return map;
  }

  function markRow(row, markMap){
    const live = markMap?.get(Number(row?.id)) || null;
    if (live) {
      return {
        current:n(live.mark_price_usd),
        markValue:n(live.mark_value_usdt),
        markPnl:n(live.estimated_exit_net_pnl_usdt ?? live.mark_gross_pnl_usdt),
        markRoi:n(live.estimated_exit_roi_pct),
        source:String(live.mark_price_source || '—'),
        age:n(live.mark_price_age_seconds),
        fresh:Boolean(live.mark_price_fresh)
      };
    }
    const tokens = n(row?.token_amount);
    const current = n(row?.current_price ?? row?.entry_price);
    const entryAmount = n(row?.entry_amount_usdt);
    const markValue = tokens !== null && current !== null ? tokens * current : null;
    const markPnl = markValue !== null && entryAmount !== null ? markValue - entryAmount : null;
    const markRoi = markPnl !== null && entryAmount && entryAmount > 0 ? markPnl / entryAmount * 100 : null;
    return {current,markValue,markPnl,markRoi,source:'PAPER_DB',age:null,fresh:false};
  }

  function sumKnown(rows, getter){
    let total = 0;
    let known = 0;
    rows.forEach(row => {
      const value = n(getter(row));
      if (value !== null) {
        total += value;
        known += 1;
      }
    });
    return {total,known};
  }

  function ensureModal(){
    let modal = document.getElementById('premiumAccountingModal');
    if (modal) return modal;
    modal = document.createElement('div');
    modal.id = 'premiumAccountingModal';
    modal.className = 'premium-accounting-modal';
    modal.innerHTML = `
      <div class="premium-accounting-shell">
        <button class="premium-accounting-close" type="button" aria-label="Kapat">×</button>
        <div id="premiumAccountingBody"></div>
      </div>`;
    document.body.appendChild(modal);
    modal.querySelector('.premium-accounting-close').addEventListener('click',() => modal.classList.remove('open'));
    modal.addEventListener('click',event => { if (event.target === modal) modal.classList.remove('open'); });
    return modal;
  }

  function portfolioComment(open, summary){
    if (!open.length) return 'Açık paper pozisyon yok. Yeni işlem öncesi radar ve veri kalitesini izleyebilirsin.';
    const investment = n(summary?.open_investment) || open.reduce((a,row) => a + (n(row.entry_amount_usdt) || 0),0);
    const sorted = open
      .map(row => ({row,value:n(row.entry_amount_usdt) || 0}))
      .sort((a,b) => b.value - a.value);
    const top = sorted.slice(0,2).reduce((a,item) => a + item.value,0);
    const concentration = investment > 0 ? top / investment * 100 : null;
    if (concentration !== null && concentration >= 65) {
      return `Açık yatırımın yaklaşık %${concentration.toFixed(1)} kadarı en büyük iki pozisyonda. Yeni alımdan önce yoğunlaşma riskini azaltmayı değerlendir.`;
    }
    return `${open.length} açık paper pozisyon var. Maruziyet dağılmış durumda; yeni işlemden önce mevcut mark PNL ve kısa fiyat hareketini birlikte izle.`;
  }

  function exposureRows(open){
    const total = open.reduce((a,row) => a + (n(row.entry_amount_usdt) || 0),0);
    return open
      .map(row => ({
        name:row.symbol || short(row.token),
        value:n(row.entry_amount_usdt) || 0,
        share:total > 0 ? (n(row.entry_amount_usdt) || 0) / total * 100 : 0
      }))
      .sort((a,b) => b.value - a.value)
      .slice(0,6);
  }

  function accountingHtml(dashboard, ledger, watch, marks, mode){
    const summary = dashboard?.summary || {};
    const markSummary = marks?.summary || {};
    const open = openPositions(dashboard);
    const markMap = marksById(marks);
    const ledgerRows = Array.isArray(ledger?.rows) ? ledger.rows : [];
    const watchRows = Array.isArray(watch?.rows) ? watch.rows : [];

    const entryTotal = sumKnown(open,row => row.entry_amount_usdt);
    const markTotal = sumKnown(open,row => markRow(row,markMap).markValue);
    const markPnl = sumKnown(open,row => markRow(row,markMap).markPnl);
    const realized = sumKnown(
      ledgerRows.filter(row => String(row?.status || '').toUpperCase() === 'CLOSED'),
      row => row.net_pnl_usdt ?? row.net_pnl
    );

    const startCapital = n(summary.starting_capital) || 10000;
    const openInvestment = n(summary.open_investment) ?? entryTotal.total;
    const exposurePct = startCapital > 0 ? openInvestment / startCapital * 100 : null;
    const modeledRiskPct = n(summary.risk_used_pct);
    const modeledRisk = n(summary.open_risk);
    const markEquity = n(markSummary.mark_equity_usdt);
    const freshMarks = n(markSummary.fresh_mark_count) ?? 0;
    const markCoverage = n(markSummary.net_mark_coverage_count) ?? 0;
    const riskWarning = openInvestment > 0 && (modeledRiskPct === null || modeledRiskPct === 0)
      ? 'Açık yatırım var fakat modellenen risk 0 görünüyor. Bu yüzden maruziyet ayrıca gösteriliyor; ikisi aynı kavram değildir.'
      : 'Modellenen risk backend risk_amount_usdt alanlarından gelir; açık maruziyet ise yatırılan sermayeyi gösterir.';

    const openRows = open.map(row => {
      const mark = markRow(row,markMap);
      const cls = mark.markPnl === null ? '' : mark.markPnl >= 0 ? 'pos' : 'neg';
      const protect = row.sl_price ?? row.stop_loss_price ?? null;
      const target = row.tp_price ?? row.take_profit_price ?? null;
      const sourceLabel = mark.fresh
        ? `${mark.source}${mark.age === null ? '' : ` · ${Math.round(mark.age)} sn`}`
        : `${mark.source} · TAZE MARK YOK`;
      return `<tr>
        <td><b>${esc(row.symbol || short(row.token))}</b><small>#${esc(row.id ?? '—')} · ${esc(String(row.trade_policy || 'PAPER'))}</small></td>
        <td>${price(row.entry_price)}</td>
        <td>${price(mark.current)}<small>${esc(sourceLabel)}</small></td>
        <td>${money(mark.markValue)}</td>
        <td>${money(row.entry_amount_usdt)}</td>
        <td class="${cls}">${money(mark.markPnl)}</td>
        <td class="${cls}">${pct(mark.markRoi)}</td>
        <td>${protect === null ? '—' : price(protect)}</td>
        <td>${target === null ? '—' : price(target)}</td>
        <td><button class="premium-row-action" type="button" data-premium-sell-id="${esc(row.id)}">SATIŞI İNCELE</button></td>
      </tr>`;
    }).join('');

    const historyRows = ledgerRows
      .filter(row => mode === 'history' ? String(row?.status || '').toUpperCase() === 'CLOSED' : true)
      .slice(0,100)
      .map(row => {
        const pnl = n(row.net_pnl_usdt ?? row.net_pnl);
        const roi = n(row.roi_pct) ?? (n(row.roi) === null ? null : n(row.roi) * 100);
        const cls = pnl === null ? '' : pnl >= 0 ? 'pos' : 'neg';
        return `<tr>
          <td>${esc(String(row.status || '—').toUpperCase())}</td>
          <td>${esc(row.symbol || short(row.token))}</td>
          <td>${price(row.entry_price)}</td>
          <td>${price(row.exit_price ?? row.current_price)}</td>
          <td class="${cls}">${money(pnl)}</td>
          <td class="${cls}">${pct(roi)}</td>
          <td>${esc(row.close_reason || '—')}</td>
        </tr>`;
      }).join('');

    const watchOpen = watchRows.filter(row => String(row?.status || '').toUpperCase() !== 'CLOSED').length;
    const watchClosed = watchRows.length - watchOpen;
    const exposure = exposureRows(open);
    const comment = portfolioComment(open,summary);

    return `
      <div class="premium-accounting-head">
        <div><div class="section-eyebrow">PAPER PORTFÖY / GERÇEK VERİ</div><h2>${mode === 'history' ? 'İŞLEM GEÇMİŞİ' : 'MUHASEBE / AÇIK POZİSYONLAR'}</h2><p>Mark-to-market, gerçekleşmiş sonuç ve açık maruziyet ayrı gösterilir.</p></div>
        <div class="premium-accounting-badge">LIVE EXECUTION KAPALI</div>
      </div>

      <div class="premium-accounting-kpis">
        <div><small>MARK EQUITY</small><b>${money(markEquity ?? summary.equity)}</b><span>${freshMarks}/${open.length} taze mark · başlangıç ${money(startCapital)}</span></div>
        <div><small>AÇIK YATIRIM</small><b>${money(openInvestment)}</b><span>${pct(exposurePct)} sermaye maruziyeti</span></div>
        <div><small>MARK DEĞERİ</small><b>${money(n(markSummary.mark_value_usdt) ?? (markTotal.known ? markTotal.total : null))}</b><span>${freshMarks}/${open.length} taze fiyat</span></div>
        <div><small>TAHMİNİ ÇIKIŞ PNL</small><b class="${(n(markSummary.open_mark_net_pnl_usdt) ?? markPnl.total) >= 0 ? 'pos' : 'neg'}">${money(n(markSummary.open_mark_net_pnl_usdt) ?? (markPnl.known ? markPnl.total : null))}</b><span>${markCoverage}/${open.length} net mark kapsamı</span></div>
        <div><small>GERÇEKLEŞMİŞ PNL</small><b class="${realized.total >= 0 ? 'pos' : 'neg'}">${money(realized.known ? realized.total : summary.realized_net)}</b><span>Kapanmış işlemler</span></div>
        <div><small>MODELLENEN RİSK</small><b>${pct(modeledRiskPct)}</b><span>${money(modeledRisk)}</span></div>
      </div>

      <div class="premium-accounting-note"><b>RİSK ≠ MARUZİYET</b><span>${esc(riskWarning)} Mark fiyatları ayrı read-only fiyat katmanından gelir; paper DB değiştirilmez.</span></div>

      ${mode !== 'history' ? `
      <div class="premium-accounting-layout">
        <section class="premium-accounting-card premium-accounting-wide">
          <div class="premium-accounting-card-head"><div><small>CANLI MARK-TO-MARKET</small><b>AÇIK POZİSYONLAR</b></div><span>${freshMarks}/${open.length} TAZE</span></div>
          <div class="premium-accounting-scroll"><table class="premium-accounting-table">
            <thead><tr><th>TOKEN</th><th>GİRİŞ</th><th>ANLIK MARK</th><th>MARK DEĞERİ</th><th>YATIRIM</th><th>TAHMİNİ NET PNL</th><th>ROI</th><th>KORUMA</th><th>HEDEF</th><th>AKSİYON</th></tr></thead>
            <tbody>${openRows || '<tr><td colspan="10">Açık paper pozisyon yok.</td></tr>'}</tbody>
          </table></div>
        </section>

        <aside class="premium-accounting-card portfolio-balance">
          <div class="premium-accounting-card-head"><div><small>YOĞUNLAŞMA</small><b>PORTFÖY DENGESİ</b></div></div>
          <div class="exposure-list">${exposure.length ? exposure.map(item => `<div class="exposure-row"><div><span>${esc(item.name)}</span><b>${money(item.value)}</b></div><div class="exposure-track"><i style="width:${Math.min(100,item.share)}%"></i></div><small>${item.share.toFixed(1)}%</small></div>`).join('') : '<div class="premium-empty">Açık maruziyet yok.</div>'}</div>
          <div class="premium-vezir-accounting"><small>VEZİR ÖZETİ</small><p>${esc(comment)}</p></div>
        </aside>
      </div>

      <div class="premium-accounting-info-grid">
        <div><b>MARK NEDİR?</b><p>Taze pool fiyatıyla pozisyonun tahmini anlık değeridir. Paper pozisyon kapanmış sayılmaz ve DB muhasebesi değiştirilmez.</p></div>
        <div><b>REALİZE ÇIKIŞ NEDİR?</b><p>Satış tamamlandıktan sonra kayda geçen gerçek kapanış sonucudur. Mark ile aynı olmak zorunda değildir.</p></div>
        <div><b>1 USDT ÖĞRENME PROBELARI</b><p>${watchOpen} açık · ${watchClosed} kapalı. Normal paper pozisyonlardan ayrı counterfactual öğrenme hesabıdır.</p></div>
      </div>` : ''}

      <section class="premium-accounting-card premium-history-card">
        <div class="premium-accounting-card-head"><div><small>KAYIT DEFTERİ</small><b>${mode === 'history' ? 'KAPANMIŞ İŞLEMLER' : 'PAPER İŞLEM GEÇMİŞİ'}</b></div><span>${ledgerRows.length} KAYIT</span></div>
        <div class="premium-accounting-scroll"><table class="premium-accounting-table">
          <thead><tr><th>DURUM</th><th>TOKEN</th><th>GİRİŞ</th><th>ÇIKIŞ / SON</th><th>NET PNL</th><th>ROI</th><th>KAPANIŞ NEDENİ</th></tr></thead>
          <tbody>${historyRows || '<tr><td colspan="7">İşlem geçmişi yok.</td></tr>'}</tbody>
        </table></div>
      </section>`;
  }

  async function openAccounting(mode='open'){
    const modal = ensureModal();
    const body = document.getElementById('premiumAccountingBody');
    modal.classList.add('open');
    body.innerHTML = '<div class="premium-accounting-loading"><b>MUHASEBE VERİSİ OKUNUYOR...</b><span>Dashboard, canlı mark, ledger ve 1 USDT öğrenme kayıtları birleştiriliyor.</span></div>';
    try {
      const [dashboard,ledger,watch,marks] = await Promise.all([
        get('/api/dashboard'),
        get('/api/accounting-ledger-v2?limit=100'),
        get('/api/watch-probes-detail-v2?limit=100'),
        get('/api/portfolio-marks-v2')
      ]);
      if (!modal.classList.contains('open')) return;
      body.innerHTML = accountingHtml(dashboard,ledger,watch,marks,mode);
    } catch (error) {
      body.innerHTML = `<div class="premium-accounting-loading"><b class="neg">MUHASEBE VERİSİ ALINAMADI</b><span>${esc(error.message)}</span></div>`;
    }
  }

  document.addEventListener('click',event => {
    const accounting = event.target.closest('#accountingButton');
    const side = event.target.closest('[data-nav]');
    const nav = side?.dataset?.nav;
    if (!accounting && nav !== 'positions' && nav !== 'history') return;
    event.preventDefault();
    event.stopPropagation();
    event.stopImmediatePropagation();
    openAccounting(nav === 'history' ? 'history' : 'open');
  },true);

  document.addEventListener('keydown',event => {
    if (event.key === 'Escape') document.getElementById('premiumAccountingModal')?.classList.remove('open');
  });
})();
