(() => {
  'use strict';

  const $ = id => document.getElementById(id);
  const n = value => {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  };
  const esc = value => String(value ?? '')
    .replaceAll('&','&amp;')
    .replaceAll('<','&lt;')
    .replaceAll('>','&gt;')
    .replaceAll('"','&quot;')
    .replaceAll("'",'&#039;');
  const norm = value => String(value || '').trim().toLocaleLowerCase('tr-TR');
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
  const getJSON = async (url, options={}) => {
    const response = await fetch(url,{cache:'no-store',...options});
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || `${url} ${response.status}`);
    return data;
  };

  let sellRenderToken = 0;

  function updateRiskBar(){
    const riskText = $('riskUsed')?.textContent || '';
    const value = n(riskText.replace('%','').replace(',','.'));
    const bar = $('riskBar');
    if (!bar) return;
    const width = value === null ? 0 : Math.max(0,Math.min(100,value));
    bar.style.width = `${width}%`;
  }

  function premiumMarketLabel(){
    const label = $('vezirMarketLabel');
    if (!label) return;
    const system = String($('systemState')?.textContent || '').toUpperCase();
    if (system.includes('ÇALIŞIYOR') || system.includes('HEALTHY')) {
      label.textContent = 'VERİ AKIŞI AKTİF';
      label.className = 'pos';
    } else if (system.includes('FALLBACK') || system.includes('DEGRADED')) {
      label.textContent = 'TEMKİNLİ';
      label.className = 'warn';
    } else if (system.includes('YOK')) {
      label.textContent = 'VERİ SINIRLI';
      label.className = 'neg';
    } else {
      label.textContent = 'VERİ OKUNUYOR';
      label.className = '';
    }
  }

  function bindSidebar(){
    document.querySelectorAll('[data-nav]').forEach(button => {
      button.addEventListener('click', () => {
        const target = button.dataset.nav;
        if (target === 'home') window.scrollTo({top:0,behavior:'smooth'});
        if (target === 'radar') $('radarPanel')?.scrollIntoView({behavior:'smooth',block:'start'});
        if (target === 'wallet') $('walletPanel')?.scrollIntoView({behavior:'smooth',block:'start'});
        if (target === 'news') $('marketPanel')?.scrollIntoView({behavior:'smooth',block:'start'});
        if (target === 'positions') $('accountingButton')?.click();
        document.querySelectorAll('[data-nav]').forEach(node => node.classList.toggle('active',node === button));
      });
    });
  }

  function baseNameFromTicket(){
    const title = String($('ticketTitle')?.textContent || '');
    return title.replace(/^SAT\s*[·:]?\s*/i,'').trim();
  }

  function positionMatch(positions, ticketName){
    const key = norm(ticketName);
    const base = norm(ticketName.split('/')[0]);
    const open = positions.filter(row => String(row?.status || 'OPEN').toUpperCase() !== 'CLOSED');
    return open.find(row => {
      const symbol = norm(row?.symbol);
      return symbol && (symbol === key || symbol === base || key.startsWith(`${symbol} /`) || key.startsWith(`${symbol}/`));
    }) || null;
  }

  function levelTop(value, min, max){
    const x = n(value);
    if (x === null || max <= min) return 50;
    const ratio = (x - min) / (max - min);
    return 88 - Math.max(0,Math.min(1,ratio)) * 76;
  }

  function sellManagerHtml(position, preview, ticketName){
    const entry = n(preview.entry_price ?? position.entry_price);
    const current = n(preview.reference_price ?? position.current_price ?? position.entry_price);
    const breakEven = n(preview.break_even_price);
    const high = n(preview.highest_price ?? position.highest_price);
    const low = n(preview.lowest_price ?? position.lowest_price);
    const m5 = n(preview.change_5m_pct);
    const roi = n(preview.roi_pct);
    const pnl = n(preview.net_pnl_usdt);
    const investment = n(position.entry_amount_usdt);
    const tokenAmount = n(position.token_amount);

    const known = [entry,current,breakEven,high,low].filter(x => x !== null && x > 0);
    const min = known.length ? Math.min(...known) * .96 : 0;
    const max = known.length ? Math.max(...known) * 1.04 : 1;

    const levels = [
      {cls:'now',label:'ŞİMDİ SATARSAN',desc:'Güncel server referans fiyatından tahmini çıkış',value:current,result:`${money(preview.proceeds_usdt)} · ${money(pnl)} (${pct(roi)})`},line:'now'},
      {cls:'',label:'BAŞA BAŞ',desc:'Tahmini zarar etmeden çıkış seviyesi',value:breakEven,result:breakEven === null ? 'VERİ YOK' : price(breakEven),line:'break'},
      {cls:'warn',label:'KÂRI KORU',desc:m5 !== null && m5 < 0 ? '5M zayıflıyor; kârı geri vermemeyi değerlendir' : 'Momentum zayıflarsa koruma seviyesi belirle',value:null,result:preview.guidance_label || 'TEYİT BEKLE',line:'stop'},
      {cls:'',label:'SON ZİRVE',desc:'Pozisyonun gördüğü doğrulanmış en yüksek fiyat',value:high,result:high === null ? 'VERİ YOK' : price(high),line:'peak'}
    ];

    const chartLines = levels
      .filter(level => n(level.value) !== null)
      .map(level => `<div class="sell-chart-line ${level.line}" style="top:${levelTop(level.value,min,max)}%"><label>${esc(level.label)} · ${esc(price(level.value))}</label></div>`)
      .join('');

    const roiClass = roi !== null && roi < 0 ? 'neg' : 'pos';
    const pnlClass = pnl !== null && pnl < 0 ? 'neg' : 'pos';
    const momentumLabel = m5 === null ? '5M TEYİDİ YOK' : m5 > 0 ? 'MOMENTUM POZİTİF' : m5 < 0 ? 'MOMENTUM ZAYIFLIYOR' : 'MOMENTUM YATAY';

    return `
      <div class="sell-manager" data-position-id="${esc(position.id)}">
        <div class="sell-manager-head">
          <div><div class="section-eyebrow">PAPER ÇIKIŞ PLANI</div><h2>SATIŞ YÖNETİMİ · ${esc(ticketName)}</h2></div>
          <div class="paper-badge">PAPER İŞLEM · GERÇEK PARA İÇERMEZ</div>
        </div>

        <div class="sell-position-strip">
          <div class="sell-position-name"><span class="sell-token-mark">${esc(String(ticketName || '?').trim().slice(0,1).toUpperCase())}</span><span><small>SEÇİLİ POZİSYON</small><b>${esc(ticketName)}</b></span></div>
          <div><small>GİRİŞ FİYATI</small><b>${price(entry)}</b></div>
          <div><small>MEVCUT FİYAT</small><b>${price(current)}</b></div>
          <div><small>YATIRIM</small><b>${money(investment)}</b></div>
          <div><small>MİKTAR</small><b>${tokenAmount === null ? '—' : tokenAmount.toLocaleString('tr-TR',{maximumFractionDigits:8})}</b></div>
          <div><small>NET PNL</small><b class="${pnlClass}">${money(pnl)}</b></div>
          <div><small>ROI</small><b class="${roiClass}">${pct(roi)}</b></div>
        </div>

        <div class="sell-main-grid">
          <section class="sell-card">
            <div class="sell-card-title">SATIŞ SEVİYELERİ</div>
            <div class="sell-levels">
              ${levels.map(level => `<div class="sell-level ${level.cls}"><span><b>${esc(level.label)}</b><small>${esc(level.desc)}</small></span><strong>${esc(level.result)}</strong></div>`).join('')}
            </div>
          </section>

          <section class="sell-card">
            <div class="sell-card-title">FİYAT SEVİYELERİ</div>
            <div class="sell-level-chart"><div class="sell-chart-axis"></div>${chartLines}</div>
          </section>

          <section class="sell-card">
            <div class="sell-card-title">ÇIKIŞ REHBERİ</div>
            <div class="sell-guidance">
              <div class="sell-guidance-box"><small>ŞU ANKİ DURUM</small><b>${esc(preview.guidance_label || 'TEYİT BEKLE')}</b><p>${esc(preview.guidance_text || 'Güncel hareket verisini izle.')}</p></div>
              <div class="sell-guidance-box"><small>5 DAKİKALIK HAREKET</small><b class="${m5 !== null && m5 < 0 ? 'neg' : m5 !== null && m5 > 0 ? 'pos' : ''}">${esc(momentumLabel)}</b><p>${m5 === null ? 'Kısa hareket verisi eksik; yalnız fiyat seviyesine dayanma.' : `Güncel 5M değişim ${pct(m5)}.`}</p></div>
              <div class="sell-guidance-box"><small>KURAL</small><b>PLANLI ÇIK</b><p>Hedef fiyat uydurulmaz. Yalnız backend tarafından doğrulanmış fiyat, başa baş, zirve ve hareket verisi gösterilir.</p></div>
            </div>
          </section>
        </div>

        <div class="sell-bottom-grid">
          <section class="sell-card sell-vezir"><div class="sell-card-title" style="margin:-12px -12px 12px">VEZİR'DEN SATIŞ YORUMU</div><p>${esc(preview.guidance_text || 'Pozisyon için güncel çıkış verisini izliyorum.')}</p><div class="sell-vezir-tags"><span>${esc(momentumLabel)}</span><span>BAŞA BAŞ ${esc(price(breakEven))}</span><span>SON ZİRVE ${esc(price(high))}</span><span>READ ONLY YORUM</span></div></section>
          <section class="sell-card sell-actions"><div class="sell-card-title" style="margin:-12px -12px 4px">SATIŞ İŞLEMİ</div><div class="sell-paper-note">Onaylanan satış mevcut canonical PAPER endpointine gider. Live execution, wallet ve signing kapalıdır.</div><button class="confirm sell premium-confirm-sell" type="button">TAMAMINI SAT</button><button class="sell-wait" type="button">BEKLE</button></section>
        </div>
      </div>`;
  }

  async function renderPremiumSell(){
    const modal = $('orderModal');
    const ticket = modal?.querySelector('.ticket');
    if (!modal?.classList.contains('open') || !ticket) return;
    const title = String($('ticketTitle')?.textContent || '');
    if (!/^SAT\b/i.test(title)) {
      ticket.classList.remove('premium-sell-ticket');
      ticket.querySelector('.sell-manager')?.remove();
      return;
    }

    const token = ++sellRenderToken;
    const name = baseNameFromTicket();
    ticket.classList.add('premium-sell-ticket');
    ticket.querySelector('.sell-manager')?.remove();
    const loading = document.createElement('div');
    loading.className = 'sell-manager';
    loading.innerHTML = '<div class="sell-manager-head"><div><div class="section-eyebrow">PAPER ÇIKIŞ PLANI</div><h2>SATIŞ YÖNETİMİ</h2></div></div><div class="sell-guidance-box"><b>Güncel satış verisi hazırlanıyor...</b></div>';
    ticket.appendChild(loading);

    try {
      const dashboard = await getJSON('/api/dashboard');
      if (token !== sellRenderToken || !modal.classList.contains('open')) return;
      const positions = Array.isArray(dashboard.positions) ? dashboard.positions : [];
      const position = positionMatch(positions,name);
      if (!position) throw new Error('Açık pozisyon eşleştirilemedi');

      const preview = await getJSON('/api/manual-paper/preview-v2',{
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body:JSON.stringify({position_id:position.id,pool:position.pool || null,token:position.token || null})
      });
      if (token !== sellRenderToken || !modal.classList.contains('open')) return;

      loading.outerHTML = sellManagerHtml(position,preview,name);
      const manager = ticket.querySelector('.sell-manager');
      manager?.querySelector('.premium-confirm-sell')?.addEventListener('click',() => $('confirmOrder')?.click());
      manager?.querySelector('.sell-wait')?.addEventListener('click',() => $('ticketClose')?.click());
    } catch (error) {
      if (token !== sellRenderToken) return;
      loading.innerHTML = `<div class="sell-manager-head"><div><div class="section-eyebrow">PAPER ÇIKIŞ PLANI</div><h2>SATIŞ YÖNETİMİ</h2></div></div><div class="sell-guidance-box"><b class="neg">Satış görünümü hazırlanamadı</b><p>${esc(error.message)}</p></div><button class="sell-wait" type="button">KAPAT</button>`;
      loading.querySelector('.sell-wait')?.addEventListener('click',() => $('ticketClose')?.click());
    }
  }

  function observeSellModal(){
    const modal = $('orderModal');
    if (!modal) return;
    const observer = new MutationObserver(mutations => {
      if (mutations.some(item => item.attributeName === 'class')) {
        if (modal.classList.contains('open')) setTimeout(renderPremiumSell,0);
        else sellRenderToken += 1;
      }
    });
    observer.observe(modal,{attributes:true,attributeFilter:['class']});
  }

  function observeStatus(){
    const targets = [$('riskUsed'),$('systemState')].filter(Boolean);
    const observer = new MutationObserver(() => {
      updateRiskBar();
      premiumMarketLabel();
    });
    targets.forEach(target => observer.observe(target,{childList:true,subtree:true,characterData:true}));
  }

  document.addEventListener('DOMContentLoaded',() => {
    bindSidebar();
    observeSellModal();
    observeStatus();
    updateRiskBar();
    premiumMarketLabel();
  });
})();
