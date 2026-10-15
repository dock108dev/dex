'use strict';
/* Canonical card screens. Display grouping never supplies collection authority. */
(() => {
  const filterKeys = ['q','set','sort','language','edition','finish','variant','species','page','page_size'];
  const listPaths = ['/cards/','/card-library/'];
  let generation = 0;
  window.invalidateCardScreens = () => { generation++; };
  function safeList(value) {
    if(window.safeSpeciesReturn){const species=window.safeSpeciesReturn(value);if(species)return species;}
    if (typeof value !== 'string' || !value.startsWith('/') || value.startsWith('//')) return null;
    try {
      const url = new URL(value, location.origin);
      if (url.origin !== location.origin || !listPaths.includes(url.pathname) || url.hash) return null;
      for (const key of url.searchParams.keys()) {
        if (![...filterKeys,'scroll'].includes(key) || url.searchParams.getAll(key).length !== 1) return null;
      }
      if([...url.searchParams.values()].some(value=>value.length>160))return null;
      for(const [key,min,max] of [['page',1,Number.MAX_SAFE_INTEGER],['page_size',1,100],['species',1,251]]){const value=url.searchParams.get(key);if(value&&(!/^[0-9]+$/.test(value)||!Number.isSafeInteger(Number(value))||Number(value)<min||Number(value)>max))return null;}
      if(url.searchParams.get('sort')&&!['set','name','number'].includes(url.searchParams.get('sort')))return null;
      const scroll = url.searchParams.get('scroll');
      if (scroll !== null && (!/^\d{1,8}$/.test(scroll) || Number(scroll) > 10000000)) return null;
      return url.pathname + url.search;
    } catch { return null; }
  }
  function backLabel(value){return value.startsWith('/pokedex/')?'Pokédex':value.startsWith('/card-library/')?'Card Library':'My Cards';}
  window.safeCardReturn=safeList;
  function account() { return data?.effective_collection?.user_id || ''; }
  function storageKey(url) { return 'dex-card-scroll:' + account() + ':' + url; }
  function tabKey(path) { return 'dex-card-tab:' + account() + ':' + path; }
  function saveTabState(path, value) {
    const safe=safeList(value);
    if(!safe||new URL(safe,location.origin).pathname!==path)return;
    try{sessionStorage.setItem(tabKey(path),safe);}catch{ /* Tab memory is optional. */ }
  }
  function tabDestination(path) {
    if(location.pathname===path){const current=safeList(location.pathname+location.search);if(current)return current;}
    try{const saved=safeList(sessionStorage.getItem(tabKey(path)));if(saved&&new URL(saved,location.origin).pathname===path)return saved;}catch{ /* Default when storage is unavailable. */ }
    return path;
  }
  function saveScroll() {
    if (!listPaths.includes(location.pathname)) return;
    const url = new URL(location.href); url.searchParams.delete('scroll');
    try { sessionStorage.setItem(storageKey(url.pathname + url.search), String(Math.min(10000000,Math.max(0,Math.round(scrollY))))); } catch { /* Storage is optional. */ }
    saveTabState(location.pathname,returnWithScroll());
  }
  addEventListener('pagehide', saveScroll);
  function listDestination(path, params) {
    const copy = new URLSearchParams();
    for (const key of filterKeys) if (params.get(key)) copy.set(key, params.get(key));
    return path + (copy.size ? '?' + copy : '');
  }
  function returnWithScroll() {
    const url = new URL(location.href);
    url.searchParams.set('scroll', String(Math.min(10000000, Math.max(0, Math.round(scrollY)))));
    return safeList(url.pathname + url.search) || '/cards/';
  }
  function detailDestination(group, returnTo, child) {
    const params = new URLSearchParams();
    if (child) params.set('child', child);
    if (returnTo) params.set('return', returnTo);
    return '/card-groups/' + encodeURIComponent(group.id) + '/' + (params.size ? '?' + params : '');
  }
  function option(value, label, selected) { return `<option value="${esc(value)}" ${value === selected ? 'selected' : ''}>${esc(label)}</option>`; }
  function select(key, label, values, params, emptyLabel) {
    const selected = params.get(key) || '';
    const options = values.map(v => typeof v === 'string' ? {id:v,name:v} : v);
    if (selected && !options.some(v => v.id === selected)) options.push({id:selected,name:selected + ' · unavailable filter'});
    const selectedLabel = options.find(v => v.id === selected)?.name || '';
    return `<div><label for="cards-${key}">${label}</label><select id="cards-${key}" name="${key}" aria-describedby="cards-${key}-value">${option('',emptyLabel,selected)}${options.map(v => option(v.id,v.name,selected)).join('')}</select><p id="cards-${key}-value" class="card-selected-label" ${selected ? '' : 'hidden'}>${selected ? esc(selectedLabel) : ''}</p></div>`;
  }
  function sortControl(params) {
    const values = [['set','Set'],['name','Card name'],['number','Collector number']], selected = params.get('sort') || 'set';
    const label = values.find(([value]) => value === selected)?.[1] || '';
    return `<div><label for="cards-sort">Sort</label><select id="cards-sort" name="sort" aria-describedby="cards-sort-value">${values.map(([value,name]) => option(value,name,selected)).join('')}</select><p id="cards-sort-value" class="card-selected-label" ${selected === 'set' ? 'hidden' : ''}>${selected === 'set' ? '' : esc(label)}</p></div>`;
  }
  function activeFilters(path, params, options) {
    const labels={q:'Search',set:'Set',sort:'Sort',language:'Language',edition:'Edition',finish:'Finish',variant:'Variant',species:'Pokédex number'};
    const names={set:options.sets,language:options.languages,edition:options.editions,finish:options.finishes,variant:options.variants};
    const rows=Object.entries(labels).filter(([key])=>params.get(key)&&(key!=='sort'||params.get(key)!=='set')).map(([key,label])=>{
      const value=(names[key]||[]).find(row=>row.id===params.get(key))?.name||params.get(key);
      return `<li>${label}: ${esc(value)}</li>`;
    });
    return rows.length?`<div class="active-filters" aria-label="Applied card filters"><ul>${rows.join('')}</ul><a href="${path}">Clear filters</a></div>`:'';
  }
  function filters(path, params, options) {
    return `<form id="card-filters" method="get" action="${path}" class="card-filter-form browse-controls"><div class="card-core-filters"><div><label for="cards-query">Search</label><input id="cards-query" name="q" type="search" maxlength="160" value="${esc(params.get('q') || '')}" placeholder="Card name, set or number"></div>${select('set','Set',options.sets,params,'All sets')}<button>Search cards</button></div><div class="card-filter-options"><details id="card-advanced-filters"><summary>Sort and variant filters</summary><div class="card-advanced-grid">${sortControl(params)}${select('language','Language',options.languages,params,'All languages')}${select('edition','Edition',options.editions,params,'All editions')}${select('finish','Finish',options.finishes,params,'All finishes')}${select('variant','Variant',options.variants,params,'All variants')}<div><label for="cards-species">Pokédex number</label><input id="cards-species" name="species" type="number" min="1" max="251" value="${esc(params.get('species') || '')}"></div></div><p class="muted">Variant filters identify matching variants; each card and its complete ownership total still appear once.</p><button class="secondary">Apply filters</button></details>${imageOptions()}</div>${params.get('page_size') ? `<input name="page_size" type="hidden" value="${esc(params.get('page_size'))}">` : ''}</form>`;
  }
  function collectionUnresolved(rows) {
    const allowed = new Set(['unmapped-collection-card','unresolved-species-mark','unmapped-collection-copy','effective-collection-conflict']);
    return (rows || []).filter(row => allowed.has(row.kind));
  }
  function unresolvedArea(rows) {
    if (!rows.length) return '';
    const seen = new Set();
    const items = rows.filter(row => {const key=JSON.stringify(row);if(seen.has(key))return false;seen.add(key);return true;});
    return `<details class="card-unresolved"><summary>Card details needed (${items.length})</summary><p>Owned evidence is retained. Identify these cards before they can appear as card tiles.</p><ul>${items.map(row => {const e=row.evidence || row;const name=e.name || e.pokemon_name || e.species_name || (e.pokemon_dex ? 'Pokémon #' + e.pokemon_dex : 'Retained collection evidence');return `<li>${row.reference_image?.image_url ? cardImage(row.reference_image,true) : ''}<strong>${esc(name)}</strong>${e.number ? ' #' + esc(e.number) : ''}${e.set_name || e.source_set ? ' · ' + esc(e.set_name || e.source_set) : ''}<p class="muted">${esc(row.kind === 'unresolved-species-mark' ? 'Species evidence; exact card details needed.' : row.kind === 'unmapped-collection-copy' ? 'Recorded copy; card identity needs review.' : (row.reference_image?.image_url ? 'English card reference; catalog details still need review.' : 'Card identity or collection evidence needs review.'))}</p></li>`;}).join('')}</ul><a href="/collection/">Review collection records</a></details>`;
  }
  function tile(group, returnTo) {
    return `<a class="owned-card-tile" href="${esc(detailDestination(group,returnTo))}" data-group-id="${esc(group.id)}" data-owned="${group.present ? 'true' : 'false'}" ${group.matching_child_ids ? `data-matching-child-ids="${esc(JSON.stringify(group.matching_child_ids))}"` : ''}>${cardImage(group.reference_image,true)}<span class="card-tile-text"><strong>${esc(group.name)}</strong><span>${esc(group.set_name)} · #${esc(group.collector_number)}</span><span class="card-tile-status"><span class="ownership-badge ${group.present ? 'is-owned' : 'is-unowned'}">${group.present ? 'Owned' : 'Not owned'}</span>${group.owned_variant === 'normal' ? ' · Normal variant' : ''}${group.established_total_quantity == null ? '' : ' · Quantity ' + esc(group.established_total_quantity)}</span></span></a>`;
  }
  function dimPreference() {
    try {return localStorage.getItem('dex-card-dim:' + account()) === 'true';}
    catch {return false;}
  }
  function imageOptions() {
    return `<div class="card-image-options"><label class="check"><input id="dim-unowned" type="checkbox" ${dimPreference() ? 'checked' : ''}> Grey out unowned cards</label></div>`;
  }
  function bindImageOptions() {
    const input=$('#dim-unowned'),grid=$('#card-group-list');
    const apply=()=>grid.classList.toggle('dim-unowned',input.checked);
    apply();
    input.onchange=()=>{apply();try{localStorage.setItem('dex-card-dim:' + account(),String(input.checked));}catch{/* Optional visual preference. */}};
  }
  function errorState(error, back = '/cards/') {
    const conflict = error.status === 409;
    $('#content').innerHTML = `<h1>${conflict ? 'Collection changed' : 'Cards unavailable'}</h1><p class="error" role="alert">${esc(error.message)}</p><p>${conflict ? 'Reload current cards before making another change. Nothing was confirmed.' : 'Your collection has not been changed. Reload to try again.'}</p><div class="actions"><button id="card-retry">Reload current cards</button><a href="${esc(back)}">Back to cards</a></div>`;
    $('#card-retry').onclick = () => location.reload();
  }
  window.renderCardGroupTile = tile;
  async function renderList(path, active) {
    const params = new URLSearchParams(location.search), scope = path === '/cards/' ? 'owned' : 'catalog';
    $('#content').innerHTML = `<h1>${scope === 'owned' ? 'My Cards' : 'Card Library'}</h1><p role="status">Loading cards…</p>`;
    const query = new URLSearchParams();
    for (const key of filterKeys) if (params.get(key)) query.set(key,params.get(key));
    const authorityGeneration=data.effective_collection?.generation;
    if(Number.isSafeInteger(authorityGeneration))query.set('generation',authorityGeneration);
    const [result, options] = await Promise.all([
      api((scope === 'owned' ? '/api/my-card-groups/' : '/api/card-groups/') + (query.size ? '?' + query : '')),
      api('/api/card-group-filters/?scope=' + scope + (Number.isSafeInteger(authorityGeneration)?'&generation='+authorityGeneration:''))
    ]);
    if (!active()) return;
    if (result.account_id && result.account_id !== account()) throw new Error('Account changed. Reload your current collection.');
    if ((Number.isSafeInteger(authorityGeneration) && result.generation !== authorityGeneration) || options.generation !== result.generation || (options.account_id && result.account_id && options.account_id !== result.account_id)) {
      const error = new Error('Your collection changed while the cards were loading. Reload current cards.'); error.status = 409; throw error;
    }
    if (result.page > Math.max(1,result.pages)) {
      params.set('page', String(Math.max(1,result.pages)));params.delete('scroll');
      location.replace(listDestination(path,params));return;
    }
    const unresolved = scope === 'owned' ? collectionUnresolved(result.unresolved) : [];
    const filtered = filterKeys.some(k => !['page','page_size','sort'].includes(k) && params.get(k));
    const empty = filtered ? '<h2>No matching cards</h2><p>Try a different search or set.</p>' : scope === 'catalog' ? '<h2>Card Library unavailable</h2><p>No supported card metadata is currently available.</p>' : unresolved.length ? '<h2>Your card evidence is retained</h2><p>Some owned cards need identification before they can appear here.</p>' : '<h2>Your collection is empty</h2><p>Find a card in Card Library and add it to your collection.</p><a class="button-link" href="/card-library/">Browse Card Library</a>';
    const pageHref = page => {const p=new URLSearchParams(params);p.set('page',page);p.delete('scroll');return listDestination(path,p);};
    $('#content').innerHTML = `<div class="page-title card-list-heading"><h1>${scope === 'owned' ? 'My Cards' : 'Card Library'}</h1><p id="cards-count" role="status">${result.total} ${result.total === 1 ? 'card' : 'cards'}${filtered ? ' match' : ''}</p></div><p class="browse-scope">${scope === 'owned' ? 'Current collection · owned cards' : 'Published catalog · owned and unowned cards'}</p>${filters(path,params,options)}${activeFilters(path,params,options)}<div id="card-group-list" class="owned-card-grid">${result.groups.map(g => tile(g,safeList(path+location.search))).join('')}</div>${result.groups.length ? `<nav class="card-pagination" aria-label="Card pages">${result.page > 1 ? `<a class="button-link secondary" rel="prev" href="${esc(pageHref(result.page-1))}">Previous cards</a>` : ''}<span>Page ${result.page} of ${result.pages}</span>${result.page < result.pages ? `<a class="button-link secondary" rel="next" href="${esc(pageHref(result.page+1))}">Next cards</a>` : ''}</nav>` : `<section class="panel empty">${empty}${filtered ? `<a href="${path}">Clear filters</a>` : ''}</section>`}${unresolvedArea(unresolved)}`;
    bindImageOptions();
    $('#card-filters').onsubmit = event => {
      event.preventDefault();
      const next = new URLSearchParams(new FormData(event.currentTarget));
      for (const key of [...next.keys()]) if (!next.get(key)) next.delete(key);
      location.assign(listDestination(path,next));
    };
    for (const key of ['set','language','edition','finish','variant','sort']) {
      const control = $('#cards-' + key), caption = $('#cards-' + key + '-value');
      control.onchange = () => {
        caption.hidden = control.value === (key === 'sort' ? 'set' : '');
        caption.textContent = caption.hidden ? '' : control.selectedOptions[0].textContent;
      };
    }
    document.querySelectorAll('.app-header [data-navigation-section="cards"], .app-header [data-navigation-tab="/card-library/"]').forEach(link=>{link.setAttribute('href',tabDestination(link.dataset.navigationTab||'/cards/'));link.onclick=()=>{saveScroll();if(new URL(link.href).pathname===location.pathname)link.href=returnWithScroll();};});
    document.querySelectorAll('.owned-card-tile').forEach(link => link.addEventListener('click',() => {
      saveScroll();const url=new URL(link.href);try{const list=new URL(location.href);list.searchParams.delete('scroll');sessionStorage.setItem(storageKey(list.pathname+list.search)+':focus',url.pathname);}catch{/* Optional focus memory. */}url.searchParams.set('return',returnWithScroll());link.href=url.pathname+url.search;
    }));
    const scrollURL = new URL(location.href); scrollURL.searchParams.delete('scroll');
    let restore = Number(params.get('scroll')) || 0;
    try { restore ||= Number(sessionStorage.getItem(storageKey(scrollURL.pathname + scrollURL.search))) || 0; } catch { /* Optional. */ }
    const retainedURL=new URL(listDestination(path,params),location.origin);retainedURL.searchParams.set('scroll',String(Math.min(10000000,Math.max(0,Math.round(restore)))));saveTabState(path,retainedURL.pathname+retainedURL.search);
    requestAnimationFrame(() => { if (!active()) return;
      try { const focus=sessionStorage.getItem(storageKey(scrollURL.pathname+scrollURL.search)+':focus');
        if(focus)Array.from(document.querySelectorAll('.owned-card-tile')).find(link=>new URL(link.href).pathname===focus)?.focus({preventScroll:true});
      } catch {/* Optional focus memory. */}
      if(restore)scrollTo(0,restore);
    });
    window.rememberCollectionDestination?.();
  }
  function variantLabel(v) { return [v.edition,v.finish,v.variant].filter(Boolean).join(' · ') || 'Variant details not recorded'; }
  async function matchingVariants(variants, returnTo, groupId, expectedGeneration) {
    const url=new URL(returnTo || '/cards/',location.origin),params=url.searchParams;
    if(!['edition','finish','variant'].some(key=>params.get(key)))return [];
    const query=new URLSearchParams();
    for(const key of filterKeys)if(params.get(key))query.set(key,params.get(key));
    query.set('generation',expectedGeneration);
    const matches=await api((url.pathname==='/cards/'?'/api/my-card-groups/':'/api/card-groups/')+'?'+query);
    if(matches.generation!==expectedGeneration || (matches.account_id && matches.account_id!==account())){const error=new Error('Your collection changed while matching variants were loading. Reload current cards.');error.status=409;throw error;}
    const ids=matches.groups.find(row=>row.id===groupId)?.matching_child_ids || [];
    return ids.filter(id=>variants.some(variant=>variant.id===id));
  }
  function facts(rows) {
    return rows.filter(([,value])=>value!=null && value!=='').map(([label,value])=>`<dt>${esc(label)}</dt><dd>${esc(value)}</dd>`).join('');
  }
  function copyDetails(copy, variants, index) {
    const variant=variants.find(v=>v.id===copy.printing_id);
    const binder=data.binders.find(b=>b.id===copy.binder_id)?.name;
    return `<article class="card-copy-row"><div class="card-copy-heading"><div><h3>Copy ${index+1}</h3><p>${esc(copy.condition || 'Condition not recorded')}${binder?' · '+esc(binder):''}</p></div><button class="secondary" data-group-copy="${esc(copy.id)}">Edit copy</button></div><p class="muted">${copy.first_edition_selected?'First edition selected':'Copy edition unresolved'} · ${esc(variant?variantLabel(variant):'Variant unresolved')}</p>${photoLink(copy)}<details class="copy-actions"><summary>More copy actions</summary><div class="actions"><button class="secondary" data-group-edition="${esc(copy.id)}">Edition</button><button class="secondary" data-group-remove="${esc(copy.id)}">Remove this copy</button></div></details></article>`;
  }
  function collectionSection(g, copies, variants, matching, selected, returnTo) {
    const counts=copies.length?`<p>${esc(g.recorded_copy_count)} recorded active matching copies${g.current_copy_count!==g.recorded_copy_count?' · '+esc(g.current_copy_count)+' supported current copies':''}. <span class="muted">Itemised records are separate from your complete card quantity.</span></p>`:'<p class="muted">No individual copy records yet. Your ownership is recorded separately.</p>';
    return `<section id="group-copies" class="card-collection" aria-labelledby="card-collection-heading"><h2 id="card-collection-heading">Your collection</h2>${counts}${copies.map((c,i)=>copyDetails(c,variants,i)).join('')}<details id="group-variants" ${selected||matching.length?'open':''}><summary>${selected?'Selected variant':matching.length?'Matching variants':'Variants and adding a copy'} (${variants.length})</summary>${selected?`<section id="group-selected" class="notice" data-selected-child="${esc(selected.id)}"><h3>Selected variant</h3><p>${esc(variantLabel(selected))} · ${selected.available?'Available':'Archived or unavailable'}</p><p class="selected-image-status">Selected variant image unavailable</p>${selected.available?'<button id="group-add-copy">Add a physical copy</button>':'<p>New copy addition is unavailable for this archived variant.</p>'}<a href="${esc(detailDestination(g,returnTo))}">Clear variant selection</a></section>`:'<p class="muted">Choose a variant to add an itemised copy. Broad ownership does not establish an exact variant.</p>'}${matching.length?`<p>${matching.length} ${matching.length===1?'variant matches':'variants match'} your list filters. Ownership and quantity are unchanged.</p>`:''}<ul class="card-variant-list">${variants.map(v=>`<li data-variant="${esc(v.id)}" ${matching.includes(v.id)?'data-filter-match="true"':''}><a href="${esc(detailDestination(g,returnTo,v.id))}">${esc(variantLabel(v))}</a><span class="muted">${v.available?'Available':'Archived or unavailable'}${v.exact_printing_owned?' · Exact variant qualified':v.declared_variant_owned?' · Owned (normal variant)':''}${matching.includes(v.id)?' · Matches filters':''}</span></li>`).join('')}</ul></details></section>`;
  }
  function supportingSection(g, variants, selected) {
    const known=key=>{const values=[...new Set(variants.map(v=>v[key]).filter(value=>value&&!['unknown','Unknown'].includes(value)))];return values.length===1?values[0]:null;};
    const rows=facts([['Language',g.language==='en'?'English':g.language],['Card type',selected?.supertype||known('supertype')],['Rarity',selected?.rarity||known('rarity')]]);
    return `<div class="card-supporting"><section id="group-details" aria-labelledby="card-facts-heading"><h2 id="card-facts-heading">Card facts</h2>${rows?`<dl class="card-facts">${rows}</dl>`:'<p class="muted">Card facts unavailable.</p>'}</section><section class="card-value" aria-labelledby="card-value-heading"><h2 id="card-value-heading">Value evidence</h2><details id="group-prices"><summary>Prices and sources</summary><div id="group-prices-body"><p>Open to view retained guide scenarios for recorded copies.</p></div></details></section></div>`;
  }
  function recordSection(g, copies, variants, history) {
    return `<details id="group-records" class="card-records"><summary>Record details</summary><dl class="card-facts">${facts([['Card reference',g.id],['Metadata',g.catalog_available?'Available':'Archived or unavailable']])}</dl>${variants.map(v=>`<section class="card-variant-information"><h3>${esc(variantLabel(v))}</h3><dl class="card-facts">${facts([['Printing reference',v.id],['Edition',v.edition],['Finish',v.finish],['Variant',v.variant]])}</dl></section>`).join('')}${copies.length?`<h3>Copy references</h3><ol>${copies.map(c=>`<li class="copy-reference">${esc(c.id)}</li>`).join('')}</ol>`:''}${g.reference_image?`<section><h3>Reference image source</h3><dl class="card-facts">${facts([['Source',g.reference_image.source_id||'Unavailable'],['Precision',g.reference_image.precision]])}</dl></section>`:''}${history.length?`<details id="group-history"><summary>Removed copies (${history.length})</summary><p class="muted">Removed records do not count as active copies. Removed photos remain inaccessible.</p>${history.map(c=>`<article class="card-copy-row"><p>${esc(c.condition||'Condition not recorded')} · <span class="copy-reference">${esc(c.id)}</span></p></article>`).join('')}</details>`:''}<a href="/settings/">Review collection operations and undo</a></details>`;
  }
  function copyPriceContent(copy) {
    const markup=copyPrices(copy);
    // Preserve the existing per-copy guide renderer while the outer disclosure owns visibility.
    const content=markup.match(/^<details><summary>Guide scenarios for this copy<\/summary>([\s\S]*)<\/details>$/);
    return content?content[1]:markup;
  }
  function bindPrices(copies, expectedGeneration, active) {
    const disclosure=$('#group-prices'),body=$('#group-prices-body');
    let loading=false,loaded=false;
    const attached=()=>active()&&$('#group-prices')===disclosure;
    const current=()=>attached()&&data.effective_collection?.generation===expectedGeneration;
    disclosure.ontoggle=async()=>{
      if(!disclosure.open||loading||loaded||!attached())return;
      if(!current()){body.innerHTML='<p class="error" role="alert">Collection version changed or is unavailable. Reload this card before viewing retained prices.</p>';return;}
      if(document.body.dataset.parity!=='true'||document.body.dataset.staging==='true'||typeof copyPrices!=='function'){
        body.innerHTML='<p>Retained prices and source details are unavailable in this installation.</p>';loaded=true;return;
      }
      loading=true;body.innerHTML='<p role="status">Loading retained prices…</p>';
      try{
        const prices=await api('/api/parity/');
        if(!current())return;
        if(prices.effective_collection?.user_id!==account()||prices.effective_collection?.generation!==expectedGeneration){body.innerHTML='<p class="error" role="alert">Collection changed. Reload this card before viewing retained prices.</p>';return;}
        if(!prices.valuation?.copies){body.innerHTML='<p>Retained prices and source details are unavailable.</p>';return;}
        window.parityData=prices;
        const hasGuide=copy=>Object.values(prices.valuation.copies[copy.id]?.conditional||{}).some(Boolean);
        if(!copies.some(hasGuide)){body.innerHTML='<p>No matching retained guide evidence for this card’s recorded copies.</p>';loaded=true;return;}
        body.innerHTML='<p class="muted">Dated guide scenarios apply to each recorded physical copy under their stated assumptions. Your complete card quantity is not a valuation multiplier.</p>'+copies.map((copy,index)=>`<section class="card-copy-row"><h3>Recorded copy ${index+1}</h3>${hasGuide(copy)?copyPriceContent(copy):'<p>No matching retained guide evidence for this copy.</p>'}</section>`).join('');
        loaded=true;
      }catch(error){if(current())body.innerHTML=`<p class="error" role="alert">${esc(error.message)}</p><p>Retained prices are unavailable. Close and reopen Prices and sources to retry.</p>`;}
      finally{loading=false;}
    };
  }
  async function renderDetail(key, active) {
    const params=new URLSearchParams(location.search), child=params.get('child');
    const returnTo=safeList(params.get('return')) || '/cards/';
    $('#content').innerHTML=`<a href="${esc(returnTo)}">Back to ${backLabel(returnTo)}</a><p role="status">Loading card…</p>`;
    const query=new URLSearchParams();if(child!==null)query.set('child',child);
    if(Number.isSafeInteger(data.effective_collection?.generation))query.set('generation',data.effective_collection.generation);
    const result=await api('/api/card-groups/'+encodeURIComponent(key)+'/'+(query.size?'?'+query:''));
    if(!active())return;
    if(result.account_id && result.account_id!==account())throw new Error('Account changed. Reload your current collection.');
    if(Number.isSafeInteger(data.effective_collection?.generation) && result.generation!==data.effective_collection.generation){const error=new Error('Your collection changed while this card was loading. Reload current cards before editing.');error.status=409;throw error;}
    const g=result.group, selected=result.selected_child, context={group:g.id,...(selected?{child:selected.id}:{})};
    const identity={set_name:g.set_name,name:g.name,number:g.collector_number,language:g.language};
    const matching=await matchingVariants(result.variants,returnTo,g.id,result.generation), copies=result.copies || [], history=result.history || [];
    if(!active())return;
    $('#content').innerHTML=`<div class="card-breadcrumbs"><a id="card-back" href="${esc(returnTo)}">← Back to ${backLabel(returnTo)}</a></div><article id="canonical-card" data-group-id="${esc(g.id)}" data-selected-child="${esc(selected?.id || '')}"><div class="card-detail-layout"><div class="card-detail-image">${cardImage(g.reference_image)}</div><div class="card-detail-summary"><h1>${esc(g.name)}</h1><p class="card-set-number">${esc(g.set_name)} · #${esc(g.collector_number)}</p><p class="card-ownership">${g.present?'Owned':'Not owned'}${g.established_total_quantity==null?'':' · Quantity '+esc(g.established_total_quantity)}</p>${g.present&&g.established_total_quantity==null?'<p class="muted quantity-unknown">Quantity not recorded.</p>':''}${g.owned_variant==='normal'?'<p class="card-owned-variant">Normal variant</p>':''}${g.identity_status==='resolved'?`<button id="edit-group-card">${g.present?'Edit collection':'Add to collection'}</button>`:'<p class="notice">Card identity needs review before collection editing.</p>'}${!g.catalog_available?'<p class="muted">Card metadata is archived or unavailable. Your owned evidence is retained.</p>':''}<p class="reference-qualification">Reference scan · exact edition and finish not verified. Copy photos stay with their records.</p><div class="card-related-links">${g.pokemon_dex?`<a class="card-pokemon-link" href="/pokedex/${encodeURIComponent(g.pokemon_dex)}/">View Pokémon #${esc(String(g.pokemon_dex).padStart(3,'0'))}</a>`:''}</div></div></div>${collectionSection(g,copies,result.variants,matching,selected,returnTo)}${supportingSection(g,result.variants,selected)}${recordSection(g,copies,result.variants,history)}</article>`;
    if($('#edit-group-card'))$('#edit-group-card').onclick=()=>editCollectionCard(identity,context,g);
    if($('#group-add-copy'))$('#group-add-copy').onclick=()=>editCopy(null,selected,context);
    bindPrices(copies,result.generation,active);
    document.querySelectorAll('[data-group-copy]').forEach(button=>button.onclick=()=>{const c=copies.find(c=>c.id===button.dataset.groupCopy);editCopy(c,null,{group:g.id,child:c.printing_id});});
    document.querySelectorAll('[data-group-edition]').forEach(button=>button.onclick=()=>{const c=copies.find(c=>c.id===button.dataset.groupEdition);editCopyEdition(c,{group:g.id,child:c.printing_id},g);});
    document.querySelectorAll('[data-group-remove]').forEach(button=>button.onclick=()=>{const c=copies.find(c=>c.id===button.dataset.groupRemove);preview('remove',{id:c.id,revision:c.revision},crypto.randomUUID(),{group:g.id,child:c.printing_id});});
    const shopping=document.createElement('a');shopping.id='card-shopping';shopping.textContent=selected?'Find this printing in Shopping':'Find cards in Shopping';
    const shoppingReturn=()=>location.pathname+location.search;
    let goalScope=null;try{const back=new URL(returnTo,location.origin);const goal=back.searchParams.get('goal');const owned=data.goals?.find(row=>row.id===goal);if(owned)goalScope={goal_id:owned.id,version:owned.version};}catch{/* No implied goal. */}
    shopping.href=window.collectionShoppingDestination?.(context,goalScope,shoppingReturn())||'/shopping/';
    shopping.addEventListener('click',()=>{shopping.href=window.collectionShoppingDestination?.(context,goalScope,shoppingReturn())||'/shopping/';});
    document.querySelector('.card-related-links').append(shopping);
    window.rememberCollectionDestination?.();
  }
  window.renderCardScreens = async route => {
    const match=route.match(/^\/card-groups\/([^/]+)\/$/);
    if(!listPaths.includes(route)&&!match)return false;
    const id=++generation, authority=data, url=location.href, principal=account();
    const active=()=>id===generation&&data===authority&&location.href===url&&account()===principal;
    try {
      if(!Number.isSafeInteger(authority.effective_collection?.generation)||authority.effective_collection.generation<0){const error=new Error('Collection version is unavailable. Reload current cards before editing.');error.status=409;throw error;}
      if(match)await renderDetail(decodeURIComponent(match[1]),active);else await renderList(route,active); }
    catch(error) {if(active())errorState(error,safeList(new URLSearchParams(location.search).get('return')) || '/cards/');}
    return true;
  };
})();
