'use strict';
/* Results remain in this page and the account-scoped temporary service, never browser storage. */
(() => {
  const $ = id => document.getElementById(id);
  if (!$('discovery-form')) return;
  const api = '/api/shopping/discovery/';
  const page = document.body, binding = page.dataset.navigationBinding || '', account = page.dataset.navigationAccount || '';
  const currentAuthority = () => !revoked && document.body === page && page.dataset.navigationBinding === binding && page.dataset.navigationAccount === account && !window.navigationAuthorityDiscarded && !window.navigationReauthorizing;
  const readJson = id => {try {return JSON.parse($(id)?.textContent || '{}');} catch {return {};}};
  const context = readJson('discovery-context'), initial = readJson('discovery-initial');
  let target = {species:context.species || null,group_id:context.group || null,printing_id:context.child || null};
  let intent = initial.intent === 'missing' ? 'missing' : 'deals', run = null, goals = readJson('discovery-goals'), captured = null, sequence = 0;
  let catalogSequence = 0, catalogTimer = null, localSets = [], catalogOffset = 0, catalogHasMore = false;
  const generation = context.generation;
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
    const response = await fetch(url, {method:body === undefined ? 'GET' : 'POST',credentials:'same-origin',redirect:'error',cache:'no-store',headers:{'X-Dex-Shopping-Binding':binding,...(generation == null ? {} : {'X-Dex-Shopping-Generation':String(generation)}),...(body === undefined ? {} : {'Content-Type':'application/json','X-CSRFToken':csrf()})},...(body === undefined ? {} : {body:JSON.stringify(body)})});
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
    return {intent,goal_id:intent === 'missing' ? $('discovery-goal').value || null : null,missing_basis:intent === 'missing' ? $('discovery-missing-basis').value : 'species',focus:$('discovery-focus').value,budget:$('discovery-budget').value.trim() || null,query:$('discovery-query').value.trim(),set_id:$('discovery-set').value || null,product_type:$('discovery-product-type').value,sort:$('discovery-sort').value,english_vintage:$('discovery-english-vintage').checked,...target,goal_version:intent === 'missing' ? goals.find(row => row.id === $('discovery-goal').value)?.version || null : null,generation,browse_requests:1};
  }
  function signature(value) {
    return JSON.stringify({intent:value.intent || 'deals',goal_id:value.goal_id || '',missing_basis:value.missing_basis || 'species',focus:value.focus || 'all',budget:value.budget == null ? '' : String(value.budget),query:value.query || '',set_id:value.set_id || '',product_type:value.product_type || 'both',sort:value.sort || 'ending_soonest',english_vintage:value.english_vintage !== false,species:value.species || null,group_id:value.group_id || null,printing_id:value.printing_id || null,goal_version:value.goal_version || null,generation:value.generation ?? generation,browse_requests:1});
  }
  function changed() { return captured !== null && signature(choices()) !== captured; }
  function updateButtons() {
    $('discovery-search').disabled = !ready || revoked || acquiring;
    $('discovery-stop').disabled = !acquiring || stopWanted || revoked;
    $('discovery-next').disabled = !run?.has_next || acquiring || changed() || revoked;
    $('discovery-next-note').textContent = changed() ? 'Choices changed. Search starts a new search with these choices.' : run?.has_next ? 'Continues the captured choices. Starts only when selected.' : run ? 'No further results in this captured search.' : '';
  }
  function selectionCaptions() {
    const captions = {
      'discovery-set':$('discovery-set').value || 'All supported sets',
      'discovery-focus':{all:'All supported Pokémon cards',kanto:'Kanto · 1–151',johto:'Johto · 152–251',rares:'Rare cards',bulk:'Common and uncommon cards'}[$('discovery-focus').value],
      'discovery-goal':goals.find(row => row.id === $('discovery-goal').value)?.name || 'My current collection',
      'discovery-product-type':{both:'Singles and mixed lots',singles:'Singles',mixed_lots:'Loose mixed lots'}[$('discovery-product-type').value],
    };
    for (const [id,value] of Object.entries(captions)) {const label = $(id + '-caption');if (label) label.textContent = value || '';}
    $('discovery-quick-sets').querySelectorAll('[data-set]').forEach(button => button.setAttribute('aria-pressed',String(button.dataset.set === $('discovery-set').value)));
  }
  function policy() {
    selectionCaptions();
    const missing = intent === 'missing';
    $('missing-controls').hidden = !missing;
    $('find-deals').setAttribute('aria-pressed',String(!missing));
    $('find-missing').setAttribute('aria-pressed',String(missing));
    $('intent-description').textContent = missing ? 'Current collection · Original 151 · missing Pokémon species. Select a frozen goal or exact printings when needed.' : 'Search supported cards automatically, including cards you already own. No goal needed.';
    const goal = goals.find(item => String(item.id) === $('discovery-goal').value);
    $('missing-basis-label').hidden = Boolean(goal);
    const basis = goal?.policy || goal?.definition?.policy;
    $('missing-policy').textContent = goal ? `Frozen goal: ${goal.name}. ${basis === 'species' ? 'Missing species' : 'Missing exact printings'} use this goal’s retained membership and ownership policy.` : $('discovery-missing-basis').value === 'species' ? 'My current collection · missing Pokémon species. A collected species does not establish every edition or finish.' : 'My current collection · missing exact printings. Broad species declarations do not establish every edition or finish.';
    updateButtons();
  }
  function restoreChoices(value) {
    intent = value?.intent === 'missing' ? 'missing' : 'deals';
    for (const [field,id] of Object.entries({goal_id:'discovery-goal',missing_basis:'discovery-missing-basis',focus:'discovery-focus',budget:'discovery-budget',query:'discovery-query',set_id:'discovery-set',product_type:'discovery-product-type',sort:'discovery-sort'})) {
      if (value?.[field] !== undefined && value[field] !== null) $(id).value = String(value[field]);
    }
    target = {species:value?.species || null,group_id:value?.group_id || null,printing_id:value?.printing_id || null};
    $('discovery-english-vintage').checked = value?.english_vintage !== false;
    policy();
    captured = signature(choices());
  }
  function rememberChoices(extra = {}) {
    const selected = choices(), url = new URL(location.href);url.searchParams.delete('missing');
    const fields = {q:selected.query,set_id:selected.set_id,intent,missing_basis:selected.missing_basis,scope:selected.focus,budget:selected.budget,product_type:selected.product_type,sort:selected.sort,english_vintage:selected.english_vintage ? '1' : '0',result_filter:$('discovery-filter').value,species:target.species,group:target.group_id,child:target.printing_id,goal:selected.goal_id,version:selected.goal_version,generation,...extra};
    for (const [key,value] of Object.entries(fields)) {if (value == null || value === '') url.searchParams.delete(key);else url.searchParams.set(key,String(value));}
    history.replaceState(null,'',url.pathname + url.search);
    return url.pathname + url.search;
  }
  function reviewReturn(resultId) { return rememberChoices({focus:'offer-' + resultId,scroll:Math.min(10000000,Math.max(0,Math.round(window.scrollY)))}); }
  function localImage(descriptor, label, kind) {
    const src = artwork(descriptor?.image_url);
    return `<span class="catalog-image ${kind}">${src ? `<img src="${esc(src)}" alt="${esc(descriptor.alt || label)}" loading="lazy" decoding="async" referrerpolicy="no-referrer">` : ''}<span class="catalog-image-fallback"${src ? ' hidden' : ''}>${esc(kind === 'species' ? 'Pokémon artwork unavailable' : 'Card reference unavailable')}</span></span>`;
  }
  function imageFallbacks() {
    $('catalog-cards').querySelectorAll('img').forEach(img => img.addEventListener('error',() => {img.hidden = true;img.nextElementSibling.hidden = false;},{once:true}));
  }
  function populateSets(sets) {
    if (!Array.isArray(sets)) return;
    const selected = $('discovery-set').value;
    localSets = sets;
    $('discovery-set').innerHTML = '<option value="">All supported sets</option>' + sets.map(set => `<option value="${esc(set.name)}">${esc(set.name)}</option>`).join('');
    const current = sets.find(set => [set.id,set.name].includes(selected));
    if (current) $('discovery-set').value = current.name;
    const quick = ['Base Set','Base Set 2','Jungle','Fossil','Team Rocket'];
    $('discovery-quick-sets').innerHTML = ['<button type="button" class="secondary" data-set="">All supported sets</button>',...quick.filter(name => sets.some(set => set.name === name)).map(name => `<button type="button" class="secondary" data-set="${esc(name)}">${esc(name)}</button>`)].join('');
    $('discovery-quick-sets').querySelectorAll('[data-set]').forEach(button => {button.setAttribute('aria-pressed',String(button.dataset.set === $('discovery-set').value));button.addEventListener('click',() => {$('discovery-set').value = button.dataset.set;target = {species:target.species,group_id:null,printing_id:null};catalogSearch();updateButtons();});});
  }
  function catalogParams(offset = 0) {
    const selected = choices(), params = new URLSearchParams({q:selected.query,intent,missing_basis:selected.missing_basis,scope:selected.focus,offset:String(offset),generation:String(generation)});
    if (selected.set_id) params.set('set_id',selected.set_id);
    if (target.species) params.set('species',target.species);
    if (target.group_id) params.set('group',target.group_id);
    if (target.printing_id) params.set('child',target.printing_id);
    if (selected.goal_id && selected.goal_version) {params.set('goal',selected.goal_id);params.set('version',selected.goal_version);}
    return params;
  }
  async function catalogSearch(more = false) {
    clearTimeout(catalogTimer);const token = ++catalogSequence;
    if (!currentAuthority()) return;
    const offset = more ? catalogOffset + 40 : 0;
    $('catalog-status').textContent = 'Searching your local catalog…';$('catalog-next').disabled = true;
    if (!more) {$('catalog-cards').replaceChildren();$('catalog-variants')?.remove();}
    try {
      const value = await request(api + 'catalog/?' + catalogParams(offset));
      if (token !== catalogSequence || revoked) return;
      populateSets(value.sets);

      if (!$('discovery-set').value && value.applied_set_id) {
        const set = localSets.find(row => row.id === value.applied_set_id);if (set) $('discovery-set').value = set.name;
      }
      const speciesMode = value.mode === 'species', rows = value.results || [];
      const cards = rows.map(row => speciesMode ? `<article class="catalog-card"><button type="button" id="catalog-species-${row.dex}" data-species="${row.dex}" class="catalog-choice">${localImage(row.species_artwork,row.name,'species')}<span class="catalog-card-text"><strong>${esc(row.name)}</strong><span>#${String(row.dex).padStart(3,'0')} · ${row.current_present ? 'Collected species' : 'Not collected'}</span><span>${row.matching_cards} matching card references · See cards</span></span></button></article>` : `<article class="catalog-card${target.group_id === row.id ? ' selected' : ''}"><button type="button" id="catalog-${esc(row.id)}" data-group="${esc(row.id)}" class="catalog-choice">${localImage(row.reference_image,row.name,'card')}<span class="catalog-card-text"><strong>${esc(row.name)}</strong><span>${esc(row.set_name)} · #${esc(row.collector_number)}</span><span>${row.present ? 'Owned card' : 'Not owned'} · ${row.variant_count} printing${row.variant_count === 1 ? '' : 's'}</span><span>${target.group_id === row.id ? 'Selected card reference' : 'Choose this card'}</span></span></button></article>`).join('');
      if (more) $('catalog-cards').insertAdjacentHTML('beforeend',cards);else $('catalog-cards').innerHTML = cards || '<p class="catalog-empty">No local matches in this scope. Try another Pokémon, set or number. You can still submit a supported eBay search.</p>';
      $('catalog-variants')?.remove();
      if (target.group_id && Array.isArray(value.variants) && value.variants.length) {
        const area = document.createElement('div');area.id = 'catalog-variants';area.innerHTML = `<label for="catalog-printing-select">Exact printing <span class="optional">optional</span><select id="catalog-printing-select"><option value="">No exact printing selected</option>${value.variants.filter(row => row.available).map(row => `<option value="${esc(row.id)}">${esc(row.label || row.id)}</option>`).join('')}</select></label><p id="catalog-printing-caption" class="selection-caption"></p><p class="field-help">The image is a card reference scan. Exact edition/finish imagery is unavailable. Selecting a card does not choose its first printing.</p>`;$('catalog-cards').after(area);$('catalog-printing-select').value = target.printing_id || '';const printingCaption = () => {$('catalog-printing-caption').textContent = value.variants.find(row => row.id === target.printing_id)?.label || 'No exact printing selected';};printingCaption();$('catalog-printing-select').addEventListener('change',() => {target.printing_id = $('catalog-printing-select').value || null;printingCaption();rememberChoices();updateButtons();});
      }
      catalogOffset = offset;catalogHasMore = Boolean(value.has_more);$('catalog-next').hidden = !catalogHasMore;$('catalog-next').disabled = false;
      $('catalog-clear-target').hidden = !target.species && !target.group_id;
      $('catalog-status').textContent = `${value.total} ${speciesMode ? 'Pokémon' : 'card reference'} match${value.total === 1 ? '' : 'es'} · local catalog only${value.number_note ? '. ' + value.number_note : ''}`;
      $('catalog-cards').querySelectorAll('[data-species]').forEach(button => button.addEventListener('click',() => {target = {species:Number(button.dataset.species),group_id:null,printing_id:null};catalogSearch();updateButtons();}));
      $('catalog-cards').querySelectorAll('[data-group]').forEach(button => button.addEventListener('click',() => {target = {species:null,group_id:button.dataset.group,printing_id:null};const row = rows.find(item => item.id === button.dataset.group);if (row) {$('discovery-query').value = row.name + ' ' + row.collector_number;$('discovery-set').value = row.set_name;}catalogSearch();updateButtons();}));
      imageFallbacks();selectionCaptions();rememberChoices();
      if (!more && (target.species || target.group_id)) $('catalog-results-title').focus({preventScroll:true});
    } catch (error) {if (token === catalogSequence && !revoked) {$('catalog-status').textContent = error.message;$('catalog-next').disabled = false;}}
  }
  function queueCatalog() { ++catalogSequence;clearTimeout(catalogTimer);$('catalog-cards').replaceChildren();$('catalog-variants')?.remove();$('catalog-status').textContent = 'Searching your local catalog…';catalogTimer = setTimeout(() => catalogSearch(),180); }
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
    const candidateLabel = result.discovery_kind === 'mixed_lot' ? 'Loose mixed-lot candidate' : result.discovery_kind === 'uncertain' ? 'Possible card or loose lot' : 'Single-card candidate';
    const classification = below(result) ? 'Below reference' : comparable ? 'Comparable' : conditional ? 'Conditional comparison' : 'Unpriced or ambiguous';
    const art = result.revealed ? artwork(identity.artwork_url) : '';
    const metadata = [identity.set_name,identity.collector_number ? '#' + identity.collector_number : '',identity.language,identity.edition,identity.finish].filter(Boolean).map(text).join(' · ');
    const difference = below(result) ? `<p class="difference">${esc(money(result.comparison.reference_minus_delivered_total))} below reference before tax</p>` : '';
    const referenceHtml = reference ? `<div class="reference"><p class="reference-value">${esc(money(reference.amount))} reference · ${esc(reference.as_of || 'date unknown')}</p><p class="reference-basis">${esc(result.basis || 'Reference applicability remains unresolved.')}</p>${difference}<details><summary>Reference dates and applicability</summary><p>Provider valuation date: ${esc(reference.valuation_as_of || 'Unknown')}.</p><p>Captured: ${esc(reference.captured_at || 'Unknown')}.${reference.publisher_built_at ? ' Publisher build: ' + esc(reference.publisher_built_at) + '.' : ''}</p>${reference.expires_at ? `<p>Expires: ${esc(reference.expires_at)}.</p>` : ''}<p>${esc([reference.language,reference.edition,reference.finish,reference.variant,reference.condition,reference.grader,reference.grade === 'raw' ? 'Raw' : reference.grade ? 'Grade ' + reference.grade + ' scenario' : ''].filter(Boolean).map(text).join(' · ') || 'Identity and condition basis unavailable.')}</p>${reference.grade && reference.grade !== 'raw' ? '<p>A grade scenario does not establish an exact slab match.</p>' : ''}${reference.source_version ? `<p>Source version: ${esc(reference.source_version)}.</p>` : ''}${link(reference.source_url) ? `<a href="${esc(link(reference.source_url))}" target="_blank" rel="noopener noreferrer">Reference source</a>` : ''}</details></div>` : `<div class="reference"><p class="reference-value">No applicable reference</p><p>${esc(result.basis || 'An admitted reference could not be applied to this proposed identity.')}</p></div>`;
    const sellerUrl = result.revealed ? link(result.item_url, true) : '';
    const seller = result.revealed ? `${result.title ? `<p class="seller-title">${esc(result.title)}</p>` : ''}${sellerUrl ? `<a href="${esc(sellerUrl)}" target="_blank" rel="noopener noreferrer">Open seller listing on eBay</a>` : '<p>Seller link unavailable.</p>'}` : `<button type="button" class="secondary" data-discovery-reveal="${esc(result.id)}">Reveal card and seller listing</button>`;
    return `<article class="discovery-card" id="offer-${esc(result.id)}" tabindex="-1" data-result="${esc(result.id)}"><div class="discovery-card-heading${art ? '' : ' no-art'}">${art ? `<img src="${esc(art)}" alt="" loading="lazy" decoding="async" referrerpolicy="no-referrer">` : ''}<div><span class="discovery-classification ${below(result) ? 'below' : conditional ? 'conditional' : ''}">${esc(classification)}</span><h3>${esc(!result.revealed ? candidateLabel : identity.name || 'Unresolved card identity')}</h3><p class="identity-meta">${esc(!result.revealed ? 'Reveal the proposed card and seller listing.' : metadata || 'Seller text does not establish an exact printing.')}</p></div></div><dl class="discovery-amounts"><div><dt>${auction ? 'Current bid' : 'Listing price'}</dt><dd>${esc(money(result.listing_price))}</dd></div><div><dt>Shipping</dt><dd>${esc(money(result.shipping))}</dd></div><div><dt>Delivered · before tax</dt><dd>${esc(money(result.delivered_total))}</dd></div></dl>${auction ? '<p>Current auction bid; the final price may rise.</p>' : ''}${result.reason ? `<p>${esc(result.reason)}</p>` : ''}${referenceHtml}${result.save_reason ? `<p class="muted">${esc(result.save_reason)}</p>` : ''}<div class="seller">${seller}${result.revealed ? `<a class="review-offer" data-review-id="${esc(result.id)}" href="/shopping/check/?discovery_run=${encodeURIComponent(run.run_id)}&amp;item_id=${encodeURIComponent(result.id)}">Review Ungraded value</a>` : ''}</div></article>`;
  }
  function renderCards() {
    pruneLocal();
    const results = Array.isArray(run?.results) ? run.results : [];
    const filter = $('discovery-filter').value;
    const rows = results.filter(result => filter === 'all' || filter === 'below' && below(result) || filter === result.classification);
    $('discovery-shown').textContent = `${rows.length} of ${results.length} results`;
    $('discovery-cards').innerHTML = rows.map(card).join('') || `<div class="discovery-empty"><h3>${results.length ? 'No results match this filter' : acquiring ? 'Searching this small batch…' : 'No listings to show'}</h3><p>${results.length ? 'Choose All results to see conditional and unpriced cards.' : acquiring ? 'You can stop acquisition at any time.' : 'This batch may have no matches, incomplete listing identity or unavailable references. Change your scope or search words, or continue when Next results is available. Dex will not search again automatically.'}</p></div>`;
    $('discovery-cards').querySelectorAll('[data-review-id]').forEach(anchor => anchor.addEventListener('click',() => {anchor.href = '/shopping/check/?' + new URLSearchParams({discovery_run:run.run_id,item_id:anchor.dataset.reviewId,return:reviewReturn(anchor.dataset.reviewId)});}));
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
    history.replaceState(null,'',url.pathname + url.search);
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
    revoked = true;++catalogSequence;clearTimeout(catalogTimer);$('catalog-cards').replaceChildren();++sequence;clearTimeout(timer);clearInterval(lifecycleTimer);clearResults();run = null;captured = null;
    $('discovery-cards').replaceChildren();$('discovery-results').hidden = true;
    status('Your session changed. Sign in again to continue.',true);updateButtons();
  }
  $('discovery-form').addEventListener('submit',event => {event.preventDefault();catalogSearch();});
  $('discovery-search').addEventListener('click',() => {rememberChoices();start();});
  $('catalog-next').addEventListener('click',() => {if (catalogHasMore) catalogSearch(true);});
  $('catalog-clear-target').addEventListener('click',() => {target = {species:null,group_id:null,printing_id:null};catalogSearch();updateButtons();});
  $('find-deals').addEventListener('click',() => {intent = 'deals';policy();catalogSearch();});
  $('find-missing').addEventListener('click',() => {intent = 'missing';if (!$('discovery-goal').value) {$('discovery-focus').value = 'kanto';$('discovery-missing-basis').value = 'species';}policy();catalogSearch();});
  $('discovery-stop').addEventListener('click',stop);
  $('discovery-next').addEventListener('click',() => start(true));
  $('discovery-filter').addEventListener('change',() => {renderCards();rememberChoices();});
  $('discovery-form').addEventListener('input',policy);
  $('discovery-form').addEventListener('change',event => {policy();if (['discovery-set','discovery-goal','discovery-missing-basis','discovery-focus'].includes(event.target.id)) {if (event.target.id === 'discovery-goal' && $('discovery-goal').value) $('discovery-focus').value = 'all';if (event.target.id === 'discovery-set') target = {species:target.species,group_id:null,printing_id:null};catalogSearch();}});
  $('discovery-query').addEventListener('input',() => {target = {species:null,group_id:null,printing_id:null};queueCatalog();});
  window.addEventListener('dex:authority-revoked',invalidate);
  window.addEventListener('pagehide',() => {++catalogSequence;clearTimeout(catalogTimer);$('catalog-cards').replaceChildren();++sequence;clearTimeout(timer);clearInterval(lifecycleTimer);clearResults();run = null;captured = null;$('discovery-cards').replaceChildren();$('discovery-results').hidden = true;});
  window.addEventListener('pageshow',event => {if (event.persisted) {invalidate();location.reload();}});
  window.addEventListener('popstate',() => location.reload());
  document.addEventListener('visibilitychange',() => {if (pruneLocal()) renderCards();if (!document.hidden) checkSources();});
  lifecycleTimer = setInterval(() => {if (pruneLocal()) renderCards();checkSources();},1000);
  for (const [field,id] of Object.entries({q:'discovery-query',scope:'discovery-focus',missing_basis:'discovery-missing-basis',budget:'discovery-budget',product_type:'discovery-product-type',sort:'discovery-sort'})) if (initial[field] !== undefined) $(id).value = initial[field];
  if (intent === 'missing' && !initial.scope && !initial.goal) $('discovery-focus').value = 'kanto';
  if (initial.english_vintage === '0') $('discovery-english-vintage').checked = false;
  populateSets(initial.set_id ? [{id:initial.set_id,name:initial.set_id}] : []);
  if (initial.set_id) $('discovery-set').value = initial.set_id;
  $('discovery-goal').innerHTML = '<option value="">My current collection</option>' + goals.map(goal => `<option value="${esc(goal.id)}">Frozen goal · ${esc(goal.name)}</option>`).join('');
  if (initial.goal) $('discovery-goal').value = initial.goal;
  policy();catalogSearch();
  (async () => {
    const token = sequence;
    try {
      const metadata = await request(api);
      if (sequence !== token || revoked) return;
      goals = Array.isArray(metadata.goals) ? metadata.goals : [];
      $('discovery-goal').innerHTML = '<option value="">My current collection</option>' + goals.map(goal => `<option value="${esc(goal.id)}">Frozen goal · ${esc(goal.name)}</option>`).join('');
      ready = Boolean(metadata.provider?.enabled && metadata.provider?.configured);
      policy();status(ready ? 'Ready. Search cards locally, then select Find on eBay for listings.' : metadata.note || metadata.reason || metadata.provider?.note || metadata.provider?.reason || 'eBay search is unavailable for this installation.');
      if (initial.goal) $('discovery-goal').value = initial.goal;
      policy();await catalogSearch();
      const runId = new URLSearchParams(location.search).get('run_id');
      if (runId && /^[0-9a-f-]{36}$/i.test(runId)) {
        const value = await request(api + '?run_id=' + encodeURIComponent(runId));
        if (sequence !== token || revoked) return;
        restoreChoices(value.choices);render(value);schedule(token);
        for (const [field,id] of Object.entries({q:'discovery-query',scope:'discovery-focus',missing_basis:'discovery-missing-basis',budget:'discovery-budget',product_type:'discovery-product-type',sort:'discovery-sort'})) if (initial[field] !== undefined) $(id).value = initial[field];
        if (initial.intent) intent = initial.intent;
        if (initial.goal) $('discovery-goal').value = initial.goal;
        if (initial.english_vintage !== undefined) $('discovery-english-vintage').checked = initial.english_vintage === '1';
        target = {species:context.species || null,group_id:context.group || null,printing_id:context.child || null};
        if (initial.set_id) $('discovery-set').value = localSets.find(row => [row.id,row.name].includes(initial.set_id))?.name || initial.set_id;
        policy();
        if (initial.result_filter) $('discovery-filter').value = initial.result_filter;
        renderCards();await catalogSearch();
        requestAnimationFrame(() => {if (initial.scroll) window.scrollTo(0,Number(initial.scroll));if (initial.focus) $(initial.focus)?.focus({preventScroll:true});});
      }
    } catch (error) { if (sequence === token && !revoked) status(error.message,true); }
  })();
})();
