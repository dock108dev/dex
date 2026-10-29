'use strict';
/* V2 transport and explicit continuation. Tokens bind reads, never authorize them. */
(() => {
  const escape = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const revisions = ['catalog_revision','account_revision','generation'];
  function message(status, body) {
    if(status===503 && body?.code==='read_state_unavailable')return 'Browsing is unavailable. Explicit catalog and collection preparation or recovery is needed. Reload after preparation is complete.';
    if(status===409)return 'These records changed. Reload the current selection before continuing.';
    if(status===403)return 'This account no longer has access. Sign in again.';
    if(status===404)return 'This record is unavailable to the current account.';
    return body?.error || 'The request could not complete. Retry explicitly.';
  }
  function revoked(){
    window.discardNavigationAuthority?.();
    for(const id of ['content','current','history'])document.getElementById(id)?.replaceChildren();
    const host=document.getElementById('content');
    if(host){const notice=document.createElement('p');notice.setAttribute('role','alert');notice.textContent='This account no longer has access. Sign in again.';const link=document.createElement('a');link.href='/login/?next='+encodeURIComponent(location.pathname+location.search);link.textContent='Sign in';const retry=document.createElement('button');retry.id='card-retry';retry.textContent='Reload current selection';retry.onclick=()=>location.reload();host.append(notice,link,retry);}
  }
  class Reader {
    constructor({active=()=>true, seed=null, publicRead=false}={}) {this.active=active;this.state=seed;this.publicRead=publicRead;this.controllers=new Map();this.disposed=false;}
    stop(){this.disposed=true;for(const controller of this.controllers.values())controller.abort();this.controllers.clear();}
    async get(path, channel=path) {
      if(this.disposed||!this.active()||window.navigationAuthorityDiscarded)throw new DOMException('Obsolete read','AbortError');
      const url=new URL(path,location.origin);
      if(url.origin!==location.origin||!url.pathname.startsWith(this.publicRead?'/api/v2/public/':'/api/v2/'))throw Error('Unsupported read destination.');
      for(const key of revisions)if(this.state?.[key]!=null)url.searchParams.set(key,String(this.state[key]));
      this.controllers.get(channel)?.abort();const controller=new AbortController();this.controllers.set(channel,controller);
      const response=await fetch(url.pathname+url.search,{credentials:'same-origin',cache:'no-store',headers:!this.publicRead&&(this.state?.account_id||document.body?.dataset?.navigationAccount)?{'X-Dex-Read-Account':this.state?.account_id||document.body.dataset.navigationAccount}:{},signal:controller.signal});
      if(response.status===403||response.redirected){this.stop();revoked();}
      let body;try{body=await response.json();}catch{body={};}
      if(!response.ok||response.redirected){const error=Error(message(response.redirected?403:response.status,body));error.status=response.status;error.code=body.code;throw error;}
      if(this.disposed||!this.active()||window.navigationAuthorityDiscarded||this.controllers.get(channel)!==controller)throw new DOMException('Obsolete read','AbortError');
      if(body.read_version!==2||body.public!==this.publicRead)throw Error('The browsing response is unavailable.');
      const principal=document.body?.dataset?.navigationAccount;
      if(!this.publicRead&&((principal&&body.account_id!==principal)||(this.state?.account_id&&body.account_id!==this.state.account_id))){this.stop();revoked();const error=Error(message(403));error.status=403;throw error;}
      if(this.state && ['account_id',...revisions].some(key=>this.state[key]!=null&&body[key]!==this.state[key])){const error=Error(message(409));error.status=409;throw error;}
      this.state=body;this.controllers.delete(channel);return body;
    }
  }
  function context(result) {
    return {context_only:true,read_state:result,effective_collection:{user_id:result.account_id,generation:result.generation,cards:[]},binders:[],copies:[],goals:[]};
  }
  function next(path,result){if(result.next!==undefined)return result.next;if(result.page>=result.pages)return null;const url=new URL(path,location.origin);url.searchParams.set('page',result.page+1);url.searchParams.set('page_size',result.page_size);return url.pathname+url.search;}
  function overflow(row){return `<a href="${escape(row.url)}">Open complete record ${escape(row.id||'')}</a>`;}
  function paged(host,{reader,url,field,render,bind=()=>{},active=()=>host.isConnected}){
    let destination=url,loading=false;
    const rows=document.createElement('div'),button=document.createElement('button'),notice=document.createElement('p');
    button.type='button';button.className='secondary';button.textContent='Load records';notice.setAttribute('role','status');host.append(rows,notice,button);
    button.onclick=async()=>{
      if(loading||!destination)return;loading=true;button.disabled=true;notice.textContent='Loading…';
      try{const result=await reader.get(destination);if(!active())return;
        rows.insertAdjacentHTML('beforeend',(result[field]||[]).map(row=>row.oversized?`<p><button type="button" class="secondary" data-full-record="${escape(row.url)}">Open complete record ${escape(row.id||'')}</button></p>`:render(row,result)).join(''));
        rows.querySelectorAll('[data-full-record]').forEach(full=>full.onclick=async()=>{full.disabled=true;try{const response=await reader.get(full.dataset.fullRecord);if(!active())return;const holder=full.parentElement;holder.innerHTML=render(response.record);bind(rows,result);}catch(error){if(active()){notice.textContent=error.message;full.disabled=false;}}});
        bind(rows,result);destination=next(destination,result);notice.textContent=`${result.total} records · page ${result.page} of ${Math.max(1,result.pages)}`;
        button.hidden=!destination;button.textContent='Load next page';
      }catch(error){if(active()&&error.name!=='AbortError'){notice.textContent=error.message;button.textContent='Retry this page';}}
      finally{loading=false;button.disabled=false;}
    };
    return button;
  }
  // Options are deliberately paged by user action; selected literals never disappear.
  function options(control,{reader,url,active=()=>control.isConnected}){
    const host=document.createElement('div');control.after(host);
    if(reader.publicRead&&control.value){const selected=control.value,labelURL=new URL(url,location.origin);labelURL.searchParams.set('value',selected);reader.get(labelURL.pathname+labelURL.search).then(result=>{if(!active()||control.value!==selected)return;const row=result.options.find(r=>r.value===selected);if(row)control.selectedOptions[0].textContent=row.label;else if(!result.options.some(r=>r.oversized))control.selectedOptions[0].textContent='Unavailable retained selection';}).catch(()=>{});}

    return paged(host,{reader,url,field:'options',active,render:row=>`<button type="button" class="secondary" data-option-value="${escape(row.value)}" data-option-label="${escape(row.label)}">${escape(row.label)}</button>`,bind:rows=>{
      rows.querySelectorAll('[data-option-value]').forEach(button=>button.onclick=()=>{
        if(![...control.options].some(o=>o.value===button.dataset.optionValue))control.add(new Option(button.dataset.optionLabel,button.dataset.optionValue));
        control.value=button.dataset.optionValue;control.dispatchEvent(new Event('change',{bubbles:true}));
      });
    }});
  }
  function artwork(reader,host,kind='group'){
    if(typeof IntersectionObserver==='undefined')return;
    const tiles=[...host.querySelectorAll(kind==='species'?'[data-dex-species]':'[data-group-id]')].filter(e=>e.querySelector('.image-frame'));
    const ids=[...new Set(tiles.map(e=>kind==='species'?e.dataset.dexSpecies:e.dataset.groupId))];if(!ids.length)return;
    let observer;const pending=[],seen=new Set();let running=0;
    const pump=()=>{while(running<4&&pending.length){const {tile,ref}=pending.shift();if(!tile.isConnected||reader.disposed)continue;running++;const frame=tile.querySelector('.image-frame'),img=document.createElement('img');img.alt=ref.alt||'Card reference';img.width=Number(ref.width)||245;img.height=Number(ref.height)||337;img.decoding='async';img.referrerPolicy='no-referrer';const complete=failed=>{running--;if(failed){img.remove();frame.classList.add('unavailable');frame.setAttribute('aria-label','Card image unavailable');}pump();};img.onload=()=>complete(false);img.onerror=()=>complete(true);frame.replaceChildren(img);frame.classList.remove('unavailable');img.src=ref.image_url;}};
    const key=kind+':'+ids.join(',');reader.artworkReads??=new Map();if(!reader.artworkReads.has(key))reader.artworkReads.set(key,reader.get((reader.publicRead?'/api/v2/public/':'/api/v2/')+kind+'-artwork/?'+new URLSearchParams({ids:ids.join(',')}),'artwork:'+key));
    reader.artworkReads.get(key).then(result=>{
      if(reader.disposed||!host.isConnected)return;
      observer=new IntersectionObserver(entries=>{for(const entry of entries)if(entry.isIntersecting){observer.unobserve(entry.target);const tile=entry.target,ref=result.artwork[kind==='species'?tile.dataset.dexSpecies:tile.dataset.groupId];if(ref?.image_url&&!seen.has(tile)){seen.add(tile);pending.push({tile,ref});}}pump();},{rootMargin:'100px'});
      for(const tile of tiles){const ref=result.artwork[kind==='species'?tile.dataset.dexSpecies:tile.dataset.groupId];if(ref?.image_url)observer.observe(tile);else tile.querySelector('.image-frame').setAttribute('aria-label','Card image unavailable');}
    }).catch(error=>{if(error.name!=='AbortError'&&host.isConnected){const notice=document.createElement('p');notice.textContent='Card images unavailable. ';const retry=document.createElement('button');retry.type='button';retry.textContent='Retry images';retry.onclick=()=>{notice.remove();reader.artworkReads.delete(key);artwork(reader,host,kind);};notice.append(retry);host.append(notice);}});
    addEventListener('pagehide',()=>observer?.disconnect(),{once:true});
  }
  async function labelControls(reader,controls){
    const items=[];for(const {element,kind} of controls)for(const option of element.selectedOptions||[])if(option.value&&!items.some(i=>i.kind===kind&&i.id===option.value))items.push({kind,id:option.value});
    if(!items.length)return;
    const result=await reader.get('/api/v2/labels/?'+new URLSearchParams({items:JSON.stringify(items)}));
    for(const {element,kind} of controls){if(!element.isConnected)continue;for(const option of element.options)if(option.selected){const item=result.labels.find(i=>i.kind===kind&&i.id===option.value);if(item){option.textContent=item.label||'Unavailable retained selection';if(item.oversized&&!element.parentElement.querySelector('[data-selected-label-record]')){const link=document.createElement('a');link.dataset.selectedLabelRecord='true';link.href=item.url;link.textContent='Open complete selected label';element.after(link);}}}}
  }
  window.BoundedReads={Reader,context,next,overflow,paged,options,message,labelControls,artwork};
})();
