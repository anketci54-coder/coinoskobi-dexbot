(() => {
  const q = id => document.getElementById(id);
  const norm = value => String(value || '').trim().toLowerCase();
  const num = value => { const parsed = Number(value); return Number.isFinite(parsed) ? parsed : null; };
  const positions = () => Array.isArray(window.state?.dashboard?.positions) ? window.state.dashboard.positions : [];
  function positionFor(row) {
    const pool = norm(row?.pool), token = norm(row?.base_token || row?.token0);
    return positions().find(p => String(p?.status || 'OPEN').toUpperCase() !== 'CLOSED' && ((pool && norm(p?.pool) === pool) || (token && norm(p?.token) === token))) || null;
  }
  function movingRows() {
    const source = window.state?.universe?.available && Array.isArray(window.state.universe.rows) ? window.state.universe.rows : [];
    if (window.state.filter === 'ACTIVE') return source.filter(row => Boolean(positionFor(row)));
    return source.filter(row => num(row?.seismic?.score) !== null && num(row.seismic.score) > 0)
      .filter(row => window.state.filter === 'ALL' || String(row.state || '').toUpperCase() === window.state.filter)
      .sort((a,b) => (num(b?.seismic?.score)||0) - (num(a?.seismic?.score)||0));
  }
  const fmtMoney = value => { const n=num(value); return n===null?'—':n.toLocaleString('tr-TR',{maximumFractionDigits:8}); };
  const fmtCompact = value => { const n=num(value); return n===null?'—':new Intl.NumberFormat('en-US',{notation:'compact',maximumFractionDigits:2}).format(n); };
  const fmtPct = value => { const n=num(value); return n===null?'—':`${n>0?'+':''}${n.toFixed(2)}%`; };
  const short = value => { const t=String(value||'').trim(); return !t?'—':t.length>18?`${t.slice(0,8)}…${t.slice(-6)}`:t; };
  const esc = value => String(value??'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;').replaceAll("'",'&#039;');
  const displayName = row => row?.display_name || row?.base_symbol || short(row?.base_token || row?.token0) || 'POOL';
  const stateClass = (row,p) => p?'active':['cold','warm','hot'].includes(String(row?.state||'').toLowerCase())?String(row.state).toLowerCase():'cold';
  const stateLabel = (row,p) => p?'AKTİF':String(row?.state||'—').toUpperCase();
  function orderButton(position) {
    if (window.state?.operatingMode !== 'MANUAL') return '';
    return `<button class="v3-order-trigger ${position?'sell':'buy'}" data-side="${position?'SELL':'BUY'}" type="button">${position?'SAT':'AL'}</button>`;
  }
  function detailHtml(row,position) {
    const price=num(row?.price_usd ?? position?.current_price ?? position?.entry_price), score=num(row?.seismic?.score);
    return `<div class="v3-radar-detail"><div class="v3-detail-grid">
      <div><small>PARİTE</small><b>${esc(displayName(row))}</b></div><div><small>QUOTE</small><b>${esc(String(row?.quote_symbol||'—').toUpperCase())}</b></div>
      <div><small>FİYAT</small><b>${esc(fmtMoney(price))}</b></div><div><small>SCORE</small><b>${esc(score===null?'—':score.toFixed(2))}</b></div>
      <div><small>5M</small><b>${esc(fmtPct(row?.change_5m_pct))}</b></div><div><small>24H HACİM</small><b>${esc(fmtCompact(row?.volume_24h_usd))}</b></div>
      <div><small>LİKİDİTE</small><b>${esc(fmtCompact(row?.liquidity_usd))}</b></div><div><small>POOL</small><b title="${esc(row?.pool)}">${esc(short(row?.pool))}</b></div>
      <div><small>TOKEN</small><b title="${esc(row?.base_token||row?.token0)}">${esc(short(row?.base_token||row?.token0))}</b></div></div>
      ${position?`<div class="v3-detail-position"><b>AÇIK PAPER POZİSYON</b><span>Giriş: ${esc(fmtMoney(position.entry_price))}</span><span>Miktar: ${esc(fmtMoney(position.entry_amount_usdt))} USDT</span><span>Token: ${esc(fmtMoney(position.token_amount))}</span></div>`:''}
      <div class="v3-detail-hint">MANUEL modda AL/SAT işlemi onay ekranından PAPER hesaba uygulanır.</div></div>`;
  }
  function render() {
    const body=q('radarBody'); if(!body)return; body.innerHTML=''; const rows=movingRows(), count=q('candidateCount');
    if(count) count.textContent=window.state?.filter==='ACTIVE'?`${positions().length} AÇIK POZİSYON`:`${rows.length} HAREKETLİ`;
    if(!rows.length){body.innerHTML=`<div class="empty" style="padding:18px">${window.state?.filter==='ACTIVE'?'Açık paper pozisyon yok':'Bu filtrede score > 0 uygun parite yok'}</div>`;return;}
    for(const row of rows){const position=positionFor(row), entry=document.createElement('div'), score=num(row?.seismic?.score); entry.className='v3-radar-entry';
      entry.innerHTML=`<div class="radar-row v3-radar-row ${position?'has-position':''}" tabindex="0"><span class="state ${stateClass(row,position)}">${esc(stateLabel(row,position))}</span><span class="token-cell"><span><div class="token">${esc(displayName(row))}</div><div class="small">${esc(short(row.pool))}</div></span>${orderButton(position)}</span><span class="small score-cell ${score&&score>0?'pos':''}">${esc(score===null?'—':score.toFixed(2))}</span><span class="small volume-cell">${esc(fmtCompact(row.volume_24h_usd))}</span><span class="small price-cell">${esc(fmtMoney(row.price_usd??position?.current_price))}</span><span class="small change-cell">${esc(fmtPct(row.change_5m_pct))}</span><span class="small liquidity-cell">${esc(fmtCompact(row.liquidity_usd))}</span></div>${detailHtml(row,position)}`;
      const rowEl=entry.querySelector('.v3-radar-row'); rowEl.onclick=e=>{if(!e.target.closest('.v3-order-trigger'))entry.classList.toggle('pinned');}; rowEl.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();entry.classList.toggle('pinned');}};
      const trigger=entry.querySelector('.v3-order-trigger'); if(trigger)trigger.onclick=e=>{e.preventDefault();e.stopPropagation();openTicket(trigger.dataset.side,row,position);}; body.appendChild(entry);}
  }
  function ensureTicket(){let modal=q('v3OrderModal');if(modal)return modal;modal=document.createElement('div');modal.id='v3OrderModal';modal.className='v3-order-modal';modal.innerHTML=`<div class="v3-order-card" role="dialog" aria-modal="true"><button type="button" class="v3-order-close">×</button><div class="v3-order-kicker">PAPER İŞLEM BİLETİ</div><h3 id="v3OrderTitle">—</h3><div id="v3OrderQuote" class="v3-order-quote"></div><div id="v3BuyFields" class="v3-buy-fields"><label>ALIM MİKTARI (USDT)<input id="v3OrderAmount" type="number" min="0.01" step="0.01" inputmode="decimal" value="10"></label><div class="v3-quick-amounts"><button type="button" data-amount="1">1</button><button type="button" data-amount="10">10</button><button type="button" data-amount="25">25</button><button type="button" data-amount="50">50</button><button type="button" data-amount="100">100</button></div></div><div id="v3OrderEstimate" class="v3-order-estimate"></div><div id="v3OrderError" class="v3-order-error"></div><button id="v3OrderConfirm" type="button" class="v3-order-confirm">ONAYLA</button><div class="v3-order-safety">Sadece PAPER hesap. Bayat fiyatla emir reddedilir. Live execution, wallet ve signing kapalıdır.</div></div>`;document.body.appendChild(modal);modal.querySelector('.v3-order-close').onclick=closeTicket;modal.onclick=e=>{if(e.target===modal)closeTicket();};modal.querySelectorAll('[data-amount]').forEach(b=>b.onclick=()=>{q('v3OrderAmount').value=b.dataset.amount;refreshEstimate();});q('v3OrderAmount').oninput=refreshEstimate;q('v3OrderConfirm').onclick=submitTicket;return modal;}
  function openTicket(side,row,position){const modal=ensureTicket(),price=num(row?.price_usd??position?.current_price??position?.entry_price);window.state.v3Order={side,row,position,price};q('v3OrderTitle').textContent=`${side==='BUY'?'AL':'SAT'} · ${displayName(row)}`;q('v3OrderQuote').innerHTML=`<span>Gösterilen fiyat</span><b>${esc(fmtMoney(price))} USD</b><span>Parite</span><b>${esc(displayName(row))}</b><span>Not</span><b>Emirde server güncel fiyatı tekrar doğrular</b>`;q('v3BuyFields').style.display=side==='BUY'?'':'none';q('v3OrderConfirm').textContent=side==='BUY'?'ALIMI ONAYLA':'SATIŞI ONAYLA';q('v3OrderConfirm').className=`v3-order-confirm ${side==='SELL'?'sell':'buy'}`;q('v3OrderError').textContent='';refreshEstimate();modal.classList.add('open');}
  function closeTicket(){const m=q('v3OrderModal');if(m)m.classList.remove('open');if(window.state)window.state.v3Order=null;}
  function refreshEstimate(){const o=window.state?.v3Order;if(!o)return;const price=num(o.price),e=q('v3OrderEstimate');if(o.side==='BUY'){const amount=num(q('v3OrderAmount')?.value),tokens=price&&amount?amount/price:null;e.innerHTML=`<div><small>EMİR</small><b>MARKET / PAPER</b></div><div><small>TUTAR</small><b>${esc(amount===null?'—':amount.toFixed(2))} USDT</b></div><div><small>TAHMİNİ TOKEN</small><b>${esc(tokens===null?'—':tokens.toLocaleString('tr-TR',{maximumFractionDigits:8}))}</b></div>`;}else{const p=o.position||{},tokens=num(p.token_amount)||0,entry=num(p.entry_amount_usdt)||0,proceeds=price?tokens*price:null,pnl=proceeds===null?null:proceeds-entry;e.innerHTML=`<div><small>EMİR</small><b>POZİSYONU KAPAT</b></div><div><small>MEVCUT TOKEN</small><b>${esc(tokens.toLocaleString('tr-TR',{maximumFractionDigits:8}))}</b></div><div><small>BRÜT TAHMİN</small><b>${esc(proceeds===null?'—':proceeds.toFixed(2))} USDT</b></div><div><small>HAM PNL TAHMİNİ</small><b class="${pnl!==null&&pnl>=0?'pos':'neg'}">${esc(pnl===null?'—':`${pnl>=0?'+':''}${pnl.toFixed(2)} USDT`)}</b></div>`;}}
  async function submitTicket(){const o=window.state?.v3Order;if(!o)return;const button=q('v3OrderConfirm'),error=q('v3OrderError');button.disabled=true;error.textContent='';const payload={confirmed:true,side:o.side,pool:o.row?.pool||o.position?.pool||null,token:o.row?.base_token||o.row?.token0||o.position?.token||null,symbol:o.row?.base_symbol||displayName(o.row),position_id:o.position?.id||null};if(o.side==='BUY')payload.amount_usdt=num(q('v3OrderAmount')?.value);try{const response=await fetch('/api/manual-paper/order-v2',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)}),data=await response.json().catch(()=>({}));if(!response.ok)throw new Error(data.detail||'İşlem gerçekleştirilemedi');closeTicket();if(typeof refresh==='function')await refresh();render();}catch(exc){error.textContent=exc?.message||'İşlem gerçekleştirilemedi';}finally{button.disabled=false;}}
  function removeStateFooter(){const source=q('universeSource');if(source?.parentElement)source.parentElement.classList.add('v3-hide-radar-footer');}
  function install(){removeStateFooter();ensureTicket();window.renderRadar=render;render();const observer=new MutationObserver(removeStateFooter),radar=document.querySelector('.panel.radar');if(radar)observer.observe(radar,{childList:true,subtree:true});}
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',install,{once:true});else install();
})();
