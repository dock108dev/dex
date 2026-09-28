'use strict';
const $ = s => document.querySelector(s);
const escapeText = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const stateLabel = s => ({queued:'Queued',processing:'Processing', 'needs-confirmation':'Ready to review','needs-better-photo':'A clearer photo would help',unsupported:'No supported match',failed:'Recognition failed',cancelled:'Cancelled',confirmed:'Added to collection'}[s] || s);
let current = null, catalog = [], copies = [], timer;
const token = () => $('input[name=csrfmiddlewaretoken]').value;
async function api(url, data) {
  const options = data === undefined ? {} : {method:'POST',headers:{'X-CSRFToken':token()},body:data instanceof FormData ? data : JSON.stringify(data)};
  if (data !== undefined && !(data instanceof FormData)) options.headers['Content-Type']='application/json';
  const r = await fetch(url, options); const value = await r.json();
  if (!r.ok) throw new Error(value.error || 'Request unavailable. Reload and try again.');
  return value;
}
function fail(e) { $('#status').textContent=e.message; }
async function refreshHistory() {
  const data = await api('/api/scans/');
  $('#history').innerHTML=data.jobs.map(j=>`<p><button class="secondary" data-job="${j.id}">${escapeText(new Date(j.created*1000).toLocaleString())} · ${escapeText(stateLabel(j.state))}${j.mode==='fixture'?' · simulated':''}</button></p>`).join('') || '<p>No photo entries yet.</p>';
  document.querySelectorAll('[data-job]').forEach(b=>b.onclick=()=>openJob(b.dataset.job).catch(fail));
}
async function openJob(id) {
  clearTimeout(timer); current=await api(`/api/scans/${id}/`); location.hash=id; render();
  if (['queued','processing'].includes(current.state)) timer=setTimeout(()=>openJob(id).catch(fail),1500);
}
function render() {
  const j=current, r=j.result, done=!!j.operation_id;
  $('#current').innerHTML=`<h2>Review photo entry</h2><p><strong>${escapeText(stateLabel(j.state))}</strong> ${j.mode==='fixture'?'· SIMULATED':''}</p><p>${escapeText(j.error || r.notice || '')}</p><div class="scan-photos">${j.photos.map(id=>`<img alt="Your uploaded card" src="/scan-photos/${id}/" style="max-width:220px;max-height:300px;object-fit:contain">`).join('')}</div>${r.clues?`<p>Visible clues: ${escapeText([r.clues.name,r.clues.set_name,r.clues.number,r.clues.language,r.clues.edition,r.clues.finish,r.clues.variant].filter(Boolean).join(' · '))}</p>`:''}<p>Edition, language, finish and variant remain unresolved. A catalog choice does not verify an exact variant. No condition, authenticity, grade or price is inferred.</p>`;
  if (done) {
    $('#current').insertAdjacentHTML('beforeend',`<p>${j.operation.state==='undone'?'Addition undone.':'One copy added to your collection.'} <a href="/">Open collection</a></p>${j.operation.state==='confirmed'?'<button data-action="undo">Undo this addition</button>':''}<button data-action="delete-photos">Delete retained photos</button>`);
  } else if (j.state !== 'cancelled') {
    if (!['queued','processing'].includes(j.state)) {
      $('#current').insertAdjacentHTML('beforeend',`<h3>Candidates and alternatives</h3>${(r.candidates||[]).map(c=>`<p><button class="secondary" data-candidate="${c.id}">${escapeText(c.name)} · ${escapeText(c.set_name)} #${escapeText(c.collector_number)}</button></p>`).join('') || '<p>No supported match. Search manually or save unidentified.</p>'}<label>Search supported catalog<input id="search" placeholder="Card name, set or number"></label><label>Reviewed card<select id="selection"><option value="">Save unidentified card · private provisional copy</option></select></label><p id="duplicate"></p><label>Notes / identity corrections<textarea id="notes" maxlength="4000"></textarea></label><label><input id="reviewed" type="checkbox"> I reviewed the photo and selection; add one physical copy.</label><button id="add-copy" disabled>Confirm one copy</button>${j.state==='failed'&&j.attempts<2?'<button data-action="retry">Retry recognition</button>':''}`);
      const fill = () => {
        const q=$('#search').value.toLowerCase();
        const selected=$('#selection').value;
        $('#selection').innerHTML='<option value="">Save unidentified card · private provisional copy</option>'+catalog.filter(p=>(p.name+' '+p.set_name+' '+p.collector_number).toLowerCase().includes(q)).slice(0,100).map(p=>`<option value="${p.id}">${escapeText(p.name)} · ${escapeText(p.set_name)} #${escapeText(p.collector_number)}</option>`).join('');
        if ([...$('#selection').options].some(o=>o.value===selected)) $('#selection').value=selected;
        duplicate();
      };
      const duplicate=()=> { const n=copies.filter(c=>c.printing_id===$('#selection').value).length; $('#duplicate').textContent=n?`${n} existing copies. Confirming intentionally adds another physical copy.`:'This confirmation adds one physical copy.'; $('#reviewed').checked=false; $('#add-copy').disabled=true; };
      fill(); $('#search').oninput=fill; $('#selection').onchange=duplicate;
      document.querySelectorAll('[data-candidate]').forEach(b=>b.onclick=()=>{$('#search').value='';fill();const p=catalog.find(p=>p.id===b.dataset.candidate); if (![...$('#selection').options].some(o=>o.value===p.id)) $('#selection').add(new Option(`${p.name} · ${p.set_name} #${p.collector_number}`,p.id)); $('#selection').value=p.id; duplicate();});
      $('#reviewed').onchange=()=>$('#add-copy').disabled=!$('#reviewed').checked;
      $('#add-copy').onclick=()=>mutate('confirm',{printing_id:$('#selection').value,notes:$('#notes').value}).catch(fail);
    }
    $('#current').insertAdjacentHTML('beforeend','<button data-action="cancel">Cancel and delete uploads</button>');
  }
  if (document.body.dataset.expansion==='true' && !['queued','processing','cancelled'].includes(j.state)) $('#current').insertAdjacentHTML('beforeend',`<p><a href="/requests/?origin=scan&origin_id=${j.id}">Request catalog support</a></p>`);
  document.querySelectorAll('[data-action]').forEach(b=>b.onclick=()=>mutate(b.dataset.action,{}).catch(fail));
}
async function mutate(action, data) {
  const id=current.id;
  document.querySelectorAll('#current button').forEach(b=>b.disabled=true);
  try { current=await api(`/api/scans/${id}/${action}/`,data); render(); await refreshHistory(); copies=(await api('/api/collection/')).copies; if(current.state==='queued') await openJob(id); }
  catch(e) {render();throw e;}
}
$('#camera').onclick=()=> { const input=$('input[name=front]');input.setAttribute('capture','environment');input.click();setTimeout(()=>input.removeAttribute('capture'),1000); };
let uploadKey=crypto.randomUUID();
$('#upload').onchange=()=>uploadKey=crypto.randomUUID();
$('#upload').onsubmit=async e=> {e.preventDefault(); const button=$('#upload button:last-child');button.disabled=true;try { const data=new FormData(e.target); if(!data.get('back').size)data.delete('back');data.set('job_id',uploadKey);const job=await api('/api/scans/',data);uploadKey=crypto.randomUUID();await openJob(job.id);await refreshHistory();$('#status').textContent='Photo saved privately. Review before adding.';}catch(e){fail(e);}finally{button.disabled=false;}};
(async()=>{catalog=(await api('/api/catalog/')).printings;copies=(await api('/api/collection/')).copies;await refreshHistory();if(location.hash)await openJob(location.hash.slice(1));})().catch(fail);
