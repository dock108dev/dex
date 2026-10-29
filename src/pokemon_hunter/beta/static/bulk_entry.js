/* Manual-only, account/session-checked, revisioned drafts. No private browser storage. */
(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  if (!$('bulk-editor')) return;
  const root = document.body, binding = root.dataset.navigationBinding;
  const state = {catalog: null, rows: [], draft: null, op: null, page: 0, trayPage: 0, reviewPage: 0,
    selected: new Set(), checked: new Set(), anchors: [], changed: false, busy: false, newBatch: false,
    epoch: 0, batchIdentity: crypto.randomUUID(), edit: null, resolved: new Map(), defaults: {}, lot: {}, savedCount: 0, recoverNeeded: false, focusAfterWork: null};
  const html=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const anchorPositions=new Map();
  const unavailableGroups=new Set();
  let readClient, pageGroups=[],pageTotal=0,pageCount=0,loadSequence=0;
  const actionLabels = {add_copies:'Add copies', set_total:'Record total', mark_owned:'Mark owned'};
  const draftLabels = {editing:'In progress', ready:'Ready to review', previewed:'Reviewed', confirmed:'Saved', cancelled:'Cancelled', expired:'Expired'};
  const fields = ['condition','grading_company','grade','certificate','binder_id','location','notes',
    'purchase_amount','purchase_currency','purchase_date','purchase_basis'];
  const labels = {condition:'Condition', grading_company:'Grading company', grade:'Grade', certificate:'Certificate',
    binder_id:'Binder', location:'Location', notes:'Notes',
    purchase_amount:'Per-copy purchase amount', purchase_currency:'Purchase currency', purchase_date:'Purchase date',
    purchase_basis:'Purchase basis'};
  const node = (tag, text, attrs = {}) => {
    const e = document.createElement(tag); if (text !== null) e.textContent = text;
    Object.entries(attrs).forEach(([k,v]) => e.setAttribute(k,v)); return e;
  };
  function status(message, error=false) {
    const target=$('bulk-status'); if(!target)return;
    target.textContent=message;target.dataset.tone=error?'error':'info';
    target.setAttribute('role',error?'alert':'status');
    target.setAttribute('aria-live',error?'assertive':'polite');
    if(error)target.focus();
  }
  function availability() {
    const busy=state.busy, hasRows=state.rows.length>0;
    $('bulk-tray-panel').dataset.empty=String(!hasRows);
    const terminal=state.draft && ['confirmed','cancelled','expired'].includes(state.draft.state);
    $('bulk-review').disabled=busy||!hasRows||Boolean(terminal);
    $('bulk-save').disabled=busy||!hasRows||Boolean(terminal);
    $('bulk-undo').disabled=busy||state.op?.state!=='confirmed';
    $('bulk-confirm').disabled=busy||!state.op||state.op.state!=='preview'||state.changed||state.op.plan.errors.length>0||state.draft?.state!=='previewed';
    ['bulk-new','bulk-cancel','bulk-recover'].forEach(id=>$(id).disabled=busy);
    ['bulk-parse-csv','bulk-parse-paste'].forEach(id=>$(id).disabled=busy||!state.catalog);
    $('bulk-current-tools').hidden=!state.draft&&!hasRows&&!state.recoverNeeded;
    $('bulk-recover').hidden=!state.draft&&!state.recoverNeeded;
    $('bulk-cancel').hidden=Boolean(terminal)||(!state.draft&&!hasRows);
    $('bulk-batch-options').hidden=!state.draft&&!hasRows&&!state.op;
    $('bulk-saved-panel').hidden=!state.savedCount;
    $('bulk-selected-details').hidden=!hasRows;
    $('bulk-lot-details').hidden=!hasRows;
    $('bulk-checked-actions').hidden=!state.checked.size;
    ['bulk-unknown','bulk-different','bulk-apply-selected','bulk-exclude','bulk-include','bulk-clear-checked'].forEach(id=>$(id).disabled=busy||!state.checked.size);
    $('bulk-check-all').disabled=busy||!hasRows;
    $('bulk-review-help').textContent=!hasRows?'Choose cards to begin. Nothing is added until you review and confirm.':
      terminal?'This saved batch cannot be edited. Start a separate batch for different physical cards.':'Review every row before confirming. Saving a draft does not change your collection.';
    $('bulk-draft-state').textContent=state.changed?'Unsaved changes':state.draft?(draftLabels[state.draft.state]||state.draft.state):'';
    $('bulk-draft-record').hidden=!state.draft;
    if(state.draft)$('bulk-draft-record-body').replaceChildren(
      node('p','Draft '+state.draft.id),node('p','Revision '+state.draft.revision),
      node('p','Expires '+new Date(state.draft.expires_at).toLocaleString()));
    $('bulk-back-edit').disabled=busy;
    $('bulk-review-prev').disabled=busy||!state.reviewPage;
    $('bulk-review-next').disabled=busy||!state.op||state.reviewPage>=Math.ceil((state.op.plan.bulk?.rows.length||0)/50)-1;
    $('bulk-review-rows').querySelectorAll('button').forEach(button=>button.disabled=busy);
  }
  function lock(value) {
    state.busy = value;
    ['bulk-editor','bulk-tray-panel','bulk-drawer'].forEach(id=>$(id).inert=value||!state.catalog);
    ['bulk-review-panel','bulk-receipt'].forEach(id=>$(id).querySelectorAll('a').forEach(link=>link.inert=value));
    $('bulk-saved').inert=value;
    availability();
    if(!value&&state.focusAfterWork){$(state.focusAfterWork)?.focus();state.focusAfterWork=null;}
  }
  function erase() {
    readClient?.stop();state.epoch++; state.rows = []; state.selected.clear(); state.checked.clear();
    $('bulk-entry').replaceChildren(node('p','Your session changed. Sign in again to resume your account’s saved draft.'));
  }
  async function api(path, data) {
    const epoch = state.epoch;
    const options = {credentials:'same-origin', cache:'no-store', headers:{'Accept':'application/json'}};
    if (data !== undefined) Object.assign(options, {method:'POST', headers:{...options.headers,
      'Content-Type':'application/json', 'X-CSRFToken':$('bulk-csrf').querySelector('input').value}, body:JSON.stringify(data)});
    let response;
    try { response=await fetch(path, options); }
    catch { if(data!==undefined)state.recoverNeeded=true;throw Error('Connection interrupted. Use Check saved result before trying again.'); }
    if (response.redirected || response.status === 401 || response.status === 403) { erase(); throw Error('Sign in again.'); }
    let result;
    try { result = await response.json(); } catch { if(data!==undefined)state.recoverNeeded=true;throw Error('Response unavailable. Use Check saved result before trying again.'); }
    if (epoch !== state.epoch) throw Error('This response belongs to an older view.');
    if (result.binding && result.binding !== binding) { erase(); throw Error('Session changed.'); }
    if (!response.ok) throw Error(result.error || 'Unable to complete this action. Your entries remain.');
    return result;
  }
  async function work(fn) {
    if (state.busy) return;
    lock(true);
    try { await fn(); } catch(e) { status(e.message,true); } finally { if ($('bulk-confirm')) lock(false); }
  }
  function changed() {
    state.changed = true; state.op = null;
    $('bulk-review-panel').hidden = true; $('bulk-receipt').hidden = true;
    $('bulk-editor').hidden=false;$('bulk-tray-panel').hidden=false;
    $('bulk-confirm').disabled = true;
    status('Unsaved changes. Save the draft or review your batch.');availability();
  }
  function defaults() {
    const result = {action:$('bulk-action').value, game:$('bulk-game').value,
      language:$('bulk-language').value, set_id:$('bulk-set').value};
    if (result.action === 'add_copies') {
      result.quantity = $('bulk-quantity').value;
      fields.forEach(k => { if ($('bulk-default-'+k).value) result[k] = $('bulk-default-'+k).value; });
    }
    return result;
  }
  function currentLot() {
    return Object.fromEntries(['amount','currency','date'].map(k => ['lot_'+k,$('bulk-lot-'+k).value]).filter(([,v])=>v));
  }
  function input() { return {schema:'dex-onboarding-v1', rows:state.rows, defaults:defaults(), lot:currentLot()}; }
  function setOptions(select, values, emptyLabel) {
    select.replaceChildren();
    if (emptyLabel) select.append(node('option',emptyLabel,{value:''}));
    values.forEach(([id,label])=>select.append(node('option',label,{value:id})));
  }
  function optionsContain(control,value){return [...control.options].some(o=>o.value===value);}
  function attributeFields(container, prefix, values, inherit=false) {
    container.replaceChildren();
    fields.forEach(key => {
      const label = node('label',labels[key]); let control;
      if (key === 'condition' || key === 'binder_id' || key === 'purchase_basis') {
        control = node('select',null,{id:prefix+key});
        const options = key === 'condition' ? ['Mint','NM','LP','MP','HP','DMG'].map(v=>[v,v]) :
          key === 'binder_id' ? state.catalog.binders.map(b=>[b.id,b.name]) : [['per_copy','Per physical copy']];
        setOptions(control, options, inherit ? 'Inherit visible default' : 'Unknown');
        if (inherit) control.append(node('option','Unknown · clear default',{value:'unknown'}));
      } else {
        control = node(key === 'notes' ? 'textarea' : 'input',null,{id:prefix+key});
        if (key === 'purchase_date' && !inherit) control.type='date';
        if (key === 'purchase_amount') control.inputMode='decimal';
        control.maxLength = key === 'notes' ? 2000 : key === 'location' ? 1000 : 200;
        control.placeholder = inherit ? 'Inherit; type unknown to clear' : 'Unknown';
      }
      if(key==='binder_id'&&values[key]&&!optionsContain(control,values[key]))control.add(new Option('Selected binder',values[key]));
      control.value = values[key] === null && control.tagName==='SELECT' && inherit ? 'unknown' : values[key] || '';
      control.dataset.explicitClear=String(values[key]===null);
      control.addEventListener('input',()=>control.dataset.explicitClear='false');
      if(values[key]===null)control.placeholder='Unknown · explicitly cleared';
      label.append(control); container.append(label);
      if(key==='binder_id'&&readClient){const host=node('div',null);label.after(host);BoundedReads.paged(host,{reader:readClient,url:'/api/v2/binders/',field:'binders',active:()=>control.isConnected,render:b=>'<button type="button" data-entry-binder="'+html(b.id)+'">'+html(b.name)+'</button>',bind:rows=>rows.querySelectorAll('[data-entry-binder]').forEach(b=>b.onclick=()=>{if(!optionsContain(control,b.dataset.entryBinder))control.add(new Option(b.textContent,b.dataset.entryBinder));control.value=b.dataset.entryBinder;control.dispatchEvent(new Event('input',{bubbles:true}));control.dispatchEvent(new Event('change',{bubbles:true}));})});}
    });
  }
  function matches() {return pageGroups;}
  async function loadCatalog(){
    const ticket=++loadSequence;
    if(!$('bulk-set').value){pageGroups=[];pageTotal=pageCount=0;renderCatalog();return;}
    const query=new URLSearchParams({set:$('bulk-set').value,q:$('bulk-search').value,page:state.page+1,page_size:50});
    if($('bulk-language').value)query.set('language',$('bulk-language').value);
    $('bulk-page').textContent='Loading cards…';
    try{const result=await readClient.get('/api/v2/card-groups/?'+query,'bulk-list');if(ticket!==loadSequence)return;
      pageTotal=result.total;pageCount=result.pages;
      pageGroups=result.groups.filter(g=>!g.oversized).map(g=>({...g,existing:g,children:[]}));
      const kept=state.catalog.groups.filter(g=>state.selected.has(g.id)&&!pageGroups.some(p=>p.id===g.id));state.catalog.groups=[...kept,...pageGroups];renderCatalog();
      for(const row of result.groups.filter(g=>g.oversized)){const p=node('p',null);p.innerHTML=BoundedReads.overflow(row);$('bulk-catalog-rows').append(p);}
    }catch(error){if(ticket===loadSequence&&error.name!=='AbortError'){pageGroups=[];$('bulk-catalog-rows').replaceChildren(node('p',error.message,{role:'alert'}));$('bulk-page').textContent='Cards unavailable';['bulk-all','bulk-prev','bulk-next'].forEach(id=>$(id).disabled=true);status(error.message,true);}}
  }
  async function loadSets(){
    const game=$('bulk-game').selectedOptions[0]?.dataset.gameId;
    const result=await readClient.get('/api/v2/entry-options/?'+new URLSearchParams({field:'set',game:game||''}),'bulk-sets');
    state.catalog.sets=result.options.filter(s=>!s.oversized);setOptions($('bulk-set'),state.catalog.sets.map(s=>[s.id,s.name]));
    const selected=state.catalog.sets[0];setOptions($('bulk-language'),selected?.language?[[selected.language,selected.language]]:[['','Unspecified language']]);
    $('bulk-set-pages')?.remove();const host=node('div',null,{id:'bulk-set-pages'});$('bulk-set').after(host);
    const first='/api/v2/entry-options/?'+new URLSearchParams({field:'set',game:game||''});const next=result.options.some(s=>s.oversized)?first:BoundedReads.next(first,result);
    if(next)BoundedReads.paged(host,{reader:readClient,url:next,field:'options',render:s=>'<button type="button" data-entry-set="'+html(s.id)+'">'+html(s.name)+'</button>',bind:rows=>rows.querySelectorAll('[data-entry-set]').forEach(b=>b.onclick=()=>{if(![...$('bulk-set').options].some(o=>o.value===b.dataset.entrySet))$('bulk-set').add(new Option(b.textContent,b.dataset.entrySet));$('bulk-set').value=b.dataset.entrySet;setOptions($('bulk-language'),[['','All languages']]);state.page=0;loadCatalog();})});
    state.page=0;await loadCatalog();
  }
  function groupFor(row) {
    const groupId=row.group_id||state.resolved.get(row.row_id);
    return state.catalog.groups.find(g => groupId === g.id || g.children.some(p=>p.id===row.printing_id));
  }
  function addGroup(g) {
    if (state.selected.has(g.id)) return;
    if (state.rows.length >= 2000) throw Error('2,000 rows reached. Start a separate batch after this receipt.');
    state.rows.push({row_id:'card-'+g.id, group_id:g.id, game:$('bulk-game').value,
      set_id:g.set_id, language:g.language, number:g.collector_number, action:$('bulk-action').value});
    state.selected.add(g.id); changed();
  }
  function removeGroup(id) {
    const removed=state.rows.filter(r=>r.group_id===id);removed.forEach(r=>state.checked.delete(r.row_id));
    state.rows=state.rows.filter(r=>r.group_id!==id); state.selected.delete(id); changed();
  }
  function renderCatalog() {
    const filtered=matches(), pages=Math.max(1,pageCount); state.page=Math.min(state.page,pages-1);
    const list=$('bulk-catalog-rows'); list.replaceChildren();
    filtered.forEach(g=>{
      const card=node('div',null,{class:'bulk-card'}), label=node('label',null);
      const check=node('input',null,{type:'checkbox','aria-label':'Select '+g.name+' #'+g.collector_number});
      check.checked=state.selected.has(g.id);
      check.addEventListener('change',()=>{
        try { if(check.checked){addGroup(g); anchorPositions.set(g.id,{page:state.page,index:filtered.indexOf(g),query:selectionQuery()});state.anchors.push(g.id);state.anchors=state.anchors.slice(-2);}else removeGroup(g.id);
          renderTray(); renderCounts(); } catch(e){ check.checked=false; status(e.message); }
      });
      const text=node('span',g.collector_number+' · '+g.name);
      const recorded=g.existing.recorded_copy_count??0;
      const ownership=!g.existing.present&&g.current_copy_count===0&&recorded===0?'Not owned':
        (g.existing.present?'Owned':'Not currently owned')+' · Total '+
        (g.existing.established_total_quantity??'Unknown')+' · '+g.current_copy_count+' current / '+recorded+' recorded copies';
      text.append(node('small',ownership,{class:'bulk-note'}));
      label.append(check,text);card.append(label);
      const button=node('button','Variant / details',{type:'button','aria-label':'Variant and details for '+g.name+' #'+g.collector_number});
      button.onclick=()=>{try{addGroup(g);check.checked=state.selected.has(g.id);renderTray();openRow(state.rows.find(r=>r.group_id===g.id),button);}catch(e){status(e.message,true);}};
      card.append(button);list.append(card);
    });
    $('bulk-page').textContent=`Page ${state.page+1} of ${pages} · ${pageTotal} matching cards`;
    $('bulk-prev').disabled=state.page===0; $('bulk-next').disabled=state.page>=pages-1;
    $('bulk-all').textContent='Select this page ('+filtered.length+')';
    if(!filtered.length)list.append(node('p','No cards match this set and search. Try another number, name or set.',{class:'bulk-help'}));
    $('bulk-all').disabled=!filtered.length;$('bulk-all-matches').disabled=!pageTotal;$('bulk-all-matches').textContent='Select all '+pageTotal+' matching cards';
    renderCounts();
  }
  function renderCounts() {
    const visible = new Set(matches().map(g=>g.id));
    const hidden=state.rows.filter(r=>!visible.has(groupFor(r)?.id)).length;
    const sets=new Set(state.rows.map(r=>groupFor(r)?.set_name || r.set || r.set_id || 'Unresolved'));
    const rowIds=new Set(state.rows.map(r=>r.row_id));state.checked.forEach(id=>{if(!rowIds.has(id))state.checked.delete(id);});
    if(!state.checked.size&&$('bulk-checked-actions').contains(document.activeElement))$('bulk-check-all').focus();
    $('bulk-count').textContent=state.rows.length?`${state.rows.length} draft ${state.rows.length===1?'row':'rows'} across ${sets.size} ${sets.size===1?'set':'sets'}${hidden?' · '+hidden+' hidden from this page':''}`:'No cards selected';
    $('bulk-checked-count').textContent=`${state.checked.size} checked draft ${state.checked.size===1?'row':'rows'}`;
    availability();
  }
  function renderTray() {
    const pages=Math.max(1,Math.ceil(state.rows.length/50));state.trayPage=Math.min(state.trayPage,pages-1);
    const target=$('bulk-tray');target.replaceChildren();
    state.rows.slice(state.trayPage*50,state.trayPage*50+50).forEach(row=>{
      const line=node('div',null,{class:'bulk-draft-row'}),check=node('input',null,{type:'checkbox','aria-label':'Edit draft row '+row.row_id});
      check.checked=state.checked.has(row.row_id);check.onchange=()=>{check.checked?state.checked.add(row.row_id):state.checked.delete(row.row_id);renderCounts();};
      const g=groupFor(row), caption=g?`${g.set_name} · #${g.collector_number} ${g.name}`:`Retained card · #${row.number||'?'} · ${unavailableGroups.has(row.group_id)?'Metadata unavailable':'Loading saved identity…'}`;
      const text=node('span',caption+(row.included===false?' · Excluded':''));
      const action=row.action||defaults().action;
      const quantity=row.quantity===''||row.quantity===undefined?defaults().quantity:row.quantity;
      const amount=action==='add_copies'?(quantity===null||quantity==='unknown'?'Quantity unknown · review required':quantity===''||quantity===undefined?'Quantity required · review required':quantity+' '+(Number(quantity)===1?'copy':'copies')):
        action==='set_total'?'Total '+(row.total===null||row.total==='unknown'?'Unknown':row.total===''||row.total===undefined?'needs a value':row.total):'Quantity unknown';
      const variant=action==='add_copies'?(row.keep_unknown?'Variant unknown':row.printing_id?'Variant selected':'Choose a variant or keep unknown'):'No copies created';
      text.append(node('small',`${actionLabels[action]||action} · ${amount} · ${variant}`,{class:'bulk-note'}));
      const exceptions=Object.keys(row).filter(k=>fields.includes(k)).length;
      if(exceptions)text.append(node('small',exceptions+' copy detail exceptions',{class:'bulk-note'}));
      const edit=node('button','Edit row',{type:'button'});edit.dataset.rowId=row.row_id;edit.onclick=()=>openRow(row,edit);
      line.append(check,text,edit);target.append(line);
    });
    const missing=[...new Set(state.rows.slice(state.trayPage*50,state.trayPage*50+50).filter(r=>r.group_id&&!groupFor(r)&&!unavailableGroups.has(r.group_id)).map(r=>r.group_id))];
    if(missing.length&&readClient)readClient.get('/api/v2/selected-groups/?'+new URLSearchParams({ids:missing.join(',')}),'draft-labels').then(result=>{const got=new Set(result.groups.map(g=>g.id));missing.filter(id=>!got.has(id)).forEach(id=>unavailableGroups.add(id));state.catalog.groups.push(...result.groups.filter(g=>!g.oversized).map(g=>({...g,existing:g,children:[]})));result.groups.filter(g=>g.oversized).forEach(g=>unavailableGroups.add(g.id));renderTray();}).catch(e=>{if(e.name!=='AbortError')status(e.message,true);});
    $('bulk-set-template').href='/api/bulk/template/?set='+encodeURIComponent($('bulk-set').value);
    $('bulk-tray-page').textContent=`${state.trayPage+1} / ${pages}`;
    $('bulk-tray-prev').disabled=!state.trayPage; $('bulk-tray-next').disabled=state.trayPage>=pages-1;
    renderCounts();
  }
  function openRow(row, origin) {
    state.edit={row,origin};const container=$('bulk-row-fields');attributeFields(container,'bulk-row-',row,true);
    const prepend=[];
    function field(key,label,options,value) {
      const wrap=node('label',label), control=node(options?'select':'input',null,{id:'bulk-row-'+key});
      if(options) setOptions(control,options);
      control.value=value??'';control.dataset.explicitClear=String(value===null);control.addEventListener('input',()=>control.dataset.explicitClear='false');wrap.append(control);prepend.push(wrap);return control;
    }
    const rowAction=field('action','Action',[['add_copies','Add physical copies'],['set_total','Record total'],['mark_owned','Mark broadly owned']],row.action||defaults().action);
    field('number','Card number (literal)',null,row.number);
    field('quantity','Copy quantity (blank inherits)',null,row.quantity);
    field('total','Card total (positive whole number or unknown)',null,row.total);
    const g=groupFor(row);
    const options=[['','Choose a supported child'],['unknown','Keep variant unknown']];
    if(row.printing_id)options.push([row.printing_id,'Selected printing']);
    if(g) g.children.forEach(p=>options.push([p.id,`Edition: ${p.edition||'Unknown'} · Finish: ${p.finish||'Unknown'} · Variant: ${p.variant||'Unknown'} · Unresolved: ${p.unresolved_fields.join(', ')||'none'}`]));
    const choice=field('choice','Card variant',options,row.keep_unknown?'unknown':row.printing_id||'');
    if(g){const host=node('div',null);prepend.push(host);BoundedReads.paged(host,{reader:readClient,url:'/api/v2/card-groups/'+encodeURIComponent(g.id)+'/variants/',field:'variants',active:()=>state.edit?.row===row,render:v=>'<button type="button" data-entry-child="'+html(v.id)+'">'+html(v.variant_label||[v.edition,v.finish,v.variant].filter(Boolean).join(' · ')||'Variant not specified')+'</button>',bind:rows=>rows.querySelectorAll('[data-entry-child]').forEach(b=>b.onclick=()=>{if(![...choice.options].some(o=>o.value===b.dataset.entryChild))choice.add(new Option(b.textContent,b.dataset.entryChild));choice.value=b.dataset.entryChild;choice.dispatchEvent(new Event('input'));choice.dispatchEvent(new Event('change'));})});}
    const variantCaption=node('p','',{class:'bulk-help'});prepend.push(variantCaption);
    const showChoice=()=>{variantCaption.textContent=choice.selectedOptions[0]?.textContent||'';};choice.onchange=showChoice;showChoice();
    if(g && ['Base Set 2','Wizards Black Star Promos'].includes(g.set_name)) prepend.push(node('p','Standard first edition: Not applicable. Other missing metadata remains Unknown.'));
    field('duplicate_decision','Repeated input / certificate decision',[['','Needs review if repeated'],['different','Different physical copies / add'],['skip','Same physical copy / skip']],row.duplicate_decision);
    const include=field('included','Include in reviewed batch',[['yes','Include'],['no','Exclude, retaining input']],row.included===false?'no':'yes');
    include.dataset.kind='include';
    const na=node('p','Copy-only fields are Not applicable to this action. Clear supplied copy values or change the action before Review.');
    const clear=node('button','Clear copy-only values for this row',{type:'button'});
    clear.onclick=()=>{fields.forEach(k=>{const c=$('bulk-row-'+k);c.value=c.tagName==='SELECT'?'unknown':'';c.dataset.explicitClear='true';});$('bulk-row-quantity').value='';state.edit.clearCopy=true;};
    const applicability=()=>{const disabled=rowAction.value!=='add_copies';fields.forEach(k=>$('bulk-row-'+k).disabled=disabled);$('bulk-row-quantity').disabled=disabled;na.hidden=!disabled;clear.hidden=!disabled;};
    container.prepend(...prepend);container.append(na,clear);rowAction.onchange=applicability;applicability();
    $('bulk-drawer-title').textContent=g?`Edit ${g.name} #${g.collector_number}`:'Edit card row';
    $('bulk-row-record').textContent=g?g.set_name+' · '+g.language:'Correct the card identity and details below.';
    const record=node('details',null);record.append(node('summary','Source row reference'),node('p',row.row_id));container.append(record);
    $('bulk-drawer').showModal();
    const labelControls=[{element:choice,kind:'printing'},{element:$('bulk-row-binder_id'),kind:'binder'}].filter(c=>c.element&&c.element.value&&c.element.value!=='unknown');
    BoundedReads.labelControls(readClient,labelControls).then(showChoice).catch(e=>status(e.message,true));
  }
  $('bulk-drawer').addEventListener('close',()=>{const origin=state.edit?.origin;if(origin?.isConnected)origin.focus();});
  $('bulk-row-save').onclick=()=>{
    const r=state.edit.row,g=groupFor(r);
    if(g){r.group_id=g.id;r.set_id=g.set_id;r.language=g.language;}
    [...fields,'action','quantity','total','number','duplicate_decision'].forEach(k=>{const control=$('bulk-row-'+k);r[k]=control.dataset.explicitClear==='true'||(k==='quantity'&&state.edit.clearCopy)?null:control.value;});
    const choice=$('bulk-row-choice').value;r.keep_unknown=choice==='unknown';
    if(choice && choice!=='unknown')r.printing_id=choice;else delete r.printing_id;
    // A bound checklist row retains its group; editing its number is checked against that identity by the server.
    r.literal_text=['notes'];
    r.included=$('bulk-row-included').value==='yes';
    changed();state.edit.origin=null;$('bulk-drawer').close();state.trayPage=Math.floor(state.rows.indexOf(r)/50);renderTray();$('bulk-selected-details').open=true;[...$('bulk-tray').querySelectorAll('button')].find(b=>b.dataset.rowId===r.row_id)?.focus();
  };
  async function saveDraft(extra={}) {
    if(!state.changed && state.draft) return state.draft;
    const result=await api('/api/bulk/save/',{input:input(), ...(state.draft?{id:state.draft.id,revision:state.draft.revision}:{}),
      new_batch:state.newBatch,batch_identity:state.batchIdentity,...extra});
    state.draft=result.draft;state.changed=false;state.newBatch=false;
    history.replaceState(null,'','/add-many/?draft='+state.draft.id);
    status(`Draft saved until ${new Date(state.draft.expires_at).toLocaleString()}.`);
    if(state.draft.state==='confirmed') await recover();
    await savedList(); return state.draft;
  }
  function renderReview(op) {
    state.op=op;state.resolved=new Map(op.plan.bulk.rows.map(r=>[r.row_id,r.group_id]));renderTray();state.reviewPage=0;$('bulk-review-panel').hidden=false;$('bulk-receipt').hidden=true;
    $('bulk-editor').hidden=true;$('bulk-tray-panel').hidden=true;
    const rows=op.plan.bulk.rows, included=rows.filter(r=>r.included&&!r.skipped&&!r.noop), excluded=rows.filter(r=>!r.included||r.skipped);
    const copies=op.plan.creates.filter(c=>c.kind==='copy').length;
    const intents=op.plan.card_intents;
    const summary=$('bulk-review-summary'),facts=node('div',null,{class:'bulk-review-facts'});
    [[rows.length,'draft rows'],[copies,'new copies'],[intents.filter(i=>i.kind==='mark_owned').length,'cards marked owned'],[intents.filter(i=>i.kind==='card_quantity').length,'card totals']].forEach(([count,label])=>{
      if(count||label==='draft rows'||label==='new copies'){const fact=node('div',null);const caption=count===1?({'draft rows':'draft row','new copies':'new copy','cards marked owned':'card marked owned','card totals':'card total'}[label]||label):label;fact.append(node('strong',String(count)+' '),node('span',caption));facts.append(fact);}
    });
    summary.replaceChildren(facts,node('p',`${included.length} included rows · ${excluded.length} excluded/skipped · ${rows.filter(r=>r.noop).length} No change.`,{class:'bulk-help'}));
    if(copies)summary.append(node('p','Adding copies makes any earlier complete card total Unknown. Recorded copies remain separate from a complete total.',{class:'bulk-help'}));
    if(op.plan.errors.length)summary.append(node('p',`${op.plan.errors.length} row errors. Correct the affected rows or explicitly exclude them before confirming.`,{class:'bulk-error',role:'alert'}));
    $('bulk-confirm').textContent='Confirm batch';
    $('bulk-confirm-help').textContent=op.plan.errors.length?'Confirmation is unavailable until the row errors are corrected or excluded.':'Confirm applies all included changes together. You can undo this whole batch from its receipt.';
    $('bulk-review-record').replaceChildren(node('p','Operation '+op.id),node('p','Collection generation '+op.generation),node('p','Whole-lot cost is recorded once, never allocated.'));
    if(op.plan.photo_review){const p=op.plan.photo_review;summary.append(node('p',`${p.excluded_crops.length} photo crops excluded. Only individually selected crops may be retained.`,{class:'bulk-help'}));$('bulk-review-record').append(node('p',`Photo batch ${p.batch_id}. Physical duplicate review completed. Excluded crop IDs: ${p.excluded_crops.join(', ')||'None'}.`));}
    renderReviewRows();availability();$('bulk-review-panel').focus();
  }
  function renderReviewRows() {
    if(!state.op)return;const rows=state.op.plan.bulk.rows,pages=Math.max(1,Math.ceil(rows.length/50));
    state.reviewPage=Math.max(0,Math.min(state.reviewPage,pages-1));const target=$('bulk-review-rows');target.replaceChildren();
    rows.slice(state.reviewPage*50,state.reviewPage*50+50).forEach(r=>{
      const line=node('div',null,{class:'bulk-review-row'}),info=node('div',`${r.identity?.set_name||'Unresolved set'} · #${r.matched_number||'?'} ${r.identity?.name||r.row_id}`);
      const existing=r.existing;
      if(existing)info.append(node('p',`Before: ${existing.present?'Owned':'Not owned'} · total ${existing.established_total_quantity??'Unknown'} · ${r.current_copy_count} current / ${existing.recorded_copy_count} recorded copies.`));
      const active=r.included&&!r.skipped&&!r.noop&&!r.errors.length;
      let effect=!r.included?'Excluded':r.skipped?'Same copy / skipped':r.noop?'No change':r.errors.length?'Fix errors before including':
        r.action==='add_copies'?`Add ${r.quantity} ${r.quantity===1?'copy':'copies'} · total Unknown · ${r.unresolved_fields.length?'variant unresolved':'qualified catalog identity'}`:
        r.action==='set_total'?`Owned · total ${r.total??'Unknown'} · no copies created`:'Broadly owned · total Unknown · no copies created';
      if(r.photo_result)effect=r.photo_result.detail+(r.photo_result.first_edition?' · ✓ First edition':'');
      info.append(node('p','After: '+effect));
      if(r.resulting)info.append(node('small',`Result for this card across the batch: ${r.resulting.present?'Owned':'Not owned'} · total ${r.resulting.established_total_quantity??'Unknown'} · ${r.resulting.current_copy_count} current / ${r.resulting.recorded_copy_count} recorded copies · ${r.resulting.exact_variant_count} qualified variants`,{class:'bulk-note'}));
      if(r.attributes)info.append(node('small',Object.entries(r.attributes).filter(([,v])=>v).map(([k,v])=>`${labels[k]||k}: ${v}`).join(' · '),{class:'bulk-note'}));
      r.errors.forEach(e=>info.append(node('p','Row '+r.row_id+': '+e,{class:'bulk-error'})));
      r.warnings.forEach(e=>info.append(node('p',e,{class:'bulk-note'})));
      if(active&&r.url)info.append(node('a','Open card',{href:r.url}));
      const edit=node('button','Edit / exclude',{type:'button'});edit.onclick=()=>openRow(state.rows.find(raw=>raw.row_id===r.row_id),edit);
      line.append(info,edit);target.append(line);
    });
    $('bulk-review-page').textContent=`${state.reviewPage+1} / ${pages}`;
    availability();
  }
  function receipt(op) {
    state.op=op;$('bulk-review-panel').hidden=true;$('bulk-receipt').hidden=false;
    $('bulk-editor').hidden=true;$('bulk-tray-panel').hidden=true;
    $('bulk-receipt').querySelector('h2').textContent=op.state==='undone'?'Batch undone':'Batch saved';
    const target=$('bulk-receipt-body');target.replaceChildren(node('p',op.state==='undone'?'This whole batch was undone. Any earlier invalidated total stays Unknown.':'Your collection has been updated. Reopening this receipt does not add copies.'));
    const copies=op.plan.creates.filter(c=>c.kind==='copy').length;
    target.append(node('p',`${op.state==='undone'?'Original batch: ':''}${copies} added copy records · ${op.plan.card_intents.filter(i=>i.kind==='mark_owned').length} cards marked owned · ${op.plan.card_intents.filter(i=>i.kind==='card_quantity').length} card totals · ${op.plan.bulk.rows.filter(r=>!r.included||r.skipped).length} excluded/skipped rows.`));
    if(copies)target.append(node('p','Complete totals became Unknown where copies were added.',{class:'bulk-help'}));
    if(op.plan.photo_report){
      const report=op.plan.photo_report,labels={added:'Added',already_owned:'Already owned · skipped',duplicate:'Duplicate · skipped',edition_updated:'First edition checked',needs_review:'Needs review',excluded:'Excluded'};
      target.append(node('h3',op.state==='undone'?'Original photo report · undone':'Photo addition report'));
      const counts=Object.entries(labels).map(([key,label])=>[report.filter(r=>r.status===key).length,label]).filter(([n])=>n);
      target.append(node('p',counts.map(([n,label])=>`${n} ${label.toLowerCase()}`).join(' · ')));
      const list=node('ul',null);for(const r of report){const title=r.identity?`${r.identity.set_name} · #${r.identity.number} ${r.identity.name}`:r.row_id;const line=node('li',`${title} — ${labels[r.status]}${r.first_edition?' · ✓ First edition':''}. ${r.detail}`);list.append(line);}target.append(list);
    }
    const record=node('details',null);record.append(node('summary','Receipt record details'),node('p','Operation '+op.id),node('p','Collection generation '+op.generation));
    if(op.plan.photo_review){const p=op.plan.photo_review;target.append(node('p','Selected crops retain private per-copy associations. Deleted images cannot be reconstructed.',{class:'bulk-help'}));record.append(node('p',`Photo batch ${p.batch_id} · excluded crop IDs: ${p.excluded_crops.join(', ')||'None'}.`));}
    const links=node('div',null,{class:'bulk-receipt-links'}),linked=op.plan.bulk.rows.filter(r=>r.url);
    linked.slice(0,50).forEach(r=>links.append(node('a',`${r.identity.name} #${r.matched_number}`,{href:r.url})));
    if(linked.length>50)target.append(node('p','Showing the first 50 card links. The receipt retains the whole batch.',{class:'bulk-help'}));
    target.append(links,record);availability();$('bulk-receipt').focus();
    status(op.state==='undone'?'Whole batch undone.':'Batch saved. Your receipt is below.');
  }
  async function recover() {
    if(!state.draft){await savedList();$('bulk-saved-panel').open=true;state.recoverNeeded=false;status('Saved drafts refreshed. Resume the matching draft to check its result.');return;}
    const result=await api(`/api/bulk/drafts/${state.draft.id}/`);state.draft=result.draft;state.recoverNeeded=false;
    if(result.operation && ['confirmed','undone'].includes(result.operation.state))receipt(result.operation);
    else if(result.operation&&state.draft.state==='previewed')renderReview(result.operation);
    else status((draftLabels[state.draft.state]||state.draft.state)+' · collection unchanged by this draft.');
  }
  async function savedList() {
    const result=await api('/api/bulk/drafts/');state.savedCount=result.drafts.length;const target=$('bulk-saved');target.replaceChildren();
    result.drafts.forEach(d=>{
      const b=node('button',`${draftLabels[d.state]||d.state} · ${new Date(d.updated_at).toLocaleString()} · ${d.id.slice(0,8)}`,{type:'button'});
      b.onclick=()=>work(()=>resume(d.id));target.append(b);
    });
    $('bulk-saved-count').textContent='('+state.savedCount+')';availability();
  }
  async function resume(id, cached=null) {
    const result=cached||await api(`/api/bulk/drafts/${id}/`),d=result.draft;state.draft=d;
    state.rows=d.input_json.rows;state.checked.clear();state.changed=false;state.newBatch=false;
    const defaults=d.input_json.defaults;
    ['action','game','language','set'].forEach(k=>{if(defaults[k==='set'?'set_id':k]){const value=defaults[k==='set'?'set_id':k],control=$('bulk-'+k);if(!optionsContain(control,value))control.add(new Option(k==='language'?value:'Retained selection — loading label',value));control.value=value;}});
    $('bulk-quantity').value=defaults.quantity??'1';fields.forEach(k=>{const control=$('bulk-default-'+k),value=defaults[k]||'';if(k==='binder_id'&&value&&!optionsContain(control,value))control.add(new Option('Retained binder — loading label',value));control.value=value;});
    if(readClient&&!readClient.disposed)BoundedReads.labelControls(readClient,[{element:$('bulk-set'),kind:'set'},{element:$('bulk-default-binder_id'),kind:'binder'}]).catch(e=>status(e.message,true));
    ['amount','currency','date'].forEach(k=>$('bulk-lot-'+k).value=d.input_json.lot?.['lot_'+k]||'');
    state.selected=new Set(state.rows.map(r=>r.group_id||groupFor(r)?.id).filter(Boolean));
    history.replaceState(null,'','/add-many/?draft='+d.id);meaning();renderCatalog();renderTray();
    if(result.operation && ['confirmed','undone'].includes(result.operation.state))receipt(result.operation);
    else if(result.operation&&d.state==='previewed')renderReview(result.operation);
    if(!result.operation||!['confirmed','undone'].includes(result.operation.state))status(`${draftLabels[d.state]||d.state} · expires ${new Date(d.expires_at).toLocaleString()}.`);
    availability();
  }
  function meaning() {
    const action=$('bulk-action').value;
    $('bulk-quantity-label').hidden=action!=='add_copies';$('bulk-default-fields').hidden=action!=='add_copies';
    $('bulk-meaning').textContent=action==='add_copies'?'Creates individual copy records. Complete card totals stay Unknown.':
      action==='set_total'?'Record a complete card total, or clear it to Unknown. The card must already be owned; no copies are created.':'Records ownership with Unknown total. Already owned cards stay unchanged. No copies or exact variants are created.';
  }
  $('bulk-save').onclick=()=>work(()=>saveDraft());
  $('bulk-back-edit').onclick=()=>{$('bulk-editor').hidden=false;$('bulk-tray-panel').hidden=false;$('bulk-review-panel').hidden=true;$('bulk-action').focus();};
  $('bulk-review').onclick=()=>work(async()=>{await saveDraft();if(state.draft.state==='confirmed')return;
    const result=await api(`/api/bulk/drafts/${state.draft.id}/review/`,{revision:state.draft.revision});state.draft=result.draft;renderReview(result.operation);status(result.operation.plan.errors.length?'Correct or explicitly exclude the named row errors.':'Review all included changes, exclusions and defaults before Confirm.');});
  $('bulk-confirm').onclick=()=>work(async()=>{
    status('Checking saved result… If the connection is interrupted, use Check saved result.');
    const result=await api(`/api/bulk/drafts/${state.draft.id}/confirm/`,{revision:state.draft.revision});state.draft=result.draft;receipt(result.operation);await savedList();
  });
  $('bulk-recover').onclick=()=>work(()=>recover());
  $('bulk-cancel').onclick=()=>work(async()=>{
    if(!state.draft){state.rows=[];state.selected.clear();state.changed=false;renderCatalog();renderTray();state.focusAfterWork='bulk-action';return;}
    const result=await api(`/api/bulk/drafts/${state.draft.id}/cancel/`,{revision:state.draft.revision});state.draft=result.draft;
    if(state.draft.state==='confirmed')await recover();else {state.rows=[];state.selected.clear();state.changed=false;state.op=null;$('bulk-review-panel').hidden=true;$('bulk-receipt').hidden=true;$('bulk-editor').hidden=false;$('bulk-tray-panel').hidden=false;renderCatalog();renderTray();status('Draft cancelled. Late confirmations are blocked.');state.focusAfterWork='bulk-action';}await savedList();
  });
  $('bulk-undo').onclick=()=>work(async()=>{const op=await api(`/api/operations/${state.op.id}/undo/`,{});receipt(op);status('Whole batch undone. Any invalidated earlier total stays Unknown.');});
  $('bulk-new').onclick=()=>work(async()=>{
    $('bulk-editor').hidden=false;$('bulk-tray-panel').hidden=false;
    state.draft=null;state.op=null;state.rows=[];state.selected.clear();state.checked.clear();state.newBatch=true;state.batchIdentity=crypto.randomUUID();state.changed=false;state.recoverNeeded=false;
    readClient?.stop();readClient=new BoundedReads.Reader({active:()=>!window.navigationAuthorityDiscarded});loadCatalog();
    history.replaceState(null,'','/add-many/');$('bulk-review-panel').hidden=true;$('bulk-receipt').hidden=true;renderCatalog();renderTray();status('Separate physical batch. Choose only different physical cards; identical printings may be different copies.');state.focusAfterWork='bulk-action';
  });
  $('bulk-all').onclick=()=>{try{const found=matches();if(found.filter(g=>!state.selected.has(g.id)).length+state.rows.length>2000)throw Error('Selection exceeds 2,000 rows. No rows selected.');found.forEach(addGroup);renderCatalog();renderTray();}catch(e){status(e.message);}};
  function selectionQuery(){return new URLSearchParams({set:$('bulk-set').value,q:$('bulk-search').value,language:$('bulk-language').value}).toString();}
  async function selectMatching(range=false){
    const signature=selectionQuery(),pending=[];let first=0,last=pageCount-1,ends;
    if(range){ends=state.anchors.map(id=>({id,...anchorPositions.get(id)})).sort((a,b)=>a.page-b.page||a.index-b.index);if(ends.length!==2||ends.some(e=>e.query!==signature))throw Error('Check the start and end within this same set and search, on any pages.');first=ends[0].page;last=ends[1].page;}
    else if(pageTotal>2000)throw Error('More than 2,000 matches. Narrow this search before selecting all. No rows selected.');
    if((last-first)*50>2000)throw Error('This range exceeds 2,000 cards. Narrow the checked range.');
    for(let n=first;n<=last;n++){
      const query=new URLSearchParams(signature);if(!query.get('language'))query.delete('language');query.set('page',n+1);query.set('page_size','50');
      status('Reading selection page '+(n-first+1)+' of '+(last-first+1)+'…');const result=await readClient.get('/api/v2/card-groups/?'+query,'bulk-selection');
      if(signature!==selectionQuery())throw Error('Selection changed. No additional rows selected.');
      if(result.groups.some(g=>g.oversized))throw Error('This selection contains a complete-record reference. Review that record before selecting this range. No additional rows selected.');
      pending.push(...result.groups.map(g=>({...g,existing:g,children:[]})));
    }
    let chosen=pending;if(range){const a=pending.findIndex(g=>g.id===ends[0].id),b=pending.findIndex(g=>g.id===ends[1].id);if(a<0||b<0)throw Error('Range changed. Reload and select its endpoints again.');chosen=pending.slice(a,b+1);}
    if(chosen.filter(g=>!state.selected.has(g.id)).length+state.rows.length>2000)throw Error('Combined selection exceeds 2,000 rows. No additional rows selected.');
    const known=new Set(state.catalog.groups.map(g=>g.id));state.catalog.groups.push(...chosen.filter(g=>!known.has(g.id)));chosen.forEach(addGroup);renderCatalog();renderTray();status(chosen.length+' matching cards selected across pages. Review before confirming.');
  }
  $('bulk-all-matches').onclick=()=>work(()=>selectMatching());
  $('bulk-range').onclick=()=>work(()=>selectMatching(true));
  $('bulk-check-all').onclick=()=>{state.rows.forEach(r=>state.checked.add(r.row_id));renderTray();};
  $('bulk-clear-checked').onclick=()=>{state.checked.clear();renderTray();};
  $('bulk-unknown').onclick=()=>{state.rows.forEach(r=>{if(state.checked.has(r.row_id)){const g=groupFor(r);if(g){r.group_id=g.id;r.set_id=g.set_id;r.number=g.collector_number;r.language=g.language;}r.keep_unknown=true;delete r.printing_id;}});changed();renderTray();};
  $('bulk-different').onclick=()=>{state.rows.forEach(r=>{if(state.checked.has(r.row_id))r.duplicate_decision='different';});changed();renderTray();};
  $('bulk-apply-selected').onclick=()=>{
    const values=defaults(), count=state.checked.size;
    ['set_id','set','game','language'].forEach(k=>delete values[k]);
    state.rows.forEach(r=>{if(state.checked.has(r.row_id))Object.assign(r,values);});changed();renderTray();status(`Visible defaults applied to ${count} checked rows. Review their changes before confirming.`);
  };
  ['exclude','include'].forEach(action=>$('bulk-'+action).onclick=()=>{state.rows.forEach(r=>{if(state.checked.has(r.row_id))r.included=action==='include';});changed();renderTray();});
  ['prev','next'].forEach((dir,i)=>$('bulk-'+dir).onclick=()=>{state.page+=i?1:-1;loadCatalog();$('bulk-search').focus();});
  ['prev','next'].forEach((dir,i)=>$('bulk-tray-'+dir).onclick=()=>{state.trayPage+=i?1:-1;renderTray();});
  ['prev','next'].forEach((dir,i)=>$('bulk-review-'+dir).onclick=()=>{state.reviewPage+=i?1:-1;renderReviewRows();});
  ['set','game','language'].forEach(k=>$('bulk-'+k).onchange=()=>{state.page=0;state.anchors=[];changed();if(k==='game')loadSets().catch(e=>status(e.message,true));else{if(k==='set')setOptions($('bulk-language'),[['','All languages']]);loadCatalog();}});
  let searchTimer;$('bulk-search').oninput=()=>{state.page=0;clearTimeout(searchTimer);searchTimer=setTimeout(loadCatalog,15);};
  $('bulk-action').onchange=()=>{meaning();changed();};
  $('bulk-quantity').oninput=changed;$('bulk-defaults').addEventListener('change',changed);
  ['amount','currency','date'].forEach(k=>$('bulk-lot-'+k).onchange=changed);
  document.querySelectorAll('[data-input]').forEach(b=>b.onclick=()=>{
    ['checklist','paste','csv'].forEach(k=>$('bulk-'+k).hidden=k!==b.dataset.input);
    document.querySelectorAll('[data-input]').forEach(x=>x.setAttribute('aria-pressed',String(x===b)));
  });
  $('bulk-parse-paste').onclick=()=>work(async()=>{
    const values=defaults();
    const result=await api('/api/bulk/parse/',{input:{source:'paste',text:$('bulk-paste-text').value,defaults:values}});
    const resolved=new Map(result.normalized.rows.map(r=>[r.row_id,r.group_id]));
    const added=result.input.rows.map(r=>({...values,...r,row_id:'paste:'+values.set_id+':'+r.row_id,
      ...(resolved.get(r.row_id)?{group_id:resolved.get(r.row_id)}:{})}));
    if(state.rows.length+added.length>2000)throw Error('Combined draft exceeds 2,000 rows. No rows appended.');
    if(added.some(r=>state.rows.some(old=>old.row_id===r.row_id)))throw Error('These source numbers are already in the draft. Edit their rows, or start a separate physical batch.');
    state.rows.push(...added);state.selected=new Set(state.rows.map(r=>r.group_id||groupFor(r)?.id).filter(Boolean));
    changed();renderCatalog();renderTray();await saveDraft();
  });
  $('bulk-parse-csv').onclick=()=>work(async()=>{
    const file=$('bulk-file').files[0];if(!file)throw Error('Choose a UTF-8 CSV file.');if(file.size>1500000)throw Error('CSV exceeds 1.5 MB.');
    if(state.changed&&state.rows.length)throw Error('Save or cancel the current draft before loading a CSV.');
    let text;try{text=new TextDecoder('utf-8',{fatal:true}).decode(await file.arrayBuffer());}catch{throw Error('CSV must be valid UTF-8. Resave the file as UTF-8 and load it again.');}const result=await api('/api/bulk/save/',{input:{source:'csv',text,defaults:defaults()},new_batch:state.newBatch,batch_identity:state.batchIdentity});await resume(result.draft.id);
  });
  window.addEventListener('beforeunload',e=>{if(state.changed){e.preventDefault();e.returnValue='';}});
  document.addEventListener('submit',e=>{if(e.target.action?.includes('/logout/')){state.changed=false;erase();}});
  window.addEventListener('dex:authority-revoked',erase);
  window.addEventListener('pageshow',e=>{if(e.persisted)location.reload();});
  work(async()=>{
    readClient=new BoundedReads.Reader({active:()=>Boolean($('bulk-editor'))&&!window.navigationAuthorityDiscarded});
    state.catalog={games:[],groups:[],sets:[],languages:[],binders:[]};
    attributeFields($('bulk-defaults'),'bulk-default-',{});await savedList();
    const id=new URLSearchParams(location.search).get('draft');if(id){await resume(id);if(['confirmed','undone'].includes(state.op?.state))return;}
    const games=await readClient.get('/api/v2/entry-options/?field=game');
    state.catalog.games=games.options.filter(g=>!g.oversized);
    setOptions($('bulk-game'),state.catalog.games.map(g=>[g.game_key,g.name]));
    [...$('bulk-game').options].forEach(o=>o.dataset.gameId=state.catalog.games.find(g=>g.game_key===o.value).id);
    const gameNext=games.options.some(g=>g.oversized)?'/api/v2/entry-options/?field=game':BoundedReads.next('/api/v2/entry-options/?field=game',games);
    if(gameNext){const host=node('div',null);$('bulk-game').after(host);BoundedReads.paged(host,{reader:readClient,url:gameNext,field:'options',render:g=>'<button type="button" data-entry-game="'+html(g.game_key)+'" data-entry-game-id="'+html(g.id)+'">'+html(g.name)+'</button>',bind:rows=>rows.querySelectorAll('[data-entry-game]').forEach(b=>b.onclick=()=>{if(!optionsContain($('bulk-game'),b.dataset.entryGame)){const o=new Option(b.textContent,b.dataset.entryGame);o.dataset.gameId=b.dataset.entryGameId;$('bulk-game').add(o);}$('bulk-game').value=b.dataset.entryGame;loadSets().catch(e=>status(e.message,true));})});}
    await loadSets();
    meaning();renderCatalog();renderTray();
    if(id)await resume(id,{draft:state.draft,operation:state.op});else status('Select cards to start a batch.');
  });
})();
