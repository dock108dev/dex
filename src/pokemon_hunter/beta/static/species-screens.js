'use strict';
/* Canonical Pokémon browsing. Current possession and frozen goal status stay separate. */
(() => {
  const multiKeys=['set','era','type','rarity','finish','released','year'];
  const scopeKeys=[...multiKeys,'date_from','date_to','card'];
  const filterKeys=['page','page_size','q','region','owned','goal','gaps',...scopeKeys];
  function scopeValues(value='') {
    if(typeof value!=='string'||value.length>1400)throw Error('Choose shorter scope values.');
    const items=value.startsWith('[')?JSON.parse(value):value?[value]:[];
    if(!Array.isArray(items)||items.length>8||items.some(v=>typeof v!=='string'||!v||v.length>160||/[\x00-\x1f\x7f]/.test(v)))throw Error('Choose up to eight values per dimension.');
    return [...new Set(items)].sort();
  }
  const encodeScope=items=>items.length===1?items[0]:items.length?JSON.stringify(items):'';
  function canonicalScope(params) {
    for(const key of multiKeys){const value=encodeScope(scopeValues(params.get(key)||''));if(value)params.set(key,value);else params.delete(key);}
    if(scopeValues(params.get('released')||'').some(v=>!['pre-2000','2000-onward','Unknown'].includes(v)))throw Error('Choose a supported release period.');
    if(scopeValues(params.get('year')||'').some(v=>!/^\d{4}$/.test(v)||+v<1996||+v>2100))throw Error('Choose a supported release year.');
    for(const key of ['date_from','date_to']){const value=params.get(key);if(value&&(!/^\d{4}-\d{2}-\d{2}$/.test(value)||+value.slice(0,4)<1||!Number.isFinite(Date.parse(value))||new Date(value).toISOString().slice(0,10)!==value))throw Error('Use a valid calendar date.');}
    if(params.get('date_from')&&params.get('date_to')&&params.get('date_from')>params.get('date_to'))throw Error('The inclusive start must precede the inclusive end.');
    const encoded=new URLSearchParams();for(const key of scopeKeys)if(params.get(key))encoded.set(key,params.get(key));
    if(encoded.toString().length>1500)throw Error('Choose a smaller combined scope for navigation.');
    return params;
  }
  const listKeys=[...filterKeys,'scroll','focus','selecting'];
  let reader;
  let sequence=0, selection=new Set(), selectionScope='', selecting=false;
  const account=()=>data?.effective_collection?.user_id || '';
  const bounded=(value,min,max)=>/^[0-9]+$/.test(value)&&Number.isSafeInteger(Number(value))&&Number(value)>=min&&Number(value)<=max;
  function safeSpeciesReturn(value, listOnly=false) {
    if(typeof value!=='string'||!value.startsWith('/')||value.startsWith('//')||/[\x00-\x1f\x7f]/.test(value))return null;
    try{
      const url=new URL(value,location.origin), species=url.pathname.match(/^\/pokedex\/([0-9]+)\/$/);
      if(url.origin!==location.origin||url.hash||url.pathname!=='/pokedex/'&&(!species||listOnly)||species&&!bounded(species[1],1,251))return null;
      const allowed=species?['goal','version','generation','scroll','return']:listKeys;
      for(const [key,val] of [...url.searchParams]){
        if(!allowed.includes(key)||url.searchParams.getAll(key).length!==1||/[\x00-\x1f\x7f]/.test(val)||val.length>(key==='return'?4096:multiKeys.includes(key)?1400:160))return null;
        if(key==='scroll'&&!bounded(val,0,10000000)||key==='focus'&&!bounded(val,1,251))return null;
        if(key==='region'&&!['','all','1','2','kanto','johto'].includes(val)||key==='owned'&&!['','all','owned','missing'].includes(val)||key==='gaps'&&!['true','false'].includes(val)||key==='selecting'&&val!=='1')return null;
        if(key==='region'&&['all','1','2'].includes(val)){if(val==='all')url.searchParams.delete(key);else url.searchParams.set(key,val==='1'?'kanto':'johto');}
        if(key==='return'){const nested=safeSpeciesReturn(val,true);if(!nested)return null;url.searchParams.set(key,nested);}
      }
      if(!species){canonicalScope(url.searchParams);const core=new URLSearchParams(url.searchParams);for(const key of ['scroll','focus','selecting'])core.delete(key);if(core.toString().length>1500||url.search.length>1801)return null;}
      if((url.pathname+url.search).length>4096)return null;
      return url.pathname+url.search;
    }catch{return null;}
  }
  window.safeSpeciesReturn=safeSpeciesReturn;
  window.invalidateSpeciesScreens=()=>{sequence++;reader?.stop();};
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
  const scopeLabels={set:'Sets / expansions',era:'Indexed series',type:'Card category',rarity:'Rarity',finish:'Finish',released:'Release period',year:'Release year',date_from:'Released on or after',date_to:'Released on or before',card:'Card name / number'};
  function scopeOptions(result) {
    return {set:result.sets||[],era:result.eras||[],type:result.types||[],rarity:result.rarities||[],finish:result.finishes||[],year:result.years||[],released:[{id:'pre-2000',name:'Pre-2000 · before Jan 1, 2000'},{id:'2000-onward',name:'2000 onward · includes Jan 1, 2000'},{id:'Unknown',name:'Unknown date'}]};
  }
  function editorKey(params) {
    const fields=new URLSearchParams();for(const key of filterKeys)if(params.get(key))fields.set(key,params.get(key));
    return 'dex-species-editor:'+(document.body?.dataset?.navigationBinding||account())+':'+fields;
  }
  function editorOpen(params) {try{return sessionStorage.getItem(editorKey(params))==='1';}catch{return false;}}
  function saveEditor(params,open) {try{sessionStorage.setItem(editorKey(params),open?'1':'0');}catch{/* Optional UI memory; server criteria remain authoritative. */}}
  function scopeEditor(result,params) {
    const options=scopeOptions(result);
    return `<details class="panel browse-controls" id="dex-scope-editor" ${editorOpen(params)?'open':''}><summary>Choose card scope</summary><p>Match any choice within a group and every selected group on the same owned card. Apply evaluates your complete selection.</p><div class="scope-choice-grid">${multiKeys.map(key=>{
      const selected=scopeValues(params.get(key)||''), rows=options[key].map(v=>typeof v==='string'?{id:v,name:v}:v);
      for(const id of selected)if(!rows.some(v=>v.id===id))rows.push({id,name:'Selected choice — loading label'});
      return `<fieldset id="dex-${key}" class="scope-choice"><legend>${scopeLabels[key]}</legend><label class="sr-only" for="scope-search-${key}">Search ${scopeLabels[key]}</label><input id="scope-search-${key}" type="search" data-scope-search="${key}" placeholder="Search choices"><div class="scope-options">${rows.map(v=>`<label class="check"><input type="checkbox" data-scope-key="${key}" value="${esc(v.id)}" ${selected.includes(v.id)?'checked':''}>${esc(v.name)}</label>`).join('')||'<p class="muted">No supported choices indexed</p>'}</div></fieldset>`;
    }).join('')}</div><div class="form-grid"><div><label for="dex-date_from">Released on or after (inclusive)</label><input id="dex-date_from" type="date" value="${esc(params.get('date_from')||'')}"></div><div><label for="dex-date_to">Released on or before (inclusive)</label><input id="dex-date_to" type="date" value="${esc(params.get('date_to')||'')}"></div><div><label for="dex-card">Card name / number</label><input id="dex-card" type="search" maxlength="160" value="${esc(params.get('card')||'')}"></div></div><p id="scope-pending" role="status">Selections are applied below.</p><p id="scope-error" class="error" role="alert"></p><div class="actions"><button id="dex-scope-apply">Apply card scope</button><button id="dex-scope-clear" class="secondary">Clear card scope</button></div><p class="muted">Sets identify expansions. Pack-family membership and the pack an owned card came from are unavailable.</p></details>`;
  }
  function goalSummary(result) {
    const scope=result.scope;
    if(scope.kind==='current')return '';
    if(!scope.supported)return `<section class="species-goal-notice"><strong>${esc(scope.name)} · Saved goal</strong><p>${result.progress.satisfied} / ${result.progress.total} ${esc(scope.units)} satisfied. This goal’s saved policy has no Pokédex completion view.</p><a href="/goals/">View this goal in Goals</a></section>`;
    return `<section class="species-goal-notice"><strong>${esc(scope.name)} · Saved species goal · original progress</strong><p>${result.progress.satisfied} / ${result.progress.total} species counted ${(scope.kind==='saved_declaration'||scope.progress_basis==='saved_declaration')?'in the saved declaration':'by qualified current copies'}. Your Cards always shows current possession.</p><details><summary>Saved goal policy and source</summary><p>${(scope.kind==='saved_declaration'||scope.progress_basis==='saved_declaration')?'Frozen declaration and species membership; current edits do not refresh this snapshot.':'Frozen species membership; progress uses this goal’s existing qualified-copy policy.'}</p><a href="/goals/">Review saved goal versions</a></details></section>`;
  }
  function failure(error) {
    $('#content').innerHTML=`<h1>${error.status===409?'Collection changed':'Pokémon unavailable'}</h1><p class="error" role="alert">${esc(error.message)}</p><p>Reload to use the current account and collection. Confirmed changes remain saved.</p><div class="actions"><button id="species-reload">Reload current collection</button><a href="/pokedex/">Current Pokédex</a><a href="/goals/">Review Goals</a></div>`;
    $('#species-reload').onclick=()=>location.reload();
  }
  function statusFor(row,restricted=true) {return row.scoped_present?(restricted?'Collected within this scope':'Collected'):({'unresolved':'Unresolved ownership or metadata','no_indexed':'No eligible indexed printing','missing':restricted?'Not collected within this scope':'Not collected'}[row.scope_status]||(restricted?'Not collected within this scope':'Not collected'));}
  function goalStatus(row,scope) {return scope.kind!=='current'&&scope.supported?`<span class="species-goal-status">${row.goal_present?'Counted in saved goal':'Not counted in saved goal'}</span>`:'';}
  function countAndActions(result,rows,params) {
    const hidden=[...selection].filter(n=>!rows.some(row=>row.dex===n)).length;
    $('#species-count').textContent=`${result.total} matching Pokémon · page ${result.page} of ${Math.max(1,result.pages)}${selecting?' · '+selection.size+' selected'+(hidden?' ('+hidden+' hidden by filters)':''):''}`;
    $('#dex-lookup-selection').disabled=!selection.size;
    $('#dex-batch-actions').hidden=!selecting;
    $('#dex-select-mode').textContent=selecting?'Done selecting':'Select';
    $('#dex-select-mode').setAttribute('aria-pressed',String(selecting));
    const query=new URLSearchParams({targets:rows.map(row=>row.dex).join(','),scope:'all'});
    if(params.get('goal'))query.set('goal',params.get('goal'));
    $('#dex-lookup-visible').href='/lookup/?'+query;$('#dex-lookup-visible').hidden=!rows.length;
    $('#species-grid').innerHTML=rows.map(row=>`<article class="species-row cx-species-row${selecting?' is-selecting':''}">${selecting?`<label class="check species-select"><input type="checkbox" data-select-species="${row.dex}" ${selection.has(row.dex)?'checked':''}><span class="sr-only">Select #${String(row.dex).padStart(3,'0')} ${esc(row.name)}</span></label>`:''}<a class="species-detail cx-species-link" data-dex-species="${row.dex}" href="${esc(speciesDestination(row.dex,params))}">${speciesImage(row.species_artwork,true)}<span class="species-row-text"><strong><span class="species-number">#${String(row.dex).padStart(3,'0')}</span> ${esc(row.name)}</strong><span>${statusFor(row,result.restricted)}</span>${row.current_present&&!row.scoped_present?'<span class="muted">Owned in overall collection</span>':''}${goalStatus(row,result.scope)}</span></a></article>`).join('')||'<section class="empty"><h2>No matching Pokémon</h2><p>Clear a filter or include unknown card metadata.</p><a href="/pokedex/">Show all Pokémon</a></section>';
    document.querySelectorAll('[data-dex-species]').forEach(link=>link.addEventListener('click',()=>{saveEditor(params,Boolean($('#dex-scope-editor')?.open));link.href=speciesDestination(Number(link.dataset.dexSpecies),params);try{sessionStorage.setItem('dex-species-return:'+account()+':'+location.pathname+location.search,JSON.stringify({focus:Number(link.dataset.dexSpecies),scroll:Math.round(scrollY)}));}catch{/* Optional. */}}));
    document.querySelectorAll('[data-select-species]').forEach(box=>box.onchange=()=>{if(box.checked)selection.add(Number(box.dataset.selectSpecies));else selection.delete(Number(box.dataset.selectSpecies));saveSelection(params);countAndActions(result,rows,params);document.querySelector('[data-select-species="'+box.dataset.selectSpecies+'"]')?.focus();});
    $('#dex-select-visible').onclick=()=>{rows.forEach(row=>selection.add(row.dex));saveSelection(params);countAndActions(result,rows,params);$('#dex-select-visible').focus();};
    const pager=document.createElement('nav');pager.setAttribute('aria-label','Pokémon pages');for(const [label,n] of [['Previous',result.page-1],['Next',result.page+1]])if(n>=1&&n<=result.pages){const p=new URLSearchParams(params);p.set('page',n);p.delete('scroll');p.delete('focus');const a=document.createElement('a');a.href='/pokedex/?'+p;a.textContent=label;pager.append(a);}$('#species-grid').append(pager);
    $('#dex-clear-selection').onclick=()=>{selection.clear();saveSelection(params);countAndActions(result,rows,params);$('#dex-clear-selection').focus();};
  }
  async function renderList(expected,active,bindRoute) {
    const canonical=safeSpeciesReturn(location.pathname+location.search,true);
    if(!canonical)throw new Error('This Pokédex address has unsupported filters. Open the current Pokédex.');
    if(canonical!==location.pathname+location.search){history.replaceState(null,'',canonical);bindRoute();}
    const params=new URLSearchParams(location.search);
    selecting=params.get('selecting')==='1';loadSelection(params);
    $('#content').innerHTML='<h1>Pokédex</h1><p role="status">Loading Pokémon…</p>';
    let result=await reader.get('/api/v2/pokedex-species/?'+paramsForApi(params,expected),'species-primary');
    if(!active())return;authority(result,expected);
    $('#content').innerHTML=`<div class="page-title dex-list-heading"><h1>Pokédex</h1><div class="species-scope"><strong id="dex-scope-label"></strong><p id="dex-progress" class="collection-progress"></p><p id="dex-overall" class="muted"></p></div></div><div class="toolbar dex-filters cx-dex-filters browse-controls"><div><label for="dex-search">Search Pokémon</label><input id="dex-search" type="search" maxlength="160" value="${esc(params.get('q')||'')}" placeholder="Name or Pokédex number"></div><div><label for="dex-region">Region</label><select id="dex-region">${option('','Kanto & Johto',params.get('region')||'')}${option('kanto','Kanto',params.get('region'))}${option('johto','Johto',params.get('region'))}</select></div><div><label id="dex-owned-label" for="dex-owned">Show within scope</label><select id="dex-owned">${option('all','All Pokémon',params.get('owned')||'all')}${option('owned','Collected',params.get('owned'))}${option('missing','Not collected',params.get('owned'))}</select></div></div><div class="dex-browse-options">${scopeEditor(result,params)}<details class="browse-controls dex-goal-picker"><summary>Saved goals</summary><label for="dex-goal">Saved goal</label><select id="dex-goal" aria-describedby="dex-goal-value">${option('','Current',params.get('goal')||'')}${data.goals.map(goal=>option(goal.id,goal.name,params.get('goal'))).join('')}</select><p id="dex-goal-value" class="species-selected-label" hidden></p><div class="actions"><button id="dex-goal-create" class="secondary">Create a goal</button><a href="/goals/">Manage Goals</a></div></details></div><div id="dex-active-filters" class="active-filters" aria-label="Applied Pokémon filters"></div><div id="dex-goal-summary"></div><div class="species-results-bar"><p id="species-count" role="status" aria-live="polite"></p><div class="selection-toolbar"><button id="dex-select-mode" class="secondary" aria-pressed="false">Select</button><div id="dex-batch-actions" class="actions" hidden><button id="dex-lookup-selection" disabled>Look up selection</button><a id="dex-lookup-visible" href="/lookup/">Look up this page</a><button id="dex-select-visible" class="secondary">Select this page</button><button id="dex-clear-selection" class="secondary">Clear selection</button><p class="muted selection-policy">Selection changes no ownership. Search-hidden selections stay selected; changing region or goal clears selection.</p></div></div></div><div class="species-list cx-species-list" id="species-grid"></div><p class="browse-maintenance"><a href="/settings/">Import and source history</a> · <a href="/collection-tools/">Collection tools</a></p>`;
    let querySequence=0;
    const resolveLabels=()=>{
      if(result.labelsResolved)return;result.labelsResolved=true;const snapshot=result;
      const items=multiKeys.filter(k=>k!=='year').flatMap(kind=>scopeValues(params.get(kind)||'').map(id=>({kind,id})));if(!items.length)return;
      reader.get('/api/v2/labels/?'+new URLSearchParams({items:JSON.stringify(items)}),'scope-labels').then(response=>{if(!active()||result!==snapshot)return;
        const names={set:'sets',era:'eras',type:'types',rarity:'rarities',finish:'finishes'};
        for(const item of response.labels){const key=names[item.kind];if(!key)continue;result[key]??=[];result[key]=result[key].filter(r=>(typeof r==='string'?r:r.id)!==item.id);result[key].push({id:item.id,name:item.label||'Unavailable retained selection'});
          for(const input of document.querySelectorAll('[data-scope-key]'))if(input.dataset.scopeKey===item.kind&&input.value===item.id){for(const node of [...input.parentElement.childNodes])if(node!==input)node.remove();input.parentElement.append(document.createTextNode(item.label||'Unavailable retained selection'));}
        }paint();
      }).catch(error=>{if(active()&&error.name!=='AbortError')$('#scope-error').textContent=error.message;});
    };
    const paint=()=>{
      const membership=new Set(Array.from({length:251},(_,i)=>i+1));
      const savedScope=result.scope.kind!=='current'&&result.scope.supported;
      $('#dex-owned-label').textContent='Show within scope';
      $('#dex-owned').innerHTML=option('all','All Pokémon',params.get('owned')||'all')+option('owned','Collected',params.get('owned'))+option('missing','Not collected',params.get('owned'));
      selection=new Set([...selection].filter(n=>membership.has(n)&&(params.get('region')!=='kanto'||n<=151)&&(params.get('region')!=='johto'||n>=152)));saveSelection(params);
      const progress=result.scoped_progress||result.current_progress||result.progress;
      $('#dex-scope-label').textContent=result.scope.kind==='current'?'Current collection · '+(params.get('region')==='kanto'?'#001–151':params.get('region')==='johto'?'#152–251':'#001–251'):result.scope.name+' · Saved '+result.scope.units+' goal';
      $('#dex-progress').textContent=`${progress.satisfied} / ${progress.total} Pokémon collected${result.restricted?' within card scope':''}`;
      $('#dex-overall').hidden=!result.restricted;
      const overall=result.current_progress||progress;$('#dex-overall').textContent=`Overall ownership: ${overall.satisfied} / ${overall.total}${savedScope?' · current cards within the saved target membership':''}`;
      $('#dex-goal-summary').innerHTML=goalSummary(result);
      saveEditor(params,Boolean($('#dex-scope-editor')?.open));
      window.rememberCollectionDestination?.();
      const goalLabel=$('#dex-goal-value');goalLabel.hidden=!params.get('goal');goalLabel.textContent=params.get('goal')?'Saved goal: '+result.scope.name+' · '+result.scope.units:'';
      const options=scopeOptions(result),chips=[];
      for(const key of scopeKeys){const selected=multiKeys.includes(key)?scopeValues(params.get(key)||''):params.get(key)?[params.get(key)]:[];
        for(const value of selected){const label=(options[key]||[]).map(v=>typeof v==='string'?{id:v,name:v}:v).find(v=>v.id===value)?.name||value;
          chips.push(`<li>${scopeLabels[key]}: ${esc(label)} <button type="button" class="scope-chip-remove secondary" data-remove-key="${key}" data-remove-value="${esc(value)}" aria-label="Remove ${esc(label)} and apply">×</button></li>`);}}
      const coverage=result.coverage||{},datedScope=['released','year','date_from','date_to'].some(key=>params.get(key));
      $('#dex-active-filters').innerHTML=`${chips.length?'<ul>'+chips.join('')+'</ul>':'<p>All cards · unrestricted</p>'}${datedScope?`<p class="scope-date-warning">Date evidence: ${coverage.dated_printings||0} / ${coverage.indexed_printings||0} indexed printings · ${coverage.unknown_dates||0} unknown.</p>`:''}<details class="scope-coverage"><summary>Catalog & date coverage</summary><p>${coverage.dated_printings||0} / ${coverage.indexed_printings||0} indexed printings have supported dates; ${coverage.unknown_dates||0} unknown. ${coverage.eligible_species||0} target species have eligible indexed printings. Target checklist stays ${progress.total}.</p><p>${esc(result.date_basis||'Dates unavailable')}</p></details>`;
      document.querySelectorAll('[data-remove-key]').forEach(button=>button.onclick=()=>{
        const key=button.dataset.removeKey,next=new URLSearchParams(params);
        if(multiKeys.includes(key)){const value=encodeScope(scopeValues(params.get(key)||'').filter(v=>v!==button.dataset.removeValue));if(value)next.set(key,value);else next.delete(key);}else next.delete(key);
        applyScope(next);
      });
      countAndActions(result,result.species,params);BoundedReads.artwork(reader,$('#species-grid'),'species');resolveLabels();
    };
    const update=async changed=>{
      if(!active())return;
      const request=++querySequence;
      if(changed==='goal'||changed==='region'){selection.clear();selectionScope=selectionKey(params);saveSelection(params);}
      if(changed){const key=changed==='search'?'q':changed;const control=$('#dex-'+changed),value=changed==='gaps'?String(control.checked):control.value;if(value)params.set(key,value);else params.delete(key);}
      if(changed==='goal'||changed==='region'){selection.clear();selectionScope=selectionKey(params);saveSelection(params);}
      params.delete('focus');params.delete('scroll');params.delete('page');
      history.replaceState(null,'','/pokedex/'+(params.size?'?'+params:''));
      bindRoute();
      $('#species-count').textContent='Updating Pokémon…';
      try{const next=await reader.get('/api/v2/pokedex-species/?'+paramsForApi(params,expected),'species-primary');if(!active()||request!==querySequence)return;authority(next,expected);result=next;paint();}catch(error){if(active()&&request===querySequence)failure(error);}
    };
    for(const key of ['region','owned','goal'])$('#dex-'+key).onchange=()=>update(key);
    let timer;for(const key of ['search'])$('#dex-'+key).oninput=()=>{querySequence++;clearTimeout(timer);timer=setTimeout(()=>update(key),15);};
    const bindScope=()=>{
      for(const field of ['set','era','type','rarity','finish','year']){
        const host=$('#dex-'+field+' .scope-options');
        BoundedReads.paged(host,{reader,url:'/api/v2/species-filter-options/?field='+field,field:'options',active,render:row=>'<label class="check"><input type="checkbox" data-scope-key="'+field+'" value="'+esc(row.value)+'">'+esc(row.label)+'</label>',bind:()=>{
          const seen=new Set();host.querySelectorAll('input').forEach(input=>{if(seen.has(input.value))input.closest('label').remove();else seen.add(input.value);});
          $('#scope-search-'+field).dispatchEvent(new Event('input'));
        }}).textContent='Browse more choices';
      }
      $('#dex-scope-editor').ontoggle=()=>saveEditor(params,$('#dex-scope-editor').open);
      document.querySelectorAll('[data-scope-search]').forEach(input=>input.oninput=()=>{const field=$('#dex-'+input.dataset.scopeSearch);field.querySelectorAll('.scope-options label').forEach(label=>label.hidden=!label.textContent.toLowerCase().includes(input.value.toLowerCase()));});
      document.querySelectorAll('[data-scope-key],#dex-date_from,#dex-date_to,#dex-card').forEach(input=>input.onchange=()=>{$('#scope-pending').textContent='Selection changed · Apply to evaluate.';});
      $('#dex-scope-apply').onclick=()=>{
        const next=new URLSearchParams(params);for(const key of scopeKeys)next.delete(key);
        for(const key of multiKeys){const items=[...document.querySelectorAll('[data-scope-key="'+key+'"]:checked')].map(e=>e.value);const value=encodeScope(items);if(value)next.set(key,value);}
        for(const key of ['date_from','date_to','card'])if($('#dex-'+key).value)next.set(key,$('#dex-'+key).value);
        applyScope(next);
      };
      $('#dex-scope-clear').onclick=()=>{const next=new URLSearchParams(params);for(const key of scopeKeys)next.delete(key);applyScope(next);};
    };
    const applyScope=async next=>{
      try{canonicalScope(next);const destination='/pokedex/?'+next;if(!safeSpeciesReturn(destination,true))throw Error('Choose a smaller combined scope for navigation.');
        for(const key of scopeKeys){if(next.get(key))params.set(key,next.get(key));else params.delete(key);}
        await update();if(!active())return;
        const old=$('#dex-scope-editor');if(!old)return;old.outerHTML=scopeEditor(result,params);$('#dex-scope-editor').open=true;saveEditor(params,true);bindScope();$('#dex-scope-apply').focus();
      }catch(error){$('#scope-error').textContent=error.message;}
    };
    bindScope();
    if(params.get('goal'))$('#dex-goal').add(new Option(result.scope.name,params.get('goal'),true,true));
    const goalsHost=document.createElement('div');$('#dex-goal').after(goalsHost);
    BoundedReads.paged(goalsHost,{reader,url:'/api/v2/goal-options/',field:'goals',active,render:g=>'<button type="button" data-goal-choice="'+esc(g.id)+'">'+esc(g.name)+'</button>',bind:host=>host.querySelectorAll('[data-goal-choice]').forEach(b=>b.onclick=()=>{const id=b.dataset.goalChoice;if(![...$('#dex-goal').options].some(o=>o.value===id))$('#dex-goal').add(new Option(b.textContent,id));$('#dex-goal').value=id;update('goal');})}).textContent='Browse saved goals';
    $('#dex-select-mode').onclick=()=>{selecting=!selecting;if(selecting)params.set('selecting','1');else params.delete('selecting');history.replaceState(null,'','/pokedex/'+(params.size?'?'+params:''));bindRoute();paint();$('#dex-select-mode').focus();};
    $('#dex-lookup-selection').onclick=()=>{if(!selection.size)return;const query=new URLSearchParams({targets:[...selection].sort((a,b)=>a-b).join(','),scope:'all'});if(params.get('goal'))query.set('goal',params.get('goal'));location.assign('/lookup/?'+query);};
    $('#dex-goal-create').onclick=()=>{dexSelection=new Set(selection);window.openBoundedSpeciesGoal();};
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
    const identityQuery=new URLSearchParams();const inherited=new URL(back,location.origin).searchParams;for(const key of [...scopeKeys,'region'])if(inherited.get(key))identityQuery.set(key,inherited.get(key));identityQuery.set('q','#'+String(dex).padStart(3,'0'));identityQuery.set('generation',expected);if(params.get('goal'))identityQuery.set('goal',params.get('goal'));
    const [identity,groups]=await Promise.all([reader.get('/api/v2/pokedex-species/?'+identityQuery),reader.get('/api/v2/species/'+dex+'/owned-groups/?'+new URLSearchParams([...identityQuery].filter(([k])=>scopeKeys.includes(k))))]);
    if(!active())return;authority(identity,expected);authority(groups,expected);
    let row=identity.species.find(row=>row.dex===dex);
    if(!row&&params.get('goal')){const currentQuery=new URLSearchParams(identityQuery);currentQuery.delete('goal');const current=await reader.get('/api/v2/pokedex-species/?'+currentQuery);if(!active())return;authority(current,expected);row=current.species.find(row=>row.dex===dex);}
    if(!row)throw new Error('Canonical Pokémon identity is unavailable. Reload the current Pokédex.');
    const owned=groups;if(!owned)throw new Error('Current card ownership is unavailable. Reload this Pokémon.');
    const all=[...owned.groups];

    const seen=new Set(),cards=all.filter(group=>{if(seen.has(group.id))return false;seen.add(group.id);return true;});
    const currentReturn=()=>{const url=new URL(location.href);url.searchParams.set('generation',String(expected));if(identity.scope.goal_id&&identity.scope.version){url.searchParams.set('goal',identity.scope.goal_id);url.searchParams.set('version',identity.scope.version);}url.searchParams.set('scroll',String(Math.min(10000000,Math.max(0,Math.round(scrollY)))));return safeSpeciesReturn(url.pathname+url.search);};
    const returnTo=currentReturn();
    const cardState=group=>groups.scope_groups?.[group.id]||'unresolved';
    const cardSections=identity.restricted?['collected','outside','unresolved']:['all'];
    const cardMarkup=cardSections.map(state=>{const matches=state==='all'?cards:cards.filter(g=>cardState(g)===state);return matches.length?`<section><h3>${({collected:'Owned cards qualifying for this scope',outside:'Owned cards outside this scope',unresolved:'Owned cards with unresolved qualification',all:'Owned cards'})[state]}</h3><div class="owned-card-grid" data-scope-cards="${state}">${matches.map(group=>window.renderCardGroupTile(group,returnTo)).join('')}</div></section>`:'';}).join('');
    const activeOptions=scopeOptions(identity),activeChips=scopeKeys.flatMap(key=>(multiKeys.includes(key)?scopeValues(inherited.get(key)||''):inherited.get(key)?[inherited.get(key)]:[]).map(value=>{
      const label=(activeOptions[key]||[]).map(v=>typeof v==='string'?{id:v,name:v}:v).find(v=>v.id===value)?.name||value;
      return `<li>${scopeLabels[key]}: ${esc(label)}</li>`;
    }));
    const scopedProgress=identity.scoped_progress||identity.current_progress;
    const scopeDescription=`<div class="active-filters" aria-label="Active card scope">${activeChips.length?'<ul>'+activeChips.join('')+'</ul>':'<p>All owned card evidence</p>'}${scopedProgress?`<p>${scopedProgress.satisfied} / ${scopedProgress.total} target Pokémon collected within this card scope</p>`:''}</div>`;
    const scopeNote=identity.scope.kind==='current'||!identity.scope.supported?'':row.goal_present!==null?`<p class="muted">${row.goal_present?'Counted':'Not counted'} in ${esc(identity.scope.name)}. Your Cards is current possession.</p>`:`<p class="muted">Outside the saved ${esc(identity.scope.name)} goal. Your Cards is current possession.</p>`;
    $('#content').innerHTML=`<a class="browse-return" href="${esc(back)}">Back to Pokédex</a><section class="species-detail-heading" data-dex-species="${dex}"><div>${speciesImage(row.species_artwork)}</div><div><h1><span class="species-title-number">#${String(dex).padStart(3,'0')}</span> ${esc(row.name)}</h1><p class="species-ownership">${statusFor(row,identity.restricted)}</p>${row.current_present&&!row.scoped_present?'<p>Owned in overall collection</p>':''}</div></section>${scopeDescription}<section aria-labelledby="your-cards-heading"><h2 id="your-cards-heading">Your Cards</h2><div id="species-owned-cards">${cardMarkup}</div>${!cards.length?`<p class="empty">${row.current_present?'This Pokémon is collected; exact card details are not recorded.':'You haven’t collected a card for this Pokémon yet.'}</p>`:''}${row.details_needed||(groups.unresolved||[]).length?'<details class="card-unresolved"><summary>Card details needed</summary><p>Species evidence is retained; some exact card identities remain unknown. No card or quantity has been inferred.</p><a href="/settings/">Review collection sources and records</a></details>':''}<div class="actions species-entry-actions"><a id="species-explore" class="button-link" href="/card-library/?species=${dex}">Explore cards<span class="sr-only"> for ${esc(row.name)}</span></a><a id="species-shopping" class="button-link secondary" href="/shopping/">Search mixed lots for this Pokémon<span class="sr-only"> · ${esc(row.name)}</span></a></div><p class="muted">Explore indexed ${esc(row.name)} cards; catalog choices do not establish ownership, quantity, edition or finish.</p></section>${scopeNote}${goalSummary(identity)}<details class="species-details"><summary>Collection details</summary><p>Species quantity is unknown. Card quantities, when recorded, belong to their individual card pages.</p><a href="/settings/">Source history and reconciliation</a></details>`;
    BoundedReads.artwork(reader,$('#species-owned-cards'));BoundedReads.artwork(reader,$('#content'),'species');
    if(owned.pages>1){const host=document.createElement('details');host.innerHTML='<summary>More owned cards ('+owned.total+' total)</summary>';$('#species-owned-cards').append(host);const q=new URLSearchParams([...identityQuery].filter(([k])=>scopeKeys.includes(k)));q.set('page','2');BoundedReads.paged(host,{reader,url:'/api/v2/species/'+dex+'/owned-groups/?'+q,field:'groups',active,render:(g,page)=>'<section><p>'+esc({collected:'Qualifies for this scope',outside:'Outside this scope',unresolved:'Unresolved qualification'}[page.scope_groups[g.id]])+'</p>'+window.renderCardGroupTile(g,currentReturn())+'</section>'});}
    if(row.evidence_url){const a=document.createElement('a');a.href=row.evidence_url;a.textContent='Open complete species evidence';$('.species-details').append(a);}
    document.querySelectorAll('#species-owned-cards .owned-card-tile').forEach(link=>link.addEventListener('click',()=>{const url=new URL(link.href);try{sessionStorage.removeItem('dex-species-action:'+account()+':'+location.pathname);sessionStorage.setItem('dex-species-card-focus:'+account()+':'+location.pathname,url.pathname);}catch{/* Optional focus memory. */}url.searchParams.set('return',currentReturn());link.href=url.pathname+url.search;}));
    const rememberAction=id=>{try{sessionStorage.setItem('dex-species-action:'+account()+':'+location.pathname,id);}catch{/* Optional focus memory. */}};
    const explore=$('#species-explore'),shopping=$('#species-shopping');
    const exploreDestination=()=>{
      const next=new URLSearchParams({species:String(dex),generation:String(expected),return:currentReturn()});
      const sets=scopeValues(inherited.get('set')||'');if(sets.length===1)next.set('set',sets[0]);
      if(identity.scope.goal_id&&identity.scope.version){next.set('goal',identity.scope.goal_id);next.set('version',identity.scope.version);}
      return '/card-library/?'+next;
    };
    explore.href=exploreDestination();explore.addEventListener('click',()=>{rememberAction('species-explore');explore.href=exploreDestination();});
    shopping.href=window.collectionShoppingDestination?.({species:dex},identity.scope,currentReturn())||'/shopping/';
    shopping.addEventListener('click',()=>{rememberAction('species-shopping');shopping.href=window.collectionShoppingDestination?.({species:dex},identity.scope,currentReturn())||'/shopping/';});
    window.rememberCollectionDestination?.();
    const restore=Number(params.get('scroll'))||0;requestAnimationFrame(()=>{if(!active())return;
      try{const focus=sessionStorage.getItem('dex-species-card-focus:'+account()+':'+location.pathname);if(focus)Array.from(document.querySelectorAll('#species-owned-cards .owned-card-tile')).find(link=>new URL(link.href).pathname===focus)?.focus({preventScroll:true});}catch{/* Optional focus memory. */}
      try{const id=sessionStorage.getItem('dex-species-action:'+account()+':'+location.pathname);if(id)document.getElementById(id)?.focus({preventScroll:true});}catch{/* Optional focus memory. */}
      if(restore)scrollTo(0,restore);
    });
  }
  window.renderSpeciesScreen=async route=>{
    const match=route.match(/^\/pokedex\/([0-9]+)\/$/);if(route!=='/pokedex/'&&!match)return false;
    const ticket=++sequence,actor=account(),expected=data?.effective_collection?.generation;
    let routeBinding=location.pathname+location.search;
    const bindRoute=()=>{routeBinding=location.pathname+location.search;};
    const active=()=>!window.navigationAuthorityDiscarded&&ticket===sequence&&actor===account()&&expected===data?.effective_collection?.generation&&location.pathname+location.search===routeBinding;
    reader?.stop();reader=new BoundedReads.Reader({active,seed:data.read_state});
    try{if(!actor||!Number.isSafeInteger(expected))throw new Error('Current collection authority is unavailable. Reload before browsing Pokémon.');if(match)await renderSpecies(Number(match[1]),expected,active);else await renderList(expected,active,bindRoute);}catch(error){if(active())failure(error);}
    return true;
  };
})();
