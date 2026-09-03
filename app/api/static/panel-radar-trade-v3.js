(() => {
  const q = id => document.getElementById(id);
  const norm = value => String(value || '').trim().toLowerCase();
  const num = value => {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  };

  function positions() {
    const rows = window.state?.dashboard?.positions;
    return Array.isArray(rows) ? rows : [];
  }

  function positionFor(row) {
    const pool = norm(row?.pool);
    const token = norm(row?.base_token || row?.token0);
    return positions().find(position => {
      if (String(position?.status || 'OPEN').toUpperCase() === 'CLOSED') return false;
      if (pool && norm(position?.pool) === pool) return true;
      return token && norm(position?.token) === token;
    }) || null;
  }

  function movingRows() {
    const source = window.state?.universe?.available && Array.isArray(window.state.universe.rows)
      ? window.state.universe.rows
      : [];

    if (window.state.filter === 'ACTIVE') {
      return source.filter(row => Boolean(positionFor(row)));
    }

    return source
      .filter(row => num(row?.seismic?.score) !== null && num(row.seismic.score) > 0)
      .filter(row => window.state.filter === 'ALL' || String(row.state || '').toUpperCase() === window.state.filter)
      .sort((a, b) => (num(b?.seismic?.score) || 0) - (num(a?.seismic?.score) || 0));
  }

  function fmtMoney(value) {
    const n = num(value);
    if (n === null) return '—';
    return n.toLocaleString('tr-TR', {maximumFractionDigits: 8});
  }

  function fmtCompact(value) {
    const n = num(value);
    if (n === null) return '—';
    return new Intl.NumberFormat('en-US', {notation: 'compact', maximumFractionDigits: 2}).format(n);
  }

  function fmtPct(value) {
    const n = num(value);
    if (n === null) return '—';
    return `${n > 0 ? '+' : ''}${n.toFixed(2)}%`;
  }

  function short(value) {
    const text = String(value || '').trim();
    if (!text) return '—';
    return text.length > 18 ? `${text.slice(0, 8)}…${text.slice(-6)}` : text;
  }

  function esc(value) {
    return String(value ?? '')
      .replaceAll('&', '&amp;')
      .replaceAll('<', '&lt;')
      .replaceAll('>', '&gt;')
      .replaceAll('"', '&quot;')
      .replaceAll("'", '&#039;');
  }

  function stateClass(row, position) {
    if (position) return 'active';
    const value = String(row?.state || '').toLowerCase();
    return ['cold', 'warm', 'hot'].includes(value) ? value : 'cold';
  }

  function stateLabel(row, position) {
    return position ? 'AKTİF' : String(row?.state || '—').toUpperCase();
  }

  function quoteLabel(row) {
    return String(row?.quote_symbol || '').toUpperCase();
  }

  function displayName(row) {
    return row?.display_name || row?.base_symbol || short(row?.base_token || row?.token0) || 'POOL';
  }

  function orderButton(row, position) {
    if (window.state?.operatingMode !== 'MANUAL') return '';
    const side = position ? 'SELL' : 'BUY';
    const label = position ? 'SAT' : 'AL';
    return `<button class="v3-order-trigger ${position ? 'sell' : 'buy'}" data-side="${side}" type="button">${label}</button>`;
  }

  function detailHtml(row, position) {
    const price = num(row?.price_usd ?? position?.current_price ?? position?.entry_price);
    const score = num(row?.seismic?.score);
    const quote = quoteLabel(row);
    const positionBlock = position ? `
      <div class="v3-detail-position">
        <b>AÇIK PAPER POZİSYON</b>
        <span>Giriş: ${esc(fmtMoney(position.entry_price))}</span>
        <span>Miktar: ${esc(fmtMoney(position.entry_amount_usdt))} USDT</span>
        <span>Token: ${esc(fmtMoney(position.token_amount))}</span>
      </div>` : '';

    return `
      <div class="v3-radar-detail">
        <div class="v3-detail-grid">
          <div><small>PARİTE</small><b>${esc(displayName(row))}</b></div>
          <div><small>QUOTE</small><b>${esc(quote || '—')}</b></div>
          <div><small>FİYAT</small><b>${esc(fmtMoney(price))}</b></div>
          <div><small>SCORE</small><b>${esc(score === null ? '—' : score.toFixed(2))}</b></div>
          <div><small>5M</small><b>${esc(fmtPct(row?.change_5m_pct))}</b></div>
          <div><small>24H HACİM</small><b>${esc(fmtCompact(row?.volume_24h_usd))}</b></div>
          <div><small>LİKİDİTE</small><b>${esc(fmtCompact(row?.liquidity_usd))}</b></div>
          <div><small>POOL</small><b title="${esc(row?.pool)}">${esc(short(row?.pool))}</b></div>
          <div><small>TOKEN</small><b title="${esc(row?.base_token || row?.token0)}">${esc(short(row?.base_token || row?.token0))}</b></div>
        </div>
        ${positionBlock}
        <div class="v3-detail-hint">MANUEL modda işlem bileti AL/SAT düğmesinden açılır.</div>
      </div>`;
  }

  function render() {
    const body = q('radarBody');
    if (!body) return;
    body.innerHTML = '';

    const rows = movingRows();
    const count = q('candidateCount');
    if (count) count.textContent = window.state?.filter === 'ACTIVE'
      ? `${positions().length} AÇIK POZİSYON`
      : `${rows.length} HAREKETLİ`;

    if (!rows.length) {
      body.innerHTML = `<div class="empty" style="padding:18px">${window.state?.filter === 'ACTIVE' ? 'Açık paper pozisyon yok' : 'Bu filtrede score > 0 uygun parite yok'}</div>`;
      return;
    }

    for (const row of rows) {
      const position = positionFor(row);
      const entry = document.createElement('div');
      entry.className = 'v3-radar-entry';
      const score = num(row?.seismic?.score);
      entry.innerHTML = `
        <div class="radar-row v3-radar-row ${position ? 'has-position' : ''}" tabindex="0">
          <span class="state ${stateClass(row, position)}">${esc(stateLabel(row, position))}</span>
          <span class="token-cell">
            <span><div class="token">${esc(displayName(row))}</div><div class="small">${esc(short(row.pool))}</div></span>
            ${orderButton(row, position)}
          </span>
          <span class="small score-cell ${score && score > 0 ? 'pos' : ''}">${esc(score === null ? '—' : score.toFixed(2))}</span>
          <span class="small volume-cell">${esc(fmtCompact(row.volume_24h_usd))}</span>
          <span class="small price-cell">${esc(fmtMoney(row.price_usd ?? position?.current_price))}</span>
          <span class="small change-cell">${esc(fmtPct(row.change_5m_pct))}</span>
          <span class="small liquidity-cell">${esc(fmtCompact(row.liquidity_usd))}</span>
        </div>
        ${detailHtml(row, position)}
      `;

      const rowEl = entry.querySelector('.v3-radar-row');
      rowEl.addEventListener('click', event => {
        if (event.target.closest('.v3-order-trigger')) return;
        entry.classList.toggle('pinned');
      });
      rowEl.addEventListener('keydown', event => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault();
          entry.classList.toggle('pinned');
        }
      });

      const trigger = entry.querySelector('.v3-order-trigger');
      if (trigger) {
        trigger.addEventListener('click', event => {
          event.preventDefault();
          event.stopPropagation();
          openTicket(trigger.dataset.side, row, position);
        });
      }

      body.appendChild(entry);
    }
  }

  function ensureTicket() {
    let modal = q('v3OrderModal');
    if (modal) return modal;

    modal = document.createElement('div');
    modal.id = 'v3OrderModal';
    modal.className = 'v3-order-modal';
    modal.innerHTML = `
      <div class="v3-order-card" role="dialog" aria-modal="true" aria-labelledby="v3OrderTitle">
        <button type="button" class="v3-order-close" aria-label="Kapat">×</button>
        <div class="v3-order-kicker">PAPER İŞLEM BİLETİ</div>
        <h3 id="v3OrderTitle">—</h3>
        <div id="v3OrderQuote" class="v3-order-quote"></div>
        <div id="v3BuyFields" class="v3-buy-fields">
          <label>ALIM MİKTARI (USDT)<input id="v3OrderAmount" type="number" min="0.01" step="0.01" inputmode="decimal" value="10"></label>
          <div class="v3-quick-amounts"><button type="button" data-amount="1">1</button><button type="button" data-amount="10">10</button><button type="button" data-amount="25">25</button><button type="button" data-amount="50">50</button><button type="button" data-amount="100">100</button></div>
        </div>
        <div id="v3OrderEstimate" class="v3-order-estimate"></div>
        <div id="v3OrderError" class="v3-order-error"></div>
        <button id="v3OrderConfirm" type="button" class="v3-order-confirm">ONAYLA</button>
        <div class="v3-order-safety">Sadece PAPER hesap. Live execution, wallet ve signing kapalıdır.</div>
      </div>`;

    document.body.appendChild(modal);
    modal.querySelector('.v3-order-close').onclick = () => closeTicket();
    modal.addEventListener('click', event => {
      if (event.target === modal) closeTicket();
    });
    modal.querySelectorAll('[data-amount]').forEach(button => {
      button.onclick = () => {
        q('v3OrderAmount').value = button.dataset.amount;
        refreshEstimate();
      };
    });
    q('v3OrderAmount').addEventListener('input', refreshEstimate);
    q('v3OrderConfirm').onclick = submitTicket;
    return modal;
  }

  function openTicket(side, row, position) {
    const modal = ensureTicket();
    const price = num(row?.price_usd ?? position?.current_price ?? position?.entry_price);
    window.state.v3Order = {side, row, position, price};

    q('v3OrderTitle').textContent = `${side === 'BUY' ? 'AL' : 'SAT'} · ${displayName(row)}`;
    q('v3OrderQuote').innerHTML = `<span>Referans fiyat</span><b>${esc(fmtMoney(price))} USD</b><span>Parite</span><b>${esc(displayName(row))}</b>`;
    q('v3BuyFields').style.display = side === 'BUY' ? '' : 'none';
    q('v3OrderConfirm').textContent = side === 'BUY' ? 'ALIMI ONAYLA' : 'SATIŞI ONAYLA';
    q('v3OrderConfirm').className = `v3-order-confirm ${side === 'SELL' ? 'sell' : 'buy'}`;
    q('v3OrderError').textContent = '';
    refreshEstimate();
    modal.classList.add('open');
  }

  function closeTicket() {
    const modal = q('v3OrderModal');
    if (modal) modal.classList.remove('open');
    if (window.state) window.state.v3Order = null;
  }

  function refreshEstimate() {
    const order = window.state?.v3Order;
    if (!order) return;
    const estimate = q('v3OrderEstimate');
    const price = num(order.price);

    if (order.side === 'BUY') {
      const amount = num(q('v3OrderAmount')?.value);
      const tokens = price && amount ? amount / price : null;
      estimate.innerHTML = `
        <div><small>EMİR</small><b>MARKET / PAPER</b></div>
        <div><small>TUTAR</small><b>${esc(amount === null ? '—' : amount.toFixed(2))} USDT</b></div>
        <div><small>TAHMİNİ TOKEN</small><b>${esc(tokens === null ? '—' : tokens.toLocaleString('tr-TR', {maximumFractionDigits: 8}))}</b></div>`;
    } else {
      const p = order.position || {};
      const tokenAmount = num(p.token_amount) || 0;
      const entry = num(p.entry_amount_usdt) || 0;
      const proceeds = price ? tokenAmount * price : null;
      const pnl = proceeds === null ? null : proceeds - entry;
      estimate.innerHTML = `
        <div><small>EMİR</small><b>POZİSYONU KAPAT</b></div>
        <div><small>MEVCUT TOKEN</small><b>${esc(tokenAmount.toLocaleString('tr-TR', {maximumFractionDigits: 8}))}</b></div>
        <div><small>TAHMİNİ USDT</small><b>${esc(proceeds === null ? '—' : proceeds.toFixed(2))}</b></div>
        <div><small>TAHMİNİ PNL</small><b class="${pnl !== null && pnl >= 0 ? 'pos' : 'neg'}">${esc(pnl === null ? '—' : `${pnl >= 0 ? '+' : ''}${pnl.toFixed(2)} USDT`)}</b></div>`;
    }
  }

  async function submitTicket() {
    const order = window.state?.v3Order;
    if (!order) return;
    const button = q('v3OrderConfirm');
    const error = q('v3OrderError');
    button.disabled = true;
    error.textContent = '';

    const payload = {
      confirmed: true,
      side: order.side,
      pool: order.row?.pool || order.position?.pool || null,
      token: order.row?.base_token || order.row?.token0 || order.position?.token || null,
      symbol: order.row?.base_symbol || displayName(order.row),
      position_id: order.position?.id || null,
    };
    if (order.side === 'BUY') payload.amount_usdt = num(q('v3OrderAmount')?.value);

    try {
      const response = await fetch('/api/manual-paper/order', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(payload),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail || 'İşlem gerçekleştirilemedi');

      closeTicket();
      if (typeof refresh === 'function') await refresh();
      render();
    } catch (exc) {
      error.textContent = exc?.message || 'İşlem gerçekleştirilemedi';
    } finally {
      button.disabled = false;
    }
  }

  function removeStateFooter() {
    const source = q('universeSource');
    if (!source) return;
    const parent = source.parentElement;
    if (parent) parent.classList.add('v3-hide-radar-footer');
  }

  function install() {
    removeStateFooter();
    ensureTicket();
    window.renderRadar = render;
    render();

    const observer = new MutationObserver(() => {
      removeStateFooter();
    });
    const radar = document.querySelector('.panel.radar');
    if (radar) observer.observe(radar, {childList: true, subtree: true});
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', install, {once: true});
  else install();
})();
