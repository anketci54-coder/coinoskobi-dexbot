(() => {
  'use strict';

  if (window.__COINOSKOBI_PANEL_PERFORMANCE_V5__) return;
  window.__COINOSKOBI_PANEL_PERFORMANCE_V5__ = true;

  const nativeSetInterval = window.setInterval.bind(window);

  // Keep the operational panel responsive without slowing the radar into
  // minute-scale polling. These functions are existing read-only refreshers.
  // The wrapper only raises their minimum cadence and pauses expensive
  // background work while the page is hidden or a full-screen detail panel
  // is open. It does not change any backend, paper or execution authority.
  const minimumCadenceMs = Object.freeze({
    refresh: 8000,
    refreshTickers: 30000,
    refreshMarket: 45000,
    refreshWallet: 30000,
    refreshProviderState: 45000,
    refreshAutoHealth: 30000
  });

  const heavyRefreshers = new Set([
    'refresh',
    'refreshMarket',
    'refreshWallet',
    'refreshProviderState',
    'refreshAutoHealth'
  ]);

  const detailPanelOpen = () => Boolean(document.querySelector(
    '.premium-accounting-modal.open,' +
    '.premium-wallet-modal.open,' +
    '.premium-intel-modal.open'
  ));

  window.setInterval = function panelAwareSetInterval(callback, delay, ...args) {
    if (typeof callback !== 'function') {
      return nativeSetInterval(callback, delay, ...args);
    }

    const name = String(callback.name || '');
    const minimum = minimumCadenceMs[name];

    if (!minimum) {
      return nativeSetInterval(callback, delay, ...args);
    }

    const requested = Number(delay);
    const cadence = Math.max(
      Number.isFinite(requested) && requested > 0 ? requested : 0,
      minimum
    );

    const wrapped = () => {
      if (document.hidden) return;
      if (heavyRefreshers.has(name) && detailPanelOpen()) return;
      callback(...args);
    };

    return nativeSetInterval(wrapped, cadence);
  };

  const paintVisibilityState = () => {
    document.documentElement.classList.toggle(
      'panel-page-hidden',
      document.hidden
    );
  };

  document.addEventListener('visibilitychange', paintVisibilityState, {passive:true});
  paintVisibilityState();
})();
