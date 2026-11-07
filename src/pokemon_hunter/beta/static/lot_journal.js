/* Leased, account-bound decisions. No browser storage or reference-value copies. */
(() => {
  const host=document.getElementById('lot-journal');if(!host)return;
  const page=document.body,binding=page.dataset.navigationBinding,account=page.dataset.navigationAccount;
  let active=true,busy=false,rows=[];
  const labels={reviewing:'Reviewed separately',shortlisted:'Shortlisted',needs_evidence:'Needs evidence',passed:'Passed'};
  const node=(tag,text)=>{const n=document.createElement(tag);n.textContent=text;return n;};
  function draw(){
    rows=rows.filter(r=>r.deadline>Date.now());host.replaceChildren();
    if(!rows.length)host.append(node('p','No retained decisions. Review a search result to start your shortlist.'));
    document.querySelectorAll('.lot-review-status').forEach(n=>n.remove());
    for(const row of rows){
      const section=node('section','');section.append(node('h3',row.title),node('p',labels[row.decision] || 'Reviewed separately'));
      section.append(node('p',`${row.budget || 'No'} USD ${row.budget_mode==='flexible'?'baseline':'limit'} · ${row.budget_rule || 'No exception rule'} · ${row.budget_value_basis==='resale'?'Net resale proceeds':'Collectible value'} · ${Math.ceil((row.deadline-Date.now())/60000)} minutes remaining`));
      if(row.notes)section.append(node('p',row.notes));
      const a=node('a','Reopen this review');a.href='/shopping/check/?'+new URLSearchParams({discovery_run:row.run_id,item_id:row.result_id,return:location.pathname==='/shopping/'?location.pathname+location.search:'/shopping/'});section.append(a);host.append(section);
      const offer=document.getElementById('offer-'+row.result_id);if(offer){const p=node('p','Separate review: '+(labels[row.decision] || 'Reviewed'));p.className='lot-review-status';offer.append(p);}
    }
  }
  async function refresh(){
    if(!active || busy || document.hidden)return;busy=true;
    try{const response=await fetch('/api/shopping/listing/journal/',{credentials:'same-origin',cache:'no-store',headers:{'X-Dex-Shopping-Binding':binding}});
      if(!response.ok)throw Error('Decisions unavailable. Refresh to check again.');
      const value=await response.json();if(!active || document.body!==page || value.authority?.binding!==binding || String(value.authority?.account_id)!==String(account))return;
      rows=value.entries.map(r=>({...r,deadline:Date.now()+r.expires_in_seconds*1000}));draw();
    }catch(e){rows=[];draw();host.replaceChildren(node('p',e.message));}finally{busy=false;}
  }
  window.addEventListener('dex:authority-revoked',()=>{active=false;rows=[];host.replaceChildren();document.querySelectorAll('.lot-review-status').forEach(n=>n.remove());});
  document.getElementById('lot-journal-refresh').onclick=refresh;
  setInterval(()=>{if(active){draw();refresh();}},5000);refresh();
})();
