(() => {
  'use strict';

  const $ = id => document.getElementById(id);
  const $$ = selector => [...document.querySelectorAll(selector)];
  const n = value => {
    if(value === null || value === undefined || value === '') return null;
    const x = Number(value);
    return Number.isFinite(x) ? x : null;
  };
  const esc = value => String(value ?? '').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;').replaceAll("'",'&#039;');
  const short = value => { const s = String(value || '').trim(); return !s ? '—' : s.length > 22 ? `${s.slice(0,9)}…${s.slice(-8)}` : s; };
  const money = value => { const x=n(value); return x===null?'—':`${x<0?'-':''}$${Math.abs(x).toLocaleString('tr-TR',{minimumFractionDigits:2,maximumFractionDigits:2})}`; };
  const num = value => { const x=n(value); return x===null?'—':x.toLocaleString('tr-TR',{maximumFractionDigits:8}); };
  const pct = value => { const x=n(value); return x===null?'—':`${x>0?'+':''}${x.toFixed(2)}%`; };
  const cls = value => { const x=n(value); return x===null?'':x>0?'pos':x<0?'neg':''; };
  const get = async url => { const r=await fetch(url,{cache:'no-store'}); const d=await r.json().catch(()=>({})); if(!r.ok) throw new Error(d.detail||`${url} ${r.status}`); return d; };
  const post = async (url,payload) => { const r=await fetch(url,{method:'POST',cache:'no-store',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)}); const d=await r.json().catch(()=>({})); if(!r.ok) throw new Error(d.detail||`${url} ${r.status}`); return d; };
  const stateBadge = value => { const s=String(value||'COLD').toUpperCase(); const k=['HOT','WARM','COLD'].includes(s)?s.toLowerCase():'cold'; return `<span class="state ${k}">${esc(s)}</span>`; };
  const formatTime = value => { if(!value) return '—'; const d=new Date(value); return Number.isNaN(d.getTime())?esc(value):d.toLocaleString('tr-TR',{day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit'}); };

  const LEDGER_PAGE_SIZE = 200;
  const MAX_LEDGER_PAGES = 25;

  let dashboard=null, universe=null, ledger=null, walletBrief=null, walletDetail=null, market=null, calendar=null;
  let radarFilter='ALL';
  let selectedWallet=null;

  function showPage(page){
    $$('.terminal-page').forEach(node=>node.classList.toggle('active',node.dataset.page===page));
    $$('.nav-item').forEach(node=>node.classList.toggle('active',node.dataset.pageTarget===page));
    window.scrollTo({top:0,behavior:'instant'});
  }

  async function getAccountingLedger(){
    const rows=[];
    const seenIds=new Set();
    let beforeId=null;
    let pages=0;
    let authority=null;

    while(pages<MAX_LEDGER_PAGES){
      const suffix=beforeId===null?'':`&before_id=${encodeURIComponent(beforeId)}`;
      const page=await get(`/api/accounting-ledger-v2?limit=${LEDGER_PAGE_SIZE}${suffix}`);
      const pageRows=Array.isArray(page?.rows)?page.rows:[];
      authority=page?.authority||authority;

      for(const row of pageRows){
        const id=row?.id;
        if(id===null||id===undefined||seenIds.has(String(id))) continue;
        seenIds.add(String(id));
        rows.push(row);
      }

      pages+=1;
      const next=page?.next_before_id;
      if(next===null||next===undefined||pageRows.length===0) break;
      if(beforeId!==null && String(next)===String(beforeId)) break;
      beforeId=next;
    }

    return {rows,pages,authority,complete:beforeId===null||pages<MAX_LEDGER_PAGES};
  }

  function accountingSummary(rows,dashboardSummary={}){
    const source=Array.isArray(rows)?rows:[];
    const openRows=source.filter(row=>String(row?.status||'OPEN').toUpperCase()!=='CLOSED');
    const closedRows=source.filter(row=>String(row?.status||'').toUpperCase()==='CLOSED');
    const openInvestment=openRows.reduce((sum,row)=>sum+(n(row?.entry_amount_usdt??row?.amount_usdt)||0),0);
    const realizedNet=closedRows.reduce((sum,row)=>sum+(n(row?.net_pnl_usdt??row?.net_pnl)||0),0);
    const wins=closedRows.filter(row=>(n(row?.net_pnl_usdt??row?.net_pnl)||0)>0).length;
    const losses=closedRows.filter(row=>(n(row?.net_pnl_usdt??row?.net_pnl)||0)<0).length;
    return {
      openCount: openRows.length,
      closedCount: closedRows.length,
      openInvestment,
      realizedNet,
      wins,
      losses,
      dashboardOpenCount: dashboardSummary?.open_count,
      dashboardOpenInvestment: dashboardSummary?.open_investment,
    };
  }

  function candidateName(row){ return row.display_name || short(row.token0 || row.token1 || row.pool); }

  function plainMarketRead(row){
    const seismic=row?.seismic || {};
    const change=n(row?.change_5m_pct);
    const volume=n(seismic.volume_z);
    const txns=n(seismic.txns_z);
    const liquidity=n(seismic.liquidity_ratio);

    if(liquidity!==null && liquidity<0.70){
      return 'Likidite hızla zayıflıyor';
    }

    if(
      change!==null &&
      change>0 &&
      volume!==null &&
      volume>1 &&
      txns!==null &&
      txns>1
    ){
      return 'Fiyat, hacim ve ilgi güçleniyor';
    }

    if(
      change!==null &&
      change<0 &&
      volume!==null &&
      volume>1
    ){
      return 'Satış baskısı güçleniyor';
    }

    if(
      volume!==null &&
      volume>1 &&
      txns!==null &&
      txns>1
    ){
      return 'Hacim ve işlem ilgisi hızlanıyor';
    }

    if(change!==null && change>0){
      return 'Kısa vadeli yön yukarı';
    }

    if(change!==null && change<0){
      return 'Kısa vadeli yön aşağı';
    }

    return 'Dengeli · izleniyor';
  }
  function radarRows(rows){
    return rows.length ? rows.map(row=>{
      const seismic=row.seismic||{};
      return `<tr>
        <td>${stateBadge(row.state)}</td>
        <td><div class="token-cell"><b>${esc(candidateName(row))}</b><small>${esc(short(row.pool))}</small></div></td>
        <td>${esc(plainMarketRead(row))}</td>
        <td>${esc(row.txns_5m ?? '—')}</td>
        <td>${num(row.price_usd)}</td>
        <td class="${cls(row.change_5m_pct)}">${pct(row.change_5m_pct)}</td>
        <td>${money(row.volume_24h_usd)}</td>
        <td>${money(row.liquidity_usd)}</td>
        <td>${formatTime(row.snapshot_at)}</td>
      </tr>`;
    }).join('') : '<tr><td colspan="9" class="muted">Güncel DEX pool kaydı yok.</td></tr>';
  }

  function renderDashboard(){
    const s=dashboard?.summary||{};
    $('metricEquity').textContent=money(s.equity);
    $('metricDailyPnl').textContent=money(s.daily_pnl); $('metricDailyPnl').className=cls(s.daily_pnl);
    $('metricDailyMeta').textContent=s.local_date||'—';
    $('metricRealizedPnl').textContent=money(s.realized_net); $('metricRealizedPnl').className=cls(s.realized_net);
    $('metricRealizedPct').textContent=pct(s.total_pnl && s.starting_capital ? s.total_pnl/s.starting_capital*100 : null);
    $('metricOpenCount').textContent=s.open_count??'—'; $('metricExposure').textContent=money(s.open_investment);
    $('metricRisk').textContent=pct(s.risk_used_pct); $('metricRiskAmount').textContent=money(s.open_risk);
    $('positionsCount').textContent=s.open_count??'—'; $('positionsInvestment').textContent=money(s.open_investment); $('positionsPnl').textContent=money(s.open_pnl); $('positionsPnl').className=cls(s.open_pnl); $('positionsRisk').textContent=pct(s.risk_used_pct);
    const health=dashboard?.health||{}; $('topSystemState').textContent=health.status==='ok'?'PANEL + PAPER VERİSİ AKTİF':'PANEL DURUMU KISITLI';
    const generated=dashboard?.generated_at||new Date().toISOString(); $('topUpdatedAt').textContent=formatTime(generated); $('footerUpdatedAt').textContent=`Son güncelleme ${formatTime(generated)}`;
    renderHomePositions(); renderHomeHistory(); renderPositions(); renderHistory(); renderVezirOps();
  }

  function renderHomePositions(){
    const rows=(dashboard?.positions||[]).slice(0,5);
    $('homePositionRows').innerHTML=rows.length?rows.map(row=>`<tr><td><b>${esc(row.symbol||short(row.token))}</b></td><td>${num(row.entry_price)}</td><td>${num(row.current_price??row.entry_price)}</td><td>${money(row.entry_amount_usdt)}</td><td class="${cls(row.net_pnl_usdt??row.net_pnl)}">${money(row.net_pnl_usdt??row.net_pnl)}</td></tr>`).join(''):'<tr><td colspan="5" class="muted">Açık paper pozisyon yok.</td></tr>';
  }
  function closedRows(){ return (ledger?.rows||[]).filter(row=>String(row.status||'').toUpperCase()==='CLOSED'); }
  function renderHomeHistory(){
    const rows=closedRows().slice(0,5);
    $('homeHistoryRows').innerHTML=rows.length?rows.map(row=>`<tr><td><b>${esc(row.symbol||short(row.token))}</b></td><td>${num(row.exit_price??row.current_price)}</td><td class="${cls(row.net_pnl_usdt??row.net_pnl)}">${money(row.net_pnl_usdt??row.net_pnl)}</td><td>${esc(row.close_reason||'—')}</td></tr>`).join(''):'<tr><td colspan="4" class="muted">Kapanmış işlem yok.</td></tr>';
  }
  function renderPositions(){
    const rows=dashboard?.positions||[];
    $('positionRows').innerHTML=rows.length?rows.map(row=>`<tr><td><div class="token-cell"><b>${esc(row.symbol||short(row.token))}</b><small>#${esc(row.id??'—')}</small></div></td><td>${esc(short(row.pool))}</td><td>${esc(row.trade_policy||'PAPER')}</td><td>${num(row.entry_price)}</td><td>${num(row.current_price??row.entry_price)}</td><td>${money(row.entry_amount_usdt)}</td><td class="${cls(row.net_pnl_usdt??row.net_pnl)}">${money(row.net_pnl_usdt??row.net_pnl)}</td><td class="${cls(row.roi_pct)}">${pct(row.roi_pct)}</td><td><button class="action-btn" data-preview-position="${esc(row.id)}">SATIŞI İNCELE</button></td></tr>`).join(''):'<tr><td colspan="9" class="muted">Açık paper pozisyon yok.</td></tr>';
  }
  function renderHistory(){
    const rows=closedRows();
    const summary=accountingSummary(ledger?.rows||[],dashboard?.summary||{});
    $('historyCount').textContent=summary.closedCount;
    $('historyWins').textContent=summary.wins;
    $('historyLosses').textContent=summary.losses;
    $('historyPnl').textContent=money(summary.realizedNet); $('historyPnl').className=cls(summary.realizedNet);
    $('historyMeta').textContent=`${summary.closedCount} kapanmış kayıt · ${ledger?.pages||1} sayfa`;
    $('historyRows').innerHTML=rows.length?rows.map(row=>`<tr><td>${esc(row.id??'—')}</td><td><b>${esc(row.symbol||short(row.token))}</b></td><td>${num(row.entry_price)}</td><td>${num(row.exit_price??row.current_price)}</td><td class="${cls(row.net_pnl_usdt??row.net_pnl)}">${money(row.net_pnl_usdt??row.net_pnl)}</td><td class="${cls(row.roi_pct)}">${pct(row.roi_pct??(n(row.roi)!==null?n(row.roi)*100:null))}</td><td>${esc(row.close_reason||'—')}</td><td>${formatTime(row.closed_at??row.created_at)}</td></tr>`).join(''):'<tr><td colspan="8" class="muted">Kapanmış işlem yok.</td></tr>';
  }

  function renderRadar(){
    const counts=universe?.counts||{}; $('radarHot').textContent=counts.HOT??'—'; $('radarWarm').textContent=counts.WARM??'—'; $('radarCold').textContent=counts.COLD??'—'; $('radarVisible').textContent=universe?.visible_count??'—'; $('radarSource').textContent=universe?.source||'—';
    const all=Array.isArray(universe?.rows)?universe.rows:[]; const filtered=radarFilter==='ALL'?all:all.filter(r=>String(r.state||'').toUpperCase()===radarFilter); $('radarRows').innerHTML=radarRows(filtered);
    const home=all.slice(0,6); $('homeRadarRows').innerHTML=home.length?home.map(row=>{ const seismic=row.seismic||{}; return `<tr><td>${stateBadge(row.state)}</td><td><div class="token-cell"><b>${esc(candidateName(row))}</b><small>${esc(short(row.pool))}</small></div></td><td>${esc(plainMarketRead(row))}</td><td>${esc(row.txns_5m ?? '—')}</td><td>${money(row.volume_24h_usd)}</td><td class="${cls(row.change_5m_pct)}">${pct(row.change_5m_pct)}</td><td>${money(row.liquidity_usd)}</td></tr>`; }).join(''):'<tr><td colspan="7" class="muted">Güncel DEX radar kaydı yok.</td></tr>'; $('homeRadarCount').textContent=`${home.length} görünür`;
  }

  function candidateReason(row){ const source=String(row?.discovery_source||row?.source||'').toUpperCase(); if(source==='TRANSACTION_FROM_ONLY')return 'BSC işlem akışında gönderen cüzdan olarak gözlendi.'; if(source.includes('ARKHAM'))return 'Harici on-chain istihbarat kaynağında gözlendi.'; if(source==='REGISTRY')return 'Canonical aday kayıt defterinde aktif.'; return source?`${source.replaceAll('_',' ')} kaynağından aday.`:'Aday kaynağı henüz ayrıntılandırılmadı.'; }
  function mergeWalletRows(){ const brief=Array.isArray(walletBrief?.rows)?walletBrief.rows:[]; const detail=Array.isArray(walletDetail?.rows)?walletDetail.rows:[]; const rich=new Map(detail.map(r=>[String(r.wallet_uid||'').toLowerCase(),r])); const out=[]; const seen=new Set(); [...brief,...detail].forEach(base=>{const key=String(base.wallet_uid||'').toLowerCase(); if(!key||seen.has(key))return; out.push({...base,...(rich.get(key)||{})}); seen.add(key);}); return out; }
  function renderWallet(){
    const rows=mergeWalletRows(); const candidates=n(walletBrief?.candidates)??n(walletDetail?.tracked_wallets)??rows.length; const successful=n(walletBrief?.successful)??n(walletDetail?.successful_wallets)??0; const whales=n(walletDetail?.active_whales)??0; const hold=Array.isArray(walletDetail?.arkham_holdings?.wallets)?walletDetail.arkham_holdings.wallets.length:0; const provider=walletDetail?.provider||{};
    $('walletCandidateCount').textContent=candidates; $('walletSuccessful').textContent=successful; $('walletWhaleCount').textContent=whales; $('walletHoldingsCount').textContent=hold; $('walletProvider').textContent=provider.configured===true?'BAĞLI':'KISITLI';
    $('walletRows').innerHTML=rows.length?rows.map(row=>{const sample=n(row.success_sample_depth); const success=String(row.success_state||'HENÜZ DOĞRULANMADI').replaceAll('_',' '); const whale=String(row.whale_state||'YOK').replaceAll('_',' '); const dir=String(row.whale_direction||'YÖN YOK').replaceAll('_',' '); return `<tr><td><div class="token-cell"><b>${esc(short(row.wallet_uid))}</b><small>${esc(row.chain||'BSC')}</small></div></td><td>${esc(candidateReason(row))}</td><td><b>${esc(success)}</b><br><span class="muted">${sample===null?'örneklem yok':`örneklem ${sample}`}</span></td><td>${esc(whale)}<br><span class="muted">${esc(dir)}</span></td><td>${esc(String(row.candidate_state||row.freshness_state||'OBSERVED').replaceAll('_',' '))}</td><td><button class="action-btn" data-wallet="${esc(row.wallet_uid)}">İNCELE</button></td></tr>`;}).join(''):'<tr><td colspan="6" class="muted">Aday cüzdan verisi yok.</td></tr>';
    if(!selectedWallet&&rows[0]) selectedWallet=rows[0].wallet_uid; renderWalletDetail(rows.find(r=>String(r.wallet_uid)===String(selectedWallet))||null);
  }
  function renderWalletDetail(row){
    const box=$('walletDetail'); if(!row){box.innerHTML='<div class="empty-state">Bir cüzdan seç.</div>';return;} const holdings=(walletDetail?.arkham_holdings?.wallets||[]).find(w=>String(w.wallet_uid||w.address||'').toLowerCase()===String(row.wallet_uid||'').toLowerCase()); const sample=n(row.success_sample_depth);
    box.innerHTML=`<div class="wallet-detail"><div class="wallet-title"><div class="wallet-avatar">W</div><div><h3>${esc(short(row.wallet_uid))}</h3><small>${esc(row.chain||'BSC')} · ${esc(short(row.address||row.wallet_uid))}</small></div></div><div class="wallet-note"><b>Neden izleniyor?</b><br>${esc(candidateReason(row))}</div><div class="wallet-facts"><div><small>BAŞARI DURUMU</small><b>${esc(String(row.success_state||'DOĞRULANMADI').replaceAll('_',' '))}</b></div><div><small>ÖRNEKLEM</small><b>${sample===null?'YOK':sample}</b></div><div><small>BALİNA DURUMU</small><b>${esc(String(row.whale_state||'YOK').replaceAll('_',' '))}</b></div><div><small>BALİNA YÖNÜ</small><b>${esc(String(row.whale_direction||'YÖN YOK').replaceAll('_',' '))}</b></div><div><small>HOLDINGS DEĞERİ</small><b>${money(holdings?.total_value_usd)}</b></div><div><small>VARLIK SAYISI</small><b>${holdings?.asset_count??'—'}</b></div></div><div class="wallet-note">Bu ekran gerçek kanıtı gösterir. Backend başarı yüzdesi üretmiyorsa yüzde gösterilmez.</div></div>`;
  }

  function newsCards(rows){ return rows.length?rows.map(row=>`<article class="news-card"><div class="news-top"><div>${stateBadge(row.state)}</div><div class="news-title">${esc(row.title_tr||row.source_title||'PİYASA')}</div><div class="news-score">${esc(row.importance_score??'—')}/100</div></div><div class="news-scope">${esc(row.market_scope_tr||'GENEL KRİPTO')}</div><div class="news-summary">${esc(row.summary_tr||'Etki özeti yok.')}</div><div class="news-action"><b>OPERASYON NOTU</b> · ${esc(row.recommendation_tr||'Fiyat, hacim ve likidite teyidi bekle.')}</div>${row.source_title?`<div class="news-source">ORİJİNAL · ${esc(row.source_title)}</div>`:''}</article>`).join(''):'<div class="empty-state">Güncel kayıt yok.</div>'; }
  function renderMarket(){ const news=Array.isArray(market?.items)?market.items:[]; const launches=Array.isArray(market?.launch_items)?market.launch_items:[]; const cal=Array.isArray(calendar?.items)?calendar.items:[]; $('newsCount').textContent=`${news.length} kayıt`; $('newsRows').innerHTML=newsCards(news); $('launchCount').textContent=`${launches.length} kayıt`; $('launchRows').innerHTML=newsCards(launches); $('calendarCount').textContent=`${cal.length} kayıt`; $('calendarRows').innerHTML=cal.length?cal.map(row=>`<article class="calendar-card"><small>${esc(row.market_scope_tr||'GENEL KRİPTO')} · ${esc(row.state||'COLD')} · ${esc(row.importance_score??'—')}/100</small><h3>${esc(row.title_tr||'EKONOMİK VERİ')}</h3><p>${esc(row.summary_tr||'Piyasa etkisi için izleniyor.')}</p><div class="news-action"><b>OPERASYON NOTU</b> · ${esc(row.recommendation_tr||'Fiyat tepkisini izle.')}</div></article>`).join(''):'<div class="empty-state">WARM/HOT makro olay yok.</div>'; $('homeNewsRows').innerHTML=news.slice(0,5).map(row=>`<div class="feed-item"><small>${esc(row.state||'—')}</small><b>${esc(row.title_tr||row.source_title||'PİYASA')}</b><span>${esc(row.importance_score??'—')}/100</span></div>`).join('')||'<div class="empty-state">Güncel haber yok.</div>'; }

  function renderVezirOps(){ const s=dashboard?.summary||{}; const radarCount=universe?.visible_count??'—'; const walletCount=walletBrief?.candidates??'—'; const newsCount=Array.isArray(market?.items)?market.items.length:'—'; $('homeVezirFacts').innerHTML=`<div class="mini-fact"><small>AÇIK İŞLEM</small><b>${esc(s.open_count??'—')}</b></div><div class="mini-fact"><small>RADAR POOL</small><b>${esc(radarCount)}</b></div><div class="mini-fact"><small>CÜZDAN ADAYI</small><b>${esc(walletCount)}</b></div><div class="mini-fact"><small>HABER</small><b>${esc(newsCount)}</b></div>`; $('vezirOps').innerHTML=`<div class="ops-section"><small>PAPER PORTFÖY</small><b>${esc(s.open_count??'—')} açık pozisyon · ${money(s.open_investment)} maruziyet</b><p>Modellenen risk ${pct(s.risk_used_pct)}. Risk ve maruziyet aynı kavram değildir.</p></div><div class="ops-section"><small>DEX RADAR</small><b>${esc(radarCount)} görünür pool</b><p>HOT/WARM/COLD evreni BSC pool readmodelinden gelir.</p></div><div class="ops-section"><small>CÜZDAN KANITI</small><b>${esc(walletCount)} aday</b><p>Başarı oranı üretilmiyorsa panel yüzdesel skor uydurmaz.</p></div><div class="ops-section"><small>PİYASA BAĞLAMI</small><b>${esc(newsCount)} önemli haber</b><p>Haber tek başına DEX alım veya satış sinyali değildir.</p></div>`; }

  async function previewPosition(id){ const row=(dashboard?.positions||[]).find(r=>String(r.id)===String(id)); if(!row)return; const box=$('positionPreview'); box.classList.add('open'); box.innerHTML='<div class="drawer-empty">Taze pool fiyatı okunuyor...</div>'; try{ const data=await post('/api/manual-paper/preview-v2',{position_id:row.id,pool:row.pool,token:row.token}); box.innerHTML=`<div class="preview-grid"><div><small>TOKEN</small><b>${esc(row.symbol||short(row.token))}</b></div><div><small>GİRİŞ</small><b>${num(row.entry_price)}</b></div><div><small>TAZE REFERANS</small><b>${num(data.reference_price)}</b></div><div><small>TAHMİNİ NET PNL</small><b class="${cls(data.net_pnl_usdt)}">${money(data.net_pnl_usdt)}</b></div><div><small>ROI</small><b class="${cls(data.roi_pct)}">${pct(data.roi_pct)}</b></div></div><div class="preview-note">${esc(data.guidance||data.sell_guidance||'Satış kararı için taze pool fiyatı ve mevcut plan birlikte değerlendirilmeli.')}</div>`; }catch(e){ box.innerHTML=`<div class="drawer-empty">Satış önizlemesi alınamadı: ${esc(e.message)}</div>`; } }

  function addChat(text,kind='vezir'){ const box=$('vezirMessages'); const div=document.createElement('div'); div.className=`chat-msg ${kind}`; div.textContent=text; box.appendChild(div); box.scrollTop=box.scrollHeight; }
  async function askVezir(question){ const q=String(question||$('vezirInput')?.value||'').trim(); if(!q)return; if($('vezirInput'))$('vezirInput').value=''; addChat(q,'user'); try{ const data=await post('/api/vezir/ask',{question:q}); addChat(data.answer||'Yanıt alınamadı.'); $('homeVezirAnswer').textContent=data.answer||'Yanıt alınamadı.'; }catch(e){ addChat(`Yanıt alınamadı: ${e.message}`); } }

  async function loadAll(){
    const jobs=[['dashboard','/api/dashboard'],['universe','/api/universe-panel'],['walletBrief','/api/wallet-brief-v3'],['walletDetail','/api/wallet-intelligence-v2'],['market','/api/market-brief-v3'],['calendar','/api/calendar-brief-v3']];
    const [results,ledgerResult]=await Promise.all([
      Promise.all(jobs.map(async ([key,url])=>{try{return [key,await get(url)]}catch(e){console.warn(key,e);return [key,null]}})),
      getAccountingLedger().catch(e=>{console.warn('ledger',e);return null;})
    ]);
    for(const [key,value] of results){ if(key==='dashboard')dashboard=value; if(key==='universe')universe=value; if(key==='walletBrief')walletBrief=value; if(key==='walletDetail')walletDetail=value; if(key==='market')market=value; if(key==='calendar')calendar=value; }
    if(ledgerResult) ledger=ledgerResult;
    renderDashboard(); renderRadar(); renderWallet(); renderMarket(); renderVezirOps();
  }

  document.addEventListener('click',e=>{
    const nav=e.target.closest('[data-page-target]'); if(nav){showPage(nav.dataset.pageTarget);return;}
    const go=e.target.closest('[data-go]'); if(go){showPage(go.dataset.go);return;}
    const filter=e.target.closest('[data-radar-filter]'); if(filter){radarFilter=filter.dataset.radarFilter; $$('[data-radar-filter]').forEach(b=>b.classList.toggle('active',b===filter)); renderRadar();return;}
    const prev=e.target.closest('[data-preview-position]'); if(prev){previewPosition(prev.dataset.previewPosition);return;}
    const w=e.target.closest('[data-wallet]'); if(w){selectedWallet=w.dataset.wallet; renderWallet();return;}
    const ask=e.target.closest('[data-quick-ask]'); if(ask){showPage('vezir'); askVezir(ask.dataset.quickAsk);return;}
    if(e.target.closest('#vezirSend')) askVezir();
  });
  $('vezirInput')?.addEventListener('keydown',e=>{if(e.key==='Enter')askVezir();});

  loadAll();
  setInterval(()=>{ if(!document.hidden) loadAll(); },30000);
})();
(() => {
  'use strict';

  const $ = id => document.getElementById(id);
  const esc = value => String(value ?? '')
    .replaceAll('&','&amp;')
    .replaceAll('<','&lt;')
    .replaceAll('>','&gt;')
    .replaceAll('"','&quot;')
    .replaceAll("'","&#039;");

  const num = value => {
    const x = Number(value);
    return Number.isFinite(x) ? x : null;
  };

  const money = value => {
    const x = num(value);
    return x === null
      ? '—'
      : `${x < 0 ? '-' : ''}$${Math.abs(x).toLocaleString(
          'tr-TR',
          {minimumFractionDigits:2,maximumFractionDigits:2}
        )}`;
  };

  const pct = value => {
    const x = num(value);
    return x === null ? '—' : `${x > 0 ? '+' : ''}${x.toFixed(2)}%`;
  };

  const get = async url => {
    const r = await fetch(url,{cache:'no-store'});
    const d = await r.json().catch(() => ({}));
    if(!r.ok) throw new Error(d.detail || `${r.status}`);
    return d;
  };

  const post = async (url,payload) => {
    const r = await fetch(url,{
      method:'POST',
      cache:'no-store',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify(payload)
    });
    const d = await r.json().catch(() => ({}));
    if(!r.ok) throw new Error(d.detail || `${r.status}`);
    return d;
  };

  let market = null;
  let calendar = null;
  let dashboard = null;

  function modal(){
    let shell = $('v61Modal');
    if(shell) return shell;

    shell = document.createElement('div');
    shell.id = 'v61Modal';
    shell.className = 'v61-modal';
    shell.innerHTML = `
      <div class="v61-modal-card">
        <div class="v61-modal-head">
          <h3 id="v61ModalTitle">DETAY</h3>
          <button class="v61-modal-close" type="button">×</button>
        </div>
        <div class="v61-modal-body" id="v61ModalBody"></div>
      </div>`;

    document.body.appendChild(shell);

    shell.querySelector('.v61-modal-close')
      .addEventListener('click',()=>shell.classList.remove('open'));

    shell.addEventListener('click',e=>{
      if(e.target===shell) shell.classList.remove('open');
    });

    return shell;
  }

  function openModal(title,html){
    const shell = modal();
    $('v61ModalTitle').textContent = title;
    $('v61ModalBody').innerHTML = html;
    shell.classList.add('open');
  }

  function closeModal(){
    modal().classList.remove('open');
  }

  function validUrl(value){
    const s = String(value || '').trim();
    return /^https?:\/\//i.test(s) ? s : null;
  }

  function contextType(row){
    const text = `${row?.title_tr || ''} ${row?.source_title || ''}`.toLowerCase();

    if(/hack|exploit|çal|saldırı|security|drain/.test(text)) return 'SECURITY';
    if(/regül|regulat|sec |law|yasa|mahkeme/.test(text)) return 'REGULATION';
    if(/cpi|enflasyon|faiz|fed|ecb|ppi|gdp|işsizlik|payroll/.test(text)) return 'MACRO';
    if(/etf|institution|kurumsal|fund|fon/.test(text)) return 'INSTITUTIONAL';
    if(/airdrop|ido|ico|tge|listing|launch|token/.test(text)) return 'LAUNCH';
    return 'MARKET';
  }

  function scenarios(row){
    const score = num(row?.importance_score) ?? 50;
    const type = contextType(row);

    const map = {
      SECURITY:{
        positive:'Olay sınırlı kalır, kayıp büyümez ve likidite çıkışı yayılmazsa piyasa baskısı kısa sürebilir.',
        negative:'Yeni cüzdanlara veya protokollere bulaşma görülürse likidite çekilmesi ve sert riskten kaçış oluşabilir.',
        action:'Etkilenen tokenlarda likidite, büyük cüzdan çıkışları ve satış hacmini özellikle izle.'
      },
      REGULATION:{
        positive:'Metin kapsamı net ve DEX erişimini doğrudan sınırlamıyorsa belirsizlik azalabilir.',
        negative:'Kapsam genişler veya erişim/uyum yükü artarsa risk primi ve satış baskısı yükselebilir.',
        action:'Başlıktan işlem açma; resmi metin ve fiyat-hacim teyidini birlikte bekle.'
      },
      MACRO:{
        positive:'Veri beklentiden daha risk-dostu okunursa BTC/ETH üzerinden kripto risk iştahı güçlenebilir.',
        negative:'Beklentiden sert veya şahin sonuç, dolar/faiz baskısıyla kriptoda satış dalgası oluşturabilir.',
        action:'Açıklama sonrası ilk hareket yerine BTC/ETH yönü ve hacmin kalıcılığını teyit et.'
      },
      INSTITUTIONAL:{
        positive:'Gerçek para girişi veya kabul haberi teyit edilirse ana varlıklardan alt piyasalara risk iştahı yayılabilir.',
        negative:'Red, çıkış veya beklentinin fiyatlanmış olması ters hareket yaratabilir.',
        action:'Akış verisi ve spot hacim teyidi olmadan yalnız başlığa güvenme.'
      },
      LAUNCH:{
        positive:'Dağıtım şeffaf, likidite yeterli ve kilit açılımları kontrollüyse sağlıklı fiyat keşfi oluşabilir.',
        negative:'Düşük likidite, yoğun insider payı veya yakın unlock satış baskısını büyütebilir.',
        action:'Tokenomics, kontrat, likidite, unlock ve sosyal hesapları birlikte doğrula.'
      },
      MARKET:{
        positive:'Haber fiyat ve hacim tarafından teyit edilirse kısa vadeli momentum güçlenebilir.',
        negative:'Teyitsiz başlık veya düşük likidite hızlı ters harekete dönüşebilir.',
        action:'Fiyat, hacim, likidite ve on-chain akışı birlikte kontrol et.'
      }
    };

    const out = map[type];

    if(score >= 85){
      out.action += ' Etki skoru yüksek olduğu için açık pozisyonlarda maruziyeti ayrıca kontrol et.';
    }else if(score < 55){
      out.action += ' Etki skoru sınırlı; tek başına öncelikli işlem gerekçesi yapma.';
    }

    return out;
  }

  function links(row){
    const values = [
      ['KAYNAK',row?.url],
      ['WEBSITE',row?.website],
      ['X / TWITTER',row?.twitter || row?.x_url],
      ['TELEGRAM',row?.telegram],
      ['DISCORD',row?.discord]
    ];

    if(row?.socials && typeof row.socials === 'object'){
      values.push(
        ['X / TWITTER',row.socials.twitter || row.socials.x],
        ['TELEGRAM',row.socials.telegram],
        ['DISCORD',row.socials.discord]
      );
    }

    const seen = new Set();

    const html = values
      .map(([label,url])=>[label,validUrl(url)])
      .filter(([,url])=>url && !seen.has(url) && seen.add(url))
      .map(([label,url])=>`<a href="${esc(url)}" target="_blank" rel="noopener noreferrer">${esc(label)} ↗</a>`)
      .join('');

    return html ? `<div class="v61-links">${html}</div>` : '';
  }

  function intelDetail(row,kind){
    if(!row) return;

    const s = scenarios(row);
    const title = row.title_tr || row.source_title || 'PİYASA OLAYI';

    const actual = row.actual ?? row.actual_value;
    const forecast = row.forecast ?? row.consensus ?? row.expected;
    const previous = row.previous ?? row.previous_value;

    const values = (actual!=null || forecast!=null || previous!=null)
      ? `<div class="v61-grid">
          <div class="v61-box"><small>GERÇEKLEŞEN</small><b>${esc(actual ?? '—')}</b></div>
          <div class="v61-box"><small>BEKLENTİ</small><b>${esc(forecast ?? '—')}</b></div>
          <div class="v61-box"><small>ÖNCEKİ</small><b>${esc(previous ?? '—')}</b></div>
          <div class="v61-box"><small>ÜLKE / VARLIK</small><b>${esc(row.country || row.currency || row.market_scope_tr || '—')}</b></div>
        </div>`
      : '';

    openModal(
      `${kind} · ${title}`,
      `
      <div class="v61-grid">
        <div class="v61-box">
          <small>ETKİ SKORU</small>
          <b>${esc(row.importance_score ?? '—')}/100 · ${esc(row.state || '—')}</b>
        </div>
        <div class="v61-box">
          <small>ETKİ ALANI</small>
          <b>${esc(row.market_scope_tr || 'GENEL KRİPTO')}</b>
        </div>
      </div>

      ${values}

      <div class="v61-box" style="margin-top:10px">
        <small>NE OLDU?</small>
        <p>${esc(row.summary_tr || row.description_tr || row.source_title || 'Ayrıntılı özet kaynaktan gelmedi.')}</p>
      </div>

      <div class="v61-box v61-positive" style="margin-top:10px">
        <small>OLUMLU SENARYO</small>
        <p>${esc(s.positive)}</p>
      </div>

      <div class="v61-box v61-negative" style="margin-top:10px">
        <small>OLUMSUZ SENARYO</small>
        <p>${esc(s.negative)}</p>
      </div>

      <div class="v61-box v61-warning" style="margin-top:10px">
        <small>COINOSKOBI DEĞERLENDİRMESİ</small>
        <p>${esc(s.action)}</p>
      </div>

      ${row.recommendation_tr ? `
        <div class="v61-box" style="margin-top:10px">
          <small>MEVCUT OPERASYON NOTU</small>
          <p>${esc(row.recommendation_tr)}</p>
        </div>` : ''}

      ${kind === 'AIRDROP / IDO / ICO' ? `
        <div class="v61-grid" style="margin-top:10px">
          <div class="v61-box"><small>AĞ</small><b>${esc(row.chain || row.network || '—')}</b></div>
          <div class="v61-box"><small>OLAY TİPİ</small><b>${esc(row.launch_type || row.type || '—')}</b></div>
          <div class="v61-box"><small>TGE / LISTING</small><b>${esc(row.date || row.tge_date || row.listing_date || row.published_at || '—')}</b></div>
          <div class="v61-box"><small>TOKENOMICS / FDV</small><b>${esc(row.fdv || row.tokenomics || 'Kaynak vermedi')}</b></div>
        </div>` : ''}

      ${links(row)}
      `
    );
  }

  async function refreshData(){
    const jobs = await Promise.allSettled([
      get('/api/dashboard'),
      get('/api/market-brief-v3'),
      get('/api/calendar-brief-v3'),
      get('/api/v61/market-tickers')
    ]);

    if(jobs[0].status==='fulfilled') dashboard=jobs[0].value;
    if(jobs[1].status==='fulfilled') market=jobs[1].value;
    if(jobs[2].status==='fulfilled') calendar=jobs[2].value;
    if(jobs[3].status==='fulfilled') renderTickers(jobs[3].value);

    enhanceIntel();
  }

  function renderTickers(data){
    const top = document.querySelector('.topbar-status');
    if(!top) return;

    let shell = document.querySelector('.v61-tickers');

    if(!shell){
      shell=document.createElement('div');
      shell.className='v61-tickers';
      top.insertBefore(shell,top.firstChild);
    }

    const rows = Array.isArray(data?.items) ? data.items : [];

    shell.innerHTML = rows.map(row=>{
      const symbol=String(row.symbol||'').replace('USDT','/USDT');
      return `<div class="v61-ticker">
        <small>${esc(symbol)}</small>
        <b>${row.available ? `${money(row.price)} · ${pct(row.change_24h_pct)}` : 'VERİ YOK'}</b>
      </div>`;
    }).join('');
  }

  function appendDetailButtons(containerId,selector,kind,attr){
    const box=$(containerId);
    if(!box) return;

    [...box.querySelectorAll(selector)].forEach((node,index)=>{
      if(node.querySelector(`[${attr}]`)) return;

      const button=document.createElement('button');
      button.type='button';
      button.className='v61-button v61-detail-btn';
      button.textContent='İNCELE';
      button.setAttribute(attr,String(index));
      node.appendChild(button);
    });
  }

  function enhanceIntel(){
    appendDetailButtons(
      'newsRows',
      '.news-card',
      'HABER',
      'data-v61-news'
    );

    appendDetailButtons(
      'calendarRows',
      '.calendar-card',
      'TAKVİM',
      'data-v61-calendar'
    );

    appendDetailButtons(
      'launchRows',
      '.news-card',
      'AIRDROP / IDO / ICO',
      'data-v61-launch'
    );

    const launches=Array.isArray(market?.launch_items)
      ? market.launch_items
      : [];

    const launchBox=$('launchRows');

    if(launchBox && launches.length===0){
      if(!launchBox.querySelector('.v61-launch-empty')){
        launchBox.innerHTML=`
          <div class="v61-launch-empty">
            <b>Şu anda doğrulanmış launch kaydı yok.</b><br><br>
            Airdrop / IDO / ICO / TGE / listing feed'i 0 kayıt döndürüyor.
            Coinoskobi burada proje veya tarih uydurmuyor.
            Yeni kayıt geldiğinde proje bilgisi, etki değerlendirmesi,
            kaynak ve mevcut sosyal bağlantılar burada açılacak.
          </div>`;
      }
    }
  }

  const v61SellPreviews=new Map();

  function injectControls(){
    const positionsHead=document.querySelector(
      '.terminal-page[data-page="positions"] .full-card .card-head'
    );

    if(positionsHead && !positionsHead.querySelector('[data-v61-buy]')){
      const actions=document.createElement('div');
      actions.className='v61-inline-actions';
      actions.innerHTML=`
        <button class="v61-button paper" type="button" data-v61-buy>
          + MANUEL PAPER AL
        </button>`;
      positionsHead.appendChild(actions);
    }

    const walletHead=document.querySelector(
      '.terminal-page[data-page="wallet"] .page-head'
    );

    if(walletHead && !walletHead.querySelector('[data-v61-wallet-connect]')){
      const actions=document.createElement('div');
      actions.className='v61-inline-actions';
      actions.innerHTML=`
        <button class="v61-button" type="button" data-v61-wallet-connect>
          CÜZDAN BAĞLA · READ ONLY
        </button>`;
      walletHead.appendChild(actions);
    }
  }

  function manualBuy(){
    openModal(
      'MANUEL PAPER AL',
      `
      <div class="v61-box v61-warning">
        <small>YETKİ SINIRI</small>
        <p>Bu işlem yalnız PAPER_10K defterine yazılır. Live emir, wallet signing veya zincir işlemi oluşturmaz.</p>
      </div>

      <div class="v61-form" style="margin-top:12px">
        <label>TOKEN ADRESİ
          <input id="v61BuyToken" placeholder="0x...">
        </label>
        <label>POOL ADRESİ
          <input id="v61BuyPool" placeholder="0x...">
        </label>
        <label>SEMBOL
          <input id="v61BuySymbol" placeholder="TOKEN">
        </label>
        <label>YATIRIM · USDT
          <input id="v61BuyAmount" type="number" min="0.01" step="0.01" value="100">
        </label>
      </div>

      <div class="v61-actions">
        <button class="v61-button paper" type="button" data-v61-buy-confirm>
          PAPER ALIMI ONAYLA
        </button>
      </div>`
    );
  }

  async function confirmBuy(){
    const payload={
      side:'BUY',
      token:$('v61BuyToken')?.value?.trim(),
      pool:$('v61BuyPool')?.value?.trim(),
      symbol:$('v61BuySymbol')?.value?.trim(),
      amount_usdt:Number($('v61BuyAmount')?.value),
      confirmed:true
    };

    try{
      const data=await post('/api/manual-paper/order-v2',payload);

      openModal(
        'PAPER ALIM TAMAMLANDI',
        `<div class="v61-box v61-positive">
          <small>POZİSYON #${esc(data.position_id)}</small>
          <b>${esc(data.symbol || payload.symbol || 'TOKEN')}</b>
          <p>Referans fiyat: ${esc(data.reference_price)}</p>
          <p>Yatırım: ${money(data.amount_usdt)}</p>
          <p>Paper bakiye: ${money(data.paper_balance_after)}</p>
        </div>`
      );

      setTimeout(()=>location.reload(),1200);

    }catch(e){
      openModal(
        'PAPER ALIM REDDEDİLDİ',
        `<div class="v61-box v61-negative"><p>${esc(e.message)}</p></div>`
      );
    }
  }

  async function previewPosition(id){
    const rows=dashboard?.positions || [];
    const row=rows.find(x=>String(x.id)===String(id));

    if(!row){
      try{
        dashboard=await get('/api/dashboard');
      }catch(_){}
    }

    const fresh=(dashboard?.positions || [])
      .find(x=>String(x.id)===String(id));

    if(!fresh){
      openModal(
        'SATIŞ İNCELEMESİ',
        '<div class="v61-box v61-negative">Pozisyon bulunamadı.</div>'
      );
      return;
    }

    openModal(
      'SATIŞ İNCELEMESİ',
      '<div class="v61-box">Taze pool fiyatı okunuyor...</div>'
    );

    try{
      const data=await post(
        '/api/manual-paper/preview-v2',
        {
          position_id:fresh.id,
          pool:fresh.pool,
          token:fresh.token
        }
      );

      v61SellPreviews.set(
        String(fresh.id),
        {
          reference_price:data.reference_price,
          net_pnl_usdt:data.net_pnl_usdt,
          roi_pct:data.roi_pct,
          captured_at:Date.now()
        }
      );

      openModal(
        `SATIŞ İNCELEMESİ · ${fresh.symbol || fresh.id}`,
        `
        <div class="v61-grid">
          <div class="v61-box"><small>GİRİŞ</small><b>${esc(fresh.entry_price)}</b></div>
          <div class="v61-box"><small>TAZE REFERANS</small><b>${esc(data.reference_price)}</b></div>
          <div class="v61-box"><small>NET PNL</small><b>${money(data.net_pnl_usdt)}</b></div>
          <div class="v61-box"><small>ROI</small><b>${pct(data.roi_pct)}</b></div>
          <div class="v61-box"><small>5M HAREKET</small><b>${pct(data.change_5m_pct)}</b></div>
          <div class="v61-box"><small>BREAK EVEN</small><b>${esc(data.break_even_price ?? '—')}</b></div>
        </div>

        <div class="v61-box v61-warning" style="margin-top:10px">
          <small>${esc(data.guidance_label || 'DEĞERLENDİRME')}</small>
          <p>${esc(data.guidance_text || 'Taze fiyat ve mevcut plan birlikte değerlendirilmeli.')}</p>
        </div>

        <div class="v61-actions">
          <button
            class="v61-button paper"
            type="button"
            data-v61-sell-confirm="${esc(fresh.id)}">
            PAPER SATIŞI ONAYLA
          </button>
        </div>`
      );

    }catch(e){
      openModal(
        'SATIŞ İNCELEMESİ ALINAMADI',
        `<div class="v61-box v61-negative"><p>${esc(e.message)}</p></div>`
      );
    }
  }

  async function confirmSell(id){
    const row=(dashboard?.positions || [])
      .find(x=>String(x.id)===String(id));

    if(!row) return;

    const preview=v61SellPreviews.get(String(id)) || null;

    try{
      const data=await post(
        '/api/manual-paper/order-v2',
        {
          side:'SELL',
          position_id:row.id,
          pool:row.pool,
          token:row.token,
          confirmed:true,
          expected_reference_price:preview?.reference_price ?? null,
          expected_net_pnl_usdt:preview?.net_pnl_usdt ?? null
        }
      );

      openModal(
        'PAPER SATIŞ TAMAMLANDI',
        `<div class="v61-box v61-positive">
          <small>POZİSYON #${esc(data.position_id)}</small>
          <p>Çıkış referansı: ${esc(data.reference_price)}</p>
          <p>Net PNL: ${money(data.net_pnl_usdt)}</p>
          <p>ROI: ${pct(data.roi_pct)}</p>
        </div>`
      );

      setTimeout(()=>location.reload(),1200);

    }catch(e){
      openModal(
        'PAPER SATIŞ REDDEDİLDİ',
        `<div class="v61-box v61-negative"><p>${esc(e.message)}</p></div>`
      );
    }
  }

  function walletAddress(value){
    const match=String(value || '').match(/0x[a-fA-F0-9]{40}/);
    return match ? match[0] : null;
  }

  function walletConnect(){
    openModal(
      'CÜZDAN BAĞLA · READ ONLY',
      `
      <div class="v61-box">
        <small>READ ONLY</small>
        <p>Yalnız public BSC adresi okunur. Private key, seed phrase, imza veya işlem yetkisi istenmez.</p>
      </div>
      <div class="v61-form" style="margin-top:12px">
        <label style="grid-column:1/-1">BSC CÜZDAN ADRESİ
          <input id="v61WalletAddress" placeholder="0x...">
        </label>
      </div>
      <div class="v61-actions">
        <button class="v61-button" type="button" data-v61-wallet-load>
          VARLIKLARI GÖSTER
        </button>
      </div>`
    );
  }

  async function showWallet(address){
    const clean=walletAddress(address);

    if(!clean){
      openModal(
        'CÜZDAN İNCELEMESİ',
        '<div class="v61-box v61-negative">Geçerli BSC adresi bulunamadı.</div>'
      );
      return;
    }

    openModal(
      'CÜZDAN İNCELEMESİ',
      '<div class="v61-box">Holdings okunuyor...</div>'
    );

    try{
      const data=await get(
        `/api/v61/wallet-readonly?address=${encodeURIComponent(clean)}`
      );

      if(data.available!==true){
        openModal(
          'CÜZDAN İNCELEMESİ',
          `<div class="v61-box v61-warning">
             <small>PROVIDER</small>
             <p>${esc(data.reason || 'Holdings sağlayıcısı veri döndürmedi.')}</p>
           </div>`
        );
        return;
      }

      const rows=Array.isArray(data.holdings)
        ? data.holdings
        : [];

      const holdings=rows.length
        ? rows.map(row=>`
          <div class="v61-holding">
            <div>
              <b>${esc(row.symbol || row.name || row.token_id)}</b>
              <div class="v61-bar">
                <span style="width:${Math.max(0,Math.min(100,num(row.portfolio_pct)||0))}%"></span>
              </div>
            </div>
            <span>${esc(row.balance ?? '—')}</span>
            <span>${money(row.value_usd)}</span>
            <span>${pct(row.portfolio_pct)}</span>
          </div>`).join('')
        : '<div class="v61-box">Bu cüzdan için holdings kaydı dönmedi.</div>';

      openModal(
        `CÜZDAN · ${clean.slice(0,8)}…${clean.slice(-6)}`,
        `
        <div class="v61-grid">
          <div class="v61-box"><small>TOPLAM DEĞER</small><b>${money(data.total_value_usd)}</b></div>
          <div class="v61-box"><small>VARLIK SAYISI</small><b>${esc(data.returned_asset_count ?? rows.length)}</b></div>
        </div>
        <div class="v61-holding" style="margin-top:12px;font-weight:900">
          <span>VARLIK</span><span>MİKTAR</span><span>DEĞER</span><span>DAĞILIM</span>
        </div>
        ${holdings}
        `
      );

    }catch(e){
      openModal(
        'CÜZDAN İNCELEMESİ',
        `<div class="v61-box v61-negative"><p>${esc(e.message)}</p></div>`
      );
    }
  }


  async function showWalletRich(address){
    const clean=walletAddress(address);

    if(!clean){
      openModal(
        'CÜZDAN İNCELEMESİ',
        '<div class="v61-box v61-negative">Geçerli BSC adresi bulunamadı.</div>'
      );
      return;
    }

    openModal(
      'CÜZDAN İNCELEMESİ',
      '<div class="v61-box">Cüzdan profili ve varlıklar okunuyor...</div>'
    );

    const jobs=await Promise.allSettled([
      get(`/api/v61/wallet-readonly?address=${encodeURIComponent(clean)}`),
      get('/api/wallet-intelligence-v2'),
      get('/api/wallet-brief-v3')
    ]);

    const holdingsData=jobs[0].status==='fulfilled' ? jobs[0].value : {};
    const intelligence=jobs[1].status==='fulfilled' ? jobs[1].value : {};
    const brief=jobs[2].status==='fulfilled' ? jobs[2].value : {};

    const candidates=[
      ...(Array.isArray(intelligence?.rows)?intelligence.rows:[]),
      ...(Array.isArray(brief?.rows)?brief.rows:[])
    ];

    const context=candidates.find(row=>{
      const uid=String(row?.wallet_uid || row?.address || '').toLowerCase();
      return uid.includes(clean.toLowerCase());
    }) || {};

    const source=String(
      context.discovery_source ||
      context.source ||
      'KANIT BEKLENİYOR'
    ).replaceAll('_',' ');

    const success=String(
      context.success_state ||
      'HENÜZ DOĞRULANMADI'
    ).replaceAll('_',' ');

    const whale=String(
      context.whale_state ||
      'KANIT YOK'
    ).replaceAll('_',' ');

    const direction=String(
      context.whale_direction ||
      'YÖN YOK'
    ).replaceAll('_',' ');

    const freshness=String(
      context.candidate_state ||
      context.freshness_state ||
      'OBSERVED'
    ).replaceAll('_',' ');

    const sample=
      context.success_sample_depth ??
      context.sample_depth ??
      '—';

    const rows=Array.isArray(holdingsData?.holdings)
      ? holdingsData.holdings
      : [];

    const holdings=rows.length
      ? rows.map(row=>`
        <div class="v61-holding">
          <div>
            <b>${esc(row.symbol || row.name || row.token_id || 'TOKEN')}</b>
            <small style="display:block;margin-top:3px">
              ${esc(row.name || row.token_address || '')}
            </small>
            <div class="v61-bar">
              <span style="width:${Math.max(
                0,
                Math.min(100,num(row.portfolio_pct)||0)
              )}%"></span>
            </div>
          </div>
          <span>${esc(row.balance ?? '—')}</span>
          <span>${money(row.value_usd)}</span>
          <span>${pct(row.portfolio_pct)}</span>
        </div>`).join('')
      : `<div class="v61-box v61-warning">
           <small>HOLDINGS</small>
           <p>${esc(
             holdingsData?.reason ||
             'Bu cüzdan için varlık kaydı dönmedi.'
           )}</p>
         </div>`;

    openModal(
      `CÜZDAN · ${clean.slice(0,8)}…${clean.slice(-6)}`,
      `
      <div class="v61-grid">
        <div class="v61-box">
          <small>NEDEN İZLENİYOR?</small>
          <b>${esc(source)}</b>
        </div>
        <div class="v61-box">
          <small>SON DURUM</small>
          <b>${esc(freshness)}</b>
        </div>
        <div class="v61-box">
          <small>BAŞARI DURUMU</small>
          <b>${esc(success)}</b>
          <p>Örneklem: ${esc(sample)}</p>
        </div>
        <div class="v61-box">
          <small>BALİNA / YÖN</small>
          <b>${esc(whale)}</b>
          <p>${esc(direction)}</p>
        </div>
        <div class="v61-box">
          <small>TOPLAM PORTFÖY</small>
          <b>${money(holdingsData?.total_value_usd)}</b>
        </div>
        <div class="v61-box">
          <small>VARLIK SAYISI</small>
          <b>${esc(
            holdingsData?.returned_asset_count ??
            rows.length
          )}</b>
        </div>
      </div>

      <div class="v61-box" style="margin-top:10px">
        <small>PUBLIC BSC ADRESİ</small>
        <b>${esc(clean)}</b>
        <p>Read only · imza yok · transaction yetkisi yok.</p>
      </div>

      <div class="v61-holding"
           style="margin-top:12px;font-weight:900">
        <span>VARLIK</span>
        <span>MİKTAR</span>
        <span>DEĞER</span>
        <span>DAĞILIM</span>
      </div>

      ${holdings}
      `
    );
  }

  document.addEventListener('click',async e=>{
    const preview=e.target.closest('[data-preview-position]');
    if(preview){
      e.preventDefault();
      e.stopImmediatePropagation();
      await previewPosition(preview.dataset.previewPosition);
      return;
    }

    const wallet=e.target.closest('[data-wallet]');
    if(wallet){
      e.preventDefault();
      e.stopImmediatePropagation();
      await showWalletRich(wallet.dataset.wallet);
      return;
    }

    if(e.target.closest('[data-v61-buy]')){
      manualBuy();
      return;
    }

    if(e.target.closest('[data-v61-buy-confirm]')){
      await confirmBuy();
      return;
    }

    const sell=e.target.closest('[data-v61-sell-confirm]');
    if(sell){
      await confirmSell(sell.dataset.v61SellConfirm);
      return;
    }

    if(e.target.closest('[data-v61-wallet-connect]')){
      walletConnect();
      return;
    }

    if(e.target.closest('[data-v61-wallet-load]')){
      await showWalletRich($('v61WalletAddress')?.value);
      return;
    }

    const news=e.target.closest('[data-v61-news]');
    if(news){
      intelDetail(
        (market?.items || [])[Number(news.dataset.v61News)],
        'HABER'
      );
      return;
    }

    const cal=e.target.closest('[data-v61-calendar]');
    if(cal){
      intelDetail(
        (calendar?.items || [])[Number(cal.dataset.v61Calendar)],
        'EKONOMİK TAKVİM'
      );
      return;
    }

    const launch=e.target.closest('[data-v61-launch]');
    if(launch){
      intelDetail(
        (market?.launch_items || [])[Number(launch.dataset.v61Launch)],
        'AIRDROP / IDO / ICO'
      );
    }
  },true);

  const observer=new MutationObserver(()=>{
    enhanceIntel();
    injectControls();
  });

  ['newsRows','calendarRows','launchRows','positionRows','walletRows']
    .forEach(id=>{
      const node=$(id);
      if(node){
        observer.observe(node,{
          childList:true,
          subtree:true
        });
      }
    });

  injectControls();
  refreshData();

  setInterval(()=>{
    if(!document.hidden) refreshData();
  },30000);
})();

(() => {
  'use strict';

  const num = value => {
    if(value === null || value === undefined || value === '') return null;
    const x=Number(value);
    return Number.isFinite(x) ? x : null;
  };

  const money = value => {
    const x=num(value);
    return x===null
      ? '—'
      : `${x<0?'-':''}$${Math.abs(x).toLocaleString(
          'tr-TR',
          {minimumFractionDigits:2,maximumFractionDigits:2}
        )}`;
  };

  const pct = value => {
    const x=num(value);
    return x===null ? '—' : `${x>0?'+':''}${x.toFixed(2)}%`;
  };

  const tone = (node,value) => {
    if(!node) return;
    node.classList.remove('pos','neg');
    const x=num(value);
    if(x>0) node.classList.add('pos');
    if(x<0) node.classList.add('neg');
  };

  async function json(url,options={}){
    const r=await fetch(url,{
      cache:'no-store',
      ...options
    });
    const d=await r.json().catch(()=>({}));
    if(!r.ok) throw new Error(d.detail || String(r.status));
    return d;
  }

  function ensureAutomaticPaperStatus(){
    const head=document.querySelector(
      '.terminal-page[data-page="positions"] .full-card .card-head'
    );
    if(!head || head.querySelector('[data-auto-paper-status]')) return;

    const chip=document.createElement('span');
    chip.setAttribute('data-auto-paper-status','1');
    chip.className='v62-auto-paper-status';
    chip.textContent='OTOMATİK PAPER AL/SAT · RUNTIME';
    head.appendChild(chip);
  }

  async function refreshOpenPaperMarks(){
    if(document.hidden) return;

    const active=document.querySelector('.terminal-page.active');
    const page=active?.dataset?.page;

    if(page!=='positions' && page!=='home') return;

    let dash;
    try{
      dash=await json('/api/dashboard');
    }catch(_){
      return;
    }

    const rows=Array.isArray(dash?.positions)
      ? dash.positions.slice(0,12)
      : [];

    if(!rows.length) return;

    const results=await Promise.allSettled(
      rows.map(async row=>{
        const data=await json(
          '/api/manual-paper/preview-v2',
          {
            method:'POST',
            headers:{'Content-Type':'application/json'},
            body:JSON.stringify({
              position_id:row.id,
              pool:row.pool,
              token:row.token
            })
          }
        );
        return {row,data};
      })
    );

    let openPnl=0;
    let valid=0;

    results.forEach((result,index)=>{
      if(result.status!=='fulfilled') return;

      const {row,data}=result.value;
      const pnl=num(data.net_pnl_usdt);
      const roi=num(data.roi_pct);
      const price=num(data.reference_price);

      if(pnl!==null){
        openPnl+=pnl;
        valid+=1;
      }

      const button=[...document.querySelectorAll(
        '[data-preview-position]'
      )].find(
        el=>String(el.dataset.previewPosition)===String(row.id)
      );

      const tr=button?.closest('tr');

      if(tr){
        const td=tr.querySelectorAll('td');

        if(td[4] && price!==null){
          td[4].textContent=price.toLocaleString(
            'tr-TR',
            {maximumFractionDigits:8}
          );
        }

        if(td[6] && pnl!==null){
          td[6].textContent=money(pnl);
          tone(td[6],pnl);
        }

        if(td[7] && roi!==null){
          td[7].textContent=pct(roi);
          tone(td[7],roi);
        }
      }

      const homeRows=document.querySelectorAll(
        '#homePositionRows tr'
      );

      const home=homeRows[index];
      if(home){
        const td=home.querySelectorAll('td');

        if(td[2] && price!==null){
          td[2].textContent=price.toLocaleString(
            'tr-TR',
            {maximumFractionDigits:8}
          );
        }

        if(td[4] && pnl!==null){
          td[4].textContent=money(pnl);
          tone(td[4],pnl);
        }
      }
    });

    if(valid){
      const node=document.getElementById('positionsPnl');
      if(node){
        node.textContent=money(openPnl);
        tone(node,openPnl);
      }

      const summary=dash?.summary || {};
      const start=num(summary.starting_capital);
      const realized=num(summary.realized_net);

      if(start!==null && realized!==null){
        const equity=document.getElementById('metricEquity');
        if(equity){
          equity.textContent=money(start + realized + openPnl);
        }
      }
    }
  }

  const observer=new MutationObserver(()=>{
    ensureAutomaticPaperStatus();
  });

  observer.observe(document.body,{
    childList:true,
    subtree:true
  });

  ensureAutomaticPaperStatus();

  setTimeout(refreshOpenPaperMarks,800);

  setInterval(refreshOpenPaperMarks,45000);
})();
