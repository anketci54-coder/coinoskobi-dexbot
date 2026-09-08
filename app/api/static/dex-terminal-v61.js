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

  function injectControls(){
    const positionsHead=document.querySelector(
      '.terminal-page[data-page="positions"] .page-head'
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

    try{
      const data=await post(
        '/api/manual-paper/order-v2',
        {
          side:'SELL',
          position_id:row.id,
          pool:row.pool,
          token:row.token,
          confirmed:true
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
      await showWallet(wallet.dataset.wallet);
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
      await showWallet($('v61WalletAddress')?.value);
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
