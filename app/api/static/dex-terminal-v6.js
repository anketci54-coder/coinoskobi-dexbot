(() => {
  'use strict';

  const $ = id => document.getElementById(id);
  const $$ = selector => [...document.querySelectorAll(selector)];
  const n = value => { const x = Number(value); return Number.isFinite(x) ? x : null; };
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

  let dashboard=null, universe=null, ledger=null, walletBrief=null, walletDetail=null, market=null, calendar=null;
  let radarFilter='ALL';
  let selectedWallet=null;

  function showPage(page){
    $$('.terminal-page').forEach(node=>node.classList.toggle('active',node.dataset.page===page));
    $$('.nav-item').forEach(node=>node.classList.toggle('active',node.dataset.pageTarget===page));
    window.scrollTo({top:0,behavior:'instant'});
  }

  function candidateName(row){ return row.display_name || short(row.token0 || row.token1 || row.pool); }
  function radarRows(rows){
    return rows.length ? rows.map(row=>{
      const seismic=row.seismic||{};
      return `<tr>
        <td>${stateBadge(row.state)}</td>
        <td><div class="token-cell"><b>${esc(candidateName(row))}</b><small>${esc(short(row.pool))}</small></div></td>
        <td>${esc(row.dex||'—')}</td>
        <td>${num(seismic.score)}</td>
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
    const rows=closedRows(); const wins=rows.filter(r=>(n(r.net_pnl_usdt??r.net_pnl)||0)>0).length; const losses=rows.filter(r=>(n(r.net_pnl_usdt??r.net_pnl)||0)<0).length; const pnl=rows.reduce((a,r)=>a+(n(r.net_pnl_usdt??r.net_pnl)||0),0);
    $('historyCount').textContent=rows.length; $('historyWins').textContent=wins; $('historyLosses').textContent=losses; $('historyPnl').textContent=money(pnl); $('historyPnl').className=cls(pnl); $('historyMeta').textContent=`${rows.length} kapanmış kayıt`;
    $('historyRows').innerHTML=rows.length?rows.map(row=>`<tr><td>${esc(row.id??'—')}</td><td><b>${esc(row.symbol||short(row.token))}</b></td><td>${num(row.entry_price)}</td><td>${num(row.exit_price??row.current_price)}</td><td class="${cls(row.net_pnl_usdt??row.net_pnl)}">${money(row.net_pnl_usdt??row.net_pnl)}</td><td class="${cls(row.roi_pct)}">${pct(row.roi_pct??(n(row.roi)!==null?n(row.roi)*100:null))}</td><td>${esc(row.close_reason||'—')}</td><td>${formatTime(row.closed_at??row.created_at)}</td></tr>`).join(''):'<tr><td colspan="8" class="muted">Kapanmış işlem yok.</td></tr>';
  }

  function renderRadar(){
    const counts=universe?.counts||{}; $('radarHot').textContent=counts.HOT??'—'; $('radarWarm').textContent=counts.WARM??'—'; $('radarCold').textContent=counts.COLD??'—'; $('radarVisible').textContent=universe?.visible_count??'—'; $('radarSource').textContent=universe?.source||'—';
    const all=Array.isArray(universe?.rows)?universe.rows:[]; const filtered=radarFilter==='ALL'?all:all.filter(r=>String(r.state||'').toUpperCase()===radarFilter); $('radarRows').innerHTML=radarRows(filtered);
    const home=all.slice(0,6); $('homeRadarRows').innerHTML=home.length?home.map(row=>{ const seismic=row.seismic||{}; return `<tr><td>${stateBadge(row.state)}</td><td><div class="token-cell"><b>${esc(candidateName(row))}</b><small>${esc(short(row.pool))}</small></div></td><td>${esc(row.dex||'—')}</td><td>${num(seismic.score)}</td><td>${money(row.volume_24h_usd)}</td><td class="${cls(row.change_5m_pct)}">${pct(row.change_5m_pct)}</td><td>${money(row.liquidity_usd)}</td></tr>`; }).join(''):'<tr><td colspan="7" class="muted">Güncel DEX radar kaydı yok.</td></tr>'; $('homeRadarCount').textContent=`${home.length} görünür`;
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
    const jobs=[['dashboard','/api/dashboard'],['universe','/api/universe-panel'],['ledger','/api/accounting-ledger-v2?limit=200'],['walletBrief','/api/wallet-brief-v3'],['walletDetail','/api/wallet-intelligence-v2'],['market','/api/market-brief-v3'],['calendar','/api/calendar-brief-v3']];
    const results=await Promise.all(jobs.map(async ([key,url])=>{try{return [key,await get(url)]}catch(e){console.warn(key,e);return [key,null]}}));
    for(const [key,value] of results){ if(key==='dashboard')dashboard=value; if(key==='universe')universe=value; if(key==='ledger')ledger=value; if(key==='walletBrief')walletBrief=value; if(key==='walletDetail')walletDetail=value; if(key==='market')market=value; if(key==='calendar')calendar=value; }
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
