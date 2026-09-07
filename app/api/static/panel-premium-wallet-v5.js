(() => {
  'use strict';

  window.__COINOSKOBI_PREMIUM_WALLET_V5__ = true;

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
  const short = value => {
    const text = String(value || '').trim();
    return !text ? '—' : text.length > 22 ? `${text.slice(0,9)}…${text.slice(-8)}` : text;
  };
  const money = value => {
    const x = n(value);
    if (x === null) return '—';
    return `${x < 0 ? '-' : ''}$${Math.abs(x).toLocaleString('tr-TR',{minimumFractionDigits:2,maximumFractionDigits:2})}`;
  };
  const get = async url => {
    const response = await fetch(url,{cache:'no-store'});
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || `${url} ${response.status}`);
    return data;
  };
  const norm = value => String(value || '').trim().toLowerCase();

  let payloadCache = null;
  let selectedWallet = null;

  function ensureModal(){
    let modal = document.getElementById('premiumWalletModal');
    if (modal) return modal;
    modal = document.createElement('div');
    modal.id = 'premiumWalletModal';
    modal.className = 'premium-wallet-modal';
    modal.innerHTML = `
      <div class="premium-wallet-shell">
        <button class="premium-wallet-close" type="button" aria-label="Kapat">×</button>
        <div id="premiumWalletBody"></div>
      </div>`;
    document.body.appendChild(modal);
    modal.querySelector('.premium-wallet-close').addEventListener('click',() => modal.classList.remove('open'));
    modal.addEventListener('click',event => { if (event.target === modal) modal.classList.remove('open'); });
    return modal;
  }

  function candidateReason(row){
    const source = String(row?.discovery_source || row?.source || '').toUpperCase();
    const provider = String(row?.provider || '').trim();
    if (source === 'TRANSACTION_FROM_ONLY') {
      return 'BSC işlem akışında gönderen cüzdan olarak gözlendi ve aday havuzuna alındı.';
    }
    if (source.includes('ARKHAM')) {
      return `Harici cüzdan istihbarat kaynağında gözlendi${provider ? ` · ${provider}` : ''}.`;
    }
    if (source === 'REGISTRY') {
      return 'Canonical cüzdan kayıt defterinde aktif aday olarak bulunuyor.';
    }
    if (source) {
      return `${source.replaceAll('_',' ')} kaynağından aday olarak gözlendi.`;
    }
    return 'Aday nedeni için kaynak kanıtı henüz ayrıntılandırılmamış.';
  }

  function evidenceLevel(row){
    const success = String(row?.success_state || '').toUpperCase();
    const sample = n(row?.success_sample_depth);
    const whale = String(row?.whale_state || '').toUpperCase();
    if (success === 'SUCCESSFUL' && sample !== null && sample >= 20) return {key:'high',label:'YÜKSEK KANIT'};
    if (success === 'SUCCESSFUL' && sample !== null && sample > 0) return {key:'medium',label:'ORTA KANIT'};
    if ((sample !== null && sample > 0) || (whale && !['UNKNOWN','NONE',''].includes(whale))) return {key:'building',label:'KANIT GELİŞİYOR'};
    return {key:'low',label:'KANIT YETERSİZ'};
  }

  function directionClass(value){
    const dir = String(value || '').toUpperCase();
    if (['BUY','IN','ACCUMULATING','ACCUMULATION','POSITIVE','LONG'].some(x => dir.includes(x))) return 'pos';
    if (['SELL','OUT','DISTRIBUTING','DISTRIBUTION','NEGATIVE','SHORT'].some(x => dir.includes(x))) return 'neg';
    return '';
  }

  function holdingsMap(detail){
    const wallets = Array.isArray(detail?.arkham_holdings?.wallets) ? detail.arkham_holdings.wallets : [];
    const map = new Map();
    wallets.forEach(wallet => map.set(norm(wallet.wallet_uid || wallet.address),wallet));
    return map;
  }

  function changesByWallet(detail){
    const changes = Array.isArray(detail?.arkham_holdings?.changes) ? detail.arkham_holdings.changes : [];
    const map = new Map();
    changes.forEach(change => {
      const key = norm(change.wallet_uid);
      if (!map.has(key)) map.set(key,[]);
      map.get(key).push(change);
    });
    return map;
  }

  function mergeRows(brief,detail){
    const briefRows = Array.isArray(brief?.rows) ? brief.rows : [];
    const detailRows = Array.isArray(detail?.rows) ? detail.rows : [];
    const detailById = new Map(detailRows.map(row => [norm(row.wallet_uid),row]));
    const holdMap = holdingsMap(detail);
    const changesMap = changesByWallet(detail);
    const merged = [];
    const seen = new Set();

    for (const base of briefRows) {
      const key = norm(base.wallet_uid);
      if (!key || seen.has(key)) continue;
      const rich = detailById.get(key) || {};
      const holding = holdMap.get(key) || null;
      merged.push({...base,...rich,_holding:holding,_changes:changesMap.get(key) || []});
      seen.add(key);
    }
    for (const rich of detailRows) {
      const key = norm(rich.wallet_uid);
      if (!key || seen.has(key)) continue;
      const holding = holdMap.get(key) || null;
      merged.push({...rich,_holding:holding,_changes:changesMap.get(key) || []});
      seen.add(key);
    }
    return merged;
  }

  function tokenList(row){
    const assets = Array.isArray(row?._holding?.holdings) ? row._holding.holdings : [];
    return assets
      .map(asset => String(asset.symbol || asset.name || asset.token_id || '').trim())
      .filter(Boolean)
      .slice(0,5);
  }

  function lastMovement(row){
    const changes = Array.isArray(row?._changes) ? row._changes : [];
    const latest = changes[0];
    if (latest) {
      const type = String(latest.change_type || 'DEĞİŞİM').replaceAll('_',' ');
      const token = String(latest.token_id || '').trim();
      return `${type}${token ? ` · ${token}` : ''}`;
    }
    const state = String(row?.candidate_state || row?.freshness_state || row?.lifecycle_state || 'OBSERVED').replaceAll('_',' ');
    return state || 'OBSERVED';
  }

  function selectedHtml(row){
    if (!row) return '<div class="wallet-empty">Detay için tablodan bir cüzdan seç.</div>';
    const evidence = evidenceLevel(row);
    const tokens = tokenList(row);
    const changes = Array.isArray(row._changes) ? row._changes.slice(0,5) : [];
    const sample = n(row.success_sample_depth);
    const success = String(row.success_state || 'UNKNOWN').toUpperCase();
    const whale = String(row.whale_state || 'UNKNOWN').toUpperCase();
    const direction = String(row.whale_direction || 'UNKNOWN').toUpperCase();
    const holdingValue = n(row?._holding?.total_value_usd);
    const holdingCount = n(row?._holding?.asset_count);

    return `
      <div class="wallet-selected">
        <div class="wallet-selected-title">
          <div class="wallet-avatar">W</div>
          <div><div class="section-eyebrow">SEÇİLİ CÜZDAN</div><h3>${esc(short(row.wallet_uid))}</h3><small>${esc(row.chain || 'BSC')} · ${esc(short(row.address || row.wallet_uid))}</small></div>
        </div>
        <p><b>Neden aday?</b> ${esc(candidateReason(row))}</p>
        <div class="wallet-facts">
          <div><small>BAŞARI DURUMU</small><b>${esc(success)}</b></div>
          <div><small>ÖRNEKLEM</small><b>${sample === null ? 'YOK' : esc(sample)}</b></div>
          <div><small>BALİNA DURUMU</small><b>${esc(whale)}</b></div>
          <div><small>BALİNA YÖNÜ</small><b class="${directionClass(direction)}">${esc(direction)}</b></div>
          <div><small>HOLDINGS DEĞERİ</small><b>${money(holdingValue)}</b></div>
          <div><small>VARLIK SAYISI</small><b>${holdingCount === null ? '—' : esc(holdingCount)}</b></div>
        </div>
        <div class="wallet-assets">${tokens.length ? tokens.map(token => `<span>${esc(token)}</span>`).join('') : '<span>HOLDINGS TOKEN VERİSİ YOK</span>'}</div>
        <div class="wallet-confidence-help"><b>${esc(evidence.label)}</b> · Bu etiket yalnız panelde mevcut doğrulanmış kanıt kapsamını özetler; kopyalama veya alım tavsiyesi değildir.</div>
      </div>
      <div class="premium-wallet-card-head"><div><small>SON DOĞRULANMIŞ HAREKETLER</small><b>HOLDINGS DEĞİŞİM KANITI</b></div></div>
      <div class="wallet-change-list">${changes.length ? changes.map(change => `<div class="wallet-change"><b>${esc(String(change.change_type || 'DEĞİŞİM').replaceAll('_',' '))} · ${esc(change.token_id || 'TOKEN')}</b><span>${money(change.previous_value_usd)} → ${money(change.current_value_usd)} · ${esc(change.provider || 'provider')}</span></div>`).join('') : '<div class="wallet-empty">Bu cüzdan için holdings değişim kanıtı henüz yok.</div>'}</div>`;
  }

  function tableRows(rows){
    return rows.length ? rows.map(row => {
      const evidence = evidenceLevel(row);
      const sample = n(row.success_sample_depth);
      const success = String(row.success_state || 'UNKNOWN').toUpperCase();
      const whale = String(row.whale_state || 'UNKNOWN').toUpperCase();
      const direction = String(row.whale_direction || 'UNKNOWN').toUpperCase();
      const tokens = tokenList(row);
      return `<tr>
        <td><b>${esc(short(row.wallet_uid))}</b><small>${esc(row.chain || 'BSC')} · ${esc(short(row.address || row.wallet_uid))}</small></td>
        <td class="wallet-why">${esc(candidateReason(row))}</td>
        <td><div class="wallet-status-line"><b>${esc(success)}</b><span>${sample === null ? 'örneklem yok' : `örneklem ${esc(sample)}`}</span></div></td>
        <td><div class="wallet-status-line"><b>${esc(whale)}</b><span class="wallet-dir ${directionClass(direction)}">${esc(direction)}</span></div></td>
        <td>${esc(lastMovement(row))}</td>
        <td class="wallet-token-list">${tokens.length ? esc(tokens.join(' · ')) : '—'}</td>
        <td><span class="wallet-evidence ${evidence.key}">${esc(evidence.label)}</span></td>
        <td><button class="wallet-detail-btn" type="button" data-wallet-select="${esc(row.wallet_uid)}">İNCELE</button></td>
      </tr>`;
    }).join('') : '<tr><td colspan="8">Güncel aday cüzdan kaydı yok.</td></tr>';
  }

  function render(brief,detail){
    const rows = mergeRows(brief,detail);
    payloadCache = {brief,detail,rows};
    const selected = rows.find(row => norm(row.wallet_uid) === norm(selectedWallet)) || rows[0] || null;
    selectedWallet = selected?.wallet_uid || null;
    const provider = detail?.provider || {};
    const successful = n(brief?.successful) ?? n(detail?.successful_wallets) ?? 0;
    const candidates = n(brief?.candidates) ?? n(detail?.tracked_wallets) ?? rows.length;
    const whales = n(detail?.active_whales) ?? 0;
    const holdingWallets = Array.isArray(detail?.arkham_holdings?.wallets) ? detail.arkham_holdings.wallets.length : 0;
    const source = brief?.candidate_source || '—';

    return `
      <div class="premium-wallet-head">
        <div><div class="section-eyebrow">SMART MONEY / READ ONLY</div><h2>CÜZDAN İSTİHBARATI</h2><p>Aday sayısı skor değildir. Her cüzdan için neden aday olduğu ve mevcut kanıt kapsamı ayrı gösterilir.</p></div>
        <div class="premium-wallet-badge">WALLET AUTHORITY KAPALI</div>
      </div>

      <div class="premium-wallet-kpis">
        <div><small>ADAY CÜZDAN</small><b>${esc(candidates)}</b><span>${esc(source)} kaynak</span></div>
        <div><small>BAŞARILI DOĞRULAMA</small><b>${esc(successful)}</b><span>qualification_state</span></div>
        <div><small>AKTİF BALİNA KANITI</small><b>${esc(whales)}</b><span>whale snapshot</span></div>
        <div><small>HOLDINGS CÜZDANI</small><b>${esc(holdingWallets)}</b><span>Arkham panel verisi</span></div>
        <div><small>PROVIDER</small><b>${provider?.configured === true ? 'BAĞLI' : 'KISITLI'}</b><span>${esc(provider?.provider || provider?.state || '—')}</span></div>
      </div>

      <div class="premium-wallet-note"><b>82 / 100 GİBİ HAYALİ PUAN YOK.</b> Bu ekran yalnız gerçek kayıtları gösterir: aday kaynağı, başarı durumu, örneklem derinliği, balina yönü, holdings ve değişim kanıtı. Başarı oranı backend tarafından üretilmiyorsa yüzde uydurulmaz.</div>

      <div class="premium-wallet-layout">
        <section class="premium-wallet-card">
          <div class="premium-wallet-card-head"><div><small>NEDEN İZLENİYOR?</small><b>ADAY CÜZDANLAR</b></div><span>${rows.length} DETAY SATIRI</span></div>
          <div class="premium-wallet-scroll"><table class="premium-wallet-table">
            <thead><tr><th>CÜZDAN</th><th>NEDEN ADAY?</th><th>BAŞARI / ÖRNEKLEM</th><th>BALİNA / YÖN</th><th>SON HAREKET</th><th>İLGİLİ TOKENLAR</th><th>KANIT GÜVENİ</th><th>DETAY</th></tr></thead>
            <tbody>${tableRows(rows)}</tbody>
          </table></div>
          <div class="wallet-confidence-help"><b>KANIT GÜVENİ</b> bir trade skoru değildir. Yalnız SUCCESSFUL durumu, örneklem derinliği ve balina/holdings kanıtının ne kadar dolu olduğunu özetleyen arayüz etiketi olarak kullanılır.</div>
        </section>

        <aside class="premium-wallet-card premium-wallet-side" id="premiumWalletSelected">${selectedHtml(selected)}</aside>
      </div>`;
  }

  async function openWallet(){
    const modal = ensureModal();
    const body = document.getElementById('premiumWalletBody');
    modal.classList.add('open');
    body.innerHTML = '<div class="premium-wallet-loading"><div><b>CÜZDAN KANITLARI OKUNUYOR...</b><span>Canonical aday kayıtları, başarı örneklemi, balina ve holdings verisi birleştiriliyor.</span></div></div>';
    try {
      const [brief,detail] = await Promise.all([
        get('/api/wallet-brief-v3'),
        get('/api/wallet-intelligence-v2')
      ]);
      if (!modal.classList.contains('open')) return;
      body.innerHTML = render(brief,detail);
    } catch (error) {
      body.innerHTML = `<div class="premium-wallet-loading"><div><b class="neg">CÜZDAN VERİSİ ALINAMADI</b><span>${esc(error.message)}</span></div></div>`;
    }
  }

  document.addEventListener('click',event => {
    const detailButton = event.target.closest('#walletDetailButton');
    const nav = event.target.closest('[data-nav="wallet"]');
    const select = event.target.closest('[data-wallet-select]');

    if (select && payloadCache) {
      event.preventDefault();
      event.stopPropagation();
      selectedWallet = select.dataset.walletSelect;
      const row = payloadCache.rows.find(item => norm(item.wallet_uid) === norm(selectedWallet));
      const target = document.getElementById('premiumWalletSelected');
      if (target) target.innerHTML = selectedHtml(row);
      return;
    }

    if (!detailButton && !nav) return;
    event.preventDefault();
    event.stopPropagation();
    event.stopImmediatePropagation();
    openWallet();
  },true);

  document.addEventListener('keydown',event => {
    if (event.key === 'Escape') document.getElementById('premiumWalletModal')?.classList.remove('open');
  });
})();
