'use strict';
// Reviewed collection source and goal tools; species-screens.js owns Pokémon browsing.
let dexSelection=new Set();
function dexOptions(values){return '<option value="">All / no restriction</option>'+[...new Set(values)].sort().map(v=>`<option value="${esc(v)}">${esc(v)}</option>`).join('');}
let sourceToolSequence=0,sourceCorrectionSequence=0;
function sourceToolActive(context){
 return context.ticket===sourceToolSequence&&context.account===data?.effective_collection?.user_id&&context.generation===data?.effective_collection?.generation&&context.route===location.pathname+location.search&&context.source.id===data.current_collection_source?.id&&context.source.source_sha256===data.current_collection_source?.source_sha256&&context.source.revision===data.current_collection_source?.revision&&$('#species-source-tools')===context.section;
}
async function dexCorrection(s,context){
 if(!sourceToolActive(context))return;
 const request=++sourceCorrectionSequence;
 const active=()=>sourceToolActive(context)&&request===sourceCorrectionSequence&&Number($('#source-correction-species').value)===s.dex_number&&context.section.open;
 const button=$('#correct-source-species');button.disabled=true;
 try{
  const src=await api('/api/collection-sources/'+encodeURIComponent(context.source.id)+'/');
  if(!active()||$('#editor').open||$('#review').open)return;
  if(src.id!==context.source.id||src.user_id!==context.account||src.source_sha256!==context.source.source_sha256||src.revision!==context.source.revision)throw new Error('Collection source changed. Reload before correcting its declaration.');
  const scoped=data.effective_collection.scoped_sources?.[s.dex_number<=151?'kanto':'johto'];
  if(scoped&&scoped.source.id!==context.source.id)throw new Error('This region uses a separate source. Review source selection in Settings before correcting it.');
  const declarations=data.effective_collection.declaration_rows.filter(row=>row.pokemon_dex===s.dex_number);
  const first=declarations[0];
  const header=src.text.replace(/^\ufeff/,'').split(/\r?\n/)[0];
  const fields=[];let cell='',quoted=false;
  for(let i=0;i<header.length;i++){const c=header[i];if(c==='"'){if(quoted&&header[i+1]==='"'){cell+='"';i++;}else quoted=!quoted;}else if(c===','&&!quoted){fields.push(cell);cell='';}else cell+=c;}fields.push(cell);
  const sets=fields.slice(3).filter(key=>key!=='Ownership notes');
  if(!sets.length||quoted)throw new Error('Source columns are unavailable. Review this source before correcting it.');
  $('#editor-title').textContent='Correct source declaration · '+s.name;
  $('#editor-body').innerHTML=`<form id="dex-correction"><p>Review the selected source’s declaration for #${String(s.dex_number).padStart(3,'0')} ${esc(s.name)}. Ordinary current ownership is edited on card pages.</p><label class="check"><input id="correct-owned" type="checkbox" ${declarations.length?'checked':''}>This source declares this Pokémon collected</label><label for="correct-set">Supplied set</label><select id="correct-set">${sets.map(key=>`<option>${esc(key)}</option>`).join('')}</select><label for="correct-card">Card declaration</label><input id="correct-card" value="${esc(first?.source_cell||'✓')}" required><p>Keep the complete supplied card names, numbers and rarity when known. A check mark alone leaves exact card details unknown. Unchecking withdraws this species’ marks from the reviewed successor source.</p><label for="correct-notes">Ownership notes</label><textarea id="correct-notes">${esc(first?.ownership_notes||'')}</textarea><p id="source-correction-error" class="error" role="alert" hidden></p><button>Preview source correction</button></form>`;
  if(first)$('#correct-set').value=first.source_set;
  const operationId=crypto.randomUUID();
  $('#dex-correction').onsubmit=event=>{event.preventDefault();if(!active()){const error=$('#source-correction-error');error.hidden=false;error.textContent='Collection or source changed. Close and reload before previewing.';return;}preview('collection_correct',{source_id:context.source.id,pokemon_dex:s.dex_number,owned:$('#correct-owned').checked,source_set:$('#correct-set').value,card_text:$('#correct-card').value,notes:$('#correct-notes').value},operationId);};
  openDialog('#editor');
 }catch(error){if(active())status(error.message,true);}finally{if(sourceToolActive(context))button.disabled=false;}
}
window.renderSpeciesSourceTools=()=>{
 const section=document.createElement('details');section.id='species-source-tools';section.className='panel';
 const source=data.current_collection_source;
 section.innerHTML='<summary>Correct a collection source declaration</summary><p>This reviewed tool creates a successor source. Ordinary card ownership changes belong on the card page; retained sources and saved goals stay unchanged until review.</p>'+(source?'<label for="source-correction-species">Pokémon in the selected source</label><select id="source-correction-species" disabled><option>Open to load Pokémon</option></select><button id="correct-source-species" class="secondary" disabled>Correct source declaration</button><p id="source-tools-status" role="status"></p>':'<p>Select or import a complete collection source before correcting a declaration.</p><button id="source-tools-import" class="secondary">Import collection source</button>');
 $('#content').append(section);
 const context={ticket:++sourceToolSequence,account:data.effective_collection.user_id,generation:data.effective_collection.generation,route:location.pathname+location.search,source,section};
 if(!source){$('#source-tools-import').onclick=dexImport;return;}
 let loading=false,loaded=false;
 section.ontoggle=async()=>{
  if(!section.open||loading||loaded||!sourceToolActive(context))return;
  loading=true;$('#source-tools-status').textContent='Loading Pokémon…';
  try{const result=await api('/api/pokedex-species/?generation='+context.generation);if(!sourceToolActive(context)||!section.open)return;if(result.account_id!==context.account||result.generation!==context.generation||result.public!==false)throw new Error('Collection changed. Reload the source tools.');
   const select=$('#source-correction-species');select.innerHTML=result.species.map(row=>`<option value="${row.dex}">#${String(row.dex).padStart(3,'0')} ${esc(row.name)}</option>`).join('');select.disabled=false;
   $('#correct-source-species').disabled=!result.species.length;
   $('#correct-source-species').onclick=()=>{const row=result.species.find(item=>item.dex===Number(select.value));if(row)dexCorrection({dex_number:row.dex,name:row.name},context);};
   $('#source-tools-status').textContent='';loaded=true;
  }catch(error){if(sourceToolActive(context))$('#source-tools-status').textContent=error.message;}finally{loading=false;}
 };
};
function dexImport(){
 $('#editor-title').textContent='Import collection';$('#editor-body').innerHTML='<form id="dex-source-import"><label for="dex-source-file">Complete collection CSV</label><input id="dex-source-file" type="file" accept=".csv"><label for="dex-source-text">Collection CSV contents</label><textarea id="dex-source-text" rows="8" required></textarea><p>Review changed species before confirmation. Earlier sources, frozen goals, physical copies and photos are retained.</p><button>Preview collection import</button></form>';
 let importText='';$('#dex-source-text').oninput=()=>{importText=$('#dex-source-text').value;};
 $('#dex-source-file').onchange=async()=>{const f=$('#dex-source-file').files[0];if(f&&f.size<=100000){importText=new TextDecoder('utf-8',{ignoreBOM:true}).decode(await f.arrayBuffer());$('#dex-source-text').value=importText;}else status('Collection source must be at most 100 KB.',true);};$('#dex-source-import').onsubmit=async e=>{e.preventDefault();const text=importText||$('#dex-source-text').value;const bytes=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(text));const sha256=[...new Uint8Array(bytes)].map(b=>b.toString(16).padStart(2,'0')).join('');preview('owner_declaration',{text,sha256},crypto.randomUUID());};openDialog('#editor');
}
function dexGoal(previous=null){
 $('#editor-title').textContent=previous?'Review goal successor':'Create collecting goal';$('#editor-body').innerHTML=`<form id="dex-new-goal"><label for="new-goal-name">Goal name</label><input id="new-goal-name" required maxlength="120" value="${esc(previous?.name||'')}"><label for="new-goal-preset">Targets</label><select id="new-goal-preset"><option value="151">Original 151</option><option value="251">Original 251</option><option value="selected">Selected Pokémon</option><option value="criteria">Supported card criteria</option></select><label for="new-goal-source">Collection source</label><select id="new-goal-source">${(data.available_collection_sources||[]).map(r=>`<option value="${esc(r.id)}" ${r.id===data.current_collection_source?.id?'selected':''}>${esc(r.source_sha256.slice(0,12))} · ${r.id===data.current_collection_source?.id?'Current collection':'Earlier source'}</option>`).join('')}</select><label for="new-goal-targets">Selected Pokémon numbers</label><input id="new-goal-targets" value="${previous?previous.definition.items.map(i=>i.pokemon_dex).join(','):[...dexSelection].sort((a,b)=>a-b).join(',')}"><div id="criteria-scope" hidden><label for="criteria-set">Indexed set</label><select id="criteria-set">${setOptions(true)}</select><label for="criteria-type">Card type</label><select id="criteria-type"><option value="all">All types</option>${data.goal_options.card_types.map(t=>`<option>${esc(t)}</option>`).join('')}</select><label for="criteria-rarity">Rarity</label><select id="criteria-rarity">${dexOptions(data.goal_options.rarities)}</select><label for="criteria-policy">Physical printing completion</label><select id="criteria-policy"><option value="catalog">Owned catalog entry</option><option value="exact">Resolved exact variant</option></select></div><p>Collection goals count canonical species; card-criteria goals use physical printing ownership. Confirming retains this version and its selected source. Later changes require a reviewed successor.</p><button>Preview collecting goal</button></form>`;
 if(previous){$('#new-goal-preset').value='selected';$('#new-goal-preset').disabled=true;}else if(dexSelection.size)$('#new-goal-preset').value='selected';
 const change=()=>{$('#criteria-scope').hidden=$('#new-goal-preset').value!=='criteria';$('#new-goal-targets').disabled=$('#new-goal-preset').value!=='selected';$('#new-goal-source').disabled=$('#new-goal-preset').value==='criteria';};$('#new-goal-preset').onchange=change;change();
 $('#dex-new-goal').onsubmit=e=>{e.preventDefault();const preset=$('#new-goal-preset').value;let req;if(preset==='criteria'){const game=data.goal_options.games.find(g=>g.game_key==='pokemon');req={name:$('#new-goal-name').value,goal_kind:'filtered',policy:$('#criteria-policy').value,filters:{game_id:game?.id,set_ids:$('#criteria-set').value?[$('#criteria-set').value]:[],card_type:$('#criteria-type').value,rarities:$('#criteria-rarity').value?[$('#criteria-rarity').value]:[],pokemon_dex_min:1,pokemon_dex_max:251,completion:'printings'}};}else{const nums=preset==='selected'?$('#new-goal-targets').value.split(',').map(v=>Number(v.trim())):Array.from({length:Number(preset)},(_,i)=>i+1);req={name:$('#new-goal-name').value,goal_kind:previous?.kind==='original151_collection'?'original151_collection':'collection_species',collection_source_id:$('#new-goal-source').value,...(previous?.kind==='original151_collection'?{}:{targets:nums})};}if(previous)Object.assign(req,{id:previous.id,revision:previous.revision});preview(previous?'goal_edit':'goal',req,crypto.randomUUID());};openDialog('#editor');
}

function dexJsonImport(){
 $('#editor-title').textContent='Import collection and goals';$('#editor-body').innerHTML=`<form id="dex-json-form"><label for="dex-json-file">Complete JSON export</label><input id="dex-json-file" type="file" accept=".json"><label for="dex-json-text">JSON contents</label><textarea id="dex-json-text" required rows="8"></textarea><label for="dex-json-policy">Duplicate handling</label><select id="dex-json-policy">${policyOptions}</select><p>Source bytes, frozen goal membership and every row are validated before confirmation. Earlier versions and saved research are retained.</p><button>Preview JSON import</button></form>`;
 $('#dex-json-file').onchange=async()=>{const f=$('#dex-json-file').files[0];if(f&&f.size<=1500000)$('#dex-json-text').value=await f.text();else status('Export must be at most 1.5 MB.',true);};$('#dex-json-form').onsubmit=e=>{e.preventDefault();preview('import',{text:$('#dex-json-text').value,format:'json',duplicate_policy:$('#dex-json-policy').value},crypto.randomUUID());};openDialog('#editor');
}
