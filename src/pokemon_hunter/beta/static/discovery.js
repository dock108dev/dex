'use strict';
/* Results remain in this page and the account-scoped temporary service, never browser storage. */
(() => {
  const $ = id => document.getElementById(id);
  if (!$('discovery-form')) return;
  const api = '/api/shopping/discovery/';
  const receiptView = () => $('discovery-form').dataset.lotSearch === 'true' ? '&view=received' : '';
  const page = document.body, binding = page.dataset.navigationBinding || '', account = page.dataset.navigationAccount || '';
  const currentAuthority = () => !revoked && document.body === page && page.dataset.navigationBinding === binding && page.dataset.navigationAccount === account && !window.navigationAuthorityDiscarded && !window.navigationReauthorizing;
  const readJson = id => {try {return JSON.parse($(id)?.textContent || '{}');} catch {return {};}};
  const context = readJson('discovery-context'), initial = readJson('discovery-initial');
  let target = {species:context.species || null,group_id:context.group || null,printing_id:context.child || null};
  let intent = initial.intent === 'missing' ? 'missing' : 'deals', run = null, goals = readJson('discovery-goals'), captured = null, sequence = 0;
  let catalogStarted = false, targetSequence = 0, targetsReady = false;
  let catalogSequence = 0, catalogTimer = null, localSets = [], catalogOffset = 0, catalogHasMore = false;
  const generation = context.generation;
  let goalVersion = initial.version || null;
  let focusResults = false, windowMinute = -1, validatingRun = false, loadingValues = false, lastRunCheck = 0;
  let timer = null, acquiring = false, stopWanted = false, ready = Boolean(initial.provider?.enabled && initial.provider?.configured), revoked = false;
  let actionId = initial.request_id || null, uncertain = Boolean(actionId), admissionPending = false;
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
  async function request(url, body, action = null, timeoutMs = 12000) {
    const controller=window.AbortController ? new window.AbortController() : null;
    const timeout=controller ? setTimeout(()=>controller.abort(),timeoutMs) : null;
    let response;
    try { response = await fetch(url, {...(controller ? {signal:controller.signal} : {}),method:body === undefined ? 'GET' : 'POST',credentials:'same-origin',redirect:'error',cache:'no-store',headers:{'X-Dex-Shopping-Binding':binding,...(action ? {'X-Dex-Shopping-Action':action} : {}),...(generation == null ? {} : {'X-Dex-Shopping-Generation':String(generation)}),...(body === undefined ? {} : {'Content-Type':'application/json','X-CSRFToken':csrf()})},...(body === undefined ? {} : {body:JSON.stringify(body)})});
    if (response.status === 403 || response.status === 401) {
      window.discardNavigationAuthority?.();if (!revoked) invalidate();
      throw new Error('Your session is unavailable. Sign in again to continue.');
    }
    let data;
    try { data = await response.json(); } catch { throw new Error('Shopping did not return a readable response.'); }
    if (!response.ok) {
      const busy = response.status === 503 && data.error === 'runtime_busy';
      if (response.status === 409 && ['lot_hunt_policy','lot_hunt_capacity'].includes(data.code)) throw Object.assign(new Error(data.error), {status:409, category:'not_dispatched', code:data.code});
      throw Object.assign(new Error(busy ? 'Dex is busy with another local action. This request did not start.' : 'This section could not be loaded. Reload this section to check its current state.'), {status:response.status, category:busy ? 'not_dispatched' : 'unknown', code:data.error});
    }
    if (!currentAuthority() || !binding || !account || data.authority?.binding !== binding || data.authority?.account_id !== account) {
      invalidate();throw new Error('Your session changed. Reload Shopping to continue.');
    }
    return data;
    } catch (error) {
      if (error.name === 'AbortError') throw new Error('Local status did not respond in time. Reload this section to check; no acquisition was retried.');
      throw error;
    } finally {clearTimeout(timeout);}
  }
  function choices() {
    const selected = {intent,goal_id:intent === 'missing' ? $('discovery-goal').value || null : null,missing_basis:intent === 'missing' ? $('discovery-missing-basis').value : 'species',focus:$('discovery-focus').value,budget:$('discovery-budget').value.trim() || null,budget_mode:$('discovery-budget-mode').value || 'limit',budget_rule:$('discovery-budget-rule').value.trim(),budget_value_basis:$('discovery-budget-value-basis').value || 'collectible',query:$('discovery-query').value.trim(),set_id:$('discovery-set').value || null,product_type:$('discovery-product-type').value,sort:$('discovery-sort').value,english_vintage:$('discovery-english-vintage').checked,...target,goal_version:intent === 'missing' ? (goalVersion || ($('discovery-form').dataset.lotSearch !== 'true' ? goals.find(row => row.id === $('discovery-goal').value)?.version : null)) : null,generation,browse_requests:1};
    if ($('discovery-form').dataset.lotSearch === 'true') Object.assign(selected, {collection_intent:intent === 'missing',prefer_vintage:Boolean($('discovery-prefer-vintage').checked),currency:'USD',missing_basis:'species',product_type:'mixed_lots',sort:'ending_soonest',english_vintage:false});
    return selected;
  }
  function signature(value) {
    return JSON.stringify({prefer_vintage:Boolean(value.prefer_vintage),collection_intent:Boolean(value.collection_intent),intent:value.intent || 'deals',goal_id:value.goal_id || '',missing_basis:value.missing_basis || 'species',focus:value.focus || 'all',budget:value.budget == null ? '' : String(value.budget),budget_mode:value.budget_mode || 'limit',budget_rule:value.budget_rule || '',budget_value_basis:value.budget_value_basis || 'collectible',query:value.query || '',set_id:value.set_id || '',product_type:value.product_type || 'both',sort:value.sort || 'ending_soonest',english_vintage:value.english_vintage !== false,species:value.species || null,group_id:value.group_id || null,printing_id:value.printing_id || null,goal_version:value.goal_version || null,generation:value.generation ?? generation,browse_requests:1});
  }
  function changed() { return captured !== null && signature(choices()) !== captured; }
  function updateButtons() {
    $('discovery-search').disabled = !ready || revoked || acquiring || uncertain || (intent === 'missing' && (!targetsReady || !target.species));
    $('discovery-stop').hidden = !acquiring && !uncertain;
    $('discovery-stop').disabled = (!acquiring && !run?.run_id) || ['stopped','expired'].includes(run?.state) || (stopWanted && !uncertain) || revoked;
    $('discovery-next').disabled = !run?.has_next || acquiring || uncertain || changed() || revoked;
    $('discovery-next-note').textContent = acquiring && run?.run_id ? 'Loading more… You can keep browsing or Stop.' : changed() ? 'Select Find lots to search with these changes.' : run?.has_next ? 'More from this search.' : run ? 'You’ve reached the end of this search.' : '';
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
    if (missing) document.querySelector('.discovery-options').open = true;
    $('find-deals').setAttribute('aria-pressed',String(!missing));
    $('find-missing').setAttribute('aria-pressed',String(missing));
    $('intent-description').textContent = missing ? 'Choose a Pokémon missing from your collection.' : 'Find the best matches for your request.';
    const goal = goals.find(item => String(item.id) === $('discovery-goal').value);
    $('missing-basis-label').hidden = true;
    $('discovery-query').readOnly = missing;
    for (const option of $('discovery-focus').options) option.disabled = missing && ['rares','bulk'].includes(option.value);
    const basis = goal?.policy || goal?.definition?.policy;
    $('missing-policy').textContent = goal ? `Frozen goal: ${goal.name}. ${basis === 'species' ? 'Missing species' : 'Missing exact printings'} use this goal’s retained membership and ownership policy.` : $('discovery-missing-basis').value === 'species' ? 'My current collection · missing Pokémon species. A collected species does not establish every edition or finish.' : 'My current collection · missing exact printings. Broad species declarations do not establish every edition or finish.';
    updateButtons();
  }
  function restoreChoices(value) {
    intent = value?.intent === 'missing' ? 'missing' : 'deals';
    goalVersion = value?.goal_version || null;
    for (const [field,id] of Object.entries({goal_id:'discovery-goal',missing_basis:'discovery-missing-basis',focus:'discovery-focus',budget:'discovery-budget',budget_mode:'discovery-budget-mode',budget_rule:'discovery-budget-rule',budget_value_basis:'discovery-budget-value-basis',query:'discovery-query',set_id:'discovery-set',product_type:'discovery-product-type',sort:'discovery-sort'})) {
      if (value?.[field] !== undefined && value[field] !== null) $(id).value = String(value[field]);
    }
    target = {species:value?.species || null,group_id:value?.group_id || null,printing_id:value?.printing_id || null};
    $('discovery-english-vintage').checked = value?.english_vintage !== false;
    $('discovery-prefer-vintage').checked = Boolean(value?.prefer_vintage);
    policy();
    captured = signature(choices());
  }
  function rememberChoices(extra = {}, replace = true) {
    const selected = choices(), url = new URL(location.href);url.searchParams.delete('missing');
    const fields = {prefer_vintage:selected.prefer_vintage ? '1' : '0',q:selected.query,set_id:selected.set_id,intent,missing_basis:selected.missing_basis,scope:selected.focus,budget:selected.budget,budget_mode:selected.budget_mode,budget_rule:selected.budget_rule,budget_value_basis:selected.budget_value_basis,product_type:selected.product_type,sort:selected.sort,english_vintage:selected.english_vintage ? '1' : '0',result_filter:$('discovery-filter').value,...(window.DexLotValues ? {time_window:$('lot-time-window').value,value_sort:$('lot-value-sort').value,buying_mode:$('lot-buying-mode').value,value_basis:$('lot-value-basis')?.value || 'all',estimate_filter:$('lot-estimate-filter').value,era_filter:$('lot-era-filter').checked?'pre2000':'all'} : {}),species:target.species,group:target.group_id,child:target.printing_id,goal:selected.goal_id,version:selected.goal_version,generation,...extra};
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
    if (selected && !sets.some(set => [set.id,set.name].includes(selected))) $('discovery-set').innerHTML += `<option value="${esc(selected)}">${esc(selected)}</option>`;
    const current = sets.find(set => [set.id,set.name].includes(selected));
    $('discovery-set').value = current ? current.name : selected;
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
  async function catalogSearch(more = false, explicit = false) {
    if (!explicit && !catalogStarted && !document.querySelector('.discovery-local').open) return;
    clearTimeout(catalogTimer);const token = ++catalogSequence;
    if (!currentAuthority()) return;
    catalogStarted = true;
    const offset = more ? catalogOffset + 40 : 0;
    $('catalog-status').textContent = 'Searching your local catalog…';$('catalog-next').disabled = true;
    try {
      const value = await request(api + 'catalog/?' + catalogParams(offset));
      if (token !== catalogSequence || revoked) return;
      populateSets(value.sets);


      const speciesMode = value.mode === 'species', rows = value.results || [];
      const cards = rows.map(row => speciesMode ? `<article class="catalog-card"><button type="button" id="catalog-species-${row.dex}" data-species="${row.dex}" class="catalog-choice">${localImage(row.species_artwork,row.name,'species')}<span class="catalog-card-text"><strong>${esc(row.name)}</strong><span>#${String(row.dex).padStart(3,'0')} · ${row.current_present ? 'Collected species' : 'Not collected'}</span><span>${row.matching_cards} matching card references · See cards</span></span></button></article>` : `<article class="catalog-card${target.group_id === row.id ? ' selected' : ''}"><button type="button" id="catalog-${esc(row.id)}" data-group="${esc(row.id)}" class="catalog-choice">${localImage(row.reference_image,row.name,'card')}<span class="catalog-card-text"><strong>${esc(row.name)}</strong><span>${esc(row.set_name)} · #${esc(row.collector_number)}</span><span>${row.present ? 'Owned card' : 'Not owned'} · ${row.variant_count} printing${row.variant_count === 1 ? '' : 's'}</span><span>${intent === 'missing' ? 'Reference only · keep your selected Pokémon' : target.group_id === row.id ? 'Selected card reference' : 'Select this card as a search target'}</span></span></button><a id="catalog-details-${esc(row.id)}" class="catalog-details" data-card-details="${esc(row.id)}" href="/card-groups/${esc(row.id)}/" aria-label="Card details for ${esc(row.name)} · ${esc(row.set_name)} #${esc(row.collector_number)}">Card details</a></article>`).join('');
      if (more) $('catalog-cards').insertAdjacentHTML('beforeend',cards);else $('catalog-cards').innerHTML = cards || '<p class="catalog-empty">No local matches in this scope. Try another Pokémon, set or number. You can still submit a supported eBay search.</p>';
      $('catalog-variants')?.remove();
      if (target.group_id && Array.isArray(value.variants) && value.variants.length) {
        const area = document.createElement('div');area.id = 'catalog-variants';area.innerHTML = `<label for="catalog-printing-select">Exact printing <span class="optional">optional</span><select id="catalog-printing-select"><option value="">No exact printing selected</option>${value.variants.filter(row => row.available).map(row => `<option value="${esc(row.id)}">${esc(row.label || row.id)}</option>`).join('')}</select></label><p id="catalog-printing-caption" class="selection-caption"></p><p class="field-help">The image is a card reference scan. Exact edition/finish imagery is unavailable. Selecting a card does not choose its first printing.</p>`;$('catalog-cards').after(area);$('catalog-printing-select').value = target.printing_id || '';const printingCaption = () => {$('catalog-printing-caption').textContent = value.variants.find(row => row.id === target.printing_id)?.label || 'No exact printing selected';};printingCaption();$('catalog-printing-select').addEventListener('change',() => {target.printing_id = $('catalog-printing-select').value || null;printingCaption();rememberChoices();updateButtons();});
      }
      catalogOffset = offset;catalogHasMore = Boolean(value.has_more);$('catalog-next').hidden = !catalogHasMore;$('catalog-next').disabled = false;
      $('catalog-clear-target').hidden = intent === 'missing' || !target.species && !target.group_id;
      $('catalog-status').textContent = `${value.total} ${speciesMode ? 'Pokémon' : 'card reference'} match${value.total === 1 ? '' : 'es'} · local catalog only${value.number_note ? '. ' + value.number_note : ''}`;
      $('catalog-cards').querySelectorAll('[data-species]').forEach(button => button.addEventListener('click',() => {target = {species:Number(button.dataset.species),group_id:null,printing_id:null};catalogSearch();updateButtons();}));
      $('catalog-cards').querySelectorAll('[data-group]').forEach(button => {button.disabled = intent === 'missing';button.addEventListener('click',() => {if(intent === 'missing') return;target = {species:null,group_id:button.dataset.group,printing_id:null};const row = rows.find(item => item.id === button.dataset.group);if (row) {$('discovery-query').value = row.name + ' ' + row.collector_number;$('discovery-set').value = row.set_name;}catalogSearch();updateButtons();});});
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
  function queueCatalog() { if (!catalogStarted && !document.querySelector('.discovery-local').open) return; ++catalogSequence;clearTimeout(catalogTimer);$('catalog-cards').replaceChildren();$('catalog-variants')?.remove();$('catalog-status').textContent = 'Searching your local catalog…';catalogTimer = setTimeout(() => catalogSearch(),180); }
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
      const lotRefs = window.DexLotValues?.references(result) || [];
      if (lotRefs.some(ref => expired(ref) || managed(ref) && sourceUnavailable || withdrawn(ref))) {
        window.DexLotValues.invalidate(result, ref => expired(ref) || managed(ref) && sourceUnavailable || withdrawn(ref));
        $('lot-values-reload').hidden = false;
        removed = true;
      }
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
    if (checkingSources || validatingRun || loadingValues || revoked || !run || !sourceUnavailable && !run.results?.some(result => managed(result.reference) || window.DexLotValues?.references(result).some(managed))) return;
    const active = run, token = sequence;let recovered = false;checkingSources = true;
    try {
      const state = await request('/api/shopping/price-source-status/',undefined,null,2000);
      if (run !== active || sequence !== token || revoked) return;
      if (!Array.isArray(state.versions) || !Array.isArray(state.sources)) throw new Error('Reference lifecycle unavailable');
      recovered = sourceUnavailable;sourceState = state;sourceUnavailable = false;
    } catch {
      if (run !== active || sequence !== token || revoked) return;
      sourceUnavailable = true;
    } finally {
      checkingSources = false;
      if (run === active && sequence === token && !revoked) {
        if (pruneLocal()) renderCards();
        // A successful lifecycle check can recover values withheld during local
        // contention. This reads retained contents only; it never repeats a Hunt.
        if (recovered && !acquiring) {active.values_checked = false;loadValues();}
      }
    }
  }
  async function revalidateRun(withhold = false) {
    if (validatingRun || checkingSources || loadingValues || acquiring || uncertain || revoked || stopWanted || !run?.results?.length) return;
    const active=run, token=sequence;validatingRun=true;lastRunCheck=Date.now();
    if (withhold) {for (const row of active.results) {delete row.lot_value;delete row.value_order;delete row.buying_order;}renderCards();}
    try {
      const value=await request(api+'?run_id='+encodeURIComponent(active.run_id)+receiptView());
      if (run!==active || sequence!==token || revoked || stopWanted) return;
      render(value);
    } catch (error) {
      if (run!==active || sequence!==token || revoked || stopWanted) return;
      for (const row of active.results) {delete row.lot_value;delete row.value_order;delete row.buying_order;row.reason='Current authority could not be checked. Reload search status.';}
      status(error.message,true);$('discovery-reload').hidden=false;renderCards();
    } finally {validatingRun=false;}
  }
  function below(result) {
    return result.classification === 'comparable' && result.comparison?.below_reference !== false && result.delivered_total !== null && result.delivered_total !== undefined && Number(result.comparison?.reference_minus_delivered_total) > 0;
  }
  function card(result) {
    if ($('discovery-form').dataset.lotSearch === 'true') return compactLot(result);
    const identity = $('discovery-form').dataset.lotSearch === 'true' ? {} : result.proposed_identity || (result.identity_candidates?.length === 1 ? result.identity_candidates[0] : {}) || {}, reference = result.reference;
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
    const seller = `${sellerUrl ? `<a href="${esc(sellerUrl)}" target="_blank" rel="noopener noreferrer" aria-label="Open seller listing on eBay">View on eBay</a>` : '<p>Seller link unavailable.</p>'}`;
    const time = auction ? `<p data-auction-end="${esc(result.ends_at || '')}">${esc(window.DexDiscoveryDisplay?.auctionTime(result.ends_at) || 'Auction · end time unknown')}</p>` : '';
    return `<article class="discovery-card" id="offer-${esc(result.id)}" tabindex="-1" data-result="${esc(result.id)}" data-offer="${esc(result.id)}"><div class="discovery-card-heading">${image}<div><h3>${esc(result.title || identity.name || candidateLabel)}</h3>${identity.name ? `<p>Proposed: ${esc(identity.name)}</p>` : ''}${metadata ? `<p class="identity-meta">${esc(metadata)}</p>` : ''}${comparable || conditional ? `<span class="discovery-classification"${$('discovery-form').dataset.lotSearch === 'true' ? ' hidden' : ''}>${esc(classification)}</span>` : ''}</div></div><dl class="discovery-amounts">${window.DexLotValues?.costs(result,{esc,money}) || `<div><dt>Offer price</dt><dd>${esc(money(result.listing_price))}</dd></div><div><dt>Shipping</dt><dd>${esc(money(result.shipping))}</dd></div><div><dt>Delivered · before tax</dt><dd>${esc(money(result.delivered_total))}</dd></div>`}</dl>${time}<p>Offer observed: ${esc(result.observed_at ? new Date(result.observed_at).toLocaleString() : 'Unknown')}. Current bids are provisional; Buy It Now is not reserved.</p>${window.DexLotValues?.html(result,{esc,money,link,correction:`<a data-review-id="${esc(result.id)}" href="/shopping/check/?discovery_run=${encodeURIComponent(run.run_id)}&amp;item_id=${encodeURIComponent(result.id)}">Correct contents in temporary review</a>`}) || ''}<p>${result.evidence_kind === 'seller_details' ? 'Based on full seller details; seller-stated contents are not independently verified.' : 'Seller summary only; full details have not been assessed.'}</p><div class="seller">${seller}<a class="review-offer" aria-label="Assess lot" data-review-id="${esc(result.id)}" href="/shopping/check/?discovery_run=${encodeURIComponent(run.run_id)}&amp;item_id=${encodeURIComponent(result.id)}">Assess lot · optional correction</a></div><details hidden><summary>Comparison & listing details</summary>${result.reason ? `<p>${esc(result.reason)}</p>` : ''}${referenceHtml}${result.save_reason ? `<p>${esc(result.save_reason)}</p>` : ''}</details></article>`;
  }

  function compactLot(result) {
    const mode=$('lot-buying-mode').value, lane=mode==='auction'?'auction':mode==='buy_now'?'buy_it_now':result.value_order?.lanes?.buy_it_now?'buy_it_now':'auction';
    const recommendation=result.buying_order?.[mode==='both'?'combined':lane];
    const value=result.lot_value, costs=value?.benchmark_costs?.[lane];
    const base=costs?.base ?? (lane==='buy_it_now'?result.buy_now_price:result.listing_price);
    const delivered=costs?.delivered_before_tax ?? (lane==='buy_it_now'?result.buy_now_delivered_total:result.delivered_total);
    const art=window.DexDiscoveryDisplay?.sellerImage(result.seller_image) || '';
    const url=link(result.item_url,true);
    const price=delivered!=null?money(delivered):base!=null?money(base):'Price unknown';
    const priceNote=delivered!=null?'incl. shipping · before tax':'shipping unknown';
    const identified=value?.physically_selected_quantity ?? value?.identified_quantity ?? 0;
    const contents=recommendation?.contents && recommendation.contents!=='Contents not confirmed'?recommendation.contents:identified?`${identified} identified cards`:'Contents need checking';
    const reason=recommendation?.reason || 'Value not established; check the contents before buying.';
    const glance=window.DexLotValues.glance(result,mode);
    const badge=`<div class="lot-value-badge tone-${glance.tone}"><strong>${esc(glance.label)}</strong>${glance.verdict?`<span>${esc(glance.verdict)}</span>`:''}</div>`;
    const estimate=glance.amount!=null?`<div class="lot-estimate"><span>${glance.complete?'Estimated value':'Known cards only'}</span><strong>${esc(money(glance.amount))}</strong><small>Ungraded guide</small></div>`:'';
    const detail=window.DexLotValues?.html(result,{esc,money,link}) || '';
    return `<article class="discovery-card compact-lot" id="offer-${esc(result.id)}" tabindex="-1" data-result="${esc(result.id)}" data-offer="${esc(result.id)}"><div class="offer-image" data-source="${esc(art)}">${art?`<img src="${esc(art)}" alt="Seller photo" loading="lazy" decoding="async" referrerpolicy="no-referrer">`:''}<span class="offer-image-fallback"${art?' hidden':''}>No photo</span></div><div class="lot-summary"><h3>${esc(result.title)}</h3><p class="lot-contents">${identified?`${identified} cards · `:''}${esc(contents)}</p>${badge}${lane==='auction'?`<p data-auction-end="${esc(result.ends_at || '')}">${esc(window.DexDiscoveryDisplay?.auctionTime(result.ends_at) || 'End time unknown')}</p>`:''}</div><div class="lot-buy"><div class="lot-price-pair"><div class="lot-offer"><span>${lane==='auction'?'Current bid':'Price + shipping'}</span><strong>${esc(price)}</strong></div>${estimate}</div><span>${lane==='auction'?'Current bid · ':''}${esc(priceNote)}</span>${url?`<a class="button-link" href="${esc(url)}" target="_blank" rel="noopener noreferrer" aria-label="Open seller listing on eBay">View on eBay</a>`:''}</div><details class="lot-more"><summary>Details</summary><p>${esc(reason)}</p>${detail}<p>Observed ${esc(result.observed_at?new Date(result.observed_at).toLocaleString():'time unknown')}.</p><a class="review-offer" aria-label="Assess lot" data-review-id="${esc(result.id)}" href="/shopping/check/?discovery_run=${encodeURIComponent(run.run_id)}&amp;item_id=${encodeURIComponent(result.id)}">Check or correct contents</a></details></article>`;
  }

  async function expandEvidence(panel) {
    if (!panel.open || panel.dataset.loading || !currentAuthority() || stopWanted) return;
    const runId = run?.run_id, token = sequence;
    const offer = panel.closest('[data-offer]')?.dataset.offer;
    const find = () => run?.results.find(r => r.id === offer);
    const row = find();
    if (!row?.evidence_version || row.evidenceLoaded) return;
    panel.dataset.loading = 'true';
    const version = row.evidence_version, revision = row.content_revision;
    const current = () => run?.run_id === runId && sequence === token && currentAuthority() && !stopWanted &&
      Date.now() < deadline && panel.isConnected && panel.open && find()?.evidence_version === version &&
      find()?.content_revision === revision && find()?.lot_value;
    try {
      const data = await request(api + encodeURIComponent(run.run_id) + '/evidence/' + encodeURIComponent(row.id) +
        '/?revision=' + encodeURIComponent(row.content_revision));
      if (!current()) return;
      if (data.run_id !== run.run_id || data.id !== offer || data.content_revision !== revision ||
          data.evidence_version !== version) {
        // A stale disclosure must not reopen on every refreshed list.
        panel.open = false;
        $('lot-values-status').textContent = 'The assessment changed. Reopen evidence after the local status refresh.';
        revalidateRun(true);
        return;
      }
      const target = find();
      target.summaryValue = target.lot_value;
      target.lot_value = data.lot_value;
      target.evidenceLoaded = true;
      renderCards();
    } catch (error) {
      if (current()) panel.querySelector('[role=status]').textContent = error.message;
    } finally { delete panel.dataset.loading; }
  }

  $('discovery-cards').addEventListener('toggle', event => {
    const panel = event.target;
    if (!panel.isConnected || !panel.matches('details.lot-evidence')) return;
    if (panel.open && panel.hasAttribute('data-local-evidence')) expandEvidence(panel);
    if (!panel.open) {
      const row = run?.results?.find(r => r.id === panel.closest('[data-offer]')?.dataset.offer);
      if (row?.summaryValue) {
        row.lot_value = row.summaryValue;
        delete row.summaryValue;
        delete row.evidenceLoaded;
        renderCards();
      }
    }
  }, true);
  function renderCards() {
    pruneLocal();
    const results = Array.isArray(run?.results) ? run.results : [];
    const filter = $('discovery-form').dataset.lotSearch === 'true' ? 'all' : $('discovery-filter').value;
    let rows = results.filter(result => filter === 'all' || filter === 'below' && below(result) || filter === result.classification);
    if (window.DexLotValues) rows = window.DexLotValues.select(rows,{hours:$('lot-time-window').value,mode:$('lot-buying-mode').value,sort:$('lot-value-sort').value,basis:$('lot-value-basis')?.value || 'all',estimate:$('lot-estimate-filter').value,era:$('lot-era-filter').checked?'pre2000':'all'});
    $('discovery-shown').textContent = `${rows.length} ${rows.length===1?'option':'options'}`;
    const groups = window.DexLotValues?.groups(rows,{mode:$('lot-buying-mode').value,sort:$('lot-value-sort').value});
    const seen = new Set();
    const grouped = groups?.map(group => {
      const heading=`<div class="lot-group-heading" data-result="group-${esc(group.key)}"><h3>${esc(group.label)} · ${group.rows.length}</h3>${group.note ? `<p>${esc(group.note)}</p>` : ''}</div>`;
      return heading + group.rows.map(row=>{
        const duplicate=seen.has(row.id);seen.add(row.id);
        const key=$('lot-value-sort').value === 'native' ? row.id+'-'+group.key : row.id;
        return card(row).replace(`data-result="${esc(row.id)}"`,`data-result="${esc(key)}"`).replace(`id="offer-${esc(row.id)}"`,`id="offer-${esc(duplicate ? key : row.id)}"`);
      }).join('');
    }).join('');
    const markup = (grouped ?? rows.map(card).join('')) || `<div class="discovery-empty"><h3>${results.length ? validatingRun || loadingValues ? 'Checking current estimates…' : 'No results match this filter' : acquiring ? 'Searching this small batch…' : 'No listings to show'}</h3><p>${results.length ? 'Broaden Value or turn off Pre-2000 only to see more of this search. Unknown contents are excluded by Pre-2000 only.' : acquiring ? 'You can stop acquisition at any time.' : 'Try different keywords or filters, or choose More results when available. No new search starts automatically.'}</p></div>`;
    if (window.DexDiscoveryDisplay) window.DexDiscoveryDisplay.patch($('discovery-cards'),markup);else $('discovery-cards').innerHTML = markup;
    if ($('discovery-form').dataset.lotSearch !== 'true') $('discovery-cards').querySelectorAll('article[data-result]').forEach(card => { const id = run?.run_id; window.DexInterpretation?.mount(card, {kind:'discovery',run_id:id,result_id:card.dataset.result}, () => currentAuthority() && run?.run_id === id && !['stopped','expired'].includes(run?.state) && !changed()); });
    $('discovery-cards').querySelectorAll('[data-review-id]').forEach(anchor => {if (anchor.dataset.reviewBound) return;anchor.dataset.reviewBound = '1';anchor.addEventListener('click',() => {anchor.href = '/shopping/check/?' + new URLSearchParams({discovery_run:run.run_id,item_id:anchor.dataset.reviewId,return:reviewReturn(anchor.dataset.reviewId)});});});
  }
  function render(value) {
    window.DexLotValues?.unpack(value);
    if (run !== value) {
      // Reuse an open disclosure only after the new local read verifies its entire evidence version.
      for (const next of value.results || []) {
        const old = run?.results?.find(r => r.id === next.id && r.evidenceLoaded);
        if (old && old.lot_value && run.run_id === value.run_id && old.content_revision === next.content_revision &&
            old.evidence_version === next.evidence_version && next.evidence_version) {
          next.summaryValue = next.lot_value; next.lot_value = old.lot_value; next.evidenceLoaded = true;
        }
      }
      clearResults();
    }
    // This authenticated response just revalidated every reference. An earlier
    // failed lifecycle read must not erase it before a fresh check can run.
    // A late result must not erase a confirmed source withdrawal.
    sourceUnavailable = false;
    run = value;captureDeadline(value);
    acquiring = Boolean(value.running);
    $('discovery-results').hidden = false;
    $('discovery-scope').textContent = value.scope_label || (value.choices?.intent === 'missing' ? 'Missing cards · current collection' : 'Find deals · includes owned cards');
    $('discovery-limitation').textContent = [value.note || 'Temporary comparison · references retain their original dates. Results are not saved to history.',value.limitation].filter(Boolean).join(' ');
    const count = Number(value.counts?.summary_count);
    status((value.contract === 'dex-lot-hunt-v2' ? (window.DexLotValues?.progress(value) || `Hunt ${value.state.replaceAll('_',' ')} · ${value.progress?.enriched || 0}/2 detailed · ${value.progress?.assessed || 0} assessed · ${value.progress?.unprocessed || 0} unprocessed`) : value.error || (value.state === 'expired' ? 'This temporary search has expired. Select Search to start a new search.' : value.state === 'stopped' ? 'Search stopped. No further requests will be sent.' : acquiring ? 'Searching a small batch… Stop prevents later requests and results.' : value.state === 'failed' ? 'Search ended after a request failed. No automatic retry.' : `Search complete${Number.isFinite(count) ? ' · ' + count + ' listing summaries checked' : ''}.`)),Boolean(value.error) || value.state === 'failed');
    lastRunCheck = Date.now();
    $('discovery-next').hidden = value.contract === 'dex-lot-hunt-v2';
    if (value.contract === 'dex-lot-hunt-v2') $('lot-values-status').textContent = value.running ? 'Checking contents and value…' : value.results?.some(r=>r.lot_value?.subtotal!=null || r.lot_value?.native_guides?.length) ? 'Value comparisons use dated references. Open Details to see the evidence.' : 'No supported value comparisons yet. Order reflects request match, contents and known cost.';
    renderCards();updateButtons();checkSources();
    if (window.DexLotValues && !acquiring && value.results?.length && !value.values_checked) loadValues();
    if (focusResults && !acquiring && value.results?.length) {
      focusResults = false;requestAnimationFrame(() => {$('discovery-results-title').focus({preventScroll:true});$('discovery-results').scrollIntoView?.({block:'start'});});
    }
  }
  async function loadValues() {
    if (!run || loadingValues || acquiring || revoked || stopWanted || run.values_checked) return;
    const active = run, token = sequence;active.values_checked = true;loadingValues = true;
    $('lot-values-status').textContent = 'Checking ungraded values from identified seller text…';
    $('lot-values-reload').hidden = true;
    try {
      const value = await request(api + '?run_id=' + encodeURIComponent(active.run_id) + '&view=values');
      if (run !== active || sequence !== token || revoked || stopWanted) return;
      if (value.run_id !== active.run_id || !Array.isArray(value.results)) throw new Error('Local value check returned an unavailable result. Your listings remain visible.');
      value.values_checked = true;
      render(value);
      $('lot-values-status').textContent = 'Values use identified seller text and dated local references. Photo-only contents remain unvalued.';
    } catch (error) {
      if (run !== active || sequence !== token || revoked || stopWanted) return;
      for (const result of run.results || []) result.lot_value = {reason:'Local value check unavailable. Reload local values.',references:[],cards:[]};
      $('lot-values-status').textContent = error.message;
      $('lot-values-reload').hidden = false;renderCards();
    } finally {loadingValues = false;}
  }
  function rememberRun(id) {
    if (typeof id !== 'string' || !/^[0-9a-f-]{36}$/i.test(id)) return;
    const url = new URL(location.href);url.searchParams.set('run_id',id);
    url.searchParams.delete('request_id');actionId = null;uncertain = false;
    history.replaceState(null,'',url.pathname + url.search);
  }
  function schedule(token) {
    clearTimeout(timer);
    if (!acquiring || revoked || stopWanted) return;
    timer = setTimeout(async () => {
      try {
        const value = await request(api + '?run_id=' + encodeURIComponent(run.run_id) + receiptView());
        if (sequence !== token || revoked || stopWanted) return;
        render(value);schedule(token);
      } catch (error) {
        if (sequence !== token || revoked || stopWanted) return;
        clearTimeout(timer);uncertain = true;status(error.message + ' Acquisition status is unknown. Reload this section or use Stop.',true);$('discovery-reload').hidden = false;updateButtons();
      }
    },650);
  }
  async function start(next = false) {
    if (acquiring || uncertain || revoked || !ready || next && (!run?.has_next || changed())) return;
    const prior = run, selected = choices();
    if ($('discovery-form').dataset.lotSearch === 'true' && intent === 'missing' && (!targetsReady || !target.species)) return;
    if (!next && $('discovery-form').dataset.lotSearch === 'true' && !selected.query) {status('Enter a Pokémon or card name.');$('discovery-query').focus();return;}
    captured = next ? captured : signature(selected);
    const token = ++sequence;
    const keepBrowsing = next && Boolean(prior.choices?.query);
    focusResults = !next;
    if (!keepBrowsing) clearResults(prior);
    acquiring = true;stopWanted = false;run = keepBrowsing ? prior : null;
    if (!keepBrowsing) {$('discovery-cards').replaceChildren();$('discovery-results').hidden = true;}
    clearTimeout(timer);updateButtons();
    status(next ? 'Starting the next results batch…' : 'Starting search…');
    try {
      actionId = crypto.randomUUID();uncertain = true;admissionPending = true;
      const destination = new URL(location.href);destination.searchParams.set('request_id',actionId);
      history.replaceState(null,'',destination.pathname + destination.search);
      const value = await request(api,next ? {continuation_run:prior.run_id} : {...selected,...($('discovery-form').dataset.lotSearch === 'true' ? {acquisition_contract:'dex-lot-hunt-v2'} : {})},actionId);
      if (sequence !== token || revoked) return;
      admissionPending = false;
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
      admissionPending = false;
      if (error.category === 'not_dispatched') {
        acquiring = false;uncertain = false;stopWanted = false;actionId = null;
        const destination = new URL(location.href);destination.searchParams.delete('request_id');
        history.replaceState(null,'',destination.pathname + destination.search);
        status(error.message + ' Select Find lots when you are ready to try again.',true);
      } else {
        uncertain = true;acquiring = true;
        status('The search response was lost or unavailable. Its outcome is unknown. Reload this section to check; no new search will be sent.',true);
        $('discovery-reload').hidden = false;
      }
      updateButtons();
    }
  }
  async function stop() {
    if ((!acquiring && !run?.run_id) || revoked) return;
    stopWanted = true;clearTimeout(timer);clearResults();$('discovery-cards').replaceChildren();updateButtons();status('Stopping search…');
    if (admissionPending) {
      if (!run?.run_id) return;
      // Named More keeps the original handle. Stop it even if the page
      // acknowledgement is pending. Its late response belongs to the old sequence.
      rememberRun(run.run_id);admissionPending = false;
    }
    if (uncertain && actionId) {await reloadRun();return;}
    if (!run?.run_id) return;
    const token = ++sequence;
    try {
      const value = await request(api + encodeURIComponent(run.run_id) + '/stop/',{});
      if (sequence !== token || revoked) return;
      uncertain = false;render(value);stopWanted = false;updateButtons();
    } catch (error) {
      if (sequence !== token || revoked) return;
      stopWanted = false;uncertain = true;status(error.message + ' Stop was not confirmed. Use Stop again.',true);updateButtons();
    }
  }
  function invalidate() {
    revoked = true;++targetSequence;$('discovery-target').replaceChildren();$('discovery-goal').replaceChildren();goals=[];target={species:null,group_id:null,printing_id:null};$('discovery-query').value='';document.querySelector('.discovery-context')?.replaceChildren();$('discovery-context').textContent='{}';$('discovery-goals').textContent='[]';$('discovery-initial').textContent='{}';targetsReady = false;++catalogSequence;clearTimeout(catalogTimer);$('catalog-cards').replaceChildren();++sequence;clearTimeout(timer);clearInterval(lifecycleTimer);clearResults();run = null;captured = null;
    $('discovery-cards').replaceChildren();$('discovery-results').hidden = true;
    status('Your session changed. Sign in again to continue.',true);updateButtons();
  }
  $('discovery-form').addEventListener('submit',event => {event.preventDefault();rememberChoices();start();});
  $('catalog-search').addEventListener('click',() => catalogSearch(false,true));
  $('catalog-next').addEventListener('click',() => {if (catalogHasMore) catalogSearch(true);});
  $('catalog-clear-target').addEventListener('click',() => {target = {species:null,group_id:null,printing_id:null};catalogSearch();updateButtons();});
  $('find-deals').addEventListener('click',() => {intent = 'deals';++targetSequence;target = {species:null,group_id:null,printing_id:null};policy();rememberChoices();});
  $('find-missing').addEventListener('click',() => {intent = 'missing';if (!$('discovery-goal').value) {$('discovery-focus').value = 'kanto';$('discovery-missing-basis').value = 'species';}policy();loadTargets();});
  $('discovery-stop').addEventListener('click',stop);
  $('discovery-next').addEventListener('click',() => start(true));
  if (window.DexLotValues) {
    for (const [id,field] of [['lot-time-window','time_window'],['lot-value-sort','value_sort'],['lot-buying-mode','buying_mode'],['lot-value-basis','value_basis'],['lot-estimate-filter','estimate_filter']]) {
      if (initial[field]) { const value = field === 'time_window' && ['all','168'].includes(initial[field]) ? '72' : field === 'value_sort' && initial[field] === 'total' ? 'value' : initial[field]; $(id).value = value; }
      $(id).addEventListener('change',() => {renderCards();rememberChoices();});
    }
    $('lot-era-filter').checked = initial.era_filter === 'pre2000';
    $('lot-era-filter').addEventListener('change',() => {renderCards();rememberChoices();});
    $('lot-values-reload').addEventListener('click',() => {if(run) {run.values_checked = false;loadValues();}});
  }
  $('discovery-filter').addEventListener('change',() => {renderCards();rememberChoices();});
  $('discovery-form').addEventListener('input',() => {policy();rememberChoices();});
  $('discovery-form').addEventListener('change',event => {policy();if (['discovery-set','discovery-goal','discovery-missing-basis','discovery-focus'].includes(event.target.id)) {if (event.target.id === 'discovery-goal') {goalVersion = goals.find(row => row.id === $('discovery-goal').value)?.version || null;if ($('discovery-goal').value) $('discovery-focus').value = 'all';}if (intent === 'missing' && ['discovery-goal','discovery-focus'].includes(event.target.id)) loadTargets();if (event.target.id === 'discovery-set') target = {species:target.species,group_id:null,printing_id:null};catalogSearch();}});
  $('discovery-form').addEventListener('change',() => rememberChoices());
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
  window.addEventListener('focus',()=>revalidateRun(true));
  window.addEventListener('popstate',() => location.reload());
  document.addEventListener('visibilitychange',() => {if (pruneLocal()) renderCards();if (!document.hidden) {checkSources();revalidateRun(true);}});
  lifecycleTimer = setInterval(() => {const minute = Math.floor(Date.now() / 60000);if (pruneLocal() || window.DexLotValues && run && minute !== windowMinute) {windowMinute = minute;renderCards();}window.DexDiscoveryDisplay?.tick($('discovery-cards'));if (!document.hidden && Date.now()-lastRunCheck>=5000) revalidateRun();else checkSources();},1000);
  for (const [field,id] of Object.entries({q:'discovery-query',scope:'discovery-focus',missing_basis:'discovery-missing-basis',budget:'discovery-budget',budget_mode:'discovery-budget-mode',budget_rule:'discovery-budget-rule',budget_value_basis:'discovery-budget-value-basis',product_type:'discovery-product-type',sort:'discovery-sort'})) if (initial[field] !== undefined) $(id).value = initial[field];
  if (intent === 'missing' && !initial.scope && !initial.goal) $('discovery-focus').value = 'kanto';
  if (initial.prefer_vintage !== undefined) $('discovery-prefer-vintage').checked = initial.prefer_vintage === '1';
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
  $('find-deals').disabled = false;$('find-missing').disabled = false;
  async function loadOptions() {
    $('discovery-options-reload').hidden = true;
    try {
      const metadata = await request(api);
      if (!currentAuthority()) return;
      // Preserve edits made while these optional choices were loading.
      const selectedGoal = $('discovery-goal').value;
      goals = Array.isArray(metadata.goals) ? metadata.goals : [];
      $('discovery-goal').innerHTML = '<option value="">My current collection</option>' + goals.map(goal => `<option value="${esc(goal.id)}">Frozen goal · ${esc(goal.name)}</option>`).join('');
      if (selectedGoal && !goals.some(g => g.id === selectedGoal)) $('discovery-goal').add(new Option('Retained goal unavailable',selectedGoal));
      $('discovery-goal').value = selectedGoal;
      ready = Boolean(metadata.provider?.enabled && metadata.provider?.configured);
      populateSets(metadata.sets);policy();
      $('discovery-options-status').textContent = ready ? '' : 'eBay search is unavailable for this installation.';
    } catch (error) {
      if (!currentAuthority()) return;
      $('discovery-options-status').textContent = 'Search options could not be loaded. Your current inputs and results remain available.';
      $('discovery-options-reload').hidden = false;
    }
  }
  async function reloadRun() {
    const token = sequence, runId = run?.run_id || initial.run_id;
    const restoreInput = !run && captured === null, inputBefore = signature(choices());
    $('discovery-reload').hidden = true;
    if (!actionId && !runId) return;
    try {
      const value = await request(api + '?' + (actionId ? 'request_id=' + encodeURIComponent(actionId) : 'run_id=' + encodeURIComponent(runId)) + receiptView());
      if (sequence !== token || !currentAuthority()) return;
      if (value.outcome_unknown) {
        uncertain = true;acquiring = true;stopWanted = false;
        status('The search outcome is still unknown. Reload this section later. A missing status does not mean the request was unused; a new search is disabled.',true);
        $('discovery-reload').hidden = false;updateButtons();return;
      }
      rememberRun(value.run_id);run = value;
      if (stopWanted) {await stop();return;}
      const restore = restoreInput && inputBefore === signature(choices());
      if (restore) restoreChoices(value.choices);
      render(value);schedule(token);
      if (restore) {
      for (const [field,id] of Object.entries({q:'discovery-query',scope:'discovery-focus',missing_basis:'discovery-missing-basis',budget:'discovery-budget',budget_mode:'discovery-budget-mode',budget_rule:'discovery-budget-rule',budget_value_basis:'discovery-budget-value-basis',product_type:'discovery-product-type',sort:'discovery-sort'})) if (initial[field] !== undefined) $(id).value = initial[field];
      if (initial.intent) intent = initial.intent;
      if (initial.goal) {$('discovery-goal').value = initial.goal;goalVersion = initial.version || null;}
      if (initial.prefer_vintage !== undefined) $('discovery-prefer-vintage').checked = initial.prefer_vintage === '1';
  if (initial.english_vintage !== undefined) $('discovery-english-vintage').checked = initial.english_vintage === '1';
      if (initial.species || initial.group) target = {species:context.species || null,group_id:context.group || null,printing_id:context.child || null};
      if (initial.set_id) $('discovery-set').value = localSets.find(row => [row.id,row.name].includes(initial.set_id))?.name || initial.set_id;
      policy();
      if (initial.result_filter) $('discovery-filter').value = initial.result_filter;
      renderCards();
      if (intent === 'missing' && !targetsReady) loadTargets();
      }
      requestAnimationFrame(() => {if (!currentAuthority()) return;if (initial.scroll) window.scrollTo(0,Number(initial.scroll));if (initial.focus) $(initial.focus)?.focus({preventScroll:true});});
    } catch (error) {
      if (sequence !== token || !currentAuthority()) return;
      uncertain = true;acquiring = true;stopWanted = false;
      status(error.message + ' Search status is unknown. Reload this section; no new search will be sent.',true);
      $('discovery-reload').hidden = false;updateButtons();
    }
  }
  async function loadTargets() {
    if ($('discovery-form').dataset.lotSearch !== 'true') return;
    const token = ++targetSequence, selected = choices();targetsReady = false;$('discovery-target').disabled = true;updateButtons();
    $('discovery-target-status').textContent = 'Loading missing Pokémon…';
    $('discovery-target-reload').hidden = true;
    const params = new URLSearchParams({scope:selected.focus,generation:String(generation)});
    if (selected.goal_id) {params.set('goal',selected.goal_id);params.set('version',selected.goal_version || '');}
    try {
      const value = await request(api + 'targets/?' + params);
      if (token !== targetSequence || !currentAuthority() || intent !== 'missing') return;
      const retained = target.species;
      $('discovery-target').innerHTML = '<option value="">Choose one Pokémon</option>' + value.targets.map(row => `<option value="${row.species}">${esc(row.name)}</option>`).join('');
      if (retained && value.targets.some(row => row.species === retained)) $('discovery-target').value = String(retained);
      else {target = {species:null,group_id:null,printing_id:null};$('discovery-query').value = '';}
      targetsReady = true;$('discovery-target').disabled = false;
      $('discovery-target-status').textContent = value.targets.length ? 'Select one target. No search starts automatically.' : 'No missing Pokémon in this scope.';
      updateButtons();
    } catch (error) {
      if (token !== targetSequence || !currentAuthority()) return;
      $('discovery-target-status').textContent = error.message;
      $('discovery-target-reload').hidden = false;updateButtons();
    }
  }
  $('discovery-target').addEventListener('keydown',event => {if(event.key === 'Enter') event.preventDefault();});
  $('discovery-target').addEventListener('change',() => {
    target = {species:Number($('discovery-target').value) || null,group_id:null,printing_id:null};
    $('discovery-query').value = target.species ? $('discovery-target').selectedOptions[0].text : '';
    policy();rememberChoices();
  });
  $('discovery-target-reload').addEventListener('click',loadTargets);
  $('discovery-options-reload').addEventListener('click',loadOptions);
  $('discovery-reload').addEventListener('click',reloadRun);
  if (initial.run_id || actionId) {
    uncertain = true;
    acquiring = true;
    updateButtons();
    // Dispatch the receipt first on the shared local admission lane.
    // Optional sections can still recover independently of its response.
    reloadRun();
  }
  if (intent === 'missing') loadTargets();
  loadOptions();
  if (!catalogStarted && document.querySelector('.discovery-local').open) catalogSearch();
})();
