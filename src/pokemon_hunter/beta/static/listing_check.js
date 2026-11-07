/* Temporary assisted review. No local/session storage, provider HTML or raw history. */
(() => {
  const $ = id => document.getElementById(id), root = $('listing-check');
  const binding = JSON.parse($('check-binding').textContent), account = JSON.parse($('check-account').textContent);
  const csrf = root.querySelector('[name=csrfmiddlewaretoken]').value;
  const entry = JSON.parse($('check-entry').textContent);
  const fields = ['title','url','price','currency','shipping','tax','other_costs','planned_bid','budget','tax_rate'];
  let reviewDirty = false, saving = null, collectionContext = null;
  let detailAction = entry.request_id || null, detailUnknown = Boolean(detailAction), admissionPending = false;
  let contents = [], correctingEntry = null;
  const authoredFields={}, authoredCards=new Map();
  function rememberCard(row, key, value){authoredCards.set(row.printing_id,{...(authoredCards.get(row.printing_id) || {printing_id:row.printing_id,quantity:0}),[key]:value});}
  async function expireEvidence(){
    invalidate();clearTimeout(saveTimer);reviewDirty=false;
    lease=null;reviewRevision=null;retentionDeadline=null;
    const manual={currency:'USD',unknown_contents:null,...authoredFields,authored_fields:Object.keys(authoredFields),cards:[...authoredCards.values()].map(r=>({...r,authored_fields:Object.keys(r).filter(k=>k!=='printing_id')}))};
    clearOffer();$('listing-identifier').value='';showContext(null);
    await applyReview(manual);preview=null;sourceOrigin=null;sourceItem=null;$('listing-preview').hidden=true;$('listing-details').replaceChildren();
  }
  let cards = [], preview = null, run = null, stopped = false, active = true, version = 0, loadVersion = 0;
  let reviewRevision=null, assessmentEnd=null, handoff=null, sellerAway=false;
  let lease = null, detailRun = null, discoveryOrigin = null, sourceOrigin = null, sourceItem = null, buyNowPrice = '', buyNowCurrency = '', correcting = null, sellerCardCount = null, lotUnits = null, stockQuantity = null, remainderAuto = false, leaseChecking = false, ticks = 0, references = [], retentionDeadline = null, previewDeadline = null, offerDeadline = null, sourceDeadline = null, searchVersion = 0, saveTimer, loading = false;
  const node = (tag, text) => {const n = document.createElement(tag); if(text !== undefined) n.textContent = text; return n;};
  const identityOnly = p => Object.fromEntries(['id','name','set_name','collector_number','language','edition','finish','variant','artwork'].map(k=>[k,p[k]]));
  const say = (text, error = false) => { if($('check-reload')) $('check-reload').hidden = !error; $('check-status').textContent = text; $('check-status').setAttribute('role', error ? 'alert' : 'status'); };
  function revoke() {
    authoredCards.clear();for(const key of Object.keys(authoredFields))delete authoredFields[key];
    invalidate();clearOffer();active = false; ++version; ++loadVersion; ++searchVersion; clearTimeout(saveTimer);
    cards = []; contents=[]; preview = null; discoveryOrigin=null;sourceOrigin=null;sourceItem=null;buyNowPrice='';buyNowCurrency='';root.querySelectorAll('input').forEach(n => n.value = '');$('review-buy-now').textContent='';$('review-source-counts').textContent='';$('check-context').textContent='';
    for(const id of ['review-cards','check-matches','listing-details','contents-preview','check-results']) $(id).replaceChildren();
    root.querySelectorAll('input,button,select').forEach(n => n.disabled = true);
    $('listing-preview').hidden = true; $('check-results').hidden = true;
    $('review-count').textContent='';
    say('Your session changed. Sign in again to use Shopping.', true);
  }
  window.addEventListener('dex:authority-revoked', revoke);
  async function request(url, data, keepalive = false, action = null, headers = {}) {
    if(!active) throw Error('This page is no longer active.');
    const response = await fetch(url, {credentials:'same-origin', cache:'no-store', keepalive, headers:{...headers,'X-Dex-Shopping-Binding':binding, ...(action ? {'X-Dex-Shopping-Action':action} : {}), ...(data === undefined ? {} : {'Content-Type':'application/json','X-CSRFToken':csrf})}, ...(data === undefined ? {} : {method:'POST',body:JSON.stringify(data)})});
    if(response.redirected || [401,403].includes(response.status)) {revoke(); throw Error('Sign in again to continue.');}
    if(!response.headers.get('content-type')?.includes('application/json')) throw Object.assign(Error('The request could not finish. Your edits remain.'),{status:response.status});
    const value = await response.json();
    if(!response.ok && response.status===503 && value.error==='runtime_busy') throw Object.assign(Error('Dex is busy with another local action. This request did not start. Reload this section.'),{status:503,category:'not_dispatched'});
    if(!response.ok) throw Object.assign(Error(value.error === 'Invalid request. Check the fields and import format.' ? 'Check whole quantities, amounts and the listing URL. Your edits remain.' : value.error || value.message || 'The request could not finish. Your edits remain.'),{status:response.status});
    if(!active) throw Error('This page is no longer active.');
    if(value.authority?.binding !== binding || value.authority?.account_id !== account) {revoke(); throw Error('Your session changed.');}
    return value;
  }
  function showContext(context) {collectionContext=context;const target=context?.selected_target;const selected=target?` · Selected exact printing: ${target.name} · ${target.set_name} #${target.collector_number} · ${[target.language,target.edition,target.finish,target.variant].filter(Boolean).join(' / ')}. The search target is not confirmed lot contents.`:'';const fit=context?.collection_fit;const benefit=fit ? ` · ${fit.mentioned_species.length} unique missing species mentioned (unconfirmed)${fit.mentioned_names?.length ? ": " + fit.mentioned_names.join(", ") : ""}. ${fit.included_species === null ? 'No included contents assessed.' : fit.included_species.length + ' potentially new species from included review identities' + (fit.included_names?.length ? ': '+fit.included_names.join(', ') : '') + '; contents remain unverified.'} ${fit.outside_scope_ids?.length ? fit.outside_scope_ids.length + ' included identities are outside retained goal coverage; their fit is unconfirmed. ' : ''}${fit.note}` : ''; $('check-context').textContent=(context?.scope_label || '')+selected+benefit; $('check-context').hidden=!context?.scope_label && !target;}
  function read() {
    return {...Object.fromEntries(fields.map(f => [f === 'url' ? 'listing_url' : f, $('review-'+f).value])), detail_run: detailRun, discovery_origin: discoveryOrigin, price_kind:$('review-price-kind').value, buy_now_price:buyNowPrice, buy_now_currency:buyNowCurrency, seller_card_count:sellerCardCount, lot_units:lotUnits, stock_quantity:stockQuantity, remainder_auto:remainderAuto, unknown_contents: $('review-unknown').value === '' ? null : Number($('review-unknown').value), contents, authored_fields:Object.keys(authoredFields), cards:cards.filter(r=>r.quantity!==0 || authoredCards.has(r.printing_id)).map(({identity,...r}) => ({...r,authored_fields:Object.keys(authoredCards.get(r.printing_id) || {}).filter(k=>k!=='printing_id')}))};
  }
  function invalidate() {handoff=null;references=[];assessmentEnd=null;delete $('check-results').dataset.pending;++version;if(collectionContext?.collection_fit) showContext({...collectionContext,collection_fit:null}); $('check-results').hidden = true; $('check-results').replaceChildren(); count();}
  function count() {
    $('review-price-label').textContent = $('review-price-kind').value === 'current_bid' ? 'Whole-lot current bid' : 'Whole-lot asking price';
    $('review-buy-now').hidden = !buyNowPrice;
    $('review-buy-now').textContent = `Separate buy-now asking price: ${buyNowPrice} ${buyNowCurrency}. This is not the auction current bid.`;
    const n = cards.reduce((s,r) => s + (Number(r.quantity) || 0),0);
    if(remainderAuto && sellerCardCount!==null)$('review-unknown').value=n<=sellerCardCount?sellerCardCount-n:'';
    $('review-source-counts').hidden=sellerCardCount===null && lotUnits===null && stockQuantity===null;
    $('review-source-counts').textContent=`Seller-stated card count: ${sellerCardCount ?? 'Unknown'} · eBay lot units: ${lotUnits ?? 'Unknown'} · Listing stock: ${stockQuantity ?? 'Unknown'}. ${remainderAuto?(n>sellerCardCount?'Included quantity exceeds the stated count; remainder is unknown.':'Remainder follows the stated count until you edit it.'):''}`;
    $('review-count').textContent = `${n} individually identified cards · unrecognized contents: ${$('review-unknown').value === '' ? 'Unknown' : $('review-unknown').value}. Whole-lot price is counted once.`;
  }
  async function persist(keepalive = false) {
    clearTimeout(saveTimer);
    if(saving)return saving;
    if(!reviewDirty)return;
    // One writer drains to the latest revision. Autosave and Back share it;
    // intermediate edits never build an obsolete queue of captured payloads.
    const drain = async () => {
      while(active && reviewDirty) {
        const data = read(), revision = version;
        if(!lease){
          const fresh=await request('/api/shopping/listing/review/');
          if(version!==revision || !active)continue;
          lease=fresh.lease;reviewRevision=fresh.revision;
          retentionDeadline=Date.now()+fresh.expires_in_seconds*1000;
        }
        const savedLease=lease;
        const value = await request('/api/shopping/listing/review/',{review:data,lease:savedLease}, keepalive);
        if(lease!==savedLease || !active)continue;
        reviewRevision=value.revision;
        if(version===revision){reviewDirty=false;showContext(value.context);}
        const expires=Date.now()+value.expires_in_seconds*1000;
        retentionDeadline=retentionDeadline ? Math.min(retentionDeadline,expires) : expires;
        if(offerDeadline)offerDeadline=Math.min(offerDeadline,retentionDeadline);
      }
    };
    const job=drain();saving=job;
    try{await job;}finally{if(saving===job)saving=null;}
  }
  function changed() {reviewDirty=true;invalidate(); clearTimeout(saveTimer); saveTimer = setTimeout(() => {persist().catch(e => say(e.message,true));},400);}
  function rememberControl(control,label,value){
    const key={'Condition claim':'condition','Language code (en, ja…)':'language','Edition claim':'edition','Finish claim':'finish','Value basis':'grade','Literal grader':'grader'}[label];
    const id=control.closest('.review-card')?.dataset.printing,row=cards.find(r=>r.printing_id===id);
    if(key && row)rememberCard(row,key,value);
  }
  function input(parent, label, value, fn, type='text') {
    const l=node('label',label), i=node('input'); i.type=type; i.value=value ?? ''; l.append(i);parent.append(l);
    i.addEventListener('input', () => {fn(type==='number' ? Number(i.value) : i.value);rememberControl(i,label,i.value);changed();}); return i;
  }
  function select(parent,label,value,options,fn) {
    const l=node('label',label), s=node('select');
    for(const [v,t] of options){const o=node('option',t);o.value=v;s.append(o);} s.value=value || '';
    l.append(s);parent.append(l);s.onchange=()=>{fn(s.value);rememberControl(s,label,s.value);changed();};return s;
  }
  function artwork(parent, p) {
    const frame=node('div');frame.className='review-art';
    const fallback=node('span','Reference image unavailable');frame.append(fallback);
    const art=p.artwork;
    if(art?.availability==='reference' && art.image_url){const img=node('img');img.src=art.image_url;img.alt=art.alt || `${p.name || 'Card'} catalog reference`;img.loading='lazy';img.decoding='async';img.referrerPolicy='no-referrer';img.onload=()=>fallback.hidden=true;img.onerror=()=>img.remove();frame.prepend(img);}
    parent.append(frame);
  }
  function exclusive(row) {
    if(row.quantity<=0)return;
    for(const entry of contents)if(entry.candidates.some(p=>p.id===row.printing_id)){
      for(const other of cards)if(other!==row && entry.candidates.some(p=>p.id===other.printing_id)){other.quantity=0;if(authoredCards.has(other.printing_id))rememberCard(other,'quantity',0);for(const control of $('review-cards').querySelectorAll('input')){if(control.dataset.printing===other.printing_id){control.checked=false;control.parentElement.lastChild.textContent='Include this proposed card';}if(control.dataset.quantity===other.printing_id)control.value=0;}}
    }
  }
  const printingLabel=p=>`${p.name} · ${p.set_name} #${p.collector_number} · ${[p.language,p.edition,p.finish,p.variant].filter(Boolean).join(' / ')}`;
  function contentsSummary(host, entry) {
    host.append(node('h3',entry.candidates.length===1?printingLabel(entry.candidates[0]):entry.candidates[0]?.name || entry.name),node('p',`Seller quantity: ${entry.quantity ?? 'Unknown'} · ${entry.candidates.length} printing alternatives · contents unverified`));
    if(entry.reasons.length)host.append(node('p',entry.reasons.join('; ')));
    const sources=node('details');sources.append(node('summary','Source evidence'));
    entry.evidence.forEach(e=>sources.append(node('p',`${e.provenance} · ${e.source_field}: ${e.text}`)));
    host.append(sources);
  }
  function renderCards() {
    const host=$('review-cards'), opened=new Set([...host.querySelectorAll('.contents-entry')].filter(e=>e.querySelector('details[data-correction]')?.open).map(e=>e.dataset.key));host.replaceChildren();const grouped=new Set(), byId=new Map(cards.map(r=>[r.printing_id,r]));
    for(const entry of contents){
      const box=node('section');box.className='contents-entry';box.dataset.key=entry.key;contentsSummary(box,entry);
      const rows=entry.candidates.map(p=>{let r=byId.get(p.id);if(!r){r={printing_id:p.id,quantity:0,grade:'raw',identity:identityOnly(p)};cards.push(r);byId.set(p.id,r);}return r;});rows.forEach(r=>grouped.add(r));
      const included=rows.filter(r=>r.quantity>0);
      box.append(node('p',included.length?`Included by your review: ${included.map(r=>`${r.quantity} × ${r.identity?.name || 'card'}`).join(', ')}. User correction; not verified seller contents.`:'Not included · choose a printing and quantity to include it.'));
      const correction=node('details');correction.dataset.correction='true';correction.append(node('summary','Correct identity and quantity'));
      const options=node('div');correction.append(options);
      const draw=()=>{
        if(options.childElementCount || !rows.length)return;
        const label=node('label','Printing to review'), picker=node('select'), editor=node('div');
        const empty=node('option','Choose a printing');empty.value='';picker.append(empty);
        rows.forEach(r=>{const choice=node('option',printingLabel(r.identity));choice.value=r.printing_id;picker.append(choice);});
        picker.value=included[0]?.printing_id || (rows.length===1?rows[0].printing_id:'');
        label.append(picker);options.append(label,editor);
        const show=()=>{editor.replaceChildren();const selected=rows.find(r=>r.printing_id===picker.value);if(selected)renderCardRows(editor,[selected]);};
        picker.onchange=show;show();
      };
      correction.addEventListener('toggle',()=>{if(correction.open)draw();});
      if(!rows.length){const help=node('p','Find a supported card using the local search below.');correction.append(help);}
      const find=node('button','Find another printing');find.type='button';find.className='secondary';find.onclick=()=>{correctingEntry=entry.key;correcting=null;$('check-query').value=entry.name;$('check-query').focus();say('Choose a local printing for this contents entry. Your selection remains a user correction.');};correction.append(find);
      box.append(correction);host.append(box);if(opened.has(entry.key)){correction.open=true;draw();}
    }
    renderCardRows(host,cards.filter(r=>!grouped.has(r)));count();
  }
  function renderCardRows(host, rows) {
    rows.forEach(r => {
      const index=cards.indexOf(r);
      const box=node('div');box.className='review-card';box.dataset.printing=r.printing_id;
      const p=r.identity || {}, heading=node('h3', `${p.name || 'Selected card'} · ${p.set_name || ''} #${p.collector_number || ''} · ${[p.edition,p.finish,p.variant].filter(Boolean).join(' / ')}`);
      artwork(box,p);const content=node('div');content.className='review-card-content';content.append(heading);const grid=node('div');grid.className='traits';
      const includeLabel=node('label'), include=node('input');include.type='checkbox';include.dataset.printing=r.printing_id;include.checked=r.quantity>0;includeLabel.className='review-include';includeLabel.append(include,node('span',r.quantity>0?'Included':'Include this proposed card'));grid.append(includeLabel);
      include.onchange=()=>{r.quantity=include.checked?Math.max(1,r.quantity,contents.find(e=>e.candidates.some(c=>c.id===r.printing_id))?.quantity || 1):0;rememberCard(r,'quantity',r.quantity);exclusive(r);renderCards();changed();[...$('review-cards').querySelectorAll('.review-include input')].find(i=>i.dataset.printing===r.printing_id)?.focus();};
      const q=input(grid,'Cards inside this one lot',r.quantity,v=>{r.quantity=v;rememberCard(r,'quantity',v);exclusive(r);include.checked=v>0;includeLabel.lastChild.textContent=v>0?'Included':'Include this proposed card';},'number');q.min='0';q.max='100000';q.dataset.quantity=r.printing_id;
      const attributes=node('details'), attributeGrid=node('div');attributeGrid.className='traits';attributes.append(node('summary',`${r.grade==='raw'?'Ungraded':r.grade?('Grade '+r.grade):'Unpriced'} · optional card details`),attributeGrid);
      select(attributeGrid,'Value basis',r.grade,[['raw','Ungraded'],['','Unknown / unpriced'],['8','Grade 8'],['9','Grade 9'],['10','Grade 10']],v=>{r.grade=v;attributes.querySelector('summary').textContent=`${v==='raw'?'Ungraded':v?('Grade '+v):'Unpriced'} · optional card details`;});
      select(attributeGrid,'Literal grader',r.grader,[['','Unknown / not graded'],['PSA','PSA'],['BGS','BGS'],['CGC','CGC'],['SGC','SGC']],v=>r.grader=v);
      input(attributeGrid,'Condition claim',r.condition,v=>r.condition=v);
      input(attributeGrid,'Language code (en, ja…)',r.language,v=>r.language=v);
      select(attributeGrid,'Edition claim',r.edition,[['','Unknown'],['unlimited','Unlimited'],['first_edition','First edition']],v=>r.edition=v);
      select(attributeGrid,'Finish claim',r.finish,[['','Unknown'],['normal','Non-holo'],['holo','Holo'],['reverse_holo','Reverse holo']],v=>r.finish=v);
      attributes.append(node('p','Claims remain unverified. Generic guides are independent scenarios, not exact slab matches.'));content.append(grid,attributes);
      const actions=node('div');actions.className='discovery-actions';const correct=node('button','Correct card');correct.type='button';correct.className='secondary';correct.onclick=()=>{correcting=index;correctingEntry=contents.find(e=>e.candidates.some(c=>c.id===r.printing_id))?.key || null;$('check-query').value=[p.name,p.set_name,p.collector_number].filter(Boolean).join(' ');$('check-query').focus();say('Find the correct card below, then choose its printing.');};actions.append(correct);
      const remove=node('button','Remove card');remove.type='button';remove.className='secondary';remove.onclick=()=>{authoredCards.delete(r.printing_id);if(contents.some(e=>e.candidates.some(p=>p.id===r.printing_id)))r.quantity=0;else cards.splice(index,1);renderCards();changed();$('check-query').focus();};actions.append(remove);content.append(actions);box.append(content);host.append(box);
    });count();
  }
  async function applyReview(value, identities=[]) {
    reviewDirty=false;contents=value.contents || [];authoredCards.clear();
    for(const key of Object.keys(authoredFields))delete authoredFields[key];
    for(const key of value.authored_fields || [])authoredFields[key]=value[key];
    for(const r of value.cards)for(const key of r.authored_fields || [])rememberCard(r,key,r[key]);
    detailRun = value.detail_run || null;discoveryOrigin=value.discovery_origin || null;buyNowPrice=value.buy_now_price || '';buyNowCurrency=value.buy_now_currency || '';correcting=null;correctingEntry=null;sellerCardCount=value.seller_card_count ?? null;lotUnits=value.lot_units ?? null;stockQuantity=value.stock_quantity ?? null;remainderAuto=value.remainder_auto===true;
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
  function clearOffer() {
    offerDeadline=null;$('listing-details').replaceChildren();$('offer-summary').replaceChildren();$('contents-preview').replaceChildren();$('offer-overview').hidden=true;
  }
  function offerMoney(value) {
    if(value?.amount===null || value?.amount===undefined || value?.amount==='' || !Number.isFinite(Number(value.amount)))return 'Unknown';
    try{return new Intl.NumberFormat('en-US',{style:'currency',currency:value.currency}).format(Number(value.amount));}
    catch{return `${value.amount} ${value.currency || ''}`;}
  }
  function offerLink(value) {
    try{const u=new URL(value);return ['https://www.ebay.com','https://ebay.com'].includes(u.origin) && !u.username && !u.password && !u.hash && (!u.search || /^\?var=[1-9]\d*$/.test(u.search)) && /^\/itm\/[1-9][0-9]{8,14}$/.test(u.pathname) ? u.href : '';}
    catch{return '';}
  }
  function showOffer(value) {
    const out=$('offer-summary');out.replaceChildren();
    const url=offerLink(value.item_url), photo=node(url?'a':'div');photo.className='offer-photo';
    if(url){photo.href=url;photo.target='_blank';photo.rel='noopener noreferrer';photo.setAttribute('aria-label','View seller photos on eBay');}
    const fallback=node('span','Seller photo unavailable');fallback.className='offer-photo-placeholder';photo.append(fallback);
    const src=window.DexDiscoveryDisplay?.sellerImage(value.seller_image);
    if(src){const img=node('img');img.src=src;img.alt='Seller photo of the selected lot';img.referrerPolicy='no-referrer';img.decoding='async';img.onload=()=>fallback.hidden=true;img.onerror=()=>img.remove();photo.append(img);}
    const caption=node('span','Seller photo');caption.className='offer-photo-label';photo.append(caption);
    const info=node('div');info.className='offer-overview-copy';info.append(node('h2',value.title || 'Selected offer'));
    const amounts=node('dl');amounts.className='offer-overview-amounts';
    for(const [label,amount] of [[value.price_kind==='current_bid'?'Current bid':'Asking price',value.price],['Shipping',value.shipping]]){
      const part=node('div'),value=node('dd',offerMoney(amount));if(value.textContent==='Unknown')value.className='is-unknown';part.append(node('dt',label),value);amounts.append(part);
    }
    info.append(amounts);
    if(value.price_kind==='current_bid'){
      const time=node('p',window.DexAuctionTime?.(value.ends_at) || 'Auction · end time unknown');time.dataset.auctionEnd=value.ends_at || '';info.append(time);
      const caution=node('p','Current bid may rise.');caution.className='field-help';info.append(caution);
    }
    if(url){const seller=node('a','Open seller listing');seller.href=url;seller.target='_blank';seller.rel='noopener noreferrer';seller.className='button-link';info.append(seller);}
    out.append(photo,info);offerDeadline=previewDeadline;$('offer-overview').hidden=false;
  }
  function showPreview(value) {
    preview=value;showOffer(value);const out=$('listing-details'), kind=value.price_kind==='current_bid'?'Auction current bid':'Whole-lot asking price';
    $('listing-preview-heading').textContent=value.discovery_origin?'Selected temporary offer':'Loaded listing';
    out.replaceChildren(node('p',`Exact item: ${value.item_id}`),node('p',`${kind}: ${value.price.amount ?? 'Unknown'} ${value.price.currency ?? ''} · Shipping: ${value.shipping.amount ?? 'Unknown'} ${value.shipping.currency ?? ''}`));
    if(value.price_kind==='current_bid' && value.buy_now?.amount!==null && value.buy_now?.amount!==undefined)out.append(node('p',`Separate buy-now asking price: ${value.buy_now.amount} ${value.buy_now.currency}. Current bid is not the final purchase cost.`));
    out.append(node('p',`Seller-stated card count: ${value.seller_lot_size ?? 'Unknown'} · eBay lot units (not necessarily cards): ${value.api_lot_size ?? 'Unknown'} · Listing stock: ${value.stock_quantity ?? 'Unknown'}`),node('p',`Condition claim: ${value.condition || 'Unknown'}`),node('p',`Identity cautions: ${value.clues.conflicts.join('; ') || 'Attributes remain seller claims'}`),node('p',`${value.contents?.length || 0} contents entries. Printing alternatives remain unverified.`));
    const d=node('details');d.append(node('summary','Seller-stated item specifics'));
    value.aspects.forEach(a=>d.append(node('p',a.name+': '+a.value)));out.append(d);
    const entries=$('contents-preview');entries.replaceChildren(node('p',`Seller-stated card count: ${value.seller_lot_size ?? 'Unknown'} · Unconfirmed remainder: ${value.unknown_contents ?? 'Unknown'} · Condition claim: ${value.condition || 'Unknown'}`));
    (value.contents || []).forEach(entry=>{const box=node('section');box.className='contents-entry';contentsSummary(box,entry);const alternatives=node('details');alternatives.append(node('summary',`Printing alternatives (${entry.candidates.length})`));alternatives.addEventListener('toggle',()=>{if(alternatives.open && alternatives.childElementCount===1)entry.candidates.forEach(p=>alternatives.append(node('p',`${p.name} · ${p.set_name} #${p.collector_number} · ${[p.language,p.edition,p.finish,p.variant].filter(Boolean).join(' / ')}`)));});box.append(alternatives);entries.append(box);});
    $('listing-preview').hidden=false;
  }
  function setLoading(value) {loading=value;$('load-listing').disabled=value;$('stop-listing').disabled=!value;}
  function rememberAction(value) {
    detailAction=value;
    const destination=new URL(location.href);if(value)destination.searchParams.set('request_id',value);else destination.searchParams.delete('request_id');
    history.replaceState(null,'',destination.pathname+destination.search);
  }
  function unknownDetails(error) {
    detailUnknown=true;setLoading(true);
    say((error?.message || 'The response is unavailable.')+' The listing request outcome is unknown. Reload this section to check without sending another acquisition.',true);
  }
  async function confirmStop() {
    if(!run){unknownDetails();return;}
    try {
      await request(`/api/shopping/listing/${run}/stop/`,{});
      detailUnknown=false;rememberAction(null);setLoading(false);run=null;
      say('Stopped. No later listing details will be applied. Consumed attempts remain counted.');
    } catch(e){detailUnknown=true;setLoading(true);say('Stop was not confirmed. Use Stop again. '+e.message,true);}
  }
  async function receiveDetails(result,expected) {
    if(expected!==loadVersion || !active)return;
    if(result.not_dispatched){
      detailUnknown=false;rememberAction(null);setLoading(false);run=null;
      say(result.error || 'Listing request did not start. No provider request was sent.',true);return;
    }
    if(result.outcome_unknown){unknownDetails();return;}
    run=result.run_id;
    if(stopped){await confirmStop();return;}
    while(result.running && !stopped && expected===loadVersion) {
      await new Promise(resolve=>setTimeout(resolve,300));
      if(stopped || expected!==loadVersion)break;
      result=await request('/api/shopping/listing/?run_id='+encodeURIComponent(run));
    }
    if(stopped || expected!==loadVersion || !active)return;
    detailUnknown=false;rememberAction(null);setLoading(false);
    if(result.listing){result.listing.detail_run=run;if(result.listing.item_id===sourceItem)result.listing.discovery_origin=sourceOrigin;previewDeadline=Date.now()+result.expires_in_seconds*1000;if(result.listing.discovery_origin && sourceDeadline)previewDeadline=Math.min(previewDeadline,sourceDeadline);showPreview(result.listing);say('Listing details loaded.');}
    else say(result.error || 'Listing details are unavailable. Manual review remains available.',true);
  }
  async function reconcileDetails() {
    if(admissionPending)return;
    const expected=loadVersion;
    try {
      const selector=detailAction?'request_id='+encodeURIComponent(detailAction):'run_id='+encodeURIComponent(run);
      const result=await request('/api/shopping/listing/?'+selector);
      await receiveDetails(result,expected);
    } catch(e){if(expected===loadVersion && active)unknownDetails(e);}
  }
  $('listing-load').onsubmit=async event=>{
    event.preventDefault();if(loading || detailUnknown || !active)return;
    const expected=++loadVersion; stopped=false;setLoading(true);run=null;
    preview=null;clearOffer();$('listing-preview').hidden=true; say('Loading listing details…');
    try {
      rememberAction(crypto.randomUUID());detailUnknown=true;admissionPending=true;
      const result=await request('/api/shopping/listing/',{identifier:$('listing-identifier').value},false,detailAction);
      admissionPending=false;
      await receiveDetails(result,expected);
    } catch(e){
      admissionPending=false;if(expected!==loadVersion || !active)return;
      if(e.category==='not_dispatched'){detailUnknown=false;rememberAction(null);setLoading(false);say(e.message,true);}
      else unknownDetails(e);
    }
  };
  $('stop-listing').onclick=async()=>{
    stopped=true;preview=null;clearOffer();$('listing-preview').hidden=true;
    say('Stopping listing request…');
    if(admissionPending)return;
    if(run)await confirmStop();else await reconcileDetails();
  };
  $('discard-listing').onclick=()=>{preview=null;clearOffer();$('listing-preview').hidden=true;say('Your current review is unchanged.');};
  $('use-listing').onclick=async()=>{
    if(!preview || Date.now()>=previewDeadline)return;
    const p=preview;
    // Ambiguous identities remain excluded. Stock is deliberately never used here.
    const currency=p.price.currency || p.shipping.currency || p.buy_now?.currency || 'USD';
    const value={budget:collectionContext?.choices?.budget ?? '',contents:p.contents || [],seller_card_count:p.seller_lot_size ?? null,lot_units:p.api_lot_size===null || p.api_lot_size===undefined?null:Number(p.api_lot_size),stock_quantity:p.stock_quantity ?? null,remainder_auto:p.seller_lot_size!==null && p.seller_lot_size!==undefined,detail_run:p.detail_run || null,discovery_origin:p.discovery_origin || null,price_kind:p.price_kind || 'current_asking_price',planned_bid:'',buy_now_price:p.price_kind==='current_bid' ? p.buy_now?.amount || '' : '',buy_now_currency:p.buy_now?.currency || '',title:p.title,listing_url:p.item_url,price:p.price.amount || '',currency,shipping:p.shipping.currency===currency ? p.shipping.amount || '' : '',tax:'',other_costs:'',unknown_contents:'unknown_contents' in p ? p.unknown_contents : p.seller_lot_size,cards:(p.proposals || []).filter(row=>row.quantity>0).map(row=>({printing_id:row.id,quantity:row.quantity,grade:row.grade || 'raw',grader:row.grader || '',condition:row.condition || '',language:row.language || '',edition:row.edition || '',finish:row.finish || ''}))};
    await applyReview(value,p.proposals);preview=null;$('listing-preview').hidden=true;$('review-editor').open=true;$('review-heading').focus({preventScroll:true});$('review-editor').scrollIntoView({block:'start'});
    try{reviewDirty=true;await persist();say('Details applied. Correct the cards and quantities, then compare.');}catch(e){say(e.message,true);}
  };
  $('check-find').onsubmit=async event=>{
    event.preventDefault();const expected=++searchVersion;
    try{
      const value=await request('/api/shopping/listing/catalog/?q='+encodeURIComponent($('check-query').value));
      if(!active || expected!==searchVersion)return;
      $('check-matches').replaceChildren(node('p',`${value.total} matching printings. Refine the search if needed; showing up to 40.`));
      value.cards.map(identityOnly).forEach(p=>{const b=node('button');artwork(b,p);b.append(node('span',`${p.name} · ${p.set_name} #${p.collector_number} · ${[p.language,p.edition,p.finish,p.variant].filter(Boolean).join(' / ')}`));b.type='button';b.className='secondary check-match';b.onclick=()=>{
        const existing=cards.find(r=>r.printing_id===p.id), replacement=correcting!==null?cards[correcting]:null;
        if(replacement){authoredCards.delete(replacement.printing_id);if(existing && existing!==replacement){existing.quantity+=replacement.quantity;cards.splice(correcting,1);}else cards[correcting]={...replacement,printing_id:p.id,identity:p};correcting=null;}
        else if(existing)existing.quantity+=1;
        else cards.push({printing_id:p.id,quantity:1,grade:'raw',grader:'',condition:'',language:'',edition:'',finish:'',identity:p});
        const entry=contents.find(e=>e.key===correctingEntry);if(entry){if(!entry.candidates.some(c=>c.id===p.id))entry.candidates.push(Object.fromEntries(Object.entries(identityOnly(p)).filter(([k])=>k!=='artwork')));entry.evidence.push({provenance:'User correction',source_field:'local selection',text:`Selected ${p.name} · ${p.set_name} #${p.collector_number}`});}const chosen=cards.find(r=>r.printing_id===p.id);rememberCard(chosen,'quantity',chosen.quantity);exclusive(chosen);correctingEntry=null;
        renderCards();changed();say('Card included with Ungraded value basis. Review its quantity and optional details.');};$('check-matches').append(b);});
    }catch(e){say(e.message,true);}
  };
  function evidenceLabel(r) {
    return [r.name, r.grade==='raw'?r.condition:[r.grader,r.grade].join(' '), r.as_of].filter(Boolean).join(' · ');
  }
  function addHandoff(out, assessment, generation, benchmark) {
    const url=offerLink(assessment.seller_url);
    if(!url)return;
    const section=node('section'), link=node('a','Open listing on eBay (new tab)');
    section.append(node('h3','eBay listing'),node('p',url));
    if(assessment.auction)section.append(node('p',window.DexAuctionTime(assessment.ends_at)));
    link.href=url;link.target='_blank';link.rel='noopener noreferrer';
    link.addEventListener('click',event=>{
      if(!active || Date.now()>=retentionDeadline || Date.parse(assessment.ends_at)<=Date.now()){
        event.preventDefault();invalidate();say('The auction or review expired. Reopen Shopping to check the listing.');return;
      }
      sellerAway=true;handoff={assessment,benchmark,link,generation};
      out.dataset.pending='true';
    });
    section.append(link);out.append(section);
  }
  async function validateReturn() {
    const trip=handoff;
    if(!active || !sellerAway || document.hidden)return;
    sellerAway=false;
    if(!trip){
      // The expiry timer may already have erased the assessment while away.
      try{await request('/api/shopping/listing/review/',undefined,false,null,{'X-Dex-Review-Lease':lease});}
      catch(e){if(active && ![400,404,409,410].includes(e.status))say(e.message,true);}
      return;
    }
    const headers={'X-Dex-Review-Lease':lease,'X-Dex-Review-Revision':reviewRevision,'X-Dex-Shopping-Generation':String(trip.generation)};
    try {
      const {assessment,benchmark}=await request('/api/shopping/listing/return/',undefined,false,null,headers);
      if(handoff!==trip)return;
      if(!trip.assessment){handoff=null;return;} // Reference cleanup already removed the decision.
      if(JSON.stringify(assessment)!==JSON.stringify(trip.assessment) || JSON.stringify(benchmark)!==JSON.stringify(trip.benchmark)){
        const missing=trip.assessment.evidence.filter(r=>!assessment.evidence.some(now=>JSON.stringify(now)===JSON.stringify(r)));
        invalidate();
        say(missing.length?'Reference expired, changed or withdrawn: '+missing.map(evidenceLabel).join('; ')+'. Compare again.':'The assessment changed. Compare again.');
        $('check-compare').focus();
        return;
      }
      delete $('check-results').dataset.pending;
      handoff=null;
      trip.link.focus({preventScroll:true});
    } catch(e) {
      if(handoff!==trip || !active)return;
      invalidate();
      const recoveryVersion=version;
      if([400,404,409,410].includes(e.status)){
        try{
          const current=await request('/api/shopping/listing/review/',undefined,false,null,headers);
          if(version!==recoveryVersion)return;
          if(current.revision!==reviewRevision && current.review){
            retentionDeadline=Math.min(retentionDeadline,Date.now()+current.expires_in_seconds*1000);
            if(detailRun!== (current.review.detail_run || null) ||
               discoveryOrigin?.run_id!==current.review.discovery_origin?.run_id ||
               discoveryOrigin?.result_id!==current.review.discovery_origin?.result_id){
              clearOffer();preview=null;sourceItem=null;sourceOrigin=null;
              $('listing-preview').hidden=true;$('listing-identifier').value=current.review.listing_url || '';
            }
            await applyReview(current.review);reviewRevision=current.revision;showContext(current.context);
            say('The saved review changed. Compare again with the current inputs.');
            $('check-compare').focus();return;
          }
        }catch{if(!active || version!==recoveryVersion)return;}
        await expireEvidence();
        say('The original offer or review is no longer available. Reopen Shopping to check the listing.',true);
      }else say(e.message,true);
      $('check-compare').focus();
    }
  }
  window.addEventListener('focus',validateReturn);
  document.addEventListener('visibilitychange',validateReturn);
  $('check-compare').onclick=async()=>{
    const expected=version;$('check-results').hidden=true;$('check-compare').disabled=true;
    try{
      const data=read();await persist();const value=await request('/api/shopping/listing/compare/',{revision:reviewRevision,lease});
      if(expected!==version || !active)return;
      const a=value.assessment;
      assessmentEnd=a.ends_at;references=[...a.evidence.flatMap(r=>[r,...r.conflicts.map(c=>({...c,name:r.name}))]),...(value.benchmark?.references || []),...(value.benchmark?.native_guides || []).flatMap(g=>g.references || [])];
      const usd=v=>v==null?'Unavailable':`$${v}`;
      const charge=v=>v ? `${v} ${data.currency}` : 'unknown';
      const out=$('check-results');out.replaceChildren(node('h2','Reviewed comparison'));
      const b=value.benchmark;
      if(b){
        const part=node('section');part.className='review-benchmark';
        part.append(node('h3','Before-tax benchmark · corrected contents'));
        if(b.unavailable)part.append(node('p',b.unavailable));
        else {
          part.append(node('p',`${b.basis_label || 'No normalized reference'} · ${b.priced_card_quantity} normalized-priced cards · ${b.unpriced_card_quantity} identified cards without normalized prices`));
          part.append(node('p',b.result.full_lot_total!=null ? `${usd(b.result.full_lot_total)} comparable lot reference` : b.result.known_selected_subtotal!=null ? `${usd(b.result.known_selected_subtotal)} comparable subtotal; other cards lack comparable references` : 'Comparable value unavailable. Publisher guide values, when available, are shown separately below.'));
          for(const [lane,c] of Object.entries(b.benchmark_costs || {})){
            if(c.base==null && c.delivered_before_tax==null)continue;
            part.append(node('p',`${lane==='auction'?'Observed current bid':'Observed Buy It Now'} ${usd(c.base)} · Shipping ${usd(c.shipping)} · Delivered before tax ${usd(c.delivered_before_tax)}`));
            if(c.difference!=null)part.append(node('p',`Reference minus delivered cost: ${usd(c.difference)} before tax`));
            if(c.subtotal_difference!=null)part.append(node('p',`Identified-card subtotal minus delivered cost: ${usd(c.subtotal_difference)} before tax. This is not a whole-lot bargain score.`));
          }
          for(const g of b.native_guides || [])part.append(node('p',`${usd(g.total ?? g.subtotal)} publisher guide ${g.complete?'total':'subtotal'} · ${g.priced_quantity ?? b.native_priced_quantity} guide-priced cards · ${g.provider} · ${g.reference_date} · shipping/tax basis unknown; condition unspecified. Separate source/date cohort; not savings or a bid ceiling.`));
          for(const r of b.references || []){
            const card=cards.find(c=>c.printing_id===r.printing_id);
            part.append(node('p',`${card?.identity?.name || r.printing_id} · ${r.basis==='sold_estimate'?'Sold estimate':'Guide'} ${usd(r.amount)} · ${r.condition || 'condition unspecified'} · reference ${r.as_of} · source ${r.source_url || 'unavailable'} · valuation ${r.valuation_as_of || 'unknown'} · publisher build ${r.publisher_built_at || 'unknown'}${r.sample ? ' · '+r.sample.unique_sales+' sales · '+r.sample.sold_from+' through '+r.sample.sold_through+' · method '+r.method?.method : ''}`));
          }
          for(const gap of b.gaps || [])part.append(node('p',gap));
        }
        part.append(node('p','Seller assertions and your corrections are not authentication or a condition guarantee. Personal bids and stricter tax-aware ceilings remain separate below.'));
        out.append(part);
      }
      for(const [basis,label] of [['listing_observation',a.auction?'Observed bid':'Fixed asking price'],...(a.auction?[['planned_bid','My planned bid']]:[])]){
        const c=a.costs[basis], part=node('section');
        part.append(node('h3',label),node('p',`Base ${usd(c.base_price)} · With shipping ${usd(c.base_plus_shipping)} · Before tax ${usd(c.before_tax)} · All-in ${usd(c.full_delivered_cost)}`));
        if(c.reference_difference!=null)part.append(node('p',`Reference minus all-in cost: ${usd(c.reference_difference)}`));
        if(c.unknown_or_ineligible_components.length)part.append(node('p','Missing or ineligible: '+c.unknown_or_ineligible_components.map(k=>k.replaceAll('_',' ')).join(', ')));
        out.append(part);
      }
      out.append(node('p',`Shipping ${charge(data.shipping)} · ${data.tax_rate ? data.tax_rate+'% tax on bid plus shipping, rounded up to cents' : 'Fixed tax '+charge(data.tax)} · Other mandatory charges ${charge(data.other_costs)}. Verify these cost assumptions at checkout.`));
      out.append(node('h3','Condition-specific reference evidence'),node('p',`${a.priced} of ${a.units} included cards have condition-specific references · Condition-specific subtotal ${usd(a.subtotal)} · Whole-lot reference ${usd(a.value)}. This coverage is separate from publisher guide values above.`));
      for(const r of a.evidence){
        out.append(node('p',`${r.name} · ${r.quantity} × ${usd(r.amount)} = ${usd(r.extended)}. Assumed ${r.grade==='raw'?r.condition:r.grader+' '+r.grade}. Source ${r.source_url} · ${r.date_basis} ${r.as_of} · Valuation date ${r.valuation_as_of ?? 'unknown'} · Captured ${r.captured_at ?? 'unknown'}.`));
      }
      if(a.auction){
        out.append(node('h3','Conditional maximum bid'),node('p',a.maximum===null?'Recommendation unavailable':usd(a.maximum)));
        if(a.maximum===null && data.budget)out.append(node('p',`Your all-in USD budget is ${usd(data.budget)}.`));
        if(a.value_limit!==undefined)out.append(node('p',`At whole cents, delivered cost must fit the ${usd(a.value)} reference total and ${usd(a.budget)} budget. Reference bid limit ${usd(a.value_limit)} · Budget bid limit ${usd(a.budget_limit)} · Binding limit: ${a.binding}.`));
        if(a.maximum!==null)out.append(node('p',`${a.price_above===null?'Observed bid unknown':a.price_above?'Observed bid already exceeds ceiling':'Observed bid is within ceiling'}. Next required bid unknown. ${a.planned_bid_above===null?'':a.planned_bid_above?'Your planned bid exceeds the ceiling.':'Your planned bid fits the ceiling.'} Verify the reviewed contents and condition before bidding.`));
      }
      for(const reason of a.issues)out.append(node('p',reason));
      addHandoff(out,a,value.authority.generation,value.benchmark);out.hidden=false;out.querySelector('h2').tabIndex=-1;out.querySelector('h2').focus();say('Comparison updated from admitted local references. No prices were refreshed.');
    }catch(e){say(e.message,true);}finally{$('check-compare').disabled=!active;}
  };
  $('clear-review').onclick=async()=>{authoredCards.clear();for(const key of Object.keys(authoredFields))delete authoredFields[key];clearOffer();preview=null;$('listing-preview').hidden=true;await applyReview({currency:'USD',cards:[],unknown_contents:null});changed();say('Review cleared. Collection and wanted targets remain unchanged.');};
  for(const f of fields)$('review-'+f).addEventListener('input',()=>{authoredFields[f==='url'?'listing_url':f]=$('review-'+f).value;changed();});
  $('review-unknown').addEventListener('input',()=>{remainderAuto=false;authoredFields.unknown_contents=$('review-unknown').value===''?null:Number($('review-unknown').value);changed();});
  $('review-price-kind').addEventListener('change',()=>{authoredFields.price_kind=$('review-price-kind').value;changed();});
  // Retention and reference cleanup are local reads. No provider request or renewal.
  function clearReferences(rows,reason){
    const generation=handoff?.generation;
    invalidate();
    // Keep only the authority needed for return after deleting the previous prices.
    if(sellerAway && generation!==undefined)handoff={generation};
    say('Reference '+reason+': '+rows.map(evidenceLabel).join('; ')+'. Compare again.');
  }
  let checking=false;
  setInterval(async()=>{
    if(!active)return;
    window.DexDiscoveryDisplay?.tick($('offer-summary'));
    if(!handoff && ++ticks%5===0 && !leaseChecking && (detailRun || discoveryOrigin || preview?.discovery_origin)){leaseChecking=true;try{
      if(preview?.discovery_origin)await request('/api/shopping/listing/candidate/?'+new URLSearchParams({discovery_run:preview.discovery_origin.run_id,item_id:preview.discovery_origin.result_id}));
      if(detailRun || discoveryOrigin){const current=await request('/api/shopping/listing/review/',undefined,false,null,{'X-Dex-Review-Lease':lease});if(!handoff && !reviewDirty && !saving && ! $('check-results').hidden && current.revision!==reviewRevision){invalidate();say('The saved review changed. Reopen it to compare again.');}}
    }catch(e){if(![400,404,410].includes(e.status)){invalidate();say(e.message,true);return;}if(detailRun || discoveryOrigin)await expireEvidence();preview=null;clearOffer();sourceOrigin=null;sourceItem=null;$('listing-preview').hidden=true;$('listing-details').replaceChildren();say(e.message,true);}finally{leaseChecking=false;}}
    if(offerDeadline && Date.now()>=offerDeadline){clearOffer();preview=null;$('listing-preview').hidden=true;$('listing-details').replaceChildren();}
    if(preview && Date.now()>=previewDeadline){preview=null;$('listing-preview').hidden=true;$('listing-details').replaceChildren();}
    if(retentionDeadline && Date.now()>=retentionDeadline){retentionDeadline=null;await expireEvidence();say('Temporary review expired. Seller evidence was cleared; your authored corrections remain on screen. The original time limit was not renewed.');}
    if(assessmentEnd && Date.parse(assessmentEnd)<=Date.now() && !$('check-results').hidden){invalidate();say('The listing ended.');}
    if(checking || $('check-results').hidden)return;
    const expected=version;
    const expired=references.filter(r=>Date.parse(r.expires_at)<=Date.now() ||
      (r.as_of && new Date().toLocaleDateString('en-CA',{timeZone:'America/New_York'})>
        new Date(Date.parse(r.as_of)+30*86400000).toISOString().slice(0,10)));
    if(expired.length){clearReferences(expired,'expired');return;}
    if(handoff && !references.some(r=>r.snapshot_version || r.source_contract))return;
    checking=true;
    try{
      const state=await request('/api/shopping/price-source-status/',undefined,false,null,{'X-Dex-Review-Lease':lease});
      if(expected!==version)return;
      const withdrawn=references.filter(r=>
        (r.snapshot_version && !state.versions.includes(r.snapshot_version)) ||
        (r.source_contract && !state.sources.includes(r.source_contract)));
      if(withdrawn.length)clearReferences(withdrawn,'withdrawn');
    }catch(e){if(active && expected===version){invalidate();say(e.message,true);}}finally{checking=false;}
  },1000);
  // Persist only inputs to bounded server memory before ordinary navigation.
  document.addEventListener('click',async event=>{const a=event.target.closest('a[href]');if(!a || a.hash || !active || a.target==='_blank' || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey)return;event.preventDefault();try{await persist();location.href=a.href;}catch(e){say(e.message,true);}});
  addEventListener('pagehide',()=>{clearOffer();if(active){persist(true).catch(()=>{});if(run && loading){request(`/api/shopping/listing/${run}/stop/`,{},true).catch(()=>{});}++loadVersion;}});
  addEventListener('pageshow',event=>{if(event.persisted)location.reload();});
  $('manual-entry').addEventListener('click',()=>{$('review-editor').open=true;});
  root.querySelectorAll('input,button,select').forEach(n=>n.disabled=true);
  async function selectedOffer(){
    const value=await request('/api/shopping/listing/candidate/?'+new URLSearchParams(entry));
    return {value,deadline:Date.now()+value.expires_in_seconds*1000};
  }
  async function restoreSection(){
    try{
      if(reviewDirty){await persist();if(detailUnknown){await reconcileDetails();return;}say('Your latest edits are retained.');return;}
      let selected=null;
      if(!lease){
        const result=await request('/api/shopping/listing/review/');
        lease=result.lease;reviewRevision=result.revision;showContext(result.context);
        retentionDeadline=Date.now()+result.expires_in_seconds*1000;
        let selectionError=null;
        if(entry.discovery_run && entry.item_id && !detailUnknown){
          try{selected=await selectedOffer();}catch(e){if(!active)throw e;selectionError=e;}
        }
        if(result.review){
          // These identities passed the same account-bound candidate admission.
          // Reuse them only when they cover every saved card; other reviews keep
          // their bounded catalog restore. Review quantities/grades stay authored.
          const identities=selected?.value.restore_cards || [];
          const complete=result.review.cards.every(r=>identities.some(p=>p.id===r.printing_id));
          await applyReview(result.review,complete?identities:[]);
          showContext(result.context);
          if(result.review.discovery_origin){sourceOrigin=result.review.discovery_origin;sourceItem=null;$('listing-identifier').value=result.review.listing_url || '';}
          say('Temporary review restored. Compare explicitly to use current local references.');
        }
        if(selectionError)throw selectionError;
      }
      if(detailUnknown){await reconcileDetails();return;}
      if(entry.discovery_run && entry.item_id){
        selected=selected || await selectedOffer();
        // Identity restoration cannot extend the received offer's remaining life.
        if(Date.now()>=selected.deadline)throw Error('The temporary offer expired. Reopen Shopping to continue.');
        const picked=selected.value;previewDeadline=selected.deadline;sourceDeadline=previewDeadline;
        sourceOrigin=picked.listing.discovery_origin;sourceItem=picked.listing.item_id;
        $('listing-identifier').value=sourceItem;$('load-listing').textContent='Load additional official details';
        showPreview(picked.listing);showContext(picked.context);say('');
      }
    }catch(e){say(e.message,true);}finally{if(active){root.querySelectorAll('input,button,select').forEach(n=>n.disabled=false);setLoading(loading || detailUnknown);}}
  }
  $('check-reload').addEventListener('click',restoreSection);
  restoreSection();
})();
