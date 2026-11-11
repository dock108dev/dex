/* Temporary assisted review. No local/session storage, provider HTML or raw history. */
(() => {
  const $ = id => document.getElementById(id), root = $('listing-check');
  const binding = JSON.parse($('check-binding').textContent), account = JSON.parse($('check-account').textContent);
  const csrf = root.querySelector('[name=csrfmiddlewaretoken]').value;
  const entry = JSON.parse($('check-entry').textContent);
  const fields = ['title','url','price','currency','shipping','tax','other_costs','planned_bid','budget','tax_rate','budget_mode','budget_rule','budget_value_basis','decision','decision_notes'];
  const costFields = new Set(['review-price','review-shipping','review-tax','review-tax_rate','review-other_costs']);
  const costLabels = {base_price:'Offer amount',shipping:'Inbound shipping',tax:'Purchase tax',other_costs:'Other required charges'};
  const usd = value => value == null ? 'Unavailable' : `$${value}`;
  let reviewDirty = false, saving = null, collectionContext = null;
  let detailAction = entry.request_id || null, detailUnknown = Boolean(detailAction), admissionPending = false;
  let contents = [], correctingEntry = null;
  const authoredFields={}, authoredCards=new Map();
  function rememberCard(row, key, value){authoredCards.set(row.printing_id,{...(authoredCards.get(row.printing_id) || {printing_id:row.printing_id,quantity:0}),[key]:value});}
  async function expireEvidence(){
    invalidate();resetBatch();clearTimeout(saveTimer);reviewDirty=false;delete authoredFields.decision;delete authoredFields.decision_notes;
    lease=null;reviewRevision=null;retentionDeadline=null;
    const manual={currency:'USD',unknown_contents:null,...authoredFields,authored_fields:Object.keys(authoredFields),cards:[...authoredCards.values()].map(r=>({...r,authored_fields:Object.keys(r).filter(k=>k!=='printing_id')}))};
    clearOffer();$('listing-identifier').value='';showContext(null);
    await applyReview(manual);preview=null;sourceOrigin=null;sourceItem=null;$('listing-preview').hidden=true;$('listing-details').replaceChildren();
  }
  let cards = [], preview = null, run = null, stopped = false, active = true, version = 0, loadVersion = 0;
  let reviewRevision=null, assessmentEnd=null, handoff=null, sellerAway=false;
  let sourceRevision=null, validationPending=false, sourcePending=false, foreground=false, leaseFailures=0, sourceFailures=0;
  let lease = null, detailRun = null, discoveryOrigin = null, sourceOrigin = null, sourceItem = null, buyNowPrice = '', buyNowCurrency = '', correcting = null, sellerCardCount = null, lotUnits = null, stockQuantity = null, remainderAuto = false, leaseChecking = false, ticks = 0, references = [], retentionDeadline = null, previewDeadline = null, offerDeadline = null, sourceDeadline = null, searchVersion = 0, saveTimer, loading = false;
  const node = (tag, text) => {const n = document.createElement(tag); if(text !== undefined) n.textContent = text; return n;};
  const identityOnly = p => Object.fromEntries(['id','name','set_name','collector_number','language','edition','finish','variant','artwork'].map(k=>[k,p[k]]));
  async function coordinate(work) {
    if(!window.navigator?.locks || !window.AbortController)return work();
    const controller=new window.AbortController(), timeout=setTimeout(()=>controller.abort(),10000);
    try{return await window.navigator.locks.request('dex-shopping-status',{signal:controller.signal},work);}
    catch(error){if(error.name==='AbortError')throw Error('Dex is still checking the search. Your review remains; try again.');throw error;}
    finally{clearTimeout(timeout);}
  }
  const say = (text, error = false) => { if($('check-reload')) $('check-reload').hidden = !error; $('check-status').textContent = text; $('check-status').setAttribute('role', error ? 'alert' : 'status'); };
  function revoke() {
    authoredCards.clear();for(const key of Object.keys(authoredFields))delete authoredFields[key];
    invalidate();resetBatch();clearOffer();active = false; ++version; ++loadVersion; ++searchVersion; clearTimeout(saveTimer);
    cards = []; contents=[]; preview = null; discoveryOrigin=null;sourceOrigin=null;sourceItem=null;buyNowPrice='';buyNowCurrency='';root.querySelectorAll('input,textarea').forEach(n => n.value = '');$('review-buy-now').textContent='';$('review-source-counts').textContent='';$('check-context').textContent='';
    for(const id of ['review-cards','check-matches','listing-details','contents-preview','check-results']) $(id).replaceChildren();
    root.querySelectorAll('input,button,select,textarea').forEach(n => n.disabled = true);
    $('listing-preview').hidden = true; $('check-results').hidden = true;
    $('review-count').textContent='';
    say('Your session changed. Sign in again to use Shopping.', true);
  }
  window.addEventListener('dex:authority-revoked', revoke);
  async function request(url, data, keepalive = false, action = null, headers = {}) {
    if(!active) throw Error('This page is no longer active.');
    const controller=data===undefined && !keepalive && window.AbortController ? new window.AbortController() : null;
    const timeout=controller ? setTimeout(()=>controller.abort(),5000) : null;
    try {
    const response = await fetch(url, {credentials:'same-origin', cache:'no-store', keepalive, ...(controller ? {signal:controller.signal} : {}), headers:{...headers,'X-Dex-Shopping-Binding':binding, ...(action ? {'X-Dex-Shopping-Action':action} : {}), ...(data === undefined ? {} : {'Content-Type':'application/json','X-CSRFToken':csrf})}, ...(data === undefined ? {} : {method:'POST',body:JSON.stringify(data)})});
    if(response.redirected || [401,403].includes(response.status)) {revoke(); throw Error('Sign in again to continue.');}
    if(!response.headers.get('content-type')?.includes('application/json')) throw Object.assign(Error('The request could not finish. Your edits remain.'),{status:response.status});
    const value = await response.json();
    if(!response.ok && response.status===503 && value.error==='runtime_busy') throw Object.assign(Error('Dex is busy with another local action. This request did not start. Reload this section.'),{status:503,category:'not_dispatched'});
    if(!response.ok) throw Object.assign(Error(value.error === 'Invalid request. Check the fields and import format.' ? 'Check whole quantities, amounts and the listing URL. Your edits remain.' : value.error || value.message || 'The request could not finish. Your edits remain.'),{status:response.status});
    if(!active) throw Error('This page is no longer active.');
    if(value.authority?.binding !== binding || value.authority?.account_id !== account) {revoke(); throw Error('Your session changed.');}
    return value;
    } catch(error) {
      if(error.name==='AbortError')throw Error('The local check timed out. Your edits remain; retry the check.');
      throw error;
    } finally {if(timeout)clearTimeout(timeout);}
  }
  function showContext(context) {
    collectionContext=context;
    const fit=context?.collection_fit, names=fit?.included_names || [], possible=(fit?.mentioned_names || []).filter(n=>!names.includes(n));
    const parts=[];
    if(context?.selected_target)parts.push(`Looking for ${context.selected_target.name}.`);
    if(fit?.included_names){
      if(fit.goal_policy==='exact' || fit.goal_policy==='catalog'){
        const printings=fit.included_printings || [];
        parts.push(printings.length ? `Reviewed goal printing matches: ${printings.map(printingLabel).join(', ')}. Seller contents remain unverified.` : 'No reviewed goal printing matches yet.');
      }else parts.push(names.length ? `Reviewed collection matches: ${names.join(', ')}. Seller contents remain unverified.` : 'No reviewed collection matches yet.');
    }
    if(possible.length)parts.push(`Possible additions mentioned in the title, not included in the review: ${possible.join(', ')}.`);
    $('check-context').textContent=parts.join(' ');
    $('check-context').hidden=!$('check-context').textContent;
  }

  function read() {
    return {...Object.fromEntries(fields.map(f => [f === 'url' ? 'listing_url' : f, $('review-'+f).value])), detail_run: detailRun, discovery_origin: discoveryOrigin, price_kind:$('review-price-kind').value, buy_now_price:buyNowPrice, buy_now_currency:buyNowCurrency, seller_card_count:sellerCardCount, lot_units:lotUnits, stock_quantity:stockQuantity, remainder_auto:remainderAuto, unknown_contents: $('review-unknown').value === '' ? null : Number($('review-unknown').value), contents, authored_fields:Object.keys(authoredFields), cards:cards.filter(r=>r.quantity!==0 || authoredCards.has(r.printing_id)).map(({identity,...r}) => ({...r,authored_fields:Object.keys(authoredCards.get(r.printing_id) || {}).filter(k=>k!=='printing_id')}))};
  }
  function invalidate() {handoff=null;references=[];assessmentEnd=null;validationPending=false;sourcePending=false;leaseFailures=0;sourceFailures=0;delete $('check-results').dataset.pending;++version;if(collectionContext?.collection_fit) showContext({...collectionContext,collection_fit:null}); $('check-results').hidden = true; $('check-results').replaceChildren(); count();}
  function pendingEvidence(kind) {
    if(kind==='lease'){validationPending=true;leaseFailures++;}else{sourcePending=true;sourceFailures++;}
    if($('check-results').childElementCount)$('check-results').hidden=true;
    say('Verification is pending. Your review is retained; retry to check the evidence.',true);
  }
  function verifiedEvidence(kind) {
    const wasPending=validationPending || sourcePending;
    if(kind==='lease'){validationPending=false;leaseFailures=0;}else{sourcePending=false;sourceFailures=0;}
    if(wasPending && !validationPending && !sourcePending && $('check-results').childElementCount && !handoff){$('check-results').hidden=false;say('Review evidence verified.');}
  }
  function count() {
    const baseline=$('review-budget').value, flexible=$('review-budget_mode').value==='flexible';
    $('review-budget-policy').textContent=`Active review ${flexible?'baseline':'budget limit'}: ${baseline ? baseline+' USD all-in' : 'not set'}. ${flexible?'Higher-priced options require explicit evidence review; no automatic exception or spending authorization. ':''}${$('review-budget_rule').value ? 'Your rule: '+$('review-budget_rule').value+'. ' : ''}${flexible?'Value basis: '+($('review-budget_value_basis').value==='resale'?'net resale proceeds after selling costs':'estimated collectible value')+'.':''}`;

    for(const summary of $('review-cards').querySelectorAll('[data-included]')){const entry=contents.find(e=>e.key===summary.dataset.included);if(entry)summary.textContent=includedSummary(cards.filter(r=>entry.candidates.some(p=>p.id===r.printing_id)));}
    const auction=$('review-price-kind').value==='current_bid', leased=Boolean(detailRun || discoveryOrigin);
    $('review-price-label').textContent=auction ? 'Current bid (provisional)' : leased ? 'Buy It Now price' : 'Whole-lot asking price';
    for(const key of ['price','shipping']){
      const amount=$('review-'+key).value, free=key==='shipping' && amount && /^0(?:\.0+)?$/.test(amount);
      const edited=Object.hasOwn(authoredFields,key) || Object.hasOwn(authoredFields,'currency');
      $('review-'+key+'-source').textContent=amount ? `${free?'Known zero · ':''}${leased && !edited ? 'Seller-reported' : 'Your entry'}` : 'Unknown';
    }
    $('review-buy-now').hidden = !buyNowPrice;
    $('review-buy-now').textContent = `Buy It Now: ${buyNowPrice} ${buyNowCurrency} · seller-reported. Compare calculates this option separately from the current bid.`;
    const n = cards.reduce((s,r) => s + (Number(r.quantity) || 0),0);
    if(remainderAuto && sellerCardCount!==null)$('review-unknown').value=n<=sellerCardCount?sellerCardCount-n:'';
    $('review-source-counts').hidden=sellerCardCount===null && lotUnits===null && stockQuantity===null;
    $('review-source-counts').textContent=`Seller-stated card count: ${sellerCardCount ?? 'Unknown'} · eBay lot units: ${lotUnits ?? 'Unknown'} · Listing stock: ${stockQuantity ?? 'Unknown'}. ${remainderAuto?(n>sellerCardCount?'Included quantity exceeds the stated count; remainder is unknown.':'Remainder follows the stated count until you edit it.'):''}`;
    $('review-count').textContent = `${n} individually identified cards · unrecognized contents: ${$('review-unknown').value === '' ? 'Unknown' : $('review-unknown').value}. Seller-stated total: ${sellerCardCount ?? 'Unknown'} · Priced copies: compare to check. Whole-lot price is counted once.`;
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
        if(version===revision){reviewDirty=false;showContext(value.context);$('review-save-status').textContent='Review saved for the remaining temporary session.';}
        const expires=Date.now()+value.expires_in_seconds*1000;
        retentionDeadline=retentionDeadline ? Math.min(retentionDeadline,expires) : expires;
        if(offerDeadline)offerDeadline=Math.min(offerDeadline,retentionDeadline);
      }
    };
    const job=drain();saving=job;
    try{await job;}finally{if(saving===job)saving=null;}
  }
  function changed() {resetBatch();$('review-save-status').textContent='Saving your changes…';reviewDirty=true;invalidate(); clearTimeout(saveTimer); saveTimer = setTimeout(() => {coordinate(()=>persist()).catch(e => say(e.message,true));},400);}
  function rememberControl(control,label,value){
    const key={'Condition claim':'condition','Language code (en, ja…)':'language','Edition claim':'edition','Finish claim':'finish','Value basis':'grade','Card status':'grade','Literal grader':'grader'}[label];
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
  function includedSummary(rows){
    const included=rows.filter(r=>r.quantity>0);
    return included.length?`Included: ${included.map(r=>`${r.quantity} × ${printingLabel(r.identity)} (${authoredCards.has(r.printing_id)?'User-confirmed allocation / edits':'Automatically proposed from seller text'})`).join('; ')}. Physical contents remain unverified.`:'Not included · choose a printing and quantity to include it.';
  }
  function allocationStatus(entry, rows) {
    const allocated=rows.reduce((n,r)=>n+(Number(r.quantity)||0),0);
    return `Allocated: ${allocated} · Remaining in this entry: ${entry.quantity === null ? 'Unknown' : Math.max(0,entry.quantity-allocated)}${entry.quantity !== null && allocated>entry.quantity ? ' · Exceeds seller quantity; reconcile before comparing.' : ''}`;
  }
  function printingTraits(p) {
    const labels={en:'English',ja:'Japanese',first_edition:'First edition',unlimited:'Unlimited',standard:'Standard',normal:'Non-holo',holo:'Holo','reverse-holo':'Reverse holo'};
    const label=value=>labels[value] || String(value).replace(/[_-]+/g,' ');
    let variant=p.variant;
    if(typeof variant==='string' && variant.trim().startsWith('{')){try{variant=JSON.parse(variant);}catch{variant=null;}}
    const attributes=variant && typeof variant==='object' ? variant : {};
    const traits=[p.language,p.edition || attributes.edition,p.finish || attributes.finish || attributes.type].filter(Boolean).map(label);
    if(variant && typeof variant==='object'){
      for(const [key,value] of Object.entries(variant)){
        if(!value || ['edition','type','finish'].includes(key))continue;
        const text=`${label(key)}: ${label(value)}`;if(!traits.includes(text))traits.push(text);
      }
    }else if(variant && !['normal','standard',p.edition,p.finish].includes(variant))traits.push(label(variant));
    return traits.join(' · ');
  }
  const printingLabel=p=>[p.name || 'Selected card',`${p.set_name || 'Set unknown'} #${p.collector_number || '?'}`,printingTraits(p)].filter(Boolean).join(' · ');
  function contentsSummary(host, entry) {
    host.append(node('h3',entry.candidates.length===1?printingLabel(entry.candidates[0]):entry.candidates[0]?.name || entry.name),node('p',`Seller quantity: ${entry.quantity ?? 'Unknown'} · ${entry.candidates.length} printing alternatives · contents unverified`));
    if(entry.key.startsWith('title-'))host.append(node('p','Unconfirmed candidate · seller title mention'));
    if(entry.reasons.length)host.append(node('p',entry.reasons.join('; ')));
    const sources=node('details');sources.append(node('summary','Source evidence'));
    entry.evidence.forEach(e=>sources.append(node('p',`${e.provenance} · ${e.source_field}: ${e.text}`)));
    host.append(sources);
  }
  function renderCards() {
    const host=$('review-cards'), opened=new Set([...host.querySelectorAll('.contents-entry')].filter(e=>e.querySelector('details[data-correction]')?.open).map(e=>e.dataset.key));host.replaceChildren();const grouped=new Set(), byId=new Map(cards.map(r=>[r.printing_id,r]));
    for(const entry of contents){
      const box=node('section');box.className='contents-entry';box.dataset.key=entry.key;contentsSummary(box,entry);
      const sharedLabel=node('label',''),shared=node('input');shared.type='checkbox';sharedLabel.className='review-include';shared.dataset.sharedEntry=entry.key;shared.onchange=resetBatch;sharedLabel.append(shared,node('span',' Include this entry in shared-trait confirmation'));box.append(sharedLabel);
      const rows=entry.candidates.map(p=>{let r=byId.get(p.id);if(!r){r={printing_id:p.id,quantity:0,grade:'',identity:identityOnly(p)};cards.push(r);byId.set(p.id,r);}return r;});rows.forEach(r=>grouped.add(r));
      const included=rows.filter(r=>r.quantity>0);
      const includedText=node('p',includedSummary(rows));includedText.dataset.included=entry.key;box.append(includedText);
      const allocation=node('p',allocationStatus(entry,rows));allocation.dataset.allocation=entry.key;box.append(allocation);
      const correction=node('details');correction.dataset.correction='true';correction.append(node('summary','Correct identity and quantity'));
      const options=node('div');correction.append(options);
      const draw=()=>{
        if(options.childElementCount || !rows.length)return;
        const label=node('label','Printing to review'), picker=node('select'), editor=node('div');
        const empty=node('option','Choose a printing');empty.value='';picker.append(empty);
        rows.forEach(r=>{const choice=node('option',printingLabel(r.identity));choice.value=r.printing_id;picker.append(choice);});
        picker.value=included[0]?.printing_id || (rows.length===1?rows[0].printing_id:'');
        label.append(picker);options.append(label,editor);
        const show=()=>{editor.replaceChildren();const selected=rows.find(r=>r.printing_id===picker.value);renderCardRows(editor,rows.filter(r=>r.quantity>0 || r===selected));};
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
      const p=r.identity || {}, heading=node('h3',printingLabel(p));
      artwork(box,p);const content=node('div');content.className='review-card-content';content.append(heading);const grid=node('div');grid.className='traits';
      const includeLabel=node('label'), include=node('input');include.type='checkbox';include.dataset.printing=r.printing_id;include.checked=r.quantity>0;includeLabel.className='review-include';includeLabel.append(include,node('span',r.quantity>0?'Included':'Include this proposed card'));grid.append(includeLabel);
      include.onchange=()=>{r.quantity=include.checked?Math.max(1,r.quantity):0;rememberCard(r,'quantity',r.quantity);renderCards();changed();[...$('review-cards').querySelectorAll('.review-include input')].find(i=>i.dataset.printing===r.printing_id)?.focus();};
      const q=input(grid,'Cards inside this one lot',r.quantity,v=>{r.quantity=v;rememberCard(r,'quantity',v);include.checked=v>0;includeLabel.lastChild.textContent=v>0?'Included':'Include this proposed card';for(const entry of contents){const status=[...$('review-cards').querySelectorAll('[data-allocation]')].find(n=>n.dataset.allocation===entry.key);if(status)status.textContent=allocationStatus(entry,cards.filter(c=>entry.candidates.some(p=>p.id===c.printing_id)));}},'number');q.min='0';q.max='100000';q.dataset.quantity=r.printing_id;
      const attributes=node('details'), attributeGrid=node('div');attributeGrid.className='traits';attributes.append(node('summary',`${r.grade==='raw'?'Ungraded':r.grade && r.grade!=='unknown'?('Grade '+r.grade):'Unpriced'} · optional card details`),attributeGrid);
      if (document.body.dataset.gradingEnabled === 'true') {
        select(attributeGrid,'Value basis',r.grade,[['raw','Ungraded'],['','Unknown / unpriced'],['8','Grade 8'],['9','Grade 9'],['10','Grade 10']],v=>{r.grade=v;attributes.querySelector('summary').textContent=`${v==='raw'?'Ungraded':v?('Grade '+v):'Unpriced'} · optional card details`;});
        select(attributeGrid,'Literal grader',r.grader,[['','Unknown / not graded'],['PSA','PSA'],['BGS','BGS'],['CGC','CGC'],['SGC','SGC']],v=>r.grader=v);
      } else if (r.grade && r.grade !== 'raw' && r.grade !== 'unknown') {
        attributes.append(node('p','A grading claim is retained; its calculation is unavailable while grading is off.'));
      } else {
        select(attributeGrid,'Card status',r.grade === 'raw' ? 'raw' : '',[['','Unknown / unpriced'],['raw','Ungraded']],v=>{r.grade=v;attributes.querySelector('summary').textContent=`${v==='raw'?'Ungraded':'Unpriced'} · optional card details`;});
      }
      input(attributeGrid,'Condition claim',r.condition,v=>r.condition=v);
      input(attributeGrid,'Language code (en, ja…)',r.language,v=>r.language=v);
      select(attributeGrid,'Edition claim',r.edition,[['','Unknown'],['unlimited','Unlimited'],['first_edition','First edition']],v=>r.edition=v);
      select(attributeGrid,'Finish claim',r.finish,[['','Unknown'],['normal','Non-holo'],['holo','Holo'],['reverse_holo','Reverse holo']],v=>r.finish=v);
      attributes.append(node('p',document.body.dataset.gradingEnabled === 'true' ? 'Claims remain unverified. Generic guides are independent scenarios, not exact slab matches.' : 'Claims remain unverified; check the seller details.'));content.append(grid,attributes);
      const actions=node('div');actions.className='discovery-actions';const correct=node('button','Find a different printing');correct.type='button';correct.className='secondary';correct.onclick=()=>{correcting=index;correctingEntry=contents.find(e=>e.candidates.some(c=>c.id===r.printing_id))?.key || null;$('check-query').value=[p.name,p.set_name,p.collector_number].filter(Boolean).join(' ');$('check-query').focus();say('Quantity and detail edits save automatically. Search below to replace this printing.');};actions.append(correct);
      const remove=node('button','Remove card');remove.type='button';remove.className='secondary';remove.onclick=()=>{if(contents.some(e=>e.candidates.some(p=>p.id===r.printing_id))){r.quantity=0;rememberCard(r,'quantity',0);}else cards.splice(index,1);renderCards();changed();$('check-query').focus();};actions.append(remove);content.append(actions);box.append(content);host.append(box);
    });count();
  }
  let batchPlan=[];
  function resetBatch(){batchPlan=[];$('batch-confirm').hidden=true;$('batch-preview').replaceChildren();}
  $('batch-plan').onclick=()=>{
    resetBatch();const selected=new Set([...$('review-cards').querySelectorAll('[data-shared-entry]:checked')].map(n=>n.dataset.sharedEntry));
    const claims=Object.fromEntries(['language','edition','finish','condition'].map(k=>[k,$('batch-'+k).value.trim()]));
    const setName=$('batch-set').value.trim().toLocaleLowerCase();
    for(const entry of contents.filter(e=>selected.has(e.key))){
      const matches=entry.candidates.filter(p=>(!setName || p.set_name.toLocaleLowerCase()===setName) && ['language','edition','finish'].every(k=>!claims[k] || p[k]===claims[k]));
      if(matches.length!==1 || !entry.quantity || entry.reasons.some(r=>/conflict|contradict|does not establish/i.test(r))){$('batch-preview').append(node('p',`${entry.name}: still needs individual identity, quantity or conflict review.`));continue;}
      const p=matches[0];batchPlan.push({entry:entry.key,p,quantity:entry.quantity,claims});
      $('batch-preview').append(node('p',`Confirm ${entry.quantity} × ${printingLabel(p)}${claims.condition?' · condition claim '+claims.condition:''}. This replaces this entry’s current allocation.`));
    }
    if(!selected.size)$('batch-preview').append(node('p','Select the entries sharing these traits first.'));
    $('batch-confirm').hidden=!batchPlan.length;
  };
  $('batch-confirm').onclick=()=>{
    for(const plan of batchPlan){
      const entry=contents.find(e=>e.key===plan.entry);if(!entry)continue;
      for(const row of cards.filter(r=>entry.candidates.some(p=>p.id===r.printing_id))){row.quantity=0;rememberCard(row,'quantity',0);}
      const row=cards.find(r=>r.printing_id===plan.p.id);row.quantity=plan.quantity;rememberCard(row,'quantity',row.quantity);
      for(const [k,v] of Object.entries(plan.claims))if(v){row[k]=v;rememberCard(row,k,v);}
      entry.evidence.push({provenance:'User confirmation',source_field:'Shared-trait review',text:`Confirmed ${plan.quantity} copies of ${printingLabel(plan.p)} after reviewing shared traits.`});
    }
    resetBatch();renderCards();changed();say('Previewed allocations confirmed. Remaining entries still need individual review. Seller claims remain unverified.');
  };
  for(const id of ['batch-set','batch-language','batch-edition','batch-finish','batch-condition'])$(id).addEventListener('input',resetBatch);
  async function applyReview(value, identities=[]) {
    reviewDirty=false;resetBatch();contents=value.contents || [];authoredCards.clear();
    for(const key of Object.keys(authoredFields))delete authoredFields[key];
    for(const key of value.authored_fields || [])authoredFields[key]=value[key];
    for(const r of value.cards)for(const key of r.authored_fields || [])rememberCard(r,key,r[key]);
    detailRun = value.detail_run || null;discoveryOrigin=value.discovery_origin || null;buyNowPrice=value.buy_now_price || '';buyNowCurrency=value.buy_now_currency || '';correcting=null;correctingEntry=null;sellerCardCount=value.seller_card_count ?? null;lotUnits=value.lot_units ?? null;stockQuantity=value.stock_quantity ?? null;remainderAuto=value.remainder_auto===true;
    $('review-price-kind').value=value.price_kind || 'current_asking_price';
    for(const f of fields) $('review-'+f).value = value[f === 'url' ? 'listing_url' : f] ?? ({budget_mode:'limit',budget_value_basis:'collectible',decision:'reviewing'}[f] || '');
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
    if(value.condition_description)out.append(node('p','Seller condition description: '+value.condition_description));
    out.append(node('p',`Seller-stated card count: ${value.seller_lot_size ?? 'Unknown'} · eBay lot units (not necessarily cards): ${value.api_lot_size ?? 'Unknown'} · Listing stock: ${value.stock_quantity ?? 'Unknown'}`),node('p',`Condition claim: ${value.condition || 'Unknown'}`),node('p',`Identity cautions: ${value.clues.conflicts.join('; ') || 'Attributes remain seller claims'}`),node('p',`${value.contents?.length || 0} contents entries. Printing alternatives remain unverified.`));
    const d=node('details');d.append(node('summary','Seller-stated item specifics'));
    value.aspects.forEach(a=>d.append(node('p',a.name+': '+a.value)));out.append(d);
    const entries=$('contents-preview');entries.replaceChildren(node('p',`Seller-stated card count: ${value.seller_lot_size ?? 'Unknown'} · Unconfirmed remainder: ${value.unknown_contents ?? 'Unknown'} · Condition claim: ${value.condition || 'Unknown'}`));
    (value.contents || []).forEach(entry=>{const box=node('section');box.className='contents-entry';contentsSummary(box,entry);const alternatives=node('details');alternatives.append(node('summary',`Printing alternatives (${entry.candidates.length})`));alternatives.addEventListener('toggle',()=>{if(alternatives.open && alternatives.childElementCount===1)entry.candidates.forEach(p=>alternatives.append(node('p',printingLabel(p))));});box.append(alternatives);entries.append(box);});
    $('listing-preview').hidden=false;
  }
  function setLoading(value) {loading=value;$('load-listing').disabled=value;$('stop-listing').disabled=!value;}
  function rememberAction(value) {
    detailAction=value;
    const destination=new URL(location.href);if(value)destination.searchParams.set('request_id',value);else destination.searchParams.delete('request_id');
    history.replaceState(history.state,'',destination.pathname+destination.search);
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
    const value={budget:$('review-budget').value || collectionContext?.choices?.budget || '',budget_mode:collectionContext?.choices?.budget_mode || $('review-budget_mode').value || 'limit',budget_rule:$('review-budget_rule').value || collectionContext?.choices?.budget_rule || '',budget_value_basis:collectionContext?.choices?.budget_value_basis || $('review-budget_value_basis').value || 'collectible',contents:p.contents || [],seller_card_count:p.seller_lot_size ?? null,lot_units:p.api_lot_size===null || p.api_lot_size===undefined?null:Number(p.api_lot_size),stock_quantity:p.stock_quantity ?? null,remainder_auto:p.seller_lot_size!==null && p.seller_lot_size!==undefined,detail_run:p.detail_run || null,discovery_origin:p.discovery_origin || null,price_kind:p.price_kind || 'current_asking_price',planned_bid:'',buy_now_price:p.price_kind==='current_bid' ? p.buy_now?.amount || '' : '',buy_now_currency:p.buy_now?.currency || '',title:p.title,listing_url:p.item_url,price:p.price.amount || '',currency,shipping:p.shipping.currency===currency ? p.shipping.amount || '' : '',tax:'',other_costs:'',unknown_contents:'unknown_contents' in p ? p.unknown_contents : p.seller_lot_size,cards:(p.proposals || []).filter(row=>row.quantity>0).map(row=>({printing_id:row.id,quantity:row.quantity,grade:row.grade || '',grader:row.grader || '',condition:row.condition || '',language:row.language || '',edition:row.edition || '',finish:row.finish || ''}))};
    await applyReview(value,p.proposals);preview=null;$('listing-preview').hidden=true;$('review-editor').open=true;$('review-heading').focus({preventScroll:true});$('review-editor').scrollIntoView({block:'start'});
    try{reviewDirty=true;await persist();say('Details applied. Correct the cards and quantities, then compare.');}catch(e){say(e.message,true);}
  };
  $('check-find').onsubmit=async event=>{
    event.preventDefault();const expected=++searchVersion;
    try{
      const value=await request('/api/shopping/listing/catalog/?q='+encodeURIComponent($('check-query').value));
      if(!active || expected!==searchVersion)return;
      $('check-matches').replaceChildren(node('p',`${value.total} matching printings. Refine the search if needed; showing up to 40.`));
    value.cards.map(identityOnly).forEach(p=>{const b=node('button');artwork(b,p);b.append(node('span',printingLabel(p)));b.type='button';b.className='secondary check-match';b.onclick=()=>{
        const existing=cards.find(r=>r.printing_id===p.id), replacement=correcting!==null?cards[correcting]:null;
        if(replacement){authoredCards.delete(replacement.printing_id);if(existing && existing!==replacement){existing.quantity+=replacement.quantity;cards.splice(correcting,1);}else cards[correcting]={...replacement,printing_id:p.id,identity:p};correcting=null;}
        else if(existing)existing.quantity+=1;
        else cards.push({printing_id:p.id,quantity:1,grade:'',grader:'',condition:'',language:'',edition:'',finish:'',identity:p});
        const entry=contents.find(e=>e.key===correctingEntry);if(entry){if(!entry.candidates.some(c=>c.id===p.id))entry.candidates.push(Object.fromEntries(Object.entries(identityOnly(p)).filter(([k])=>k!=='artwork')));entry.evidence.push({provenance:'User correction',source_field:'local selection',text:`Selected ${p.name} · ${p.set_name} #${p.collector_number}`});}const chosen=cards.find(r=>r.printing_id===p.id);rememberCard(chosen,'quantity',chosen.quantity);correctingEntry=null;
        renderCards();changed();say('Card included. Review its quantity and card status; unknown status remains unpriced.');};$('check-matches').append(b);});
    }catch(e){say(e.message,true);}
  };
  function evidenceLabel(r) {
    return [r.name, r.grade==='raw'?r.condition:[r.grader,r.grade].join(' '), r.as_of].filter(Boolean).join(' · ');
  }
  function renderCosts(shell, assessment, data) {
    const section=node('section');section.append(node('h3','Delivered cost'));
    const lanes=node('div');lanes.className='review-cost-options';section.append(lanes);
    const labels={listing_observation:assessment.auction?'Current bid · provisional':'Buy It Now / asking price',buy_it_now:'Buy It Now',planned_bid:'Your planned bid · provisional'};
    for(const basis of ['listing_observation','buy_it_now','planned_bid']){
      const cost=assessment.costs[basis];
      if(!cost || basis==='planned_bid' && (!assessment.auction || !data.planned_bid))continue;
      const lane=node('section'), list=node('dl');lane.className='review-cost-option';
      lane.append(node('h4',labels[basis]),list);lanes.append(lane);
      const missing=cost.unknown_or_ineligible_components;
      for(const [key,label] of Object.entries(costLabels)){
        const component=cost.components?.[key];
        if(!component)continue;
        const {amount,currency,source}=component;
        const display=amount==null?'Unknown':currency==='USD'?usd(amount):`${amount} ${currency}`;
        const free=key==='shipping' && amount!=null && /^0(?:\.0+)?$/.test(amount);
        const origin={seller_reported:'Seller-reported',your_entry:'Your entry',rate_estimate:`Your ${data.tax_rate}% estimate on price plus shipping`}[source];
        let note=origin || '';
        if(cost.cost_component_eligibility?.[key]==='unsupported_or_missing_currency')note+=`${note?' · ':''}USD required for totals`;
        else if(key==='tax' && amount==null && data.tax_rate)note='Rate estimate needs the offer amount and shipping';
        const details=node('dd',free?`Free (${display})`:display);
        if(note){const small=node('small',note);details.append(small);}
        list.append(node('dt',label),details);
      }
      if(cost.base_plus_shipping!=null)lane.append(node('p',`Price plus shipping ${usd(cost.base_plus_shipping)} · before tax and other charges`));
      if(cost.full_delivered_cost!=null)lane.append(node('strong',`All-in ${usd(cost.full_delivered_cost)}`));
      else if(missing.length)lane.append(node('p',`All-in unavailable · check ${missing.map(key=>costLabels[key].toLowerCase()).join(', ')}.`));
      else lane.append(node('p','All-in total unavailable.'));
      if(basis==='listing_observation' && assessment.auction)lane.append(node('p','The current bid can rise before the auction ends.'));
    }
    section.append(node('p','Verify your entered charges and estimates at checkout. Percentage tax rounds up to the next cent when needed.'));
    shell.append(section);
  }
  function renderMarket(shell, assessment, benchmark, data) {
    const section=node('section');section.className='review-market';
    section.append(node('h3','Market comparison'),node('p',assessment.value!=null
      ? `${usd(assessment.value)} condition-specific whole-lot reference. Verify the seller’s cards and condition.`
      : 'Near-market comparison unavailable. Dex needs a reference for the exact printing and reviewed condition of each included card.'));
    if(assessment.market_issues?.length){
      const reasons=node('ul');
      for(const reason of assessment.market_issues)reasons.append(node('li',reason));
      section.append(reasons);
    }
    const labels={listing_observation:assessment.auction?'Current bid':'Asking price',buy_it_now:'Buy It Now',planned_bid:'Your planned bid'};
    for(const [basis,cost] of Object.entries(assessment.costs)){
      if(cost.reference_difference!=null && (basis!=='planned_bid' || assessment.auction && data.planned_bid)){
        section.append(node('p',`${labels[basis]} · condition-specific reference minus all-in cost ${usd(cost.reference_difference)}`));
      }
    }
    if(benchmark){
      const part=node('section');part.className='review-benchmark';
      part.append(node('h4','Before-tax benchmark · reviewed contents'));
      if(benchmark.unavailable)part.append(node('p',benchmark.unavailable));
      else {
        const {full_lot_total:total,known_selected_subtotal:subtotal}=benchmark.result;
        part.append(node('p',`${benchmark.basis_label || 'No normalized reference'} · ${benchmark.priced_card_quantity} normalized-priced cards · ${benchmark.unpriced_card_quantity} identified cards without normalized prices`));
        part.append(node('p',total!=null ? `${usd(total)} comparable lot reference` : subtotal!=null ? `${usd(subtotal)} comparable subtotal; other cards lack comparable references` : 'Comparable value unavailable.'));
        for(const [lane,cost] of Object.entries(benchmark.benchmark_costs || {})){
          if(cost.base==null && cost.delivered_before_tax==null)continue;
          part.append(node('p',`${lane==='auction'?'Observed current bid':'Observed Buy It Now'} ${usd(cost.base)} · Shipping ${usd(cost.shipping)} · Delivered before tax ${usd(cost.delivered_before_tax)}`));
          if(cost.difference!=null)part.append(node('p',`Reference minus delivered cost: ${usd(cost.difference)} before tax`));
          if(cost.subtotal_difference!=null)part.append(node('p',`Identified-card subtotal minus delivered cost: ${usd(cost.subtotal_difference)} before tax. Other cards lack comparable references.`));
        }
        for(const ref of benchmark.references || []){
          const card=cards.find(c=>c.printing_id===ref.printing_id)?.identity;
          part.append(node('p',`${card?.name || ref.printing_id} · ${ref.basis==='sold_estimate'?'Sold estimate':'Guide'} ${usd(ref.amount)} · ${ref.condition || 'condition unspecified'} · reference ${ref.as_of} · source ${ref.source_url || 'unavailable'} · valuation ${ref.valuation_as_of || 'unknown'} · publisher build ${ref.publisher_built_at || 'unknown'}${ref.sample ? ' · '+ref.sample.unique_sales+' sales · '+ref.sample.sold_from+' through '+ref.sample.sold_through+' · method '+ref.method?.method : ''}`));
        }
        for(const gap of benchmark.gaps || [])part.append(node('p',gap));
      }
      section.append(part);
    }
    if(benchmark?.native_guides?.length){
      section.append(node('h4','Dated publisher guides'),node('p','Publisher guide amounts have unspecified condition and unknown shipping and tax basis. They are shown separately from market comparison.'));
      for(const group of benchmark.native_guides){
        section.append(node('p',`${usd(group.total ?? group.subtotal)} publisher guide ${group.complete?'total':'subtotal'} · ${group.priced_quantity} guide-priced cards · ${group.provider} · ${group.date_basis==='publisher_build'?'Build date':'Reference date'} ${group.reference_date}`));
        const items=node('ul');
        for(const ref of group.references || []){
          const card=cards.find(c=>c.printing_id===ref.printing_id)?.identity;
          items.append(node('li',`${card ? printingLabel(card) : ref.printing_id} · ${usd(ref.amount)} per card`));
        }
        section.append(items);
      }
    }
    shell.append(section);
  }
  function addHandoff(out, assessment, generation, benchmark) {
    const url=offerLink(assessment.seller_url);
    if(!url)return;
    const section=node('section'), link=node('a','Open listing on eBay (new tab)'), retry=node('button','Verify comparison');
    section.append(node('h3','eBay listing'),node('p',url));
    if(assessment.auction)section.append(node('p',window.DexAuctionTime(assessment.ends_at)));
    link.href=url;link.target='_blank';link.rel='noopener noreferrer';
    link.addEventListener('click',event=>{
      if(!active || Date.now()>=retentionDeadline || Date.parse(assessment.ends_at)<=Date.now()){
        event.preventDefault();invalidate();say('The auction or review expired. Reopen Shopping to check the listing.');return;
      }
      sellerAway=true;handoff={assessment,benchmark,link,retry,generation};
      out.dataset.pending='true';
      retry.hidden=false;
    });
    retry.type='button';retry.className='secondary';retry.hidden=true;retry.addEventListener('click',validateReturn);
    section.append(link,retry);out.append(section);
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
    const expected=version, headers={'X-Dex-Review-Lease':lease,'X-Dex-Review-Revision':reviewRevision,'X-Dex-Shopping-Generation':String(trip.generation)};
    try {
      const value=await coordinate(()=>expected!==version ? null : request('/api/shopping/listing/return/',undefined,false,null,headers));
      if(handoff!==trip || !active)return;
      if(!value || expected!==version){sellerAway=true;pendingEvidence('lease');return;}
      const {assessment,benchmark}=value;
      if(!trip.assessment){handoff=null;return;} // Reference cleanup already removed the decision.
      if(JSON.stringify(assessment)!==JSON.stringify(trip.assessment) || JSON.stringify(benchmark)!==JSON.stringify(trip.benchmark)){
        const missing=trip.assessment.evidence.filter(r=>!assessment.evidence.some(now=>JSON.stringify(now)===JSON.stringify(r)));
        invalidate();
        say(missing.length?'Reference expired, changed or withdrawn: '+missing.map(evidenceLabel).join('; ')+'. Compare again.':'The assessment changed. Compare again.');
        $('check-compare').focus();
        return;
      }
      delete $('check-results').dataset.pending;
      validationPending=false;sourcePending=false;$('check-results').hidden=false;
      handoff=null;
      trip.retry.hidden=true;
      trip.link.focus({preventScroll:true});
    } catch(e) {
      if(expected!==version || handoff!==trip || !active)return;
      if(![400,404,409,410].includes(e.status)){
        sellerAway=true;pendingEvidence('lease');return;
      }
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
      }
      $('check-compare').focus();
    }
  }
  window.addEventListener('focus',validateReturn);
  document.addEventListener('visibilitychange',validateReturn);
  $('check-compare').onclick=async()=>{
    const expected=++version;foreground=true;$('check-results').hidden=true;$('check-compare').disabled=true;
    say('Checking your review…');
    try{
      await coordinate(async()=>{
      if(expected!==version || !active)return;
      const data=read();await persist();const value=await request('/api/shopping/listing/compare/',{revision:reviewRevision,lease});
      if(expected!==version || !active)return;
      validationPending=false;sourcePending=false;leaseFailures=0;sourceFailures=0;
      const a=value.assessment;
      assessmentEnd=a.ends_at;references=[...a.evidence.flatMap(r=>[r,...r.conflicts.map(c=>({...c,name:r.name}))]),...(value.benchmark?.references || []),...(value.benchmark?.native_guides || []).flatMap(g=>g.references || [])];
      const shell=$('check-results');shell.replaceChildren(node('h2','Compare reviewed lot'));
      shell.append(node('p',`Seller-stated total: ${sellerCardCount ?? 'Unknown'} · Identified copies: ${a.units} · Condition-specific priced copies: ${a.priced} · Unresolved remainder: ${data.unknown_contents ?? 'Unknown'}. Guide coverage is shown separately below.`));
      renderCosts(shell,a,data);
      renderMarket(shell,a,value.benchmark,data);
      const out=node('details');out.append(node('summary','Reference details, budget and bid limits'));shell.append(out);
      if(data.budget_mode==='flexible')out.append(node('p',`Baseline ${usd(data.budget || null)} all-in. ${data.budget_rule ? 'Your exception rule: '+data.budget_rule+'. ' : 'No exception rule specified. '}A higher-price exception requires complete contents, costs and applicable value evidence. ${data.budget_value_basis==='resale'?'Net resale proceeds require selling costs and eligible resale evidence.':'Collectible value and resale proceeds have separate evidence requirements.'}`));
      out.append(node('h3','Condition-specific reference evidence'),node('p',`${a.priced} of ${a.units} included cards have condition-specific references · Condition-specific subtotal ${usd(a.subtotal)} · Whole-lot reference ${usd(a.value)}.`));
      for(const r of a.evidence){
        out.append(node('p',`${r.name} · ${r.quantity} × ${usd(r.amount)} = ${usd(r.extended)}. Assumed ${r.grade==='raw'?r.condition:r.grader+' '+r.grade}. Source ${r.source_url} · ${r.date_basis} ${r.as_of} · Valuation date ${r.valuation_as_of ?? 'unknown'} · Captured ${r.captured_at ?? 'unknown'}.`));
      }
      if(a.auction){
        out.append(node('h3','Conditional maximum bid'),node('p',a.maximum===null?'Recommendation unavailable':usd(a.maximum)));
        if(a.maximum===null && data.budget)out.append(node('p',`Your all-in USD budget is ${usd(data.budget)}.`));
        if(a.value_limit!==undefined)out.append(node('p',`At whole cents, delivered cost must fit the ${usd(a.value)} reference total and ${usd(a.budget)} budget. Reference bid limit ${usd(a.value_limit)} · Budget bid limit ${usd(a.budget_limit)} · Binding limit: ${a.binding}.`));
        if(a.maximum!==null)out.append(node('p',`${a.price_above===null?'Observed bid unknown':a.price_above?'Observed bid already exceeds ceiling':'Observed bid is within ceiling'}. Next required bid unknown. ${a.planned_bid_above===null?'':a.planned_bid_above?'Your planned bid exceeds the ceiling.':'Your planned bid fits the ceiling.'} Verify the reviewed contents and condition before bidding.`));
      }
      for(const reason of a.issues.slice(a.market_issues?.length ?? 0))out.append(node('p',reason));
      addHandoff(shell,a,value.authority.generation,value.benchmark);shell.hidden=false;shell.querySelector('h2').tabIndex=-1;shell.querySelector('h2').focus();say('Lot summary updated.');
      });
    }catch(e){if($('check-results').childElementCount)pendingEvidence('lease');else say(e.message,true);$('check-compare').focus();}finally{foreground=false;$('check-compare').disabled=!active;}
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
    if(!active || foreground || document.hidden)return;
    window.DexDiscoveryDisplay?.tick($('offer-summary'));
    ++ticks;
    const origin=preview?.discovery_origin || discoveryOrigin;
    if(!handoff && ticks%5===0 && (!validationPending || leaseFailures<3) && !leaseChecking && !checking && !saving && !reviewDirty && (origin || detailRun)){leaseChecking=true;const expected=version;try{
      const current=await coordinate(()=>expected!==version || foreground ? null : origin
        ? request('/api/shopping/listing/validate/?'+new URLSearchParams({discovery_run:origin.run_id,item_id:origin.result_id}),undefined,false,null,{'X-Dex-Review-Lease':lease})
        : request('/api/shopping/listing/review/',undefined,false,null,{'X-Dex-Review-Lease':lease}));
      if(!current || expected!==version || foreground)return;
      if(origin && sourceRevision!==null && current.source_revision!==sourceRevision){await expireEvidence();say('The offer evidence changed. Reopen Shopping to review it again.',true);return;}
      if(current.revision!==reviewRevision){invalidate();say('The saved review changed. Reopen it to compare again.',true);return;}
      if(origin && sourceRevision===null)sourceRevision=current.source_revision;
      verifiedEvidence('lease');
    }catch(e){if(expected!==version || foreground)return;if(![400,404,410].includes(e.status)){pendingEvidence('lease');return;}await expireEvidence();preview=null;clearOffer();sourceOrigin=null;sourceItem=null;$('listing-preview').hidden=true;$('listing-details').replaceChildren();say(e.message,true);}finally{leaseChecking=false;}}
    if(offerDeadline && Date.now()>=offerDeadline){clearOffer();preview=null;$('listing-preview').hidden=true;$('listing-details').replaceChildren();}
    if(preview && Date.now()>=previewDeadline){preview=null;$('listing-preview').hidden=true;$('listing-details').replaceChildren();}
    if(retentionDeadline && Date.now()>=retentionDeadline){retentionDeadline=null;await expireEvidence();say('Temporary review expired. Seller evidence was cleared; your authored corrections remain on screen. The original time limit was not renewed.');}
    if(assessmentEnd && Date.parse(assessmentEnd)<=Date.now() && !$('check-results').hidden){invalidate();say('The listing ended.');}
    if(ticks%5!==2 || (sourcePending && sourceFailures>=3) || checking || leaseChecking || ! $('check-results').childElementCount || validationPending)return;
    const expected=version;
    const expired=references.filter(r=>Date.parse(r.expires_at)<=Date.now() ||
      (r.as_of && new Date().toLocaleDateString('en-CA',{timeZone:'America/New_York'})>
        new Date(Date.parse(r.as_of)+30*86400000).toISOString().slice(0,10)));
    if(expired.length){clearReferences(expired,'expired');return;}
    if(handoff && !references.some(r=>r.snapshot_version || r.source_contract))return;
    checking=true;
    try{
      const state=await coordinate(()=>expected!==version || foreground ? null : request('/api/shopping/price-source-status/',undefined,false,null,{'X-Dex-Review-Lease':lease}));
      if(!state || expected!==version)return;
      const withdrawn=references.filter(r=>
        (r.snapshot_version && !state.versions.includes(r.snapshot_version)) ||
        (r.source_contract && !state.sources.includes(r.source_contract)));
      if(withdrawn.length)clearReferences(withdrawn,'withdrawn');
      else verifiedEvidence('source');
    }catch(e){if(active && expected===version && !foreground)pendingEvidence('source');}finally{checking=false;}
  },1000);
  // Persist only inputs to bounded server memory before ordinary navigation.
  document.addEventListener('click',async event=>{const a=event.target.closest('a[href]');if(!a || a.hash || !active || a.target==='_blank' || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey)return;event.preventDefault();foreground=true;const expected=++version;try{await coordinate(async()=>{if(expected!==version || !active)return;await persist();location.href=a.href;});}catch(e){foreground=false;say(e.message,true);a.focus?.();}});
  addEventListener('pagehide',()=>{clearOffer();if(active){persist(true).catch(()=>{});if(run && loading){request(`/api/shopping/listing/${run}/stop/`,{},true).catch(()=>{});}++loadVersion;}});
  addEventListener('pageshow',event=>{if(event.persisted)location.reload();});
  $('manual-entry').addEventListener('click',()=>{$('review-editor').open=true;});
  root.querySelectorAll('input,button,select,textarea').forEach(n=>n.disabled=true);
  async function selectedOffer(){
    let value;
    try {value=await request('/api/shopping/listing/candidate/?'+new URLSearchParams(entry));}
    catch(error){if(error.status===404) throw Error('This temporary offer is unavailable. Use Back to search to keep your search inputs.');throw error;}
    return {value,deadline:Date.now()+value.expires_in_seconds*1000};
  }
  async function restoreSection(){
    try{
      await coordinate(async()=>{
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
        sourceRevision=picked.source_revision;
        sourceOrigin=picked.listing.discovery_origin;sourceItem=picked.listing.item_id;
        $('listing-identifier').value=sourceItem;$('load-listing').textContent='Load full seller details';
        showPreview(picked.listing);showContext(picked.context);say('');
        if(picked.saved_review){
          retentionDeadline=Math.min(retentionDeadline,Date.now()+picked.review_expires_in_seconds*1000);
          await applyReview(picked.saved_review);reviewDirty=true;await persist();
          $('review-editor').open=true;say('This lot’s temporary review and decision were restored. Original expiry is unchanged.');
        }
      }
      });
    }catch(e){say(e.message,true);}finally{if(active){root.querySelectorAll('input,button,select,textarea').forEach(n=>n.disabled=false);setLoading(loading || detailUnknown);}}
  }
  root.addEventListener('focusin', event=>{
    const id=event.target.id, focus=costFields.has(id) ? id : null;
    if((history.state?.reviewCostFocus || null)!==focus)history.replaceState({...history.state,reviewCostFocus:focus},'');
  });
  const reloadFocus=globalThis.performance?.getEntriesByType?.('navigation')[0]?.type==='reload' ? history.state?.reviewCostFocus : null;
  $('check-reload').addEventListener('click',()=>{if(sellerAway && handoff)validateReturn();else if(validationPending && (preview?.discovery_origin || discoveryOrigin || detailRun)){leaseFailures=0;ticks=4;say('Checking your review…');}else if(sourcePending){sourceFailures=0;ticks=1;say('Checking your evidence…');}else restoreSection();});
  restoreSection().then(()=>{
    if(active && costFields.has(reloadFocus) && document.activeElement===document.body && !$('check-status').matches('[role=alert]')){
      $('review-editor').open=true;
      $(reloadFocus).focus({preventScroll:true});
    }
  });
})();
