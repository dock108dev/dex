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
  let catalogStarted = false;
  let catalogSequence = 0, catalogTimer = null, localSets = [], catalogOffset = 0, catalogHasMore = false;
  const generation = context.generation;
  let focusResults = false;
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
      if (ebayOnly && (url.protocol !== 'https:' || url.port && url.port !== '443' || !/(^|\.)ebay\.com$/i.test(url.hostname) || /[\\\x00-\x20\x7f]/.test(value))) return '';
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
    return {intent,goal_id:intent === 'missing' ? $('discovery-goal').value || null : null,missing_basis:intent === 'missing' ? $('discovery-missing-basis').value : 'species',focus:$('discovery-focus').value,budget:$('discovery-budget').value.trim() || null,query:$('discovery-query').value.trim(),set_id:$('discovery-set').value || null,product_type:$('discovery-product-type').value,sort:$('discovery-sort').value,english_vintage:$('discovery-english-vintage').checked,...target,goal_version:intent === 'missing' ? (context.query?.goal === $('discovery-goal').value ? context.query.version : goals.find(row => row.id === $('discovery-goal').value)?.version) || null : null,generation,browse_requests:1};
  }
  function signature(value) {
    return JSON.stringify({intent:value.intent || 'deals',goal_id:value.goal_id || '',missing_basis:value.missing_basis || 'species',focus:value.focus || 'all',budget:value.budget == null ? '' : String(value.budget),query:value.query || '',set_id:value.set_id || '',product_type:value.product_type || 'both',sort:value.sort || 'ending_soonest',english_vintage:value.english_vintage !== false,species:value.species || null,group_id:value.group_id || null,printing_id:value.printing_id || null,goal_version:value.goal_version || null,generation:value.generation ?? generation,browse_requests:1});
  }
  function changed() { return captured !== null && signature(choices()) !== captured; }
  function updateButtons() {
    $('discovery-search').disabled = !ready || revoked || acquiring;
    $('discovery-stop').disabled = (!acquiring && !run?.run_id) || ['stopped','expired'].includes(run?.state) || stopWanted || revoked;
    $('discovery-next').disabled = !run?.has_next || acquiring || changed() || revoked;
    $('discovery-next-note').textContent = acquiring && run?.run_id ? 'Loading more… You can keep browsing or Stop.' : changed() ? 'Choices changed. Select Search eBay to start a new search.' : run?.has_next ? 'More from this search.' : run ? 'You’ve reached the end of this search.' : '';
  }
  function selectionCaptions() {
    const captions = {
      'discovery-set':$('discovery-set').value || 'All supported sets',
      'discovery-focus':{all:'All supported Pokémon cards',kanto:'Kanto · 1–151',johto:'Johto · 152–251',rares:'Rare cards',bulk:'Common and uncommon cards'}[$('discovery-focus').value],
      'discovery-goal':goals.find(row => row.id === $('discovery-goal').value)?.name || 'My current collection',
      'discovery-product-type':{both:'Singles and mixed lots',singles:'Singles',mixed_lots:'Loose mixed lots'}[$('discovery-product-type').value],
    };
    const measure = document.createElement('canvas').getContext('2d');
    for (const [id,value] of Object.entries(captions)) {
      const label = $(id + '-caption'), select = $(id);
      if (!label) continue;
      label.textContent = value || '';
      if (measure) {
        measure.font = window.getComputedStyle(select).font;
        const selected = select.selectedOptions?.[0]?.text || value || '';
        label.hidden = !value || measure.measureText(selected).width <= select.clientWidth - 52;
      } else label.hidden = false;
    }
    $('discovery-quick-sets').querySelectorAll('[data-set]').forEach(button => button.setAttribute('aria-pressed',String(button.dataset.set === $('discovery-set').value)));
  }
  function policy() {
    selectionCaptions();
    const missing = intent === 'missing';
    $('missing-controls').hidden = !missing;
    $('find-deals').setAttribute('aria-pressed',String(!missing));
    $('find-missing').setAttribute('aria-pressed',String(missing));
    $('intent-description').textContent = missing ? 'Current collection · Original 151 · missing Pokémon species. Select a frozen goal or exact printings when needed.' : 'Search by name or broad words, including cards you own. Mixed lots may contain the card; contents are unverified.';
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
  function rememberChoices(extra = {}, replace = true) {
    const selected = choices(), url = new URL(location.href);url.searchParams.delete('missing');
    const fields = {q:selected.query,set_id:selected.set_id,intent,missing_basis:selected.missing_basis,scope:selected.focus,budget:selected.budget,product_type:selected.product_type,sort:selected.sort,english_vintage:selected.english_vintage ? '1' : '0',result_filter:$('discovery-filter').value,species:target.species,group:target.group_id,child:target.printing_id,goal:selected.goal_id,version:selected.goal_version,generation,...extra};
    for (const [key,value] of Object.entries(fields)) {if (value == null || value === '') url.searchParams.delete(key);else url.searchParams.set(key,String(value));}
    if (replace) history.replaceState(null,'',url.pathname + url.search);
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
    $('discovery-quick-sets').innerHTML = quick.filter(name => sets.some(set => set.name === name)).map(name => `<button type="button" class="secondary" data-set="${esc(name)}">${esc(name)}</button>`).join('');
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
    catalogStarted = true;
    const offset = more ? catalogOffset + 40 : 0;
    $('catalog-status').textContent = 'Searching your local catalog…';$('catalog-next').disabled = true;
    if (!more) {$('catalog-cards').replaceChildren();$('catalog-variants')?.remove();}
    try {
      const value = await request(api + 'catalog/?' + catalogParams(offset));
      if (token !== catalogSequence || revoked) return;
      populateSets(value.sets);


      const speciesMode = value.mode === 'species', rows = value.results || [];
      const cards = rows.map(row => speciesMode ? `<article class="catalog-card"><button type="button" id="catalog-species-${row.dex}" data-species="${row.dex}" class="catalog-choice">${localImage(row.species_artwork,row.name,'species')}<span class="catalog-card-text"><strong>${esc(row.name)}</strong><span>#${String(row.dex).padStart(3,'0')} · ${row.current_present ? 'Collected species' : 'Not collected'}</span><span>${row.matching_cards} matching card references · See cards</span></span></button></article>` : `<article class="catalog-card${target.group_id === row.id ? ' selected' : ''}"><button type="button" id="catalog-${esc(row.id)}" data-group="${esc(row.id)}" class="catalog-choice">${localImage(row.reference_image,row.name,'card')}<span class="catalog-card-text"><strong>${esc(row.name)}</strong><span>${esc(row.set_name)} · #${esc(row.collector_number)}</span><span>${row.present ? 'Owned card' : 'Not owned'} · ${row.variant_count} printing${row.variant_count === 1 ? '' : 's'}</span><span>${target.group_id === row.id ? 'Selected card reference' : 'Select this card as a search target'}</span></span></button><a id="catalog-details-${esc(row.id)}" class="catalog-details" data-card-details="${esc(row.id)}" href="/card-groups/${esc(row.id)}/" aria-label="Card details for ${esc(row.name)} · ${esc(row.set_name)} #${esc(row.collector_number)}">Card details</a></article>`).join('');
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
      $('catalog-cards').querySelectorAll('[data-card-details]').forEach(anchor => {
        const destination = (replace = false) => {
          const id = anchor.dataset.cardDetails, params = new URLSearchParams({generation:String(generation),return:rememberChoices({focus:anchor.id,scroll:Math.min(10000000,Math.max(0,Math.round(window.scrollY)))},replace)});
          const child = target.group_id === id ? target.printing_id : rows.find(row => row.id === id)?.selected_child;
          if (child) params.set('child',child);
          return '/card-groups/' + encodeURIComponent(id) + '/?' + params;
        };
        anchor.href = destination();
        anchor.addEventListener('click',() => {anchor.href = destination(true);});
      });
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
    const identity = result.proposed_identity || (result.identity_candidates?.length === 1 ? result.identity_candidates[0] : {}) || {}, reference = result.reference;
    const comparable = result.classification === 'comparable', conditional = result.classification === 'conditional';
    const auction = result.price_kind === 'current_bid' || result.type === 'auction';
    const candidateLabel = result.discovery_kind === 'mixed_lot' ? 'Loose mixed-lot candidate' : result.discovery_kind === 'uncertain' ? 'Possible card or loose lot' : 'Single-card candidate';
    const classification = below(result) ? 'Below reference' : comparable ? 'Comparable' : conditional ? 'Conditional comparison' : 'Unpriced or ambiguous';
    const sellerArt = window.DexDiscoveryDisplay?.sellerImage(result.seller_image) || '';
    const art = sellerArt || artwork(identity.artwork_url);
    const artLabel = sellerArt ? 'Seller photo' : 'Catalog reference';
    const image = `<div class="offer-image" data-source="${esc(art)}">${art ? `<img src="${esc(art)}" alt="${esc(artLabel)}" loading="lazy" decoding="async" referrerpolicy="no-referrer">` : ''}<span class="offer-image-fallback"${art ? ' hidden' : ''}>Image unavailable</span><span class="offer-image-label">${esc(art ? artLabel : 'No seller photo or catalog image')}</span></div>`;
    const metadata = [identity.set_name,identity.collector_number ? '#' + identity.collector_number : '',identity.language,identity.edition,identity.finish].filter(Boolean).map(text).join(' · ');
    const difference = below(result) ? `<p class="difference">${esc(money(result.comparison.reference_minus_delivered_total))} below reference before tax</p>` : '';
    const referenceHtml = reference ? `<div class="reference"><p class="reference-value">${esc(money(reference.amount))} reference · ${esc(reference.as_of || 'date unknown')}</p><p class="reference-basis">${esc(result.basis || 'Reference applicability remains unresolved.')}</p>${difference}<details><summary>Reference dates and applicability</summary><p>Provider valuation date: ${esc(reference.valuation_as_of || 'Unknown')}.</p><p>Captured: ${esc(reference.captured_at || 'Unknown')}.${reference.publisher_built_at ? ' Publisher build: ' + esc(reference.publisher_built_at) + '.' : ''}</p>${reference.expires_at ? `<p>Expires: ${esc(reference.expires_at)}.</p>` : ''}<p>${esc([reference.language,reference.edition,reference.finish,reference.variant,reference.condition,reference.grader,reference.grade === 'raw' ? 'Raw' : reference.grade ? 'Grade ' + reference.grade + ' scenario' : ''].filter(Boolean).map(text).join(' · ') || 'Identity and condition basis unavailable.')}</p>${reference.grade && reference.grade !== 'raw' ? '<p>A grade scenario does not establish an exact slab match.</p>' : ''}${reference.source_version ? `<p>Source version: ${esc(reference.source_version)}.</p>` : ''}${link(reference.source_url) ? `<a href="${esc(link(reference.source_url))}" target="_blank" rel="noopener noreferrer">Reference source</a>` : ''}</details></div>` : `<div class="reference"><p class="reference-value">No applicable reference</p><p>${esc(result.basis || 'An admitted reference could not be applied to this proposed identity.')}</p></div>`;
    const sellerUrl = link(result.item_url, true);
    const seller = `${sellerUrl ? `<a href="${esc(sellerUrl)}" target="_blank" rel="noopener noreferrer" aria-label="Open seller listing on eBay">Open seller</a>` : '<p>Seller link unavailable.</p>'}`;
    const time = auction ? `<p data-auction-end="${esc(result.ends_at || '')}">${esc(window.DexDiscoveryDisplay?.auctionTime(result.ends_at) || 'Auction · end time unknown')}</p>` : '';
    return `<article class="discovery-card" id="offer-${esc(result.id)}" tabindex="-1" data-result="${esc(result.id)}"><div class="discovery-card-heading">${image}<div><h3>${esc(result.title || identity.name || candidateLabel)}</h3>${identity.name ? `<p>Proposed: ${esc(identity.name)}</p>` : ''}${metadata ? `<p class="identity-meta">${esc(metadata)}</p>` : ''}${comparable || conditional ? `<span class="discovery-classification">${esc(classification)}</span>` : ''}</div></div><dl class="discovery-amounts"><div><dt>${auction ? 'Current bid' : 'Listing price'}</dt><dd class="${result.listing_price == null ? 'is-unknown' : ''}">${esc(money(result.listing_price))}</dd></div><div><dt>Shipping</dt><dd class="${result.shipping == null ? 'is-unknown' : ''}">${esc(money(result.shipping))}</dd></div><div><dt>Delivered · before tax</dt><dd class="${result.delivered_total == null ? 'is-unknown' : ''}">${esc(money(result.delivered_total))}</dd></div></dl>${time}<div class="seller">${seller}<a class="review-offer" data-review-id="${esc(result.id)}" href="/shopping/check/?discovery_run=${encodeURIComponent(run.run_id)}&amp;item_id=${encodeURIComponent(result.id)}">Inspect lot</a></div><details><summary>Comparison & listing details</summary>${result.reason ? `<p>${esc(result.reason)}</p>` : ''}${referenceHtml}${result.save_reason ? `<p>${esc(result.save_reason)}</p>` : ''}</details></article>`;
  }

  function renderCards() {
    pruneLocal();
    const results = Array.isArray(run?.results) ? run.results : [];
    const filter = $('discovery-filter').value;
    const rows = results.filter(result => filter === 'all' || filter === 'below' && below(result) || filter === result.classification);
    $('discovery-shown').textContent = `${rows.length} of ${results.length} results${filter === 'all' ? '' : ' · ' + ({below:'Comparable · below reference',conditional:'Conditional comparisons',unpriced:'Unpriced or ambiguous'}[filter] || '')}`;
    const markup = rows.map(card).join('') || `<div class="discovery-empty"><h3>${results.length ? 'No results match this filter' : acquiring ? 'Searching this small batch…' : 'No listings to show'}</h3><p>${results.length ? 'Choose All results to see conditional and unpriced cards.' : acquiring ? 'You can stop acquisition at any time.' : 'This batch may have no matches, incomplete listing identity or unavailable references. Change your scope or search words, or continue when More results is available. Dex will not search again automatically.'}</p></div>`;
    if (window.DexDiscoveryDisplay) window.DexDiscoveryDisplay.patch($('discovery-cards'),markup);else $('discovery-cards').innerHTML = markup;
    $('discovery-cards').querySelectorAll('[data-review-id]').forEach(anchor => {if (anchor.dataset.reviewBound) return;anchor.dataset.reviewBound = '1';anchor.addEventListener('click',() => {anchor.href = '/shopping/check/?' + new URLSearchParams({discovery_run:run.run_id,item_id:anchor.dataset.reviewId,return:reviewReturn(anchor.dataset.reviewId)});});});
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
    if (focusResults && !acquiring && value.results?.length) {
      focusResults = false;requestAnimationFrame(() => {$('discovery-results-title').focus({preventScroll:true});$('discovery-results').scrollIntoView?.({block:'start'});});
    }
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
    const keepBrowsing = next && Boolean(prior.choices?.query);
    focusResults = !next;
    if (!keepBrowsing) clearResults(prior);
    acquiring = true;stopWanted = false;run = keepBrowsing ? prior : null;
    if (!keepBrowsing) {$('discovery-cards').replaceChildren();$('discovery-results').hidden = true;}
    clearTimeout(timer);updateButtons();
    status(next ? 'Starting the next results batch…' : 'Starting search…');
    try {
      const value = await request(api,next ? {continuation_run:prior.run_id} : selected);
      if (sequence !== token || revoked) return;
      // Admission acknowledges the same named run without reprojecting listings.
      // Keep its received page under the original deadline while polling; local
      // reference expiry/withdrawal checks continue on these visible results.
      if (next && value.running && value.run_id === prior.run_id && !value.results?.length) value.results = prior.results;
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
    if ((!acquiring && !run?.run_id) || revoked) return;
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
  function invalidate() {
    revoked = true;++catalogSequence;clearTimeout(catalogTimer);$('catalog-cards').replaceChildren();++sequence;clearTimeout(timer);clearInterval(lifecycleTimer);clearResults();run = null;captured = null;
    $('discovery-cards').replaceChildren();$('discovery-results').hidden = true;
    status('Your session changed. Sign in again to continue.',true);updateButtons();
  }
  $('discovery-form').addEventListener('submit',event => {event.preventDefault();rememberChoices();start();});
  $('catalog-search').addEventListener('click',() => catalogSearch());
  $('catalog-next').addEventListener('click',() => {if (catalogHasMore) catalogSearch(true);});
  $('catalog-clear-target').addEventListener('click',() => {target = {species:null,group_id:null,printing_id:null};catalogSearch();updateButtons();});
  $('find-deals').addEventListener('click',() => {intent = 'deals';policy();catalogSearch();});
  $('find-missing').addEventListener('click',() => {intent = 'missing';if (!$('discovery-goal').value) {$('discovery-focus').value = 'kanto';$('discovery-missing-basis').value = 'species';}policy();catalogSearch();});
  $('discovery-stop').addEventListener('click',stop);
  $('discovery-next').addEventListener('click',() => start(true));
  $('discovery-filter').addEventListener('change',() => {renderCards();rememberChoices();});
  $('discovery-form').addEventListener('input',policy);
  $('discovery-form').addEventListener('change',event => {policy();if (['discovery-set','discovery-goal','discovery-missing-basis','discovery-focus'].includes(event.target.id)) {if (event.target.id === 'discovery-goal' && $('discovery-goal').value) $('discovery-focus').value = 'all';if (event.target.id === 'discovery-set') target = {species:target.species,group_id:null,printing_id:null};catalogSearch();}});
  let dismissedSpelling = '';
  function spelling() {
    const value = $('discovery-query').value;
    const corrected = value.replace(/\bVenasaur\b/ig,'Venusaur').replace(/\bGyrados\b/ig,'Gyarados');
    const box = $('discovery-suggestions');box.hidden = corrected === value || dismissedSpelling === value;
    box.innerHTML = box.hidden ? '' : `<p>Did you mean <strong>${esc(corrected)}</strong>?</p><button type="button" data-spelling="correct">Use ${esc(corrected)}</button> <button type="button" data-spelling="original">Keep ${esc(value)} as typed</button>`;
    box.querySelectorAll('[data-spelling]').forEach(button => button.addEventListener('click',() => {if (button.dataset.spelling === 'correct') $('discovery-query').value = corrected;dismissedSpelling = $('discovery-query').value;spelling();target = {species:null,group_id:null,printing_id:null};queueCatalog();policy();}));
  }
  $('discovery-query').addEventListener('input',() => {spelling();target = {species:null,group_id:null,printing_id:null};queueCatalog();});
  window.addEventListener('dex:authority-revoked',invalidate);
  window.addEventListener('pagehide',() => {++catalogSequence;clearTimeout(catalogTimer);$('catalog-cards').replaceChildren();++sequence;clearTimeout(timer);clearInterval(lifecycleTimer);clearResults();run = null;captured = null;$('discovery-cards').replaceChildren();$('discovery-results').hidden = true;});
  window.addEventListener('pageshow',event => {if (event.persisted) {invalidate();location.reload();}});
  window.addEventListener('popstate',() => location.reload());
  document.addEventListener('visibilitychange',() => {if (pruneLocal()) renderCards();if (!document.hidden) checkSources();});
  lifecycleTimer = setInterval(() => {if (pruneLocal()) renderCards();window.DexDiscoveryDisplay?.tick($('discovery-cards'));checkSources();},1000);
  for (const [field,id] of Object.entries({q:'discovery-query',scope:'discovery-focus',missing_basis:'discovery-missing-basis',budget:'discovery-budget',product_type:'discovery-product-type',sort:'discovery-sort'})) if (initial[field] !== undefined) $(id).value = initial[field];
  if (intent === 'missing' && !initial.scope && !initial.goal) $('discovery-focus').value = 'kanto';
  if (initial.english_vintage !== undefined) $('discovery-english-vintage').checked = initial.english_vintage === '1';
  populateSets(initial.set_id ? [{id:initial.set_id,name:initial.set_id}] : []);
  if (initial.set_id) $('discovery-set').value = initial.set_id;
  $('discovery-goal').innerHTML = '<option value="">My current collection</option>' + goals.map(goal => `<option value="${esc(goal.id)}">Frozen goal · ${esc(goal.name)}</option>`).join('');
  if (initial.goal) $('discovery-goal').value = initial.goal;
  if (initial.focus?.startsWith('catalog-')) document.querySelector('.discovery-local').open = true;
  document.querySelector('.discovery-local').addEventListener('toggle',event => {if (event.target.open && !catalogStarted) catalogSearch();});
  window.addEventListener('resize',selectionCaptions);
  if (window.ResizeObserver) {
    const captions = new window.ResizeObserver(selectionCaptions);
    ['discovery-set','discovery-product-type','discovery-focus','discovery-goal'].forEach(id => captions.observe($(id)));
  }
  policy();spelling();
  (async () => {
    const token = sequence;
    try {
      // Start local revalidation alongside independent options, not after them.
      // Capture failure immediately so an early rejected read is never unhandled.
      const options = request(api);
      const runId = initial.run_id;
      const restoring = runId && /^[0-9a-f-]{36}$/i.test(runId);
      const restored = restoring ? request(api + '?run_id=' + encodeURIComponent(runId)).then(value => ({value}),error => ({error})) : null;
      const metadata = await options;
      if (sequence !== token || revoked) return;
      goals = Array.isArray(metadata.goals) ? metadata.goals : [];
      $('discovery-goal').innerHTML = '<option value="">My current collection</option>' + goals.map(goal => `<option value="${esc(goal.id)}">Frozen goal · ${esc(goal.name)}</option>`).join('');
      ready = Boolean(metadata.provider?.enabled && metadata.provider?.configured);
      policy();status(ready ? '' : metadata.note || metadata.reason || metadata.provider?.note || metadata.provider?.reason || 'eBay search is unavailable for this installation.');
      if (initial.goal) $('discovery-goal').value = initial.goal;
      populateSets(metadata.sets);policy();
      if (restoring) {
        status('Restoring your search…');
        const response = await restored;
        if (response.error) throw response.error;
        const value = response.value;
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
        renderCards();
      }
      // Restore received offers and the reading position before optional local
      // catalog work. No provider content is cached across navigation.
      requestAnimationFrame(() => {if (!currentAuthority()) return;if (initial.scroll) window.scrollTo(0,Number(initial.scroll));if (initial.focus) $(initial.focus)?.focus({preventScroll:true});});
      // A closed local explorer does not need another all-catalog ownership read.
      // Opening it explicitly still uses the ordinary checked local service.
      if (!catalogStarted && (!restoring || document.querySelector('.discovery-local').open)) await catalogSearch();
    } catch (error) { if (sequence === token && !revoked) status(error.message,true); }
  })();
})();
