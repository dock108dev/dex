/* Selected photos -> one analysis -> human review -> idempotent shared confirmation. */
(() => {
  'use strict';
  const $=id=>document.getElementById(id);
  if(!$('photo-csrf'))return;
  const recognitionEnabled=$('photo-entry').dataset.recognitionEnabled==='true';
  let batch=null,catalog=[],busy=false,timer=null,epoch=0,operation=null;
  let catalogReader;
  const choices=new Map(),binding=document.body.dataset.navigationBinding;
  const node=(tag,text,attrs={})=>{const e=document.createElement(tag);if(text!==null)e.textContent=text;for(const [k,v] of Object.entries(attrs))e.setAttribute(k,v);return e;};
  const status=(text,error=false)=>{$('photo-status').textContent=text;$('photo-status').dataset.error=String(error);if(error)$('photo-status').focus();};
  const running=()=>!!batch?.stages.some(s=>['queued','processing'].includes(s.state));
  function lock(value){busy=value;const waiting=value||running();$('photo-entry').querySelectorAll('button,input,select,textarea').forEach(e=>{if(e.id!=='photo-stop')e.disabled=waiting;});$('photo-stop').hidden=!running();}
  function erase(){catalogReader?.stop();epoch++;clearTimeout(timer);batch=null;choices.clear();$('photo-entry').replaceChildren(node('p','Your session changed. Sign in again.'));}
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

      if(proposed){select.append(node('option',`${proposed.group.name} — ${proposed.group.set_name}`,{value:proposed.group.id}));select.value=proposed.group.id;}
      else select.append(node('option','Choose a card',{value:''}));
      const searchStatus=node('p','',{role:'status'}),more=node('button','Search choices',{type:'button'});corrections.append(searchStatus,more);
      const searchReader=new BoundedReads.Reader({seed:catalogReader?.state,active:()=>card.isConnected&&!window.navigationAuthorityDiscarded});let destination=null;
      const options=async(next=false)=>{const chosen=select.selectedOptions[0],retained=chosen?.value?new Option(chosen.textContent,chosen.value):null;
        try{const url=next?destination:'/api/v2/card-groups/?'+new URLSearchParams({q:search.value});if(!url)return;const result=await searchReader.get(url,'choices');
          if(!next){select.replaceChildren(node('option','Choose a card',{value:''}));if(retained)select.add(retained);}
          for(const g of result.groups){if(g.oversized){searchStatus.insertAdjacentHTML('beforeend',BoundedReads.overflow(g));continue;}const adapted={...g,existing:g,children:[]};const index=catalog.findIndex(row=>row.id===g.id);if(index<0)catalog.push(adapted);else catalog[index]={...catalog[index],...adapted,children:catalog[index].children};if(![...select.options].some(o=>o.value===g.id))select.add(new Option(`${g.name} — ${g.set_name} #${g.collector_number}`,g.id));}
          if(retained)select.value=retained.value;
          destination=BoundedReads.next(url,result);more.hidden=!destination;more.textContent='More choices';searchStatus.textContent=result.total+' choices · page '+result.page+' of '+Math.max(1,result.pages);
        }catch(error){if(card.isConnected&&error.name!=='AbortError'){searchStatus.textContent=error.message;more.hidden=false;more.textContent='Retry search';destination=null;}}
      };
      let searchTimer;search.oninput=()=>{clearTimeout(searchTimer);searchTimer=setTimeout(()=>options(),15);};more.onclick=()=>options(!!destination);
      const firstLabel=node('label',''),first=node('input',null,{type:'checkbox'});first.checked=!!c.row_json.first_edition_selected||['first_edition','1st-edition','1st edition'].includes((c.proposal.edition||'').toLowerCase());firstLabel.append(first,node('span',' First edition stamp visible'));corrections.append(firstLabel);
      if(first.checked)row.row.first_edition_selected=true;first.onchange=()=>{row.row.first_edition_selected=first.checked;};
      select.onchange=()=>{const g=catalog.find(g=>g.id===select.value);if(!g){row.included=false;include.checked=false;row.row={};return;}row.row={group_id:g.id,keep_unknown:true};row.row.first_edition_selected=first.checked;row.included=true;include.checked=true;heading.textContent=g.name;identity.textContent=`${g.set_name} · #${g.collector_number}`;owned.textContent=g.existing.present?'Already owned — will skip adding another copy.':'';};
      if(!proposed){corrections.open=true;text.append(node('p','Choose the correct card, or leave it excluded.'));}
    }
    for(const p of activePhotos())$('photo-sources').append(node('img',null,{src:`/api/photo-batches/${batch.id}/photos/${p.id}/`,alt:'Original photo',class:'photo-original'}));
    if(running())status('Identifying the cards…');else if(crops.length)status('');else{const last=batch.stages.at(-1);status(!recognitionEnabled?'AI photo recognition is temporarily unavailable. Add cards manually.':last?.error||'Choose a photo to identify its cards.');}
    lock(busy);
    if(wasHidden&&!$('photo-results').hidden)$('photo-results-title')?.focus();
  }
  async function refresh(){const r=await api(`/api/photo-batches/${batch.id}/`);batch=r.batch;if(batch.draft_id){const d=await api(`/api/bulk/drafts/${batch.draft_id}/`);if(d.operation&&['confirmed','undone'].includes(d.operation.state)){report(d.operation);return;}status('This batch has an existing review.');$('photo-results').hidden=true;$('photo-status').append(node('a',' Open review',{href:'/add-many/?draft='+batch.draft_id}));return;}
    const ids=[...new Set(batch.crops.filter(c=>c.state==='active').flatMap(c=>c.candidates.map(p=>p.id)))];
    catalogReader?.stop();catalogReader=new BoundedReads.Reader({active:()=>Boolean($('photo-entry'))&&!window.navigationAuthorityDiscarded});catalog=[];
    if(ids.length&&ids.length<=100){try{const result=await catalogReader.get('/api/v2/selection-groups/?ids='+encodeURIComponent(ids.join(',')));catalog=result.groups.filter(g=>!g.oversized).map(g=>({...g,existing:g,children:result.candidates.filter(p=>p.group_id===g.id)}));}catch(error){status(error.message,true);}}
    render();
  }
  function poll(){clearTimeout(timer);if(!running())return;timer=setTimeout(async()=>{try{await refresh();poll();}catch(e){status(e.message,true);}},1000);}
  async function resume(id){clearTimeout(timer);const r=await api(`/api/photo-batches/${id}/`);batch=r.batch;history.replaceState(null,'','/add-photos/?batch='+id);await refresh();poll();}
  async function saved(){const r=await api('/api/photo-batches/');$('photo-saved').replaceChildren();for(const b of r.batches){const button=node('button',`${new Date(b.created*1000).toLocaleString()} · ${b.state}`,{type:'button'});button.onclick=()=>work(()=>resume(b.id));$('photo-saved').append(button);}return r.batches;}
  $('photo-confirm').onclick=()=>work(async()=>{const selected=[...choices.values()];if(!selected.some(c=>c.included))throw Error('Select at least one matched card.');const r=await action('confirm-cards',{revision:batch.revision,choices:selected});report(r.operation);await saved();});
  $('photo-stop').onclick=async()=>{try{await action('stop');clearTimeout(timer);render();status('Analysis stopped.');}catch(e){status(e.message,true);}};
  $('photo-undo').onclick=()=>work(async()=>{report(await api(`/api/operations/${operation.id}/undo/`,{}));});
  window.addEventListener('dex:authority-revoked',erase);
  work(async()=>{const batches=await saved();const id=new URLSearchParams(location.search).get('batch');if(id)await resume(id);else if(batches.length===1&&batches[0].state==='editing')await resume(batches[0].id);else status('');});
})();
