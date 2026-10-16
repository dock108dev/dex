/* Temporary assisted review. No local/session storage, provider HTML or raw history. */
(() => {
  const $ = id => document.getElementById(id), root = $('listing-check');
  const binding = JSON.parse($('check-binding').textContent), account = JSON.parse($('check-account').textContent);
  const csrf = root.querySelector('[name=csrfmiddlewaretoken]').value;
  const entry = JSON.parse($('check-entry').textContent);
  const fields = ['title','url','price','currency','shipping','tax','other_costs','planned_bid'];
  let cards = [], preview = null, run = null, stopped = false, active = true, version = 0, loadVersion = 0;
  let lease = null, detailRun = null, discoveryOrigin = null, sourceOrigin = null, sourceItem = null, buyNowPrice = '', buyNowCurrency = '', correcting = null, sellerCardCount = null, lotUnits = null, stockQuantity = null, remainderAuto = false, leaseChecking = false, ticks = 0, references = [], retentionDeadline = null, previewDeadline = null, searchVersion = 0, saveTimer, saved = Promise.resolve(), loading = false;
  const node = (tag, text) => {const n = document.createElement(tag); if(text !== undefined) n.textContent = text; return n;};
  const identityOnly = p => Object.fromEntries(['id','name','set_name','collector_number','language','edition','finish','variant','artwork'].map(k=>[k,p[k]]));
  const say = (text, error = false) => { $('check-status').textContent = text; $('check-status').setAttribute('role', error ? 'alert' : 'status'); };
  function revoke() {
    active = false; ++version; ++loadVersion; ++searchVersion; clearTimeout(saveTimer);
    cards = []; preview = null; discoveryOrigin=null;sourceOrigin=null;sourceItem=null;buyNowPrice='';buyNowCurrency='';root.querySelectorAll('input').forEach(n => n.value = '');$('review-buy-now').textContent='';$('review-source-counts').textContent='';$('check-context').textContent='';
    for(const id of ['review-cards','check-matches','listing-details','check-results']) $(id).replaceChildren();
    root.querySelectorAll('input,button,select').forEach(n => n.disabled = true);
    $('listing-preview').hidden = true; $('check-results').hidden = true;
    say('Your session changed. Sign in again to use Shopping.', true);
  }
  window.addEventListener('dex:authority-revoked', revoke);
  async function request(url, data, keepalive = false) {
    if(!active) throw Error('This page is no longer active.');
    const response = await fetch(url, {credentials:'same-origin', cache:'no-store', keepalive, headers:{'X-Dex-Shopping-Binding':binding, ...(data === undefined ? {} : {'Content-Type':'application/json','X-CSRFToken':csrf})}, ...(data === undefined ? {} : {method:'POST',body:JSON.stringify(data)})});
    if(response.redirected || [401,403].includes(response.status)) {revoke(); throw Error('Sign in again to continue.');}
    if(!response.headers.get('content-type')?.includes('application/json')) throw Error('The request could not finish. Your edits remain.');
    const value = await response.json();
    if(!response.ok) throw Error(value.error === 'Invalid request. Check the fields and import format.' ? 'Check whole quantities, amounts and the listing URL. Your edits remain.' : value.error || value.message || 'The request could not finish. Your edits remain.');
    if(!active) throw Error('This page is no longer active.');
    if(value.authority?.binding !== binding || value.authority?.account_id !== account) {revoke(); throw Error('Your session changed.');}
    return value;
  }
  function showContext(context) {const target=context?.selected_target;const selected=target?` · Selected exact printing: ${target.name} · ${target.set_name} #${target.collector_number} · ${[target.language,target.edition,target.finish,target.variant].filter(Boolean).join(' / ')}. The search target is not confirmed lot contents.`:'';$('check-context').textContent=(context?.scope_label || '')+selected; $('check-context').hidden=!context?.scope_label && !target;}
  function read() {
    return {...Object.fromEntries(fields.map(f => [f === 'url' ? 'listing_url' : f, $('review-'+f).value])), detail_run: detailRun, discovery_origin: discoveryOrigin, price_kind:$('review-price-kind').value, buy_now_price:buyNowPrice, buy_now_currency:buyNowCurrency, seller_card_count:sellerCardCount, lot_units:lotUnits, stock_quantity:stockQuantity, remainder_auto:remainderAuto, unknown_contents: $('review-unknown').value === '' ? null : Number($('review-unknown').value), cards:cards.map(({identity,...r}) => r)};
  }
  function invalidate() {++version; $('check-results').hidden = true; $('check-results').replaceChildren(); count();}
  function count() {
    $('review-price-label').textContent = $('review-price-kind').value === 'current_bid' ? 'Whole-lot current bid' : 'Whole-lot asking price';
    $('review-buy-now').hidden = !buyNowPrice;
    $('review-buy-now').textContent = `Separate buy-now asking price: ${buyNowPrice} ${buyNowCurrency}. This is not the auction current bid.`;
    const n = cards.reduce((s,r) => s + (Number(r.quantity) || 0),0);
    if(remainderAuto && sellerCardCount!==null)$('review-unknown').value=Math.max(0,sellerCardCount-n);
    $('review-source-counts').hidden=sellerCardCount===null && lotUnits===null && stockQuantity===null;
    $('review-source-counts').textContent=`Seller-stated card count: ${sellerCardCount ?? 'Unknown'} · eBay lot units: ${lotUnits ?? 'Unknown'} · Listing stock: ${stockQuantity ?? 'Unknown'}. ${remainderAuto?'Remainder follows the stated count until you edit it.':''}`;
    $('review-count').textContent = `${n} individually identified cards · unrecognized contents: ${$('review-unknown').value || 'Unknown'}. Whole-lot price is counted once.`;
  }
  async function persist(keepalive = false) {
    clearTimeout(saveTimer);
    const data = read();
    const job = saved.catch(() => {}).then(() => request('/api/shopping/listing/review/',{review:data,lease}, keepalive)).then(value => {
      retentionDeadline = Date.now() + value.expires_in_seconds * 1000;showContext(value.context);
    });
    saved = job; return job;
  }
  function changed() {invalidate(); clearTimeout(saveTimer); saveTimer = setTimeout(() => {persist().catch(e => say(e.message,true));},400);}
  function input(parent, label, value, fn, type='text') {
    const l=node('label',label), i=node('input'); i.type=type; i.value=value ?? ''; l.append(i);parent.append(l);
    i.addEventListener('input', () => {fn(type==='number' ? Number(i.value) : i.value);changed();}); return i;
  }
  function select(parent,label,value,options,fn) {
    const l=node('label',label), s=node('select');
    for(const [v,t] of options){const o=node('option',t);o.value=v;s.append(o);} s.value=value || '';
    l.append(s);parent.append(l);s.onchange=()=>{fn(s.value);changed();};return s;
  }
  function artwork(parent, p) {
    const frame=node('div');frame.className='review-art';
    const fallback=node('span','Reference image unavailable');frame.append(fallback);
    const art=p.artwork;
    if(art?.availability==='reference' && art.image_url){const img=node('img');img.src=art.image_url;img.alt=art.alt || `${p.name || 'Card'} catalog reference`;img.loading='lazy';img.decoding='async';img.referrerPolicy='no-referrer';img.onload=()=>fallback.hidden=true;img.onerror=()=>img.remove();frame.prepend(img);}
    parent.append(frame);
  }
  function renderCards() {
    $('review-cards').replaceChildren();
    cards.forEach((r,index) => {
      const box=node('div');box.className='review-card';
      const p=r.identity || {}, heading=node('h3', `${p.name || 'Selected card'} · ${p.set_name || ''} #${p.collector_number || ''} · ${[p.edition,p.finish,p.variant].filter(Boolean).join(' / ')}`);
      artwork(box,p);const content=node('div');content.className='review-card-content';content.append(heading);const grid=node('div');grid.className='traits';
      const includeLabel=node('label'), include=node('input');include.type='checkbox';include.checked=r.quantity>0;includeLabel.className='review-include';includeLabel.append(include,node('span',r.quantity>0?'Included':'Include this proposed card'));grid.append(includeLabel);
      include.onchange=()=>{r.quantity=include.checked?Math.max(1,r.quantity):0;renderCards();changed();$('review-cards').querySelectorAll('.review-include input')[index]?.focus();};
      const q=input(grid,'Cards inside this one lot',r.quantity,v=>{r.quantity=v;include.checked=v>0;includeLabel.lastChild.textContent=v>0?'Included':'Include this proposed card';},'number');q.min='0';q.max='100000';
      const attributes=node('details'), attributeGrid=node('div');attributeGrid.className='traits';attributes.append(node('summary',`${r.grade==='raw'?'Ungraded':r.grade?('Grade '+r.grade):'Unpriced'} · optional card details`),attributeGrid);
      select(attributeGrid,'Value basis',r.grade,[['raw','Ungraded'],['','Unknown / unpriced'],['8','Grade 8'],['9','Grade 9'],['10','Grade 10']],v=>{r.grade=v;attributes.querySelector('summary').textContent=`${v==='raw'?'Ungraded':v?('Grade '+v):'Unpriced'} · optional card details`;});
      select(attributeGrid,'Literal grader',r.grader,[['','Unknown / not graded'],['PSA','PSA'],['BGS','BGS'],['CGC','CGC'],['SGC','SGC']],v=>r.grader=v);
      input(attributeGrid,'Condition claim',r.condition,v=>r.condition=v);
      input(attributeGrid,'Language code (en, ja…)',r.language,v=>r.language=v);
      select(attributeGrid,'Edition claim',r.edition,[['','Unknown'],['unlimited','Unlimited'],['first_edition','First edition']],v=>r.edition=v);
      select(attributeGrid,'Finish claim',r.finish,[['','Unknown'],['normal','Non-holo'],['holo','Holo'],['reverse_holo','Reverse holo']],v=>r.finish=v);
      attributes.append(node('p','Claims remain unverified. Generic guides are independent scenarios, not exact slab matches.'));content.append(grid,attributes);
      const actions=node('div');actions.className='discovery-actions';const correct=node('button','Correct card');correct.type='button';correct.className='secondary';correct.onclick=()=>{correcting=index;$('check-query').value=[p.name,p.set_name,p.collector_number].filter(Boolean).join(' ');$('check-query').focus();say('Find the correct card below, then choose its printing.');};actions.append(correct);
      const remove=node('button','Remove card');remove.type='button';remove.className='secondary';remove.onclick=()=>{cards.splice(index,1);renderCards();changed();$('check-query').focus();};actions.append(remove);content.append(actions);box.append(content);$('review-cards').append(box);
    });count();
  }
  async function applyReview(value, identities=[]) {
    detailRun = value.detail_run || null;discoveryOrigin=value.discovery_origin || null;buyNowPrice=value.buy_now_price || '';buyNowCurrency=value.buy_now_currency || '';correcting=null;sellerCardCount=value.seller_card_count ?? null;lotUnits=value.lot_units ?? null;stockQuantity=value.stock_quantity ?? null;remainderAuto=value.remainder_auto===true;
    $('review-price-kind').value=value.price_kind || 'current_asking_price';
    for(const f of fields) $('review-'+f).value = value[f === 'url' ? 'listing_url' : f] ?? '';
    $('review-unknown').value=value.unknown_contents ?? '';
    const ids=value.cards.map(r=>r.printing_id);
    if(ids.length && !identities.length) {
      const params=new URLSearchParams();ids.forEach(id=>params.append('restore',id));
      identities=(await request('/api/shopping/listing/catalog/?'+params)).cards;
    }
    cards=value.cards.map(r=>({...r,identity:identities.find(p=>p.id===r.printing_id) ? identityOnly(identities.find(p=>p.id===r.printing_id)) : null}));
    renderCards();invalidate();
  }
  function showPreview(value) {
    preview=value;const out=$('listing-details'), kind=value.price_kind==='current_bid'?'Auction current bid':'Whole-lot asking price';
    $('listing-preview-heading').textContent=value.discovery_origin?'Selected temporary offer':'Loaded listing';
    out.replaceChildren(node('h3',value.title),node('p',`Exact item: ${value.item_id}`),node('p',`${kind}: ${value.price.amount ?? 'Unknown'} ${value.price.currency ?? ''} · Shipping: ${value.shipping.amount ?? 'Unknown'} ${value.shipping.currency ?? ''}`));
    if(value.price_kind==='current_bid' && value.buy_now?.amount!==null && value.buy_now?.amount!==undefined)out.append(node('p',`Separate buy-now asking price: ${value.buy_now.amount} ${value.buy_now.currency}. Current bid is not the final purchase cost.`));
    out.append(node('p',`Seller-stated card count: ${value.seller_lot_size ?? 'Unknown'} · eBay lot units (not necessarily cards): ${value.api_lot_size ?? 'Unknown'} · Listing stock: ${value.stock_quantity ?? 'Unknown'}`),node('p',`Condition claim: ${value.condition || 'Unknown'}`),node('p',`Identity cautions: ${value.clues.conflicts.join('; ') || 'Attributes remain seller claims'}`),node('p',`${value.proposals.length} proposed printing choices. Ambiguous choices stay excluded until you include them.`));
    const d=node('details');d.append(node('summary','Seller-stated item specifics'));
    value.aspects.forEach(a=>d.append(node('p',a.name+': '+a.value)));out.append(d);
    $('listing-preview').hidden=false;
  }
  function setLoading(value) {loading=value;$('load-listing').disabled=value;$('stop-listing').disabled=!value;}
  $('listing-load').onsubmit=async event=>{
    event.preventDefault();if(loading || !active)return;
    const expected=++loadVersion; stopped=false;setLoading(true);run=null;
    preview=null;$('listing-preview').hidden=true; say('Loading official eBay details… Your current review stays available.');
    try {
      let result=await request('/api/shopping/listing/',{identifier:$('listing-identifier').value});run=result.run_id;
      if(stopped || expected!==loadVersion){await request(`/api/shopping/listing/${run}/stop/`,{});return;}
      while(result.running && !stopped && expected===loadVersion) {
        await new Promise(resolve=>setTimeout(resolve,300));
        if(stopped || expected!==loadVersion)break;
        result=await request('/api/shopping/listing/?run_id='+encodeURIComponent(run));
      }
      if(stopped || expected!==loadVersion)return;
      if(result.listing){result.listing.detail_run=run;if(result.listing.item_id===sourceItem)result.listing.discovery_origin=sourceOrigin;previewDeadline=Date.now()+result.expires_in_seconds*1000;showPreview(result.listing);say('Listing loaded. Review the preview, then choose Use these details.');}
      else say(result.error || 'Listing details are unavailable. Manual review remains available.',true);
    } catch(e){if(expected===loadVersion && !stopped)say(e.message,true);}
    finally{if(expected===loadVersion)setLoading(false);}
  };
  $('stop-listing').onclick=async()=>{
    stopped=true;preview=null;$('listing-preview').hidden=true;++loadVersion;setLoading(false);
    const key=run;run=null;
    say('Stopped. No later listing details will be applied. Consumed attempts remain counted.');
    if(key)try{await request(`/api/shopping/listing/${key}/stop/`,{});}catch(e){say(e.message,true);}
  };
  $('discard-listing').onclick=()=>{preview=null;$('listing-preview').hidden=true;say('Your current review is unchanged.');};
  $('use-listing').onclick=async()=>{
    if(!preview || Date.now()>=previewDeadline)return;
    const p=preview,c=p.clues;
    // Ambiguous identities remain excluded. Stock is deliberately never used here.
    const known=p.proposals.length===1 ? p.proposals[0].quantity : 0;
    const currency=p.price.currency || p.shipping.currency || p.buy_now?.currency || 'USD';
    const value={seller_card_count:p.seller_lot_size ?? null,lot_units:p.api_lot_size===null || p.api_lot_size===undefined?null:Number(p.api_lot_size),stock_quantity:p.stock_quantity ?? null,remainder_auto:known!==1 && p.seller_lot_size!==null && p.seller_lot_size!==undefined,detail_run:p.detail_run || null,discovery_origin:p.discovery_origin || null,price_kind:p.price_kind || 'current_asking_price',planned_bid:'',buy_now_price:p.price_kind==='current_bid' ? p.buy_now?.amount || '' : '',buy_now_currency:p.buy_now?.currency || '',title:p.title,listing_url:p.item_url,price:p.price.amount || '',currency,shipping:p.shipping.currency===currency ? p.shipping.amount || '' : '',tax:'',other_costs:'',unknown_contents:known===1 ? 0 : p.seller_lot_size,cards:p.proposals.map(r=>({printing_id:r.id,quantity:r.quantity,condition:c.condition || '',grade:c.graded ? (c.conflicts?.length ? '' : c.grade || '') : 'raw',grader:c.grader || '',language:c.language || '',edition:c.edition || '',finish:c.finish || ''}))};
    await applyReview(value,p.proposals);preview=null;$('listing-preview').hidden=true;
    try{await persist();say('Details applied. Correct the cards and quantities, then compare.');}catch(e){if(discoveryOrigin || detailRun)await applyReview({currency:'USD',cards:[],unknown_contents:null});say(e.message,true);}
  };
  $('check-find').onsubmit=async event=>{
    event.preventDefault();const expected=++searchVersion;
    try{
      const value=await request('/api/shopping/listing/catalog/?q='+encodeURIComponent($('check-query').value));
      if(!active || expected!==searchVersion)return;
      $('check-matches').replaceChildren(node('p',`${value.total} matching printings. Refine the search if needed; showing up to 40.`));
      value.cards.map(identityOnly).forEach(p=>{const b=node('button');artwork(b,p);b.append(node('span',`${p.name} · ${p.set_name} #${p.collector_number} · ${[p.language,p.edition,p.finish,p.variant].filter(Boolean).join(' / ')}`));b.type='button';b.className='secondary check-match';b.onclick=()=>{
        const existing=cards.find(r=>r.printing_id===p.id), replacement=correcting!==null?cards[correcting]:null;
        if(replacement){if(existing && existing!==replacement){existing.quantity+=replacement.quantity;cards.splice(correcting,1);}else cards[correcting]={...replacement,printing_id:p.id,identity:p};correcting=null;}
        else if(existing)existing.quantity+=1;
        else cards.push({printing_id:p.id,quantity:1,grade:'raw',grader:'',condition:'',language:'',edition:'',finish:'',identity:p});
        renderCards();changed();say('Card included with Ungraded value basis. Review its quantity and optional details.');};$('check-matches').append(b);});
    }catch(e){say(e.message,true);}
  };
  $('check-compare').onclick=async()=>{
    const expected=version;$('check-compare').disabled=true;
    try{
      const data=read();await persist();const value=await request('/api/shopping/listing/compare/',{review:data,lease});
      if(expected!==version || !active)return;
      references=Object.values(value.scenarios).flatMap(s=>s.references.flatMap(r=>[r,...(r.conflicts || [])])).map(r=>({snapshot_version:r.snapshot_version,source_contract:r.source_contract,expires_at:r.expires_at}));
      const out=$('check-results');out.replaceChildren(node('h2','Reviewed comparison'),node('p',value.note));
      for(const [g,s] of Object.entries(value.scenarios)) {
        const r=s.result;if(g!=='raw' && !r.coverage.priced_units)continue;
        const part=node('div');part.append(node('h3',g==='raw'?'Ungraded':`Grade ${g} scenario`),node('p',`Priced subtotal: ${r.known_selected_subtotal ?? 'Unavailable'} USD · ${r.coverage.priced_units} of ${r.coverage.selected_units} identified units priced`),node('p',`Whole-lot reference total: ${r.full_lot_total ?? 'Unavailable; incomplete contents or pricing'}`));
        const c=r.comparisons.listing_observation;
        part.append(node('p',`${c.price_kind==='current_bid'?'Current bid plus known costs':'Asking amount plus known costs'}: ${c.full_delivered_cost ?? 'Unavailable'} USD · Missing or ineligible costs: ${c.unknown_or_ineligible_components.join(', ') || 'None'}`));
        if(r.full_lot_total!==null)part.append(node('p',`Complete reference minus observed delivered amount: ${c.full_selected_reference_minus_delivered_cost ?? 'Unavailable'} USD`));
        const planned=r.comparisons.planned_bid;if(read().planned_bid)part.append(node('p',`Planned manual bid with known costs: ${planned.full_delivered_cost ?? 'Unavailable'} USD. This is your proposed amount, not a final purchase cost or maximum bid.`));
        for(const ref of s.references){const p=node('p',`Reference: ${ref.amount} ${ref.currency} · ${ref.date_basis} ${ref.as_of} · Provider valuation date: ${ref.valuation_as_of ?? 'Unknown'} · Captured: ${ref.captured_at ?? 'Unknown'} · Expires: ${ref.expires_at ?? 'Unknown'} · ${ref.grader || 'Ungraded'} · Condition: ${ref.condition || 'Unknown'} · Language: ${ref.language || 'Unknown'} · Edition: ${ref.edition || 'Unknown'} · Finish: ${ref.finish || 'Unknown'} · Conditional physical applicability`);p.className='reference-note';part.append(p);}
        out.append(part);
      }
      out.hidden=false;say('Comparison updated from admitted local references. No prices were refreshed.');
    }catch(e){say(e.message,true);}finally{$('check-compare').disabled=!active;}
  };
  $('clear-review').onclick=async()=>{await applyReview({currency:'USD',cards:[],unknown_contents:null});changed();say('Review cleared. Collection and wanted targets remain unchanged.');};
  for(const f of fields)$('review-'+f).addEventListener('input',changed);
  $('review-unknown').addEventListener('input',()=>{remainderAuto=false;changed();});
  $('review-price-kind').addEventListener('change',changed);
  // Retention and reference cleanup are local reads. No provider request or renewal.
  let checking=false;
  setInterval(async()=>{
    if(!active)return;
    if(++ticks%5===0 && !leaseChecking && (detailRun || discoveryOrigin || preview?.discovery_origin)){leaseChecking=true;try{
      if(preview?.discovery_origin)await request('/api/shopping/listing/candidate/?'+new URLSearchParams({discovery_run:preview.discovery_origin.run_id,item_id:preview.discovery_origin.result_id}));
      if(detailRun || discoveryOrigin)await request('/api/shopping/listing/review/');
    }catch(e){if(detailRun || discoveryOrigin)await applyReview({currency:'USD',cards:[],unknown_contents:null});preview=null;sourceOrigin=null;sourceItem=null;$('listing-preview').hidden=true;$('listing-details').replaceChildren();say(e.message,true);}finally{leaseChecking=false;}}
    if(preview && Date.now()>=previewDeadline){preview=null;$('listing-preview').hidden=true;$('listing-details').replaceChildren();}
    if(retentionDeadline && Date.now()>=retentionDeadline){retentionDeadline=null;await applyReview({currency:'USD',cards:[],unknown_contents:null});say('Temporary review expired. Reopen this page to start another review. No provider request was made.');}
    if(checking || $('check-results').hidden)return;checking=true;
    try{const state=await request('/api/shopping/price-source-status/');
      const withdrawn=references.some(r=>(r.snapshot_version && !state.versions.includes(r.snapshot_version)) || (r.source_contract && !state.sources.includes(r.source_contract))); 
      const expiry=references.some(r=>r.expires_at && Date.parse(r.expires_at)<=Date.now());
      if(expiry || withdrawn){$('check-results').hidden=true;$('check-results').replaceChildren();}
    }catch{ $('check-results').hidden=true;$('check-results').replaceChildren(); }finally{checking=false;}
  },1000);
  // Persist only inputs to bounded server memory before ordinary navigation.
  document.addEventListener('click',async event=>{const a=event.target.closest('a[href]');if(!a || a.hash || !active)return;event.preventDefault();try{await persist();location.href=a.href;}catch(e){say(e.message,true);}});
  addEventListener('pagehide',()=>{if(active){persist(true).catch(()=>{});if(run && loading){request(`/api/shopping/listing/${run}/stop/`,{},true).catch(()=>{});}++loadVersion;}});
  addEventListener('pageshow',event=>{if(event.persisted)location.reload();});
  root.querySelectorAll('input,button,select').forEach(n=>n.disabled=true);
  (async()=>{try{const result=await request('/api/shopping/listing/review/');lease=result.lease;showContext(result.context);retentionDeadline=Date.now()+result.expires_in_seconds*1000;if(result.review){await applyReview(result.review);if(result.review.discovery_origin){sourceOrigin=result.review.discovery_origin;sourceItem=null;$('listing-identifier').value=result.review.listing_url || '';}retentionDeadline=Date.now()+result.expires_in_seconds*1000;say('Temporary review restored. Compare explicitly to use current local references.');}
      if(entry.discovery_run && entry.item_id){const picked=await request('/api/shopping/listing/candidate/?'+new URLSearchParams(entry));previewDeadline=Date.now()+picked.expires_in_seconds*1000;sourceOrigin=picked.listing.discovery_origin;sourceItem=picked.listing.item_id;$('listing-identifier').value=sourceItem;$('load-listing').textContent='Load additional official details';showPreview(picked.listing);showContext(picked.context);say('Selected offer carried forward. Use its summary, or explicitly load additional official details. No eBay request was made on entry.');}}catch(e){say(e.message,true);}finally{if(active){root.querySelectorAll('input,button,select').forEach(n=>n.disabled=false);$('stop-listing').disabled=true;}}})();
})();
