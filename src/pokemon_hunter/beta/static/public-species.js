'use strict';
// Public UI memory contains only validated local list filters, scroll and active row.
(() => {
  if (location.pathname !== '/pokedex/') return;
  const number = value => /^[0-9]+$/.test(value || '') ? Number(value) : null;
  const params = new URLSearchParams(location.search);
  const focus = number(params.get('focus'));
  const scroll = number(params.get('scroll'));
  requestAnimationFrame(() => {
    if (focus >= 1 && focus <= 251) document.getElementById('public-species-' + focus)?.focus({preventScroll: true});
    if (scroll !== null && scroll >= 0 && scroll <= 10000000) window.scrollTo(0, scroll);
  });
  document.querySelectorAll('.public-species-link[data-dex]').forEach(link => {
    link.addEventListener('click', () => {
      const dex = number(link.dataset.dex);
      if (!(dex >= 1 && dex <= 251)) return;
      const destination = new URL(link.href, location.origin);
      if (destination.origin !== location.origin || destination.pathname !== '/pokedex/' + dex + '/') return;
      const context = new URLSearchParams(location.search);
      context.set('focus', String(dex));
      context.set('scroll', String(Math.min(10000000, Math.max(0, Math.round(window.scrollY)))));
      destination.searchParams.set('return', '/pokedex/?' + context);
      link.href = destination.pathname + destination.search;
    });
  });
})();
