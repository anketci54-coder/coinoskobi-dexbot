(() => {
  'use strict';

  window.__COINOSKOBI_PREMIUM_INTEL_V5__ = true;

  const $ = id => document.getElementById(id);
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
  const get = async url => {
    const response = await fetch(url,{cache:'no-store'});
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || `${url} ${response.status}`);
    return data;
  };
  const post = async (url,payload) => {
    const response = await fetch(url,{
      method:'POST',
      cache:'no-store',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify(payload)
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || `${url} ${response.status}`);
    return data;
  };

  let cache = {market:null,calendar:null,operations:null};
  let activeTab = 'NEWS';

  function ensureModal(){
    let modal = $('premiumIntelModal');
    if (modal) return modal;
    modal = document.createElement('div');
    modal.id = 'premiumIntelModal';
    modal.className = 'premium-intel-modal';
    modal.innerHTML = `
      <div class="premium-intel-shell">
        <button class="premium-intel-close" type="button" aria-label="Kapat">×</button>
        <div id="premiumIntelBody"></div>
      </div>`;
    document.body.appendChild(modal);
    modal.querySelector('.premium-intel-close').addEventListener('click',() => modal.classList.remove('open'));
    modal.addEventListener('click',event => { if (event.target === modal) modal.classList.remove('open'); });
    return modal;
  }

  function stateClass(value){
    const state = String(value || '').toLowerCase();
    return ['hot','warm','cold'].includes(state) ? state : 'cold';
  }

  function newsRows(rows){
    if (!rows.length) return '<div class="premium-intel-empty">Önem filtresini geçen güncel haber yok.</div>';
    return `<div class="premium-news-list">${rows.map(row => {
      const url = String(row.url || '').trim();
      const link = /^https?:\/\//i.test(url)
        ? `<a class="premium-news-link" href="${esc(url)}" target="_blank" rel="noopener noreferrer">KAYNAĞI AÇ ↗</a>`
        : '';
      return `<article class="premium-news-item">
        <div class="premium-news-top">
          <span class="premium-news-state ${stateClass(row.state)}">${esc(row.state || 'COLD')}</span>
          <div class="premium-news-title">${esc(row.title_tr || 'PİYASA')}</div>
          <div class="premium-news-score">${esc(row.importance_score ?? '—')}/100</div>
        </div>
        <div class="premium-news-scope">ETKİ ALANI · ${esc(row.market_scope_tr || 'GENEL KRİPTO')}</div>
        <div class="premium-news-summary">${esc(row.summary_tr || 'Etki özeti yok.')}</div>
        <div class="premium-news-action"><b>NE YAPMALI?</b> ${esc(row.recommendation_tr || 'Teyit bekle; haberi tek başına işlem sinyali olarak kullanma.')}</div>
        ${row.source_title ? `<div class="premium-news-source">ORİJİNAL BAŞLIK · ${esc(row.source_title)}</div>` : ''}
        ${row.source ? `<div class="premium-news-source">KAYNAK · ${esc(row.source)}</div>` : ''}
        ${link}
      </article>`;
    }).join('')}</div>`;
  }

  function calendarRows(rows){
    if (!rows.length) return '<div class="premium-intel-empty">WARM/HOT ekonomik takvim olayı yok.</div>';
    return `<div class="premium-calendar-list">${rows.map(row => `<article class="premium-calendar-item">
      <h4>${esc(row.title_tr || 'EKONOMİK VERİ')}</h4>
      <div class="scope">${esc(row.market_scope_tr || 'GENEL KRİPTO / RİSK İŞTAHI')} · ${esc(row.state || 'COLD')} · ${esc(row.importance_score ?? '—')}/100</div>
      <p>${esc(row.summary_tr || 'Piyasa etkisi için izleniyor.')}</p>
      <div class="action"><b>NE YAPMALI?</b> ${esc(row.recommendation_tr || 'Fiyat tepkisini izle.')}</div>
      ${row.source_title ? `<p>ORİJİNAL · ${esc(row.source_title)}</p>` : ''}
    </article>`).join('')}</div>`;
  }

  function launchRows(rows){
    return newsRows(rows);
  }

  function marketSide(market,calendar){
    const news = Array.isArray(market?.items) ? market.items : [];
    const launches = Array.isArray(market?.launch_items) ? market.launch_items : [];
    const cal = Array.isArray(calendar?.items) ? calendar.items : [];
    const hot = [...news,...launches,...cal].filter(row => String(row?.state || '').toUpperCase() === 'HOT').length;
    const top = [...news,...launches].sort((a,b) => (n(b.importance_score) || 0) - (n(a.importance_score) || 0))[0] || null;
    return `
      <div class="premium-intel-sidebox"><small>HOT OLAY</small><b>${hot}</b><p>Yüksek önem filtresini geçen haber/takvim/launch sayısı.</p></div>
      <div class="premium-intel-sidebox"><small>EN GÜÇLÜ GÜNCEL BAŞLIK</small><b>${esc(top?.title_tr || 'YOK')}</b><p>${esc(top?.summary_tr || 'Öne çıkan doğrulanmış olay yok.')}</p></div>
      <div class="premium-intel-sidebox warning"><small>PANEL PRENSİBİ</small><b>HABER ≠ AL/SAT SİNYALİ</b><p>Haber yalnız risk ve bağlam katmanıdır. Fiyat, hacim, likidite ve radar teyidi olmadan işlem gerekçesi sayılmaz.</p></div>`;
  }

  function overviewHtml(market,calendar){
    const news = Array.isArray(market?.items) ? market.items : [];
    const launches = Array.isArray(market?.launch_items) ? market.launch_items : [];
    const cal = Array.isArray(calendar?.items) ? calendar.items : [];
    const hot = [...news,...launches,...cal].filter(row => String(row?.state || '').toUpperCase() === 'HOT').length;
    const warm = [...news,...launches,...cal].filter(row => String(row?.state || '').toUpperCase() === 'WARM').length;
    return `<div class="premium-intel-overview">
      <div><small>HABER</small><b>${news.length}</b><span>Önem filtresini geçen piyasa haberi</span></div>
      <div><small>LAUNCH / DROP</small><b>${launches.length}</b><span>Airdrop / IDO / ICO / TGE / listing</span></div>
      <div><small>EKONOMİK TAKVİM</small><b>${cal.length}</b><span>WARM/HOT makro olay</span></div>
      <div><small>HOT</small><b>${hot}</b><span>Yüksek önem</span></div>
      <div><small>WARM</small><b>${warm}</b><span>Orta önem</span></div>
    </div>`;
  }

  function intelHtml(market,calendar){
    const news = Array.isArray(market?.items) ? market.items : [];
    const launches = Array.isArray(market?.launch_items) ? market.launch_items : [];
    const cal = Array.isArray(calendar?.items) ? calendar.items : [];
    return `
      <div class="premium-intel-head">
        <div><div class="section-eyebrow">PİYASA BAĞLAMI / TÜRKÇE ETKİ</div><h2>HABER ETKİSİ</h2><p>Ne oldu, kimi etkiler ve ne yapmalı? Orijinal başlık kaynak olarak korunur.</p></div>
        <div class="premium-intel-badge">TRADE SIGNAL YOK · READ ONLY</div>
      </div>
      ${overviewHtml(market,calendar)}
      <div class="premium-intel-tabs">
        <button class="premium-intel-tab ${activeTab === 'NEWS' ? 'active' : ''}" data-premium-intel-tab="NEWS">HABERLER</button>
        <button class="premium-intel-tab ${activeTab === 'CALENDAR' ? 'active' : ''}" data-premium-intel-tab="CALENDAR">EKONOMİK TAKVİM</button>
        <button class="premium-intel-tab ${activeTab === 'LAUNCH' ? 'active' : ''}" data-premium-intel-tab="LAUNCH">AIRDROP / IDO / ICO</button>
        <button class="premium-intel-tab ${activeTab === 'VEZIR' ? 'active' : ''}" data-premium-intel-tab="VEZIR">VEZİR 2.0</button>
      </div>
      <div class="premium-intel-pane ${activeTab === 'NEWS' ? 'active' : ''}" data-premium-pane="NEWS"><div class="premium-intel-grid"><section class="premium-intel-card"><div class="premium-intel-card-head"><div><small>TÜRKÇE ETKİ ÖZETİ</small><b>PİYASA HABERLERİ</b></div><span>${news.length} KAYIT</span></div>${newsRows(news)}</section><aside class="premium-intel-card premium-intel-side">${marketSide(market,calendar)}</aside></div></div>
      <div class="premium-intel-pane ${activeTab === 'CALENDAR' ? 'active' : ''}" data-premium-pane="CALENDAR"><section class="premium-intel-card"><div class="premium-intel-card-head"><div><small>MAKRO RİSK</small><b>EKONOMİK TAKVİM</b></div><span>${cal.length} KAYIT</span></div>${calendarRows(cal)}</section></div>
      <div class="premium-intel-pane ${activeTab === 'LAUNCH' ? 'active' : ''}" data-premium-pane="LAUNCH"><section class="premium-intel-card"><div class="premium-intel-card-head"><div><small>LAUNCH / DROP</small><b>AIRDROP / IDO / ICO / TGE / LISTING</b></div><span>${launches.length} KAYIT</span></div>${launchRows(launches)}</section></div>
      <div class="premium-intel-pane ${activeTab === 'VEZIR' ? 'active' : ''}" data-premium-pane="VEZIR">${vezirHtml()}</div>`;
  }

  function vezirHtml(){
    return `<div class="premium-vezir-layout">
      <section class="premium-intel-card premium-vezir-chat">
        <div class="premium-intel-card-head"><div><small>AZ TEKNİK · GERÇEK PANEL VERİSİ</small><b>VEZİR 2.0</b></div><span>READ ONLY</span></div>
        <div class="premium-vezir-quick">
          <button data-premium-ask="Genel operasyon özetini ver. Neye dikkat etmeliyim?">GENEL ÖZET</button>
          <button data-premium-ask="Şu an en önemli risk ne ve ne yapmalıyım?">RİSK</button>
          <button data-premium-ask="Son haberlerin bizim piyasaya etkisini ve ne yapmam gerektiğini özetle.">HABER ETKİ</button>
          <button data-premium-ask="Açık paper pozisyonlar için neye dikkat etmeliyim?">AÇIK İŞLEMLER</button>
          <button data-premium-ask="Aday cüzdanlar bize şu an ne söylüyor?">CÜZDANLAR</button>
        </div>
        <div class="premium-vezir-messages" id="premiumVezirMessages"><div class="premium-vezir-message">Hazırım. Panelde doğrulanmış verileri kullanarak kısa ve anlaşılır operasyon yorumu vereceğim.<small>Live execution / wallet / signing yetkisi yok.</small></div></div>
        <div class="premium-vezir-input"><input id="premiumVezirInput" maxlength="500" placeholder="Örn: Şu an neye dikkat etmeliyim?"><button id="premiumVezirSend" type="button">GÖNDER</button></div>
      </section>
      <aside class="premium-vezir-side">
        <div class="premium-vezir-principle green"><small>ÇALIŞMA ŞEKLİ</small><b>ÖZET → NEDEN → NE YAPMALI</b><p>Vezir teknik ayrıntıyı varsayılan olarak gizler; operasyon açısından önemli sonucu öne çıkarır.</p></div>
        <div class="premium-vezir-principle"><small>GERÇEKLİK SINIRI</small><b>EKSİK VERİYİ UYDURMAZ</b><p>Panelde bulunmayan fiyat, hedef, cüzdan başarısı veya haber etkisi üretilmez.</p></div>
        <div class="premium-vezir-principle amber"><small>YETKİ SINIRI</small><b>TAVSİYE DEĞİL, KARAR DESTEĞİ</b><p>Vezir trade açamaz, wallet kullanamaz, imza atamaz ve canlı emir veremez.</p></div>
      </aside>
    </div>`;
  }

  function switchTab(tab){
    activeTab = tab;
    document.querySelectorAll('[data-premium-intel-tab]').forEach(button => button.classList.toggle('active',button.dataset.premiumIntelTab === tab));
    document.querySelectorAll('[data-premium-pane]').forEach(pane => pane.classList.toggle('active',pane.dataset.premiumPane === tab));
  }

  function addVezirMessage(text,kind='vezir',meta=''){
    const box = $('premiumVezirMessages');
    if (!box) return;
    const node = document.createElement('div');
    node.className = `premium-vezir-message ${kind === 'user' ? 'user' : ''}`;
    node.innerHTML = `${esc(text)}${meta ? `<small>${esc(meta)}</small>` : ''}`;
    box.appendChild(node);
    box.scrollTop = box.scrollHeight;
  }

  async function askVezir(question){
    const input = $('premiumVezirInput');
    const q = String(question ?? input?.value ?? '').trim();
    if (!q) return;
    if (input) input.value = '';
    addVezirMessage(q,'user');
    const send = $('premiumVezirSend');
    if (send) send.disabled = true;
    try {
      const data = await post('/api/vezir/ask',{question:q});
      const meta = [data.intent ? `Niyet: ${data.intent}` : '',data.authority ? `Yetki: ${data.authority}` : ''].filter(Boolean).join(' · ');
      addVezirMessage(data.answer || 'Yanıt alınamadı.','vezir',meta);
    } catch (error) {
      addVezirMessage(`Yanıt alınamadı: ${error.message}`,'vezir','Panel bağlantısı');
    } finally {
      if (send) send.disabled = false;
      input?.focus();
    }
  }

  async function loadData(){
    const [market,calendar,operations] = await Promise.allSettled([
      get('/api/market-brief-v3'),
      get('/api/calendar-brief-v3'),
      get('/api/operations-summary')
    ]);
    cache.market = market.status === 'fulfilled' ? market.value : {items:[],launch_items:[]};
    cache.calendar = calendar.status === 'fulfilled' ? calendar.value : {items:[]};
    cache.operations = operations.status === 'fulfilled' ? operations.value : null;
  }

  async function openIntel(tab='NEWS'){
    activeTab = tab;
    const modal = ensureModal();
    const body = $('premiumIntelBody');
    modal.classList.add('open');
    body.innerHTML = '<div class="premium-intel-loading"><div><b>PİYASA İSTİHBARATI HAZIRLANIYOR...</b><span>Haber, ekonomik takvim ve launch etkileri Türkçe karar desteğine dönüştürülüyor.</span></div></div>';
    try {
      await loadData();
      if (!modal.classList.contains('open')) return;
      body.innerHTML = intelHtml(cache.market,cache.calendar);
      switchTab(activeTab);
    } catch (error) {
      body.innerHTML = `<div class="premium-intel-loading"><div><b class="neg">PİYASA VERİSİ ALINAMADI</b><span>${esc(error.message)}</span></div></div>`;
    }
  }

  function addVezirOpenButton(){
    const head = document.querySelector('#vezirPanel .vezir-head');
    if (!head || head.querySelector('.premium-vezir-open')) return;
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'premium-vezir-open';
    button.textContent = 'GENİŞLET';
    button.addEventListener('click',event => {
      event.preventDefault();
      event.stopPropagation();
      openIntel('VEZIR');
    });
    head.appendChild(button);
  }

  document.addEventListener('click',event => {
    const tab = event.target.closest('[data-premium-intel-tab]');
    if (tab) {
      event.preventDefault();
      switchTab(tab.dataset.premiumIntelTab);
      return;
    }

    const ask = event.target.closest('[data-premium-ask]');
    if (ask) {
      event.preventDefault();
      askVezir(ask.dataset.premiumAsk);
      return;
    }

    if (event.target.closest('#premiumVezirSend')) {
      event.preventDefault();
      askVezir();
      return;
    }

    const nav = event.target.closest('[data-nav]');
    if (nav && ['news','market'].includes(nav.dataset.nav)) {
      event.preventDefault();
      event.stopPropagation();
      event.stopImmediatePropagation();
      openIntel(nav.dataset.nav === 'news' ? 'NEWS' : 'CALENDAR');
    }
  },true);

  document.addEventListener('keydown',event => {
    if (event.key === 'Escape') $('premiumIntelModal')?.classList.remove('open');
    if (event.key === 'Enter' && event.target?.id === 'premiumVezirInput') {
      event.preventDefault();
      askVezir();
    }
  });

  document.addEventListener('DOMContentLoaded',addVezirOpenButton);
})();
