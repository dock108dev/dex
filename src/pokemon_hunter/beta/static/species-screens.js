'use strict';
/* Canonical Pokémon browsing. Current possession and frozen goal status stay separate. */
(() => {
  const filterKeys=['q','region','owned','goal','set','era','type','rarity','card','gaps'];
  const listKeys=[...filterKeys,'scroll','focus','selecting'];
  let sequence=0, selection=new Set(), selectionScope='', selecting=false;
  const account=()=>data?.effective_collection?.user_id || '';
  const bounded=(value,min,max)=>/^[0-9]+$/.test(value)&&Number.isSafeInteger(Number(value))&&Number(value)>=min&&Number(value)<=max;
  function safeSpeciesReturn(value, listOnly=false) {
    if(typeof value!=='string'||!value.startsWith('/')||value.startsWith('//')||/[\x00-\x1f\x7f]/.test(value))return null;
    try{
      const url=new URL(value,location.origin), species=url.pathname.match(/^\/pokedex\/([0-9]+)\/$/);
      if(url.origin!==location.origin||url.hash||url.pathname!=='/pokedex/'&&(!species||listOnly)||species&&!bounded(species[1],1,251))return null;
      const allowed=species?['goal','scroll','return']:listKeys;
      for(const [key,val] of [...url.searchParams]){
        if(!allowed.includes(key)||url.searchParams.getAll(key).length!==1||/[\x00-\x1f\x7f]/.test(val)||val.length>(key==='return'?4096:160))return null;
        if(key==='scroll'&&!bounded(val,0,10000000)||key==='focus'&&!bounded(val,1,251))return null;
        if(key==='region'&&!['','all','1','2','kanto','johto'].includes(val)||key==='owned'&&!['','all','owned','missing'].includes(val)||key==='gaps'&&!['true','false'].includes(val)||key==='selecting'&&val!=='1')return null;
        if(key==='region'&&['all','1','2'].includes(val)){if(val==='all')url.searchParams.delete(key);else url.searchParams.set(key,val==='1'?'kanto':'johto');}
        if(key==='return'){const nested=safeSpeciesReturn(val,true);if(!nested)return null;url.searchParams.set(key,nested);}
      }
      return url.pathname+url.search;
    }catch{return null;}
  }
  window.safeSpeciesReturn=safeSpeciesReturn;
  window.invalidateSpeciesScreens=()=>{sequence++;};
  addEventListener('pagehide',()=>{sequence++;});
  function authority(result, expected) {
    if(result.public!==false||result.account_id!==account()||result.generation!==expected){const error=new Error('Your collection changed while Pokémon were loading. Reload the current collection.');error.status=409;throw error;}
  }
  function paramsForApi(params, expected) {
    const query=new URLSearchParams();
    for(const key of filterKeys)if(params.get(key))query.set(key,params.get(key));
    query.set('generation',expected);
    return query;
  }
  function listContext(params, focus) {
    const next=new URLSearchParams();
    for(const key of filterKeys)if(params.get(key))next.set(key,params.get(key));
    if(selecting)next.set('selecting','1');
    next.set('scroll',String(Math.min(10000000,Math.max(0,Math.round(scrollY)))));
    if(focus)next.set('focus',String(focus));
    return safeSpeciesReturn('/pokedex/?'+next,true) || '/pokedex/';
  }
  function speciesDestination(dex,params) {
    const next=new URLSearchParams();
    if(params.get('goal'))next.set('goal',params.get('goal'));
    next.set('return',listContext(params,dex));
    return '/pokedex/'+dex+'/?'+next;
  }
  function selectionKey(params) {return 'dex-species-selection:'+account()+':'+(params.get('goal')||'current')+':'+(params.get('region')||'all');}
  function saveSelection(params) {try{sessionStorage.setItem(selectionKey(params),JSON.stringify([...selection]));}catch{/* Optional account-local UI memory. */}}
  function loadSelection(params) {
    const key=selectionKey(params);
    if(selectionScope===key)return;
    selectionScope=key;selection.clear();
    try{const saved=JSON.parse(sessionStorage.getItem(key)||'[]');if(Array.isArray(saved))selection=new Set(saved.filter(n=>Number.isInteger(n)&&n>=1&&n<=251));}catch{/* Invalid UI memory is ignored. */}
  }
  function option(value,label,selected) {return `<option value="${esc(value)}" ${value===selected?'selected':''}>${esc(label)}</option>`;}
  function choices(id,label,values,params) {
    const selected=params.get(id)||'';
    const rows=values.map(v=>typeof v==='string'?{id:v,name:v}:v);
    if(selected&&!rows.some(v=>v.id===selected))rows.push({id:selected,name:selected+' · unavailable filter'});
    return `<div><label for="dex-${id}">${label}</label><select id="dex-${id}" aria-describedby="dex-${id}-value">${option('','All',selected)}${rows.map(v=>option(v.id,v.name,selected)).join('')}</select><p id="dex-${id}-value" class="species-selected-label" hidden></p></div>`;
  }
  function goalSummary(result) {
    const scope=result.scope;
    if(scope.kind==='current')return '';
    if(!scope.supported)return `<section class="species-goal-notice"><strong>${esc(scope.name)} · Saved goal</strong><p>${result.progress.satisfied} / ${result.progress.total} ${esc(scope.units)} satisfied. This goal’s saved policy has no Pokédex completion view.</p><a href="/goals/">View this goal in Goals</a></section>`;
    return `<section class="species-goal-notice"><strong>${esc(scope.name)} · Saved species goal</strong><p>${result.progress.satisfied} / ${result.progress.total} species counted ${scope.kind==='saved_declaration'?'in the saved declaration':'by qualified current copies'}. Your Cards always shows current possession.</p><details><summary>Saved goal policy and source</summary><p>${scope.kind==='saved_declaration'?'Frozen declaration and species membership; current edits do not refresh this snapshot.':'Frozen species membership; progress uses this goal’s existing qualified-copy policy.'}</p><a href="/goals/">Review saved goal versions</a></details></section>`;
  }
  function failure(error) {
    $('#content').innerHTML=`<h1>${error.status===409?'Collection changed':'Pokémon unavailable'}</h1><p class="error" role="alert">${esc(error.message)}</p><p>Reload to use the current account and collection. No changes were made.</p><div class="actions"><button id="species-reload">Reload current collection</button><a href="/pokedex/">Current Pokédex</a><a href="/goals/">Review Goals</a></div>`;
    $('#species-reload').onclick=()=>location.reload();
  }
  function statusFor(row) {return row.current_present?'Collected':'Not collected';}
  function goalStatus(row,scope) {return scope.kind!=='current'&&scope.supported?`<span class="species-goal-status">${row.goal_present?'Counted in saved goal':'Not counted in saved goal'}</span>`:'';}
  function countAndActions(result,rows,params) {
    const hidden=[...selection].filter(n=>!rows.some(row=>row.dex===n)).length;
    $('#species-count').textContent=`${rows.length} matching Pokémon${selecting?' · '+selection.size+' selected'+(hidden?' ('+hidden+' hidden by filters)':''):''}`;
    $('#dex-lookup-selection').disabled=!selection.size;
    $('#dex-batch-actions').hidden=!selecting;
    $('#dex-select-mode').textContent=selecting?'Done selecting':'Select';
    $('#dex-select-mode').setAttribute('aria-pressed',String(selecting));
    const query=new URLSearchParams({targets:rows.map(row=>row.dex).join(','),scope:'all'});
    if(params.get('goal'))query.set('goal',params.get('goal'));
    $('#dex-lookup-visible').href='/lookup/?'+query;$('#dex-lookup-visible').hidden=!rows.length;
    $('#species-grid').innerHTML=rows.map(row=>`<article class="species-row cx-species-row${selecting?' is-selecting':''}">${selecting?`<label class="check species-select"><input type="checkbox" data-select-species="${row.dex}" ${selection.has(row.dex)?'checked':''}><span class="sr-only">Select #${String(row.dex).padStart(3,'0')} ${esc(row.name)}</span></label>`:''}<a class="species-detail cx-species-link" data-dex-species="${row.dex}" href="${esc(speciesDestination(row.dex,params))}">${speciesImage(row.species_artwork,true)}<span class="species-row-text"><strong><span class="species-number">#${String(row.dex).padStart(3,'0')}</span> ${esc(row.name)}</strong><span>${statusFor(row)}</span>${goalStatus(row,result.scope)}</span></a></article>`).join('')||'<section class="empty"><h2>No matching Pokémon</h2><p>Clear a filter or include unknown card metadata.</p><a href="/pokedex/">Show all Pokémon</a></section>';
    document.querySelectorAll('[data-dex-species]').forEach(link=>link.addEventListener('click',()=>{link.href=speciesDestination(Number(link.dataset.dexSpecies),params);try{sessionStorage.setItem('dex-species-return:'+account()+':'+location.pathname+location.search,JSON.stringify({focus:Number(link.dataset.dexSpecies),scroll:Math.round(scrollY)}));}catch{/* Optional. */}}));
    document.querySelectorAll('[data-select-species]').forEach(box=>box.onchange=()=>{if(box.checked)selection.add(Number(box.dataset.selectSpecies));else selection.delete(Number(box.dataset.selectSpecies));saveSelection(params);countAndActions(result,rows,params);document.querySelector('[data-select-species="'+box.dataset.selectSpecies+'"]')?.focus();});
    $('#dex-select-visible').onclick=()=>{rows.forEach(row=>selection.add(row.dex));saveSelection(params);countAndActions(result,rows,params);$('#dex-select-visible').focus();};
    $('#dex-clear-selection').onclick=()=>{selection.clear();saveSelection(params);countAndActions(result,rows,params);$('#dex-clear-selection').focus();};
  }
  async function renderList(expected,active,bindRoute) {
    const canonical=safeSpeciesReturn(location.pathname+location.search,true);
    if(!canonical)throw new Error('This Pokédex address has unsupported filters. Open the current Pokédex.');
    if(canonical!==location.pathname+location.search){history.replaceState(null,'',canonical);bindRoute();}
    const params=new URLSearchParams(location.search);
    selecting=params.get('selecting')==='1';loadSelection(params);
    $('#content').innerHTML='<h1>Pokédex</h1><p role="status">Loading Pokémon…</p>';
    let result=await api('/api/pokedex-species/?'+paramsForApi(params,expected));
    if(!active())return;authority(result,expected);
    $('#content').innerHTML=`<div class="page-title"><h1>Pokédex</h1></div><div class="toolbar dex-filters cx-dex-filters"><div><label for="dex-search">Search Pokémon</label><input id="dex-search" type="search" maxlength="160" value="${esc(params.get('q')||'')}" placeholder="Name or Pokédex number"></div><div><label for="dex-region">Region</label><select id="dex-region">${option('','Kanto & Johto',params.get('region')||'')}${option('kanto','Kanto',params.get('region'))}${option('johto','Johto',params.get('region'))}</select></div><div class="species-scope"><strong id="dex-scope-label"></strong><p id="dex-progress" class="collection-progress"></p></div></div><details class="panel"><summary>Collection scope and saved goals</summary><label id="dex-owned-label" for="dex-owned">Current collection</label><select id="dex-owned">${option('all','All Pokémon',params.get('owned')||'all')}${option('owned','Collected',params.get('owned'))}${option('missing','Not collected',params.get('owned'))}</select><label for="dex-goal">Saved goal</label><select id="dex-goal" aria-describedby="dex-goal-value">${option('','Current',params.get('goal')||'')}${data.goals.map(goal=>option(goal.id,goal.name,params.get('goal'))).join('')}</select><p id="dex-goal-value" class="species-selected-label" hidden></p><div class="actions"><button id="dex-goal-create" class="secondary">Create a goal</button><a href="/goals/">Manage Goals</a></div></details><div id="dex-goal-summary"></div><details class="panel"><summary>Filter by card details</summary><div class="form-grid">${choices('set','Indexed set',result.sets||[],params)}${choices('era','Indexed era',result.eras||[],params)}${choices('type','Card type',result.types||[],params)}${choices('rarity','Rarity',result.rarities||[],params)}<div><label for="dex-card">Card name / number</label><input id="dex-card" type="search" maxlength="160" value="${esc(params.get('card')||'')}"></div></div><label class="check"><input id="dex-gaps" type="checkbox" ${params.get('gaps')!=='false'?'checked':''}>Keep unknown or unindexed metadata visible</label></details><div class="selection-toolbar"><p id="species-count" role="status" aria-live="polite"></p><button id="dex-select-mode" class="secondary" aria-pressed="false">Select</button><div id="dex-batch-actions" class="actions" hidden><button id="dex-lookup-selection" disabled>Look up selection</button><a id="dex-lookup-visible" href="/lookup/">Look up all matches</a><button id="dex-select-visible" class="secondary">Select all matches</button><button id="dex-clear-selection" class="secondary">Clear selection</button><p class="muted selection-policy">Selection changes no ownership. Search-hidden selections stay selected; changing region or goal clears selection.</p></div></div><div class="species-list cx-species-list" id="species-grid"></div><details class="panel"><summary>Collection tools and history</summary><div class="actions"><button id="dex-import" class="secondary">Import collection</button><a href="/settings/">Source history and reconciliation</a><a href="/api/export/">Export copy and goal JSON</a><button id="dex-json-import" class="secondary">Import copy and goal JSON</button></div></details>`;
    let querySequence=0;
    const paint=()=>{
      const membership=new Set(result.scope.supported?(result.scope.membership||result.species.map(row=>row.dex)):Array.from({length:251},(_,i)=>i+1));
      const savedScope=result.scope.kind!=='current'&&result.scope.supported;
      $('#dex-owned-label').textContent=savedScope?'Saved goal status':'Current collection';
      $('#dex-owned').innerHTML=option('all','All Pokémon',params.get('owned')||'all')+option('owned',savedScope?'Counted in saved goal':'Collected',params.get('owned'))+option('missing',savedScope?'Not counted in saved goal':'Not collected',params.get('owned')); 
      selection=new Set([...selection].filter(n=>membership.has(n)&&(params.get('region')!=='kanto'||n<=151)&&(params.get('region')!=='johto'||n>=152)));saveSelection(params);
      const progress=result.current_progress||result.progress;
      $('#dex-scope-label').textContent=result.scope.kind==='current'?'Current collection · '+(params.get('region')==='kanto'?'#001–151':params.get('region')==='johto'?'#152–251':'#001–251'):result.scope.name+' · Saved '+result.scope.units+' goal';
      $('#dex-progress').textContent=`${progress.satisfied} / ${progress.total} Pokémon collected in current scope`;
      $('#dex-goal-summary').innerHTML=goalSummary(result);
      window.rememberCollectionDestination?.();
      for(const key of ['set','era','type','rarity']){const label=$('#dex-'+key+'-value'),selected=params.get(key)||'';label.hidden=!selected;const value=key==='set'?(result.sets||[]).find(row=>row.id===selected)?.name||selected:selected;label.textContent=selected?'Selected '+({set:'set',era:'era',type:'card type',rarity:'rarity'}[key])+': '+value:'';}
      const goalLabel=$('#dex-goal-value');goalLabel.hidden=!params.get('goal');goalLabel.textContent=params.get('goal')?'Saved goal: '+result.scope.name+' · '+result.scope.units:'';
      countAndActions(result,result.species,params);
    };
    const update=async changed=>{
      if(!active())return;
      const request=++querySequence;
      if(changed==='goal'||changed==='region'){selection.clear();selectionScope=selectionKey(params);saveSelection(params);}
      const key=changed==='search'?'q':changed;
      const control=$('#dex-'+changed),value=changed==='gaps'?String(control.checked):control.value;
      if(value)params.set(key,value);else params.delete(key);
      if(changed==='goal'||changed==='region'){selection.clear();selectionScope=selectionKey(params);saveSelection(params);}
      params.delete('focus');params.delete('scroll');
      history.replaceState(null,'','/pokedex/'+(params.size?'?'+params:''));
      bindRoute();
      $('#species-count').textContent='Updating Pokémon…';
      try{const next=await api('/api/pokedex-species/?'+paramsForApi(params,expected));if(!active()||request!==querySequence)return;authority(next,expected);result=next;paint();}catch(error){if(active()&&request===querySequence)failure(error);}
    };
    for(const key of ['region','owned','goal','set','era','type','rarity','gaps'])$('#dex-'+key).onchange=()=>update(key);
    let timer;for(const key of ['search','card'])$('#dex-'+key).oninput=()=>{querySequence++;clearTimeout(timer);timer=setTimeout(()=>update(key),180);};
    $('#dex-select-mode').onclick=()=>{selecting=!selecting;if(selecting)params.set('selecting','1');else params.delete('selecting');history.replaceState(null,'','/pokedex/'+(params.size?'?'+params:''));bindRoute();paint();$('#dex-select-mode').focus();};
    $('#dex-lookup-selection').onclick=()=>{if(!selection.size)return;const query=new URLSearchParams({targets:[...selection].sort((a,b)=>a-b).join(','),scope:'all'});if(params.get('goal'))query.set('goal',params.get('goal'));location.assign('/lookup/?'+query);};
    $('#dex-import').onclick=()=>withCollectionTools(dexImport);$('#dex-json-import').onclick=()=>withCollectionTools(dexJsonImport);$('#dex-goal-create').onclick=()=>withCollectionTools(()=>{dexSelection=new Set(selection);dexGoal();});
    paint();
    let focus=Number(params.get('focus'))||0,restore=Number(params.get('scroll'))||0;
    try{const saved=JSON.parse(sessionStorage.getItem('dex-species-return:'+account()+':'+location.pathname+location.search)||'null');if(saved){focus||=saved.focus;restore||=saved.scroll;}}catch{/* Optional. */}
    requestAnimationFrame(()=>{if(active()){if(focus)document.querySelector('[data-dex-species="'+focus+'"]')?.focus({preventScroll:true});if(restore)scrollTo(0,restore);}});
  }
  async function renderSpecies(dex,expected,active) {
    const params=new URLSearchParams(location.search);
    if(!safeSpeciesReturn(location.pathname+location.search))throw new Error('This Pokémon address has unsupported context. Open the current Pokédex.');
    const back=safeSpeciesReturn(params.get('return'),true)||'/pokedex/';
    $('#content').innerHTML='<h1>Pokémon</h1><p role="status">Loading Your Cards…</p>';
    const identityQuery=new URLSearchParams({q:'#'+String(dex).padStart(3,'0'),generation:expected});if(params.get('goal'))identityQuery.set('goal',params.get('goal'));
    const [identity,groups]=await Promise.all([api('/api/pokedex-species/?'+identityQuery),api('/api/species/'+dex+'/card-groups/?generation='+expected+'&page_size=100')]);
    if(!active())return;authority(identity,expected);authority(groups,expected);
    let row=identity.species.find(row=>row.dex===dex);
    if(!row&&params.get('goal')){const currentQuery=new URLSearchParams({q:'#'+String(dex).padStart(3,'0'),generation:expected});const current=await api('/api/pokedex-species/?'+currentQuery);if(!active())return;authority(current,expected);row=current.species.find(row=>row.dex===dex);}
    if(!row)throw new Error('Canonical Pokémon identity is unavailable. Reload the current Pokédex.');
    const owned=groups.owned;if(!owned)throw new Error('Current card ownership is unavailable. Reload this Pokémon.');
    const all=[...owned.groups];
    for(let page=2;page<=owned.pages;page++){const next=await api('/api/species/'+dex+'/card-groups/?generation='+expected+'&page_size=100&page='+page);if(!active())return;authority(next,expected);all.push(...next.owned.groups);}
    const seen=new Set(),cards=all.filter(group=>{if(seen.has(group.id))return false;seen.add(group.id);return true;});
    const currentReturn=()=>{const url=new URL(location.href);url.searchParams.set('scroll',String(Math.min(10000000,Math.max(0,Math.round(scrollY)))));return safeSpeciesReturn(url.pathname+url.search);};
    const returnTo=currentReturn();
    const scopeNote=identity.scope.kind==='current'||!identity.scope.supported?'':identity.scope.membership.includes(dex)?`<p class="muted">${row.goal_present?'Counted':'Not counted'} in ${esc(identity.scope.name)}. Your Cards is current possession.</p>`:`<p class="muted">Outside the saved ${esc(identity.scope.name)} goal. Your Cards is current possession.</p>`;
    $('#content').innerHTML=`<a class="browse-return" href="${esc(back)}">Back to Pokédex</a><section class="species-detail-heading"><div>${speciesImage(row.species_artwork)}</div><div><h1><span class="species-title-number">#${String(dex).padStart(3,'0')}</span> ${esc(row.name)}</h1><p class="species-ownership">${statusFor(row)}</p></div></section><section aria-labelledby="your-cards-heading"><h2 id="your-cards-heading">Your Cards</h2><div id="species-owned-cards" class="owned-card-grid">${cards.map(group=>window.renderCardGroupTile(group,returnTo)).join('')}</div>${!cards.length?`<p class="empty">${row.current_present?'This Pokémon is collected; exact card details are not recorded.':'You haven’t collected a card for this Pokémon yet.'}</p>`:''}${row.details_needed||(groups.unresolved||[]).length?'<details class="card-unresolved"><summary>Card details needed</summary><p>Species evidence is retained; some exact card identities remain unknown. No card or quantity has been inferred.</p><a href="/settings/">Review collection sources and records</a></details>':''}<p class="species-catalog-link"><a href="/card-library/?species=${dex}">Explore ${esc(row.name)} cards</a></p></section>${scopeNote}${goalSummary(identity)}<details class="species-details"><summary>Collection details</summary><p>Species quantity is unknown. Card quantities, when recorded, belong to their individual card pages.</p><a href="/settings/">Source history and reconciliation</a></details>`;
    document.querySelectorAll('#species-owned-cards .owned-card-tile').forEach(link=>link.addEventListener('click',()=>{const url=new URL(link.href);url.searchParams.set('return',currentReturn());link.href=url.pathname+url.search;}));
    const shopping=document.createElement('a');shopping.id='species-shopping';shopping.textContent='Find cards for '+row.name;shopping.href=window.collectionShoppingDestination?.({species:dex},identity.scope,currentReturn())||'/shopping/';
    shopping.addEventListener('click',()=>{shopping.href=window.collectionShoppingDestination?.({species:dex},identity.scope,currentReturn())||'/shopping/';});
    const action=document.createElement('p');action.className='species-shopping-action';shopping.className='button-link secondary';action.append(shopping);document.querySelector('.species-detail-heading>div:last-child').append(action);
    window.rememberCollectionDestination?.();
    const restore=Number(params.get('scroll'))||0;if(restore)requestAnimationFrame(()=>{if(active())scrollTo(0,restore);});
  }
  window.renderSpeciesScreen=async route=>{
    const match=route.match(/^\/pokedex\/([0-9]+)\/$/);if(route!=='/pokedex/'&&!match)return false;
    const ticket=++sequence,actor=account(),expected=data?.effective_collection?.generation;
    let routeBinding=location.pathname+location.search;
    const bindRoute=()=>{routeBinding=location.pathname+location.search;};
    const active=()=>ticket===sequence&&actor===account()&&expected===data?.effective_collection?.generation&&location.pathname+location.search===routeBinding;
    try{if(!actor||!Number.isSafeInteger(expected))throw new Error('Current collection authority is unavailable. Reload before browsing Pokémon.');if(match)await renderSpecies(Number(match[1]),expected,active);else await renderList(expected,active,bindRoute);}catch(error){if(active())failure(error);}
    return true;
  };
})();
