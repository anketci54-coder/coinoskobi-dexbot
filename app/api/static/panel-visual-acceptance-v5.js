(() => {
  'use strict';

  if (window.__COINOSKOBI_VISUAL_ACCEPTANCE_V5__) return;
  window.__COINOSKOBI_VISUAL_ACCEPTANCE_V5__ = true;

  const $ = id => document.getElementById(id);
  const num = value => {
    const parsed = Number(String(value ?? '').replace('%','').replace('$','').replaceAll('.','').replace(',','.').replace(/[^0-9+\-.]/g,''));
    return Number.isFinite(parsed) ? parsed : null;
  };

  function polishRisk(){
    const card = document.querySelector('.risk-metric');
    if (!card) return;
    let line = card.querySelector('.risk-exposure-line');
    if (!line) {
      line = document.createElement('div');
      line.className = 'risk-exposure-line';
      line.innerHTML = '<span>AÇIK MARUZİYET</span><b id="riskExposureValue">—</b><span id="riskExposureHint">riskten ayrı</span>';
      card.querySelector('.metric-copy')?.appendChild(line);
    }

    const investmentText = $('openInvestment')?.textContent || '—';
    const riskText = $('riskUsed')?.textContent || '—';
    const investment = num(investmentText);
    const risk = num(riskText);
    const exposure = $('riskExposureValue');
    if (exposure) exposure.textContent = investmentText;

    const hasExposure = investment !== null && investment > 0;
    const zeroModeledRisk = risk !== null && Math.abs(risk) < 0.0001;
    card.classList.toggle('risk-has-exposure',hasExposure && zeroModeledRisk);

    const hint = $('riskExposureHint');
    if (hint) hint.textContent = hasExposure && zeroModeledRisk ? 'model risk 0' : 'riskten ayrı';
  }

  function polishWallet(){
    const body = $('premiumWalletBody');
    if (!body) return;
    const note = body.querySelector('.premium-wallet-note');
    if (note && !note.dataset.acceptance) {
      note.dataset.acceptance = '1';
      note.innerHTML = '<b>ADAY SAYISI SKOR DEĞİLDİR.</b> Cüzdanlar yalnız doğrulanmış kaynak, başarı durumu, örneklem, balina yönü ve holdings kanıtıyla değerlendirilir. Backend başarı yüzdesi üretmiyorsa panel yüzde göstermez.';
    }

    body.querySelectorAll('.wallet-status-line b').forEach(node => {
      if (node.textContent.trim() === 'UNKNOWN') node.textContent = 'HENÜZ DOĞRULANMADI';
    });
    body.querySelectorAll('.wallet-dir').forEach(node => {
      if (node.textContent.trim() === 'UNKNOWN') node.textContent = 'YÖN YOK';
    });
    body.querySelectorAll('.wallet-evidence.low').forEach(node => {
      if (node.textContent.includes('KANIT YETERSİZ')) node.textContent = 'KANIT BEKLİYOR';
    });
  }

  function polishIntel(){
    const body = $('premiumIntelBody');
    if (!body) return;

    const newsPane = body.querySelector('[data-premium-pane="NEWS"]');
    const newsGrid = newsPane?.querySelector('.premium-intel-grid');
    const newsSide = newsGrid?.querySelector('.premium-intel-side');
    newsPane?.classList.add('acceptance-news-pane');
    newsGrid?.classList.add('acceptance-news-grid');
    newsSide?.classList.add('acceptance-news-summary');

    const vezirPane = body.querySelector('[data-premium-pane="VEZIR"]');
    vezirPane?.querySelector('.premium-vezir-layout')?.classList.add('acceptance-vezir-layout');

    body.querySelectorAll('.premium-vezir-message:not(.user)').forEach(formatVezirMessage);
  }

  function formatVezirMessage(node){
    if (!node || node.dataset.acceptanceFormatted === '1') return;
    node.dataset.acceptanceFormatted = '1';

    const small = node.querySelector('small');
    const meta = small?.textContent || '';
    if (small) small.remove();

    let text = node.textContent.trim();
    text = text
      .replace(/\s*\|\s*/g,'\n\n')
      .replace(/\s+(Ne yapmalı:)/g,'\n$1')
      .replace(/\s+(Etki alanı:)/g,'\n$1')
      .replace(/\.\s+(AÇIK|REGÜLASYON|PİYASA|LİSTELEME|AIRDROP|TOKEN|HACK|EXPLOIT)(?=\s|\/)/g,'.\n\n$1');

    node.textContent = text;
    if (meta) {
      const metaNode = document.createElement('small');
      metaNode.textContent = meta;
      node.appendChild(metaNode);
    }
  }

  function bindObservers(){
    const targets = [
      $('riskUsed'),
      $('openInvestment'),
      $('premiumWalletBody'),
      $('premiumIntelBody')
    ].filter(Boolean);

    const observer = new MutationObserver(() => {
      polishRisk();
      polishWallet();
      polishIntel();
    });

    targets.forEach(target => observer.observe(target,{childList:true,subtree:true,characterData:true}));

    const bodyObserver = new MutationObserver(() => {
      polishWallet();
      polishIntel();
      const walletBody = $('premiumWalletBody');
      const intelBody = $('premiumIntelBody');
      if (walletBody && !targets.includes(walletBody)) observer.observe(walletBody,{childList:true,subtree:true,characterData:true});
      if (intelBody && !targets.includes(intelBody)) observer.observe(intelBody,{childList:true,subtree:true,characterData:true});
    });
    bodyObserver.observe(document.body,{childList:true,subtree:false});
  }

  document.addEventListener('DOMContentLoaded',() => {
    polishRisk();
    polishWallet();
    polishIntel();
    bindObservers();
  });
})();
