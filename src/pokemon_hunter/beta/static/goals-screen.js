'use strict';
/* Goal browsing reads frozen, authorized records; preview remains mutation authority. */
(() => {
 let reader,epoch=0;
 const fresh=()=>{reader?.stop();const n=++epoch,authority=data;reader=new BoundedReads.Reader({seed:data.read_state,active:()=>n===epoch&&data===authority&&!window.navigationAuthorityDiscarded});return reader;};
 addEventListener('pagehide',()=>{epoch++;reader?.stop();});
 function choices(select,url,field='options',selected=null){
  const host=document.createElement('div'),known=new Map();select.after(host);
  if(selected){select.add(new Option(selected.label||'Retained selection — loading label',selected.id,true,true));}
  return BoundedReads.paged(host,{reader,url,field,render:r=>{known.set(String(r.id??r.value),r);return `<button type="button" data-choice="${esc(r.id??r.value)}" ${r.available===false?'disabled':''}>${esc(r.name??r.label??r.value)}</button>`;},bind:(rows,result)=>rows.querySelectorAll('[data-choice]').forEach(button=>button.onclick=()=>{
   const value=button.dataset.choice,row=known.get(value);
   let option=[...select.options].find(o=>o.value===value);if(!option){option=new Option(button.textContent,value);select.add(option);}option.textContent=button.textContent;if(select.multiple)option.selected=true;else select.value=value;
   if(row?.game_key)select.dataset.gameKey=row.game_key;
   select.dispatchEvent(new Event('change',{bubbles:true}));
  })});
 }
 function checklist(goal){
  $('#editor-title').textContent=goal.name;
  $('#editor-body').innerHTML='<label for="goal-target-query">Card or species</label><input id="goal-target-query" type="search"><label for="goal-target-status">Progress</label><select id="goal-target-status"><option value="">All targets</option><option value="missing">Missing</option><option value="owned">Owned</option><option value="unavailable">Unavailable coverage</option></select><div id="goal-target-list"></div>';
  const update=()=>{const host=$('#goal-target-list');host.replaceChildren();const url=new URL(goal.items_url,location.origin);url.searchParams.set('q',$('#goal-target-query').value);url.searchParams.set('status',$('#goal-target-status').value);BoundedReads.paged(host,{reader,url:url.pathname+url.search,field:'items',render:r=>`<article><strong>${esc(r.label)}</strong><p>${esc(r.status)} · ${r.printing_ids.length} retained printings</p></article>`}).click();};
  $('#goal-target-query').onchange=update;$('#goal-target-status').onchange=update;openDialog('#editor');update();
 }
 function preserve(goal){
  $('#editor-title').textContent='Edit retained goal';
  $('#editor-body').innerHTML=`<p>This goal has a frozen checklist without saved editable filters. This checklist keeps its original membership. Rename it here, or create a separate replacement while retaining this version.</p><form id="preserve-goal"><label for="retained-goal-name">Goal name</label><input id="retained-goal-name" required maxlength="120" value="${esc(goal.name)}"><button>Preview name change</button></form><button type="button" id="replace-goal">Create separate replacement</button>`;
  const id=crypto.randomUUID();$('#preserve-goal').onsubmit=e=>{e.preventDefault();preview('goal_edit',{id:goal.id,revision:goal.revision,goal_kind:goal.kind,name:$('#retained-goal-name').value,preserve_membership:true},id);};
  $('#replace-goal').onclick=()=>{$('#editor').close();$('#goal-name').value=goal.name+' — replacement';$('#goal-name').focus();};openDialog('#editor');
 }
 function goalCard(g){return `<article class="card" data-goal="${esc(g.id)}"><h2>${esc(g.name)}</h2><p>${g.satisfied} / ${g.total} ${g.header?.policy==='species'?'species':'targets'} complete · ${g.unavailable} unavailable</p><p>${esc(g.header?.coverage||'Frozen checklist')}</p><p>${g.coverage_update_available?'New catalog coverage available.':''} ${g.collection_update_available?'Another collection source is available.':''}</p><button type="button" data-checklist="${esc(g.id)}">View frozen checklist and progress</button>${['original151','original151_collection','collection_species'].includes(g.kind)?`<button type="button" data-successor="${esc(g.id)}" ${g.successor_ids?.length?'disabled':''}>Preview successor version</button>`:`<button type="button" data-edit-goal="${esc(g.id)}">Edit goal</button><button type="button" data-remove-goal="${esc(g.id)}">Remove goal</button>`}<p><a href="/shopping/?${esc(new URLSearchParams({goal:g.id,version:g.version,generation:String(data.effective_collection.generation),return:'/goals/'}))}">Find cards for this goal</a> · <a href="/missing/?goal=${encodeURIComponent(g.id)}">Find missing</a> · <a href="/packs/?goal=${encodeURIComponent(g.id)}">Packs to open</a></p><details><summary>Version details</summary><p>${esc(g.version)}</p></details></article>`;}
 function builder(previous=null){
  const f=previous?.header?.filters;
  $('#goal-builder').innerHTML=`<h2>${previous?'Edit collecting filters':'Create a tracking goal'}</h2><form id="bounded-goal-form"><label for="goal-name">Goal name</label><input id="goal-name" required maxlength="120" value="${esc(previous?.name||'')}"><label for="goal-kind">Goal type</label><select id="goal-kind"><option value="filtered">Filtered collecting goal</option><option value="set">Track a set</option><option value="custom">Custom checklist</option><option value="original151">Original 151 · reviewed coverage</option><option value="original151_collection">Original 151 · collection source</option><option value="vintage">Vintage 251 · legacy</option></select><div id="bounded-source"><label for="goal-source">Collection source</label><select id="goal-source"><option value="">Choose source</option></select></div><div id="bounded-game"><label for="goal-game">Game</label><select id="goal-game" required><option value="">Choose game</option></select></div><div id="bounded-set"><label for="goal-set">Catalog set</label><select id="goal-set"><option value="">Choose set</option></select></div><div id="bounded-filters"><label for="goal-sets">Sets that count</label><select id="goal-sets" multiple></select><p>Leave unselected for all supported sets. Choices remain selected across pages.</p><label for="goal-type">Card type</label><select id="goal-type"><option value="all">All types</option></select><label for="goal-rarities">Rarities</label><select id="goal-rarities" multiple></select><label for="goal-completion">Completion</label><select id="goal-completion"><option value="species">Unique Pokémon species</option><option value="printings">Each matching printing</option></select><label for="goal-min">First Pokémon number</label><input id="goal-min" type="number" min="1" max="251" value="${f?.pokemon_dex_min??1}"><label for="goal-max">Last Pokémon number</label><input id="goal-max" type="number" min="1" max="251" value="${f?.pokemon_dex_max??251}"></div><div id="bounded-policy"><label for="goal-policy">Printing policy</label><select id="goal-policy"><option value="catalog">Owned catalog entry</option><option value="exact">Resolved exact variant</option></select></div><div id="custom-checklist" hidden><label for="goal-search">Find checklist entries</label><input id="goal-search" type="search"><div id="goal-members"></div></div><p>Preview evaluates complete membership on the server. Tracking never adds physical copies.</p><button>Preview tracking goal</button>${previous?'<button type="button" id="cancel-goal-edit">Cancel edit</button>':''}</form>`;
  choices($('#goal-source'),'/api/v2/goal-sources/','sources');
  choices($('#goal-game'),'/api/v2/entry-options/?field=game','options',f?{id:f.game_id}:null);
  choices($('#goal-set'),'/api/v2/entry-options/?field=set');
  choices($('#goal-sets'),'/api/v2/entry-options/?field=set');
  choices($('#goal-type'),'/api/v2/species-filter-options/?field=type');
  choices($('#goal-rarities'),'/api/v2/species-filter-options/?field=rarity');
  if(f){for(const id of f.set_ids)$('#goal-sets').add(new Option('Retained set — loading label',id,true,true));for(const value of f.rarities)$('#goal-rarities').add(new Option(value,value,true,true));$('#goal-type').add(new Option(f.card_type,f.card_type,true,true));$('#goal-completion').value=f.completion;$('#goal-policy').value=previous.header.policy==='exact'?'exact':'catalog';}
  goalMemberSelection.clear();
  const change=()=>{const kind=$('#goal-kind').value;for(const [id,on] of [['bounded-source',kind==='original151_collection'],['bounded-game',kind==='filtered'],['bounded-set',['set','custom'].includes(kind)],['bounded-filters',kind==='filtered'],['bounded-policy',['set','custom','filtered'].includes(kind)],['custom-checklist',kind==='custom']]){const host=$('#'+id);host.hidden=!on;host.querySelectorAll('input,select,button').forEach(c=>c.disabled=!on);}if(kind==='custom'&&$('#goal-set').value)loadGoalMembers();};
  $('#goal-kind').onchange=change;$('#goal-set').onchange=()=>{if($('#goal-kind').value==='custom')loadGoalMembers();};$('#goal-search').onchange=loadGoalMembers;change();
  BoundedReads.labelControls(reader,[{element:$('#goal-game'),kind:'game'},{element:$('#goal-sets'),kind:'set'}]).catch(e=>status(e.message,true));
  if(previous){$('#goal-kind').disabled=true;$('#cancel-goal-edit').onclick=()=>builder();}
  const operation=crypto.randomUUID();$('#bounded-goal-form').onsubmit=e=>{e.preventDefault();const kind=$('#goal-kind').value,req={name:$('#goal-name').value,goal_kind:kind,policy:$('#goal-policy').value};
   if(kind==='filtered'){const pokemon=$('#goal-game').dataset.gameKey==='pokemon'||f?.pokemon_dex_min!=null;req.filters={game_id:$('#goal-game').value,set_ids:[...$('#goal-sets').selectedOptions].map(o=>o.value),card_type:$('#goal-type').value,rarities:[...$('#goal-rarities').selectedOptions].map(o=>o.value),completion:$('#goal-completion').value,pokemon_dex_min:pokemon?Number($('#goal-min').value):null,pokemon_dex_max:pokemon?Number($('#goal-max').value):null};}
   if(['set','custom'].includes(kind))req.set_id=$('#goal-set').value;if(kind==='custom')req.printing_ids=[...goalMemberSelection.keys()];if(kind==='original151_collection')req.collection_source_id=$('#goal-source').value;
   if(previous)Object.assign(req,{id:previous.id,revision:previous.revision});preview(previous?'goal_edit':'goal',req,operation);
  };
 }
 window.renderBoundedGoals=async()=>{
  fresh();$('#content').innerHTML='<h1>Goals</h1><p>Saved membership and progress stay separate from current collection ownership.</p><div id="saved-goals" class="grid"></div><section id="goal-builder" class="panel"></section>';builder();
  const saved=new Map();BoundedReads.paged($('#saved-goals'),{reader,url:'/api/v2/goals/?page_size=10',field:'goals',render:g=>{saved.set(g.id,g);return goalCard(g);},bind:rows=>{
   rows.querySelectorAll('[data-checklist]').forEach(b=>b.onclick=()=>checklist(saved.get(b.dataset.checklist)));
   rows.querySelectorAll('[data-remove-goal]').forEach(b=>b.onclick=()=>{const g=saved.get(b.dataset.removeGoal);preview('goal_remove',{id:g.id,revision:g.revision},crypto.randomUUID());});
   rows.querySelectorAll('[data-edit-goal]').forEach(b=>b.onclick=()=>{const g=saved.get(b.dataset.editGoal);if(g.header?.filters)builder(g);else preserve(g);});
   rows.querySelectorAll('[data-successor]').forEach(b=>b.onclick=async()=>{const g=saved.get(b.dataset.successor);if(g.kind==='original151'){preview('goal_edit',{id:g.id,revision:g.revision,name:g.name,goal_kind:g.kind},crypto.randomUUID());return;}try{const full=await reader.get('/api/v2/resources/goal/'+encodeURIComponent(g.id)+'/');window.openBoundedSpeciesGoal({...g,definition:full.record.definition});}catch(e){status(e.message,true);}});
  }}).click();
 };
 window.openBoundedSpeciesGoal=previous=>{
  fresh();data.available_collection_sources=[];data.sets=[];data.goal_options={games:[],card_types:[],rarities:[]};dexGoal(previous);
  choices($('#new-goal-source'),'/api/v2/goal-sources/','sources',previous?.definition.collection_source?{id:previous.definition.collection_source.id,label:'Retained source '+previous.definition.collection_source.source_sha256.slice(0,12)}:null);
  choices($('#criteria-set'),'/api/v2/entry-options/?field=set');choices($('#criteria-type'),'/api/v2/species-filter-options/?field=type');choices($('#criteria-rarity'),'/api/v2/species-filter-options/?field=rarity');
  reader.get('/api/v2/entry-options/?field=game&game_key=pokemon').then(r=>{data.goal_options.games=r.options;}).catch(e=>status(e.message,true));
 };
})();
