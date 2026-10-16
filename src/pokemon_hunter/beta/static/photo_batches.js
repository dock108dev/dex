/* Private local staging. No browser persistence, hidden inference or automatic retry. */
(() => {
  'use strict';
  const $=id=>document.getElementById(id);
  if (!$('photo-workspace')) return;
  const binding=document.body.dataset.navigationBinding;
  let batch=null,catalog=[],busy=false,epoch=0,timer=null;
  const node=(tag,text,attrs={})=>{const e=document.createElement(tag);if(text!==null)e.textContent=text;for(const [k,v] of Object.entries(attrs))e.setAttribute(k,v);return e;};
  const status=t=>{$('photo-status').textContent=t;};
  const csrf=()=>$('photo-csrf').querySelector('input').value;
  function erase(){epoch++;clearTimeout(timer);batch=null;$('photo-entry').replaceChildren(node('p','Your session changed. Sign in again to resume your own batch.'));}
  async function api(path,data){
    const token=epoch,options={credentials:'same-origin',cache:'no-store',headers:{Accept:'application/json'}};
    if(data!==undefined){options.method='POST';options.headers['X-CSRFToken']=csrf();options.headers['X-Dex-Binding']=binding;
      if(data instanceof FormData)options.body=data;else{options.headers['Content-Type']='application/json';options.body=JSON.stringify(data);}}
    const response=await fetch(path,options);
    if(response.redirected||response.status===401||response.status===403){erase();throw Error('Sign in again.');}
    const result=await response.json();if(token!==epoch)throw Error('An older view was discarded.');
    if(result.binding&&result.binding!==binding){erase();throw Error('Session changed.');}
    if(!response.ok)throw Error(result.error||'Action unavailable. Reload the saved result before retrying.');
    return result;
  }
  function setBusy(value){busy=value;$('photo-workspace').querySelectorAll('button').forEach(e=>{if(e.id!=='photo-stop')e.disabled=value;});$('photo-new').disabled=value;}
  async function work(fn){if(busy)return;const active=document.activeElement,focus={id:active?.id,crop:active?.closest('[data-crop-id]')?.dataset.cropId,label:active?.getAttribute('aria-label'),text:active?.tagName==='BUTTON'?active.textContent:null};setBusy(true);try{await fn();}catch(e){status(e.message);}finally{if($('photo-workspace')){setBusy(false);let target=focus.id?$(focus.id):null;if(!target&&focus.crop){const card=[...document.querySelectorAll('[data-crop-id]')].find(c=>c.dataset.cropId===focus.crop);target=card&&[...card.querySelectorAll('button,input,select')].find(e=>focus.label?e.getAttribute('aria-label')===focus.label:e.textContent===focus.text);}if(target)target.focus({preventScroll:true});}}}
  async function act(action,data={}){const result=await api(`/api/photo-batches/${batch.id}/${action}/`,data);batch=result.batch;render();return result;}
  async function saved(){const r=await api('/api/photo-batches/');$('photo-saved').replaceChildren();r.batches.forEach(b=>{const button=node('button',`${new Date(b.created*1000).toLocaleDateString()} · ${b.state} · ${b.id.slice(0,8)}`,{type:'button'});button.onclick=()=>work(()=>resume(b.id));$('photo-saved').append(button);});}
  async function resume(id){clearTimeout(timer);const result=await api(`/api/photo-batches/${id}/`);batch=result.batch;history.replaceState(null,'','/add-photos/?batch='+id);render();status('Saved photo state loaded. No analysis or collection change.');poll();}
  function poll(){clearTimeout(timer);if(!batch||!batch.stages.some(s=>['queued','processing'].includes(s.state)))return;
    const id=batch.id;timer=setTimeout(async()=>{if(busy){poll();return;}try{const r=await api(`/api/photo-batches/${id}/`);if(batch?.id===id){batch=r.batch;render();poll();}}catch(e){status(e.message);}},1200);}
  function field(parent,label,type,value){const l=node('label',label),input=node('input',null,{type,'aria-label':label});input.value=value;l.append(input);parent.append(l);return input;}
  function choose(parent,label,options,current=''){const l=node('label',label),s=node('select',null,{'aria-label':label});options.forEach(([v,t])=>s.append(node('option',t,{value:v})));s.value=current;l.append(s);parent.append(l);return s;}
  function button(parent,text,fn){const b=node('button',text,{type:'button'});b.onclick=()=>work(fn);parent.append(b);return b;}
  function manualBox(){return {x:0.05,y:0.05,width:0.4,height:0.8,rotation:0,issues:[]};}
  function render(){
    $('photo-workspace').hidden=false;$('photo-capacity').textContent=`${batch.source_admissions} of 5 photo admissions used, including removed photos and retakes. ${batch.crops.filter(c=>c.state==='active').length} candidate crops. Unconfirmed expiry: ${new Date((batch.created+7*86400)*1000).toLocaleString()}.`;
    $('photo-protocol').textContent=`Codex CLI · ${batch.model} · ${batch.attempts}/10 attempts reserved. Batch active time remaining: ${batch.remaining_active_seconds.toFixed(1)} seconds.`;
    $('photo-duplicates').checked=false;
    const link=$('photo-review-link');link.hidden=!batch.draft_id;if(batch.draft_id)link.href='/add-many/?draft='+batch.draft_id;
    $('photo-photos').replaceChildren();
    for(const [index,p] of batch.photos.entries()){
      const panel=node('article',null,{'class':'photo-panel'});panel.append(node('h3',`Photo ${index+1} · ${p.state}`),node('p',`${(p.source_bytes/1000000).toFixed(2)} MB source · ${p.remaining_active_seconds.toFixed(1)} active seconds remaining · detection ${p.stage_attempts.detection}/2, identity ${p.stage_attempts.identity}/2 attempts.`));$('photo-photos').append(panel);
      if(p.state!=='active'||['cancelled','expired','confirmed'].includes(batch.state))continue;
      button(panel,'Move photo earlier',async()=>{const ids=batch.photos.filter(p=>p.state==='active').map(p=>p.id),at=ids.indexOf(p.id);if(at>0){[ids[at-1],ids[at]]=[ids[at],ids[at-1]];await act('reorder',{revision:batch.revision,photo_ids:ids});}});
      const retake=field(panel,'Retake file for these same physical objects','file','');retake.accept='image/jpeg,image/png,image/webp';
      const same=field(panel,'This retake shows the same physical objects; retain their crop IDs for correction','checkbox','');
      button(panel,'Stage retake of these objects',async()=>{if(!retake.files[0]||!same.checked)throw Error('Select a retake and confirm the same physical objects.');const f=new FormData();f.append('photo',retake.files[0]);f.append('photo_id',p.id);f.append('revision',batch.revision);f.append('same_objects','true');const r=await api(`/api/photo-batches/${batch.id}/retake/`,f);batch=r.batch;render();status('Retake staged; crop IDs retained. Correct and confirm the new layout/count.');});
      const crops=batch.crops.filter(c=>c.photo_id===p.id&&c.state==='active');
      const figure=node('div',null,{'class':'photo-source'});figure.append(node('img',null,{src:`/api/photo-batches/${batch.id}/photos/${p.id}/`,alt:`Staged source photo ${index+1}`}));panel.append(figure);
      let edits=crops.map(c=>({id:c.id,box:{...c.geometry}}));
      const geometry=node('details');geometry.append(node('summary','Adjust crop boxes and rotations'));const editor=node('div');geometry.append(editor);panel.append(geometry);
      function draw(){editor.replaceChildren();figure.querySelectorAll('.photo-outline').forEach(e=>e.remove());
        edits.forEach((entry,i)=>{const outline=node('div',null,{'class':'photo-outline'});outline.append(node('span',String(i+1)));Object.assign(outline.style,{left:entry.box.x*100+'%',top:entry.box.y*100+'%',width:entry.box.width*100+'%',height:entry.box.height*100+'%'});figure.append(outline);
          const group=node('fieldset');group.append(node('legend',`Photo ${index+1}, box ${i+1}`));const grid=node('div',null,{'class':'photo-grid'});group.append(grid);
          for(const k of ['x','y','width','height']){const f=field(grid,k+' · normalized 0 to 1','number',entry.box[k]);f.min='0';f.max='1';f.step='.001';f.onchange=()=>{entry.box[k]=Number(f.value);};}
          const rotation=choose(grid,'Clockwise rotation',[0,90,180,270].map(v=>[String(v),v+'°']),String(entry.box.rotation));rotation.onchange=()=>{entry.box.rotation=Number(rotation.value);};
          for(const issue of ['glare','overlap','cut_off','unreadable']){const f=field(group,issue.replace('_',' '),'checkbox','');f.checked=entry.box.issues.includes(issue);f.onchange=()=>{entry.box.issues=f.checked?[...new Set([...entry.box.issues,issue])]:entry.box.issues.filter(x=>x!==issue);};}
          const del=node('button','Delete this box',{type:'button'});del.onclick=()=>{edits.splice(i,1);draw();};group.append(del);editor.append(group);
        });
      }
      draw();
      button(panel,'Add a manual box',async()=>{if(edits.length>=15)throw Error('Maximum 15 cards per photo; retake a smaller layout.');edits.push({id:null,box:manualBox()});draw();});
      if(p.proposal.boxes){panel.append(node('p',`Detection: ${p.proposal.status}. Proposals are not confirmed cards.`));button(panel,'Use proposed boxes for correction',async()=>{edits=p.proposal.boxes.map(box=>({id:null,box}));draw();});}
      button(panel,`Confirm layout and count for photo ${index+1}`,async()=>{await act('layout',{revision:batch.revision,photo_id:p.id,boxes:edits});status('Crop layout confirmed; choose identities manually or explicitly request identity proposals.');});
      for(const [stage,label] of [['detection','Analyze overview for detection'],['identity','Analyze reviewed crops for identity']]){
        button(panel,`${label} · photo ${index+1}`,async()=>{if(!$('photo-consent').checked)throw Error('Review the transmission notice and select its consent checkbox first.');await act('analyze',{revision:batch.revision,photo_id:p.id,stage,consent:batch.consent_version});$('photo-consent').checked=false;status('Analysis admitted. Stop remains available.');poll();});}
      button(panel,'Remove this photo · admission remains used',async()=>{await act('remove',{revision:batch.revision,photo_id:p.id});status('Photo access revoked and unretained bytes removed.');});
      for(const [i,c] of crops.entries()){
        const card=node('article',null,{'class':'photo-crop','data-crop-id':c.id});card.append(node('h4',`Photo ${index+1}, crop ${i+1} · ${c.id.slice(0,8)}`),node('img',null,{src:'/scan-photos/'+c.id+'/',alt:`Reviewed crop ${i+1} from photo ${index+1}`}));
        card.append(node('p','Visible clues: '+(Object.keys(c.proposal).length?[c.proposal.status,...['name','set_name','number','language','edition','finish','variant'].map(k=>c.proposal[k]?k.replace('_',' ')+': '+c.proposal[k]:null).filter(Boolean),c.proposal.reason].filter(Boolean).join(' · '):'None. Manual matching available.')+(c.geometry.issues.length?' · Issues: '+c.geometry.issues.join(', '):'')));
        const d=choose(card,'Physical copy decision',[['','Choose explicitly'],['different','Different copy · include only after matching'],['same','Same physical card · exclude this duplicate'],['unsure','Not sure · exclude for now']],c.decision);
        const search=field(card,'Find a catalog card · name, set or number','search','');
        const select=choose(card,'Supported catalog printing',[['','Unresolved · choose manually']],c.row_json.printing_id||'');
        function choices(){const q=search.value.toLowerCase();const suggested=new Set(c.candidates.map(p=>p.id));const options=catalog.flatMap(g=>g.children.map(p=>({...p,group:g}))).filter(p=>q?`${p.group.name} ${p.group.set_name} ${p.group.collector_number}`.toLowerCase().includes(q):suggested.has(p.id)||p.id===c.row_json.printing_id).slice(0,100);select.replaceChildren(node('option','Unresolved · choose manually',{value:''}));for(const p of options)select.append(node('option',`${p.group.set_name} · #${p.group.collector_number} ${p.group.name} · ${p.edition??'edition unknown'} / ${p.finish??'finish unknown'} / ${p.variant??'variant unknown'}`,{value:p.id}));select.value=c.row_json.printing_id||'';}
        choices();search.oninput=choices;
        const unknown=choose(card,'Or keep catalog variant unknown',[['','Choose a card first'],...catalog.filter(g=>{const q=search.value.toLowerCase();return g.id===c.row_json.group_id||(q&&`${g.name} ${g.set_name} ${g.collector_number}`.toLowerCase().includes(q));}).slice(0,100).map(g=>[g.id,`${g.set_name} #${g.collector_number} ${g.name}`])],c.row_json.group_id||'');
        search.addEventListener('input',()=>{unknown.replaceChildren(node('option','Unresolved · optional broad card identity',{value:''}));catalog.filter(g=>search.value&&`${g.name} ${g.set_name} ${g.collector_number}`.toLowerCase().includes(search.value.toLowerCase())).slice(0,100).forEach(g=>unknown.append(node('option',`${g.set_name} #${g.collector_number} ${g.name}`,{value:g.id})));});
        const identityText=node('p');card.append(identityText);
        function showIdentity(){identityText.textContent=unknown.value?'Chosen card: '+unknown.selectedOptions[0].textContent+' · catalog variant remains unknown.':select.value?'Chosen printing: '+select.selectedOptions[0].textContent:'Identity unresolved. Match manually or exclude this crop.';}
        select.addEventListener('change',()=>{unknown.value='';showIdentity();});unknown.addEventListener('change',()=>{select.value='';showIdentity();});search.addEventListener('input',showIdentity);showIdentity();
        const include=field(card,'Include this one physical card','checkbox','');include.checked=!!c.included;
        const retain=field(card,'Retain this selected crop with its copy after Confirm','checkbox','');retain.checked=!!c.retain;
        button(card,'Save crop choice',async()=>{const row=unknown.value?{group_id:unknown.value,keep_unknown:true}:select.value?{printing_id:select.value}:{};await act('select',{revision:batch.revision,crop_id:c.id,row,included:include.checked,retain:retain.checked,decision:d.value});status('Human crop choice saved. Nothing added to collection.');});
        panel.append(card);
      }
    }
    $('photo-pairs').replaceChildren();
    for(const pair of batch.possible_duplicates){
      const panel=node('article',null,{'class':'photo-panel'});panel.append(node('h3','Possible same physical card'),node('p',`${pair.same_printing?'Matching printing identity. ':''}${pair.similar_pixels?'Similar crop pixels. ':''}These are hints, not physical verification. Review both thumbnails.`));
      for(const id of [pair.first,pair.second])panel.append(node('img',null,{src:'/scan-photos/'+id+'/',alt:'Duplicate review crop '+id.slice(0,8),width:'120'}));
      async function decision(id,include,choice){const crop=batch.crops.find(c=>c.id===id);const row={...crop.row_json};for(const k of ['row_id','quantity','action','included','duplicate_decision'])delete row[k];await act('select',{revision:batch.revision,crop_id:id,row,included:include,retain:include&&!!crop.retain,decision:choice});}
      button(panel,'Same card · keep first and exclude second',async()=>{await decision(pair.second,false,'same');status('Second crop excluded as the same physical card. Review the first crop inclusion separately.');});
      button(panel,'Different copies · keep both matched cards',async()=>{await decision(pair.first,true,'different');await decision(pair.second,true,'different');status('Both included as different physical copies.');});
      button(panel,'Not sure · exclude both for now',async()=>{await decision(pair.first,false,'unsure');await decision(pair.second,false,'unsure');status('Both crops excluded for now.');});
      $('photo-pairs').append(panel);
    }
    for(const stage of batch.stages){$('photo-photos').append(node('p',`${stage.stage}: ${stage.state}${stage.error?' · '+stage.error:''}. Active seconds: ${stage.elapsed??'Unknown'}. Reported usage: ${stage.usage&&stage.usage!=='null'?stage.usage:'Unknown'}.`));}
    if(batch.draft_id||batch.state!=='editing')status('Photo batch '+batch.state+'. Use the shared review/receipt link when available.');
  }
  $('photo-new').onclick=()=>work(async()=>{const r=await api('/api/photo-batches/create/',{id:crypto.randomUUID()});batch=r.batch;history.replaceState(null,'','/add-photos/?batch='+batch.id);render();await saved();status('Empty photo batch created. Collection unchanged.');});
  $('photo-upload').onclick=()=>work(async()=>{const f=$('photo-file').files[0];if(!f)throw Error('Select one photo.');if(f.size>8000000)throw Error('Each photo must be at most 8 MB.');const data=new FormData();data.append('photo',f);data.append('revision',batch.revision);const r=await api(`/api/photo-batches/${batch.id}/upload/`,data);batch=r.batch;$('photo-file').value='';render();status('Photo staged locally. No analysis requested.');});
  // Deliberately bypasses the ordinary busy guard and needs no draft revision.
  $('photo-stop').onclick=async()=>{try{await act('stop');clearTimeout(timer);status('Stop recorded. Transmitted images cannot be recalled; attempts remain consumed.');}catch(e){status(e.message);}};
  $('photo-delete-images').onclick=()=>work(async()=>{await act('delete-images');status('Image access revoked and bytes removed. Confirmed collection records remain.');});
  $('photo-cancel').onclick=()=>work(async()=>{await act('cancel');await saved();status('Cancelled. Image access revoked; cleanup and consumed attempt history retained.');});
  $('photo-handoff').onclick=()=>work(async()=>{let rows=[];const text=$('photo-manual').value;if(text.trim()){const parsed=await api('/api/bulk/parse/',{input:{source:'csv',text}});rows=parsed.input.rows;}const r=await act('handoff',{revision:batch.revision,duplicates_reviewed:$('photo-duplicates').checked,manual_rows:rows});location.assign('/add-many/?draft='+r.draft.id);});
  window.addEventListener('dex:authority-revoked',erase);
  work(async()=>{const r=await api('/api/bulk/catalog/');catalog=r.groups;await saved();const id=new URLSearchParams(location.search).get('batch');if(id)await resume(id);else status('Start or resume a photo batch. Manual entry needs no Codex.');});
})();
