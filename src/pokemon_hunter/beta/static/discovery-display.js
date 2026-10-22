'use strict';
/* Temporary display only; no provider operations or browser storage. */
window.DexDiscoveryDisplay = (() => {
  const auctionTime = (value, now) => window.DexAuctionTime(value, now);
  function sellerImage(value) {
    if (typeof value !== 'string' || /[\\\x00-\x20\x7f]/.test(value)) return '';
    try {
      const url = new URL(value);
      return url.origin === 'https://i.ebayimg.com' && !url.username && !url.password && !url.search && !url.hash && /^\/images\/g\/[A-Za-z0-9_~%-]+\/s-l[0-9]+\.(jpg|jpeg|png|webp)$/.test(url.pathname) ? url.href : '';
    } catch { return ''; }
  }
  function patch(container, html) {
    const incoming = document.createElement('div');incoming.innerHTML = html;
    const old = new Map([...container.children].map(child => [child.dataset.result,child]));
    let index = 0;
    for (let child of [...incoming.children]) {
      const existing = old.get(child.dataset.result);
      if (existing && child.dataset.result) {
        old.delete(child.dataset.result);
        if (existing.dataset.markup === child.outerHTML) child = existing;
        else {
          const before = existing.querySelector('.offer-image'), after = child.querySelector('.offer-image');
          const markup = child.outerHTML;
          if (before && after && before.dataset.source === after.dataset.source) after.replaceWith(before);
          existing.replaceWith(child);child.dataset.markup = markup;
        }
      } else child.dataset.markup = child.outerHTML;
      const position = container.children[index] || null;
      if (child !== position) container.insertBefore(child,position);
      index += 1;
    }
    for (const stale of old.values()) stale.remove();
    container.querySelectorAll('.offer-image img').forEach(img => {
      if (img.dataset.bound) return;
      img.dataset.bound = '1';
      img.addEventListener('error',() => {img.hidden = true;img.parentElement.querySelector('.offer-image-fallback').hidden = false;},{once:true});
    });
  }
  function tick(container) {
    container.querySelectorAll('[data-auction-end]').forEach(el => {el.textContent = auctionTime(el.dataset.auctionEnd);});
  }
  return {auctionTime,sellerImage,patch,tick};
})();
