'use strict';
/* Results remain in this page and the account-scoped temporary service, never browser storage. */
(() => {
  const $ = id => document.getElementById(id);
  if (!$('discovery-form')) return;
  const api = '/api/shopping/discovery/';
  const page = document.body, binding = page.dataset.navigationBinding || '', account = page.dataset.navigationAccount || '';
  const currentAuthority = () => !revoked && document.body === page && page.dataset.navigationBinding === binding && page.dataset.navigationAccount === account && !window.navigationAuthorityDiscarded && !window.navigationReauthorizing;
  let intent = 'deals', run = null, goals = [], captured = null, sequence = 0;
  let timer = null, acquiring = false, stopWanted = false, ready = false, revoked = false;
  let deadline = Infinity, deadlineRun = null, sourceState = null, sourceUnavailable = false, checkingSources = false, lifecycleTimer = null;
  const esc = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
  const csrf = () => $('discovery-form').querySelector('[name=csrfmiddlewaretoken]')?.value || '';
  const text = value => typeof value === 'string' || typeof value === 'number' ? String(value) : '';
  const amount = value => value && typeof value === 'object' ? value.amount : value;
  function money(value) {
    const raw = amount(value);
    if (raw === null || raw === undefined || raw === '' || !Number.isFinite(Number(raw))) return 'Unknown';
    const currency = value && typeof value === 'object' ? value.currency || 'USD' : 'USD';
    try { return new Intl.NumberFormat('en-US', {style:'currency', currency}).format(Number(raw)); }
    catch { return String(raw) + ' ' + currency; }
  }
  function link(value, ebayOnly = false) {
    if (typeof value !== 'string' || !value) return '';
    try {
      const url = new URL(value, location.origin);
      if (!['https:','http:'].includes(url.protocol) || url.username || url.password) return '';
      if (ebayOnly && !/(^|\.)ebay\.com$/i.test(url.hostname)) return '';
      return url.href;
    } catch { return ''; }
  }
  function artwork(value) {
    if (typeof value !== 'string' || !value || /[\\\x00-\x20]/.test(value)) return '';
    try {
      const url = new URL(value, location.origin);
      if (url.username || url.password) return '';
      if (value.startsWith('/') && !value.startsWith('//') && url.origin === location.origin) return value;
      return url.protocol === 'https:' && !url.port && ['assets.tcgdex.net','raw.githubusercontent.com'].includes(url.hostname) ? url.href : '';
    } catch { return ''; }
  }
  function status(message, error = false) {
    $('discovery-status').textContent = message;
    $('discovery-status').dataset.error = error ? 'true' : 'false';
  }
  async function request(url, body) {
    const response = await fetch(url, {method:body === undefined ? 'GET' : 'POST',credentials:'same-origin',redirect:'error',cache:'no-store',headers:{'X-Dex-Shopping-Binding':binding,...(body === undefined ? {} : {'Content-Type':'application/json','X-CSRFToken':csrf()})},...(body === undefined ? {} : {body:JSON.stringify(body)})});
    if (response.status === 403 || response.status === 401) {
      window.discardNavigationAuthority?.();if (!revoked) invalidate();
      throw new Error('Your session is unavailable. Sign in again to continue.');
    }
    let data;
    try { data = await response.json(); } catch { throw new Error('Shopping did not return a readable response.'); }
    if (!response.ok) throw new Error(typeof data.error === 'string' ? data.error : 'This search is unavailable. Start a new search to try again.');
    if (!currentAuthority() || !binding || !account || data.authority?.binding !== binding || data.authority?.account_id !== account) {
      invalidate();throw new Error('Your session changed. Reload Shopping to continue.');
    }
    return data;
  }
  function choices() {
    return {intent,goal_id:intent === 'missing' ? $('discovery-goal').value || null : null,missing_basis:intent === 'missing' ? $('discovery-missing-basis').value : 'printing',focus:$('discovery-focus').value,budget:$('discovery-budget').value.trim() || null,query:$('discovery-query').value.trim(),set_id:$('discovery-set').value || null,browse_requests:1};
  }
  function signature(value) {
    return JSON.stringify({intent:value.intent || 'deals',goal_id:value.goal_id || '',missing_basis:value.missing_basis || 'printing',focus:value.focus || 'all',budget:value.budget == null ? '' : String(value.budget),query:value.query || '',set_id:value.set_id || '',browse_requests:1});
  }
  function changed() { return captured !== null && signature(choices()) !== captured; }
  function updateButtons() {
    $('discovery-search').disabled = !ready || revoked || acquiring;
    $('discovery-stop').disabled = !acquiring || stopWanted || revoked;
    $('discovery-next').disabled = !run?.has_next || acquiring || changed() || revoked;
    $('discovery-next-note').textContent = changed() ? 'Choices changed. Search starts a new search with these choices.' : run?.has_next ? 'Continues the captured choices. Starts only when selected.' : run ? 'No further results in this captured search.' : '';
  }
  function policy() {
    const missing = intent === 'missing';
    $('missing-controls').hidden = !missing;
    $('find-deals').setAttribute('aria-pressed',String(!missing));
    $('find-missing').setAttribute('aria-pressed',String(missing));
    $('intent-description').textContent = missing ? 'Find missing cards automatically from your current collection or a frozen goal you select.' : 'Search supported cards automatically, including cards you already own. No goal needed.';
    const goal = goals.find(item => String(item.id) === $('discovery-goal').value);
    $('missing-basis-label').hidden = Boolean(goal);
    const basis = goal?.policy || goal?.definition?.policy;
    $('missing-policy').textContent = goal ? `Frozen goal: ${goal.name}. ${basis === 'species' ? 'Missing species' : 'Missing exact printings'} use this goal’s retained membership and ownership policy.` : $('discovery-missing-basis').value === 'species' ? 'My current collection · missing Pokémon species. A collected species does not establish every edition or finish.' : 'My current collection · missing exact printings. Broad species declarations do not establish every edition or finish.';
    updateButtons();
  }
  function restoreChoices(value) {
    intent = value?.intent === 'missing' ? 'missing' : 'deals';
    for (const [field,id] of Object.entries({goal_id:'discovery-goal',missing_basis:'discovery-missing-basis',focus:'discovery-focus',budget:'discovery-budget',query:'discovery-query',set_id:'discovery-set'})) {
      if (value?.[field] !== undefined && value[field] !== null) $(id).value = String(value[field]);
    }
    policy();
    captured = signature(choices());
  }
  function clearResults(value = run) {
    if (!Array.isArray(value?.results)) return;
    for (const result of value.results) for (const key of Object.keys(result)) delete result[key];
    value.results = [];
  }
  function captureDeadline(value) {
    const remaining = Number(value.expires_in_seconds);
    const next = Date.now() + (Number.isFinite(remaining) && remaining >= 0 ? Math.min(1800,remaining) : 0) * 1000;
    if (deadlineRun !== value.run_id) {
      deadlineRun = value.run_id;deadline = next;sourceState = null;sourceUnavailable = false;
    } else deadline = Math.min(deadline,next);
  }
  function managed(reference) {
    return Boolean(reference && (reference.snapshot_version || reference.source_contract || reference.conflicts?.some(managed)));
  }
  function expired(reference) {
    if (!reference) return false;
    if (reference.expires_at && (!Number.isFinite(Date.parse(reference.expires_at)) || Date.parse(reference.expires_at) <= Date.now())) return true;
    return Boolean(reference.conflicts?.some(expired));
  }
  function withdrawn(reference) {
    if (!reference || !sourceState) return false;
    return Boolean(reference.snapshot_version && !sourceState.versions.includes(reference.snapshot_version) || reference.source_contract && !sourceState.sources.includes(reference.source_contract) || reference.conflicts?.some(withdrawn));
  }
  function pruneLocal() {
    if (!run || revoked) return false;
    if (Date.now() >= deadline && run.state !== 'expired') {
      ++sequence;clearTimeout(timer);clearResults();run.state = 'expired';run.running = false;run.has_next = false;acquiring = false;
      status('This temporary search has expired. Its listing data and comparisons were removed. Select Search to start a new search.');
      updateButtons();return true;
    }
    let removed = false;
    for (const result of run.results || []) {
      const reference = result.reference;
      if (!reference) continue;
      const reason = expired(reference) ? 'Reference expired' : managed(reference) && sourceUnavailable ? 'Reference lifecycle could not be checked' : withdrawn(reference) ? 'Reference source was withdrawn or replaced' : '';
      if (!reason) continue;
      result.reference = null;result.comparison = {};result.classification = 'unpriced';
      result.reason = reason + '; its value and comparison were removed.';
      result.basis = 'No current admitted reference is available. Listing prices and shipping remain separate.';
      result.save_reason = 'Temporary listing research; no reference value is retained.';
      removed = true;
    }
    return removed;
  }
  async function checkSources() {
    if (checkingSources || revoked || !run || !run.results?.some(result => managed(result.reference))) return;
    const active = run, token = sequence;let timeout;checkingSources = true;
    try {
      const state = await Promise.race([request('/api/shopping/price-source-status/'),new Promise((resolve,reject) => {timeout = setTimeout(() => reject(new Error('Reference lifecycle unavailable')),2000);})]);
      if (run !== active || sequence !== token || revoked) return;
      if (!Array.isArray(state.versions) || !Array.isArray(state.sources)) throw new Error('Reference lifecycle unavailable');
      sourceState = state;sourceUnavailable = false;
    } catch {
      if (run !== active || sequence !== token || revoked) return;
      sourceUnavailable = true;
    } finally {
      clearTimeout(timeout);checkingSources = false;
      if (run === active && sequence === token && !revoked && pruneLocal()) renderCards();
    }
  }
  function below(result) {
    return result.classification === 'comparable' && result.comparison?.below_reference !== false && result.delivered_total !== null && result.delivered_total !== undefined && Number(result.comparison?.reference_minus_delivered_total) > 0;
  }
  function card(result) {
    const identity = result.proposed_identity || {}, reference = result.reference;
    const comparable = result.classification === 'comparable', conditional = result.classification === 'conditional';
    const auction = result.price_kind === 'current_bid' || result.type === 'auction';
    const classification = below(result) ? 'Below reference' : comparable ? 'Comparable' : conditional ? 'Conditional comparison' : 'Unpriced or ambiguous';
    const art = result.revealed ? artwork(identity.artwork_url) : '';
    const metadata = [identity.set_name,identity.collector_number ? '#' + identity.collector_number : '',identity.language,identity.edition,identity.finish].filter(Boolean).map(text).join(' · ');
    const difference = below(result) ? `<p class="difference">${esc(money(result.comparison.reference_minus_delivered_total))} below reference before tax</p>` : '';
    const referenceHtml = reference ? `<div class="reference"><p class="reference-value">${esc(money(reference.amount))} reference · ${esc(reference.as_of || 'date unknown')}</p><p class="reference-basis">${esc(result.basis || 'Reference applicability remains unresolved.')}</p>${difference}<details><summary>Reference dates and applicability</summary><p>Provider valuation date: ${esc(reference.valuation_as_of || 'Unknown')}.</p><p>Captured: ${esc(reference.captured_at || 'Unknown')}.${reference.publisher_built_at ? ' Publisher build: ' + esc(reference.publisher_built_at) + '.' : ''}</p>${reference.expires_at ? `<p>Expires: ${esc(reference.expires_at)}.</p>` : ''}<p>${esc([reference.language,reference.edition,reference.finish,reference.variant,reference.condition,reference.grader,reference.grade === 'raw' ? 'Raw' : reference.grade ? 'Grade ' + reference.grade + ' scenario' : ''].filter(Boolean).map(text).join(' · ') || 'Identity and condition basis unavailable.')}</p>${reference.grade && reference.grade !== 'raw' ? '<p>A grade scenario does not establish an exact slab match.</p>' : ''}${reference.source_version ? `<p>Source version: ${esc(reference.source_version)}.</p>` : ''}${link(reference.source_url) ? `<a href="${esc(link(reference.source_url))}" target="_blank" rel="noopener noreferrer">Reference source</a>` : ''}</details></div>` : `<div class="reference"><p class="reference-value">No applicable reference</p><p>${esc(result.basis || 'An admitted reference could not be applied to this proposed identity.')}</p></div>`;
    const sellerUrl = result.revealed ? link(result.item_url, true) : '';
    const seller = result.revealed ? `${result.title ? `<p class="seller-title">${esc(result.title)}</p>` : ''}${sellerUrl ? `<a href="${esc(sellerUrl)}" target="_blank" rel="noopener noreferrer">Open seller listing on eBay</a>` : '<p>Seller link unavailable.</p>'}` : `<button type="button" class="secondary" data-discovery-reveal="${esc(result.id)}">Reveal card and seller listing</button>`;
    return `<article class="discovery-card" data-result="${esc(result.id)}"><div class="discovery-card-heading${art ? '' : ' no-art'}">${art ? `<img src="${esc(art)}" alt="" loading="lazy" decoding="async" referrerpolicy="no-referrer">` : ''}<div><span class="discovery-classification ${below(result) ? 'below' : conditional ? 'conditional' : ''}">${esc(classification)}</span><h3>${esc(!result.revealed ? 'Single-card candidate' : identity.name || 'Unresolved card identity')}</h3><p class="identity-meta">${esc(!result.revealed ? 'Reveal the proposed card and seller listing.' : metadata || 'Seller text does not establish an exact printing.')}</p></div></div><dl class="discovery-amounts"><div><dt>${auction ? 'Current bid' : 'Listing price'}</dt><dd>${esc(money(result.listing_price))}</dd></div><div><dt>Shipping</dt><dd>${esc(money(result.shipping))}</dd></div><div><dt>Delivered · before tax</dt><dd>${esc(money(result.delivered_total))}</dd></div></dl>${auction ? '<p>Current auction bid; the final price may rise.</p>' : ''}${result.reason ? `<p>${esc(result.reason)}</p>` : ''}${referenceHtml}${result.save_reason ? `<p class="muted">${esc(result.save_reason)}</p>` : ''}<div class="seller">${seller}</div></article>`;
  }
  function renderCards() {
    pruneLocal();
    const results = Array.isArray(run?.results) ? run.results : [];
    const filter = $('discovery-filter').value;
    const rows = results.filter(result => filter === 'all' || filter === 'below' && below(result) || filter === result.classification);
    $('discovery-shown').textContent = `${rows.length} of ${results.length} results`;
    $('discovery-cards').innerHTML = rows.map(card).join('') || `<div class="discovery-empty"><h3>${results.length ? 'No results match this filter' : acquiring ? 'Searching this small batch…' : 'No listings to show'}</h3><p>${results.length ? 'Choose All results to see conditional and unpriced cards.' : acquiring ? 'You can stop acquisition at any time.' : 'This batch may have no matches, incomplete listing identity or unavailable references. Change your scope or search words, or continue when Next results is available. Dex will not search again automatically.'}</p></div>`;
    $('discovery-cards').querySelectorAll('[data-discovery-reveal]').forEach(button => button.addEventListener('click',() => reveal(button)));
  }
  function render(value) {
    if (run !== value) clearResults();
    run = value;captureDeadline(value);
    acquiring = Boolean(value.running);
    $('discovery-results').hidden = false;
    $('discovery-scope').textContent = value.scope_label || (value.choices?.intent === 'missing' ? 'Missing cards · current collection' : 'Find deals · includes owned cards');
    $('discovery-limitation').textContent = [value.note || 'Temporary comparison · references retain their original dates. Results are not saved to history.',value.limitation].filter(Boolean).join(' ');
    const count = Number(value.counts?.summary_count);
    status(value.error || (value.state === 'expired' ? 'This temporary search has expired. Select Search to start a new search.' : value.state === 'stopped' ? 'Search stopped. No further requests will be sent.' : acquiring ? 'Searching a small batch… Stop prevents later requests and results.' : value.state === 'failed' ? 'Search ended after a request failed. No automatic retry.' : `Search complete${Number.isFinite(count) ? ' · ' + count + ' listing summaries checked' : ''}.`),Boolean(value.error) || value.state === 'failed');
    renderCards();updateButtons();checkSources();
  }
  function rememberRun(id) {
    if (typeof id !== 'string' || !/^[0-9a-f-]{36}$/i.test(id)) return;
    const url = new URL(location.href);url.searchParams.set('run_id',id);
    history.replaceState(null,'',url.pathname + url.search + url.hash);
  }
  function schedule(token) {
    clearTimeout(timer);
    if (!acquiring || revoked || stopWanted) return;
    timer = setTimeout(async () => {
      try {
        const value = await request(api + '?run_id=' + encodeURIComponent(run.run_id));
        if (sequence !== token || revoked || stopWanted) return;
        render(value);schedule(token);
      } catch (error) {
        if (sequence !== token || revoked || stopWanted) return;
        clearTimeout(timer);status(error.message + ' Acquisition status is unknown; use Stop before starting another search.',true);
      }
    },650);
  }
  async function start(next = false) {
    if (acquiring || revoked || !ready || next && (!run?.has_next || changed())) return;
    const prior = run, selected = choices(), token = ++sequence;
    clearResults(prior);
    acquiring = true;stopWanted = false;run = null;$('discovery-cards').replaceChildren();$('discovery-results').hidden = true;clearTimeout(timer);updateButtons();
    status(next ? 'Starting the next results batch…' : 'Starting search…');
    try {
      const value = await request(api,next ? {continuation_run:prior.run_id} : selected);
      if (sequence !== token || revoked) return;
      run = value;rememberRun(value.run_id);
      captured = next ? captured : signature(selected);
      if (stopWanted) { await stop();return; }
      render(value);schedule(token);
    } catch (error) {
      if (sequence !== token || revoked) return;
      acquiring = false;stopWanted = false;status(error.message,true);updateButtons();
    }
  }
  async function stop() {
    if (!acquiring || revoked) return;
    stopWanted = true;clearTimeout(timer);updateButtons();status('Stopping search…');
    if (!run?.run_id) return;
    const token = ++sequence;
    try {
      const value = await request(api + encodeURIComponent(run.run_id) + '/stop/',{});
      if (sequence !== token || revoked) return;
      render(value);stopWanted = false;updateButtons();
    } catch (error) {
      if (sequence !== token || revoked) return;
      stopWanted = false;status(error.message + ' Stop was not confirmed. Use Stop again.',true);updateButtons();
    }
  }
  async function reveal(button) {
    if (!run?.run_id || revoked) return;
    const initialRun = run, initialToken = sequence;
    if (pruneLocal()) renderCards();
    if (run.state === 'expired') return;
    await checkSources();
    if (run !== initialRun || sequence !== initialToken || revoked || run.state === 'expired') return;
    const token = sequence, runId = run.run_id, resultId = button.dataset.discoveryReveal;
    button.disabled = true;
    try {
      const value = await request(api + encodeURIComponent(runId) + '/reveal/' + encodeURIComponent(resultId) + '/',{});
      if (sequence !== token || revoked || run?.run_id !== runId) return;
      if (Array.isArray(value.results)) {
        const priorState = sourceState, priorUnavailable = sourceUnavailable;
        clearResults();run = value;captureDeadline(value);sourceState = priorState;sourceUnavailable = priorUnavailable;
      }
      else {
        const result = value.result || value;
        run.results = run.results.map(row => row.id === resultId ? {...row,...result} : row);
      }
      renderCards();if (run.state !== 'expired') status('Seller listing revealed. No new eBay request.');checkSources();
    } catch (error) { if (sequence === token && !revoked) { status(error.message,true);button.disabled = false; } }
  }
  function invalidate() {
    revoked = true;++sequence;clearTimeout(timer);clearInterval(lifecycleTimer);clearResults();run = null;captured = null;
    $('discovery-cards').replaceChildren();$('discovery-results').hidden = true;
    status('Your session changed. Sign in again to continue.',true);updateButtons();
  }
  $('discovery-form').addEventListener('submit',event => {event.preventDefault();start();});
  $('find-deals').addEventListener('click',() => {intent = 'deals';policy();});
  $('find-missing').addEventListener('click',() => {intent = 'missing';policy();});
  $('discovery-stop').addEventListener('click',stop);
  $('discovery-next').addEventListener('click',() => start(true));
  $('discovery-filter').addEventListener('change',renderCards);
  $('discovery-form').addEventListener('input',policy);
  $('discovery-form').addEventListener('change',policy);
  window.addEventListener('dex:authority-revoked',invalidate);
  window.addEventListener('pagehide',() => {++sequence;clearTimeout(timer);clearInterval(lifecycleTimer);clearResults();run = null;captured = null;$('discovery-cards').replaceChildren();$('discovery-results').hidden = true;});
  window.addEventListener('pageshow',event => {if (event.persisted) {invalidate();location.reload();}});
  window.addEventListener('popstate',() => location.reload());
  document.addEventListener('visibilitychange',() => {if (pruneLocal()) renderCards();if (!document.hidden) checkSources();});
  lifecycleTimer = setInterval(() => {if (pruneLocal()) renderCards();checkSources();},1000);
  (async () => {
    const token = sequence;
    try {
      const metadata = await request(api);
      if (sequence !== token || revoked) return;
      goals = Array.isArray(metadata.goals) ? metadata.goals : [];
      $('discovery-goal').innerHTML = '<option value="">My current collection</option>' + goals.map(goal => `<option value="${esc(goal.id)}">Frozen goal · ${esc(goal.name)}</option>`).join('');
      const sets = Array.isArray(metadata.sets) ? metadata.sets : [];
      $('discovery-set').innerHTML = '<option value="">All supported sets</option>' + sets.map(set => `<option value="${esc(set.id || set.set_id)}">${esc(set.name || set.set_name)}</option>`).join('');
      ready = Boolean(metadata.provider?.enabled && metadata.provider?.configured);
      policy();status(ready ? 'Ready. Select Search to find singles.' : metadata.note || metadata.reason || metadata.provider?.note || metadata.provider?.reason || 'eBay search is unavailable for this installation.');
      const runId = new URLSearchParams(location.search).get('run_id');
      if (runId && /^[0-9a-f-]{36}$/i.test(runId)) {
        const value = await request(api + '?run_id=' + encodeURIComponent(runId));
        if (sequence !== token || revoked) return;
        restoreChoices(value.choices);render(value);schedule(token);
      }
    } catch (error) { if (sequence === token && !revoked) status(error.message,true); }
  })();
})();
