/* Selected photos -> one analysis -> human review -> idempotent shared confirmation. */
(() => {
  'use strict';
  const $=id=>document.getElementById(id);
  if(!$('photo-csrf'))return;
  let batch=null,catalog=[],busy=false,timer=null,epoch=0,operation=null;
  const choices=new Map(),binding=document.body.dataset.navigationBinding;
  const node=(tag,text,attrs={})=>{const e=document.createElement(tag);if(text!==null)e.textContent=text;for(const [k,v] of Object.entries(attrs))e.setAttribute(k,v);return e;};
  const status=(text,error=false)=>{$('photo-status').textContent=text;$('photo-status').dataset.error=String(error);if(error)$('photo-status').focus();};
  const running=()=>!!batch?.stages.some(s=>['queued','processing'].includes(s.state));
  function lock(value){busy=value;const waiting=value||running();$('photo-entry').querySelectorAll('button,input,select,textarea').forEach(e=>{if(e.id!=='photo-stop')e.disabled=waiting;});$('photo-stop').hidden=!running();}
  function erase(){epoch++;clearTimeout(timer);batch=null;choices.clear();$('photo-entry').replaceChildren(node('p','Your session changed. Sign in again.'));}
  async function api(url,data){const current=epoch,options={credentials:'same-origin',cache:'no-store',headers:{Accept:'application/json'}};
    if(data!==undefined){options.method='POST';options.headers['X-CSRFToken']=$('photo-csrf').querySelector('input').value;options.headers['X-Dex-Binding']=binding;
      if(data instanceof FormData)options.body=data;else{options.headers['Content-Type']='application/json';options.body=JSON.stringify(data);}}
    const response=await fetch(url,options);if(response.redirected||[401,403].includes(response.status)){erase();throw Error('Sign in again.');}
    const result=await response.json();if(current!==epoch)throw Error('Session changed.');if(result.binding&&result.binding!==binding){erase();throw Error('Session changed.');}
    if(!response.ok)throw Error(result.error||'Unable to complete this action. Your collection has not been changed.');return result;
  }
  async function work(fn){if(busy)return;lock(true);try{await fn();}catch(e){status(e.message,true);}finally{if($('photo-csrf'))lock(false);}}
  async function action(name,data={}){const r=await api(`/api/photo-batches/${batch.id}/${name}/`,data);if(r.batch)batch=r.batch;return r;}
  const activePhotos=()=>batch.photos.filter(p=>p.state==='active');
  function report(op){operation=op;const upload=$('photo-upload-panel');if(upload)upload.open=false;$('photo-results').hidden=true;$('photo-report').hidden=false;const target=$('photo-report-body');target.replaceChildren();
    const labels={added:'Added',already_owned:'Already owned · skipped',duplicate:'Duplicate · skipped',edition_updated:'First edition checked',needs_review:'Needs review',excluded:'Excluded'};
    const rows=op.plan.photo_report||[];target.append(node('p',op.state==='undone'?'These changes were undone.':Object.entries(labels).map(([key,label])=>[rows.filter(r=>r.status===key).length,label]).filter(([n])=>n).map(([n,label])=>`${n} ${label.toLowerCase()}`).join(' · ')));
    for(const r of rows){const title=r.identity?`${r.identity.name} — ${r.identity.set_name} #${r.identity.number}`:'Unidentified card';target.append(node('p',`${title}: ${labels[r.status]}${r.first_edition?' · ✓ First edition':''}.`));}
    $('photo-undo').hidden=op.state!=='confirmed';status('');$('photo-report').focus();
  }
  function suggestion(c){const ids=new Set(c.candidates.map(p=>p.id));const groups=catalog.filter(g=>g.children.some(p=>ids.has(p.id)));if(groups.length!==1)return null;const g=groups[0];const children=g.children.filter(p=>ids.has(p.id));return {group:g,row:children.length===1?{printing_id:children[0].id}:{group_id:g.id,keep_unknown:true}};}
  function render(){
    const wasHidden=$('photo-results').hidden;
    choices.clear();$('photo-cards').replaceChildren();$('photo-sources').replaceChildren();$('photo-report').hidden=true;
    const crops=batch.crops.filter(c=>c.state==='active');$('photo-results').hidden=!crops.length||running();
    $('photo-summary').textContent=`${crops.length} cards found`;
    const upload=$('photo-upload-panel');if(upload&&(crops.length||running()))upload.open=false;
    for(const [i,c] of crops.entries()){
      const proposed=suggestion(c), row={id:c.id,included:!!proposed,row:proposed?{...proposed.row}:{}};choices.set(c.id,row);
      const card=node('article',null,{class:'photo-card'}), image=node('img',null,{src:'/scan-photos/'+c.id+'/',alt:`Card ${i+1}`});const thumb=node('div',null,{class:'photo-thumb'}),fallback=node('span','No image');fallback.hidden=true;image.onerror=()=>{image.hidden=true;fallback.hidden=false;};thumb.append(image,fallback);card.append(thumb);
      const text=node('div',null,{class:'photo-card-details'});card.append(text);$('photo-cards').append(card);
      const heading=node('h3',proposed?.group.name||c.proposal.name||`Card ${i+1}`);text.append(heading);
      const identity=node('p',proposed?`${proposed.group.set_name} · #${proposed.group.collector_number}`:'Needs a match');text.append(identity);
      const observed=[c.proposal.finish,c.proposal.edition].filter(Boolean).map(s=>s.replaceAll('_',' ')).join(' · ');if(observed)text.append(node('p',observed,{class:'photo-muted'}));
      const owned=node('p',proposed?.group.existing.present?'Already owned — will skip adding another copy.':'');text.append(owned);
      const includeLabel=node('label','',{class:'photo-include'}),include=node('input',null,{type:'checkbox'});include.checked=row.included;includeLabel.append(include,node('span',' Include'));text.append(includeLabel);include.onchange=()=>{row.included=include.checked;};
      const corrections=node('details');corrections.append(node('summary','Correct details'));text.append(corrections);
      const search=node('input',null,{type:'search','aria-label':'Find another card',placeholder:'Search card name, set or number'});corrections.append(search);
      const select=node('select',null,{'aria-label':'Card match'});corrections.append(select);
      function options(){select.replaceChildren(node('option','Choose a card',{value:''}));const q=search.value.trim().toLowerCase();const matches=catalog.filter(g=>q?`${g.name} ${g.set_name} ${g.collector_number}`.toLowerCase().includes(q):g.id===proposed?.group.id).slice(0,80);for(const g of matches)select.append(node('option',`${g.name} — ${g.set_name} #${g.collector_number}`,{value:g.id}));select.value=proposed?.group.id||'';}
      options();search.oninput=options;
      const firstLabel=node('label',''),first=node('input',null,{type:'checkbox'});first.checked=!!c.row_json.first_edition_selected||['first_edition','1st-edition','1st edition'].includes((c.proposal.edition||'').toLowerCase());firstLabel.append(first,node('span',' First edition stamp visible'));corrections.append(firstLabel);
      if(first.checked)row.row.first_edition_selected=true;first.onchange=()=>{row.row.first_edition_selected=first.checked;};
      select.onchange=()=>{const g=catalog.find(g=>g.id===select.value);if(!g){row.included=false;include.checked=false;row.row={};return;}row.row=g.children.length===1?{printing_id:g.children[0].id}:{group_id:g.id,keep_unknown:true};row.row.first_edition_selected=first.checked;row.included=true;include.checked=true;heading.textContent=g.name;identity.textContent=`${g.set_name} · #${g.collector_number}`;owned.textContent=g.existing.present?'Already owned — will skip adding another copy.':'';};
      if(!proposed){corrections.open=true;text.append(node('p','Choose the correct card, or leave it excluded.'));}
    }
    for(const p of activePhotos())$('photo-sources').append(node('img',null,{src:`/api/photo-batches/${batch.id}/photos/${p.id}/`,alt:'Original photo',class:'photo-original'}));
    if(running())status('Identifying the cards…');else if(crops.length)status('');else{const last=batch.stages.at(-1);status(last?.error||'Choose a photo to identify its cards.');}
    lock(busy);
    if(wasHidden&&!$('photo-results').hidden)$('photo-results-title')?.focus();
  }
  async function refresh(){const r=await api(`/api/photo-batches/${batch.id}/`);batch=r.batch;if(batch.draft_id){const d=await api(`/api/bulk/drafts/${batch.draft_id}/`);if(d.operation&&['confirmed','undone'].includes(d.operation.state)){report(d.operation);return;}status('This batch has an existing review.');$('photo-results').hidden=true;$('photo-status').append(node('a',' Open review',{href:'/add-many/?draft='+batch.draft_id}));return;}render();}
  function poll(){clearTimeout(timer);if(!running())return;timer=setTimeout(async()=>{try{await refresh();poll();}catch(e){status(e.message,true);}},1000);}
  async function resume(id){clearTimeout(timer);const r=await api(`/api/photo-batches/${id}/`);batch=r.batch;history.replaceState(null,'','/add-photos/?batch='+id);await refresh();poll();}
  async function saved(){const r=await api('/api/photo-batches/');$('photo-saved').replaceChildren();for(const b of r.batches){const button=node('button',`${new Date(b.created*1000).toLocaleString()} · ${b.state}`,{type:'button'});button.onclick=()=>work(()=>resume(b.id));$('photo-saved').append(button);}return r.batches;}
  async function identify(p,notes){await action('analyze',{revision:batch.revision,photo_id:p.id,stage:'photo',consent:batch.consent_version,notes});render();poll();}
  $('photo-identify').onclick=()=>work(async()=>{const file=$('photo-file').files[0];if(!file)throw Error('Choose a photo first.');if(file.size>8000000)throw Error('Choose a photo under 8 MB.');const notes=$('photo-notes').value;
    batch=(await api('/api/photo-batches/create/',{id:crypto.randomUUID()})).batch;const data=new FormData();data.append('photo',file);data.append('revision',batch.revision);batch=(await api(`/api/photo-batches/${batch.id}/upload/`,data)).batch;history.replaceState(null,'','/add-photos/?batch='+batch.id);
    if(batch.state!=='editing'){await refresh();return;}const p=activePhotos().at(-1);if(!p)throw Error('This saved photo is no longer available.');await identify(p,notes);await saved();});
  $('photo-retry').onclick=()=>work(async()=>{const photos=activePhotos();if(photos.length!==1)throw Error('For this older multi-photo batch, review its saved result or upload one photo.');await identify(photos[0],photos[0].proposal.user_notes||'');});
  $('photo-confirm').onclick=()=>work(async()=>{const selected=[...choices.values()];if(!selected.some(c=>c.included))throw Error('Select at least one matched card.');const r=await action('confirm-cards',{revision:batch.revision,choices:selected});report(r.operation);await saved();});
  $('photo-stop').onclick=async()=>{try{await action('stop');clearTimeout(timer);render();status('Analysis stopped.');}catch(e){status(e.message,true);}};
  $('photo-undo').onclick=()=>work(async()=>{report(await api(`/api/operations/${operation.id}/undo/`,{}));});
  window.addEventListener('dex:authority-revoked',erase);
  work(async()=>{catalog=(await api('/api/bulk/catalog/')).groups;const batches=await saved();const id=new URLSearchParams(location.search).get('batch');if(id)await resume(id);else if(batches.length===1&&batches[0].state==='editing')await resume(batches[0].id);else status('');});
})();
