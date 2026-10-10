/* Manual workspace. Money stays as strings; the server computes every amount. */
(() => {
  const $ = (id) => document.getElementById(id);
  const today = new Intl.DateTimeFormat('en-CA', {timeZone:'America/New_York', year:'numeric', month:'2-digit', day:'2-digit'}).format(new Date());
  const selections = new Map(), references = new Map(), manualVersions = new Map(), acceptedReferences = new Set();
  let goals = [], offset = 0, total = 0;
  const node = (tag, value, className) => { const el = document.createElement(tag); if (value !== undefined) el.textContent = value; if (className) el.className = className; return el; };
  const option = (value, label) => { const el = node('option', label); el.value = value; return el; };
  const dollars = (v) => v === null || v === undefined ? 'Unavailable' : `$${v}`;
  const pair = (v) => v ? `${v[0]} / ${v[1]}` : 'Unknown denominator';
  function status(message, error=false) { $('status').textContent = message; $('status').setAttribute('role', error ? 'alert' : 'status'); if (error) $('status').focus(); }
  async function request(url, init={}) {
    const response = await fetch(url, {...init, credentials:'same-origin'});
    if (response.redirected || !response.headers.get('content-type')?.includes('application/json')) throw new Error('Sign in again, then retry. Your entries remain here.');
    const data = await response.json();
    if (!response.ok) throw new Error('Could not complete this request. Check the selected goal, quantities, decimal amounts, dates, assumptions and reference choices, then retry. Your entries remain here.');
    return data;
  }
  function input(parent, label, value='', type='text', attributes={}) {
    const wrap = node('label', label), field = node('input'); field.type = type; field.value = value;
    Object.entries(attributes).forEach(([k,v]) => field.setAttribute(k, v)); wrap.append(field); parent.append(wrap); return field;
  }
  function select(parent, label, choices) {
    const wrap = node('label', label), field = node('select'); field.setAttribute('aria-label',label); choices.forEach(([v,l]) => field.append(option(v,l))); wrap.append(field); parent.append(wrap); return field;
  }
  function detail(parent, title, value) {
    const details = node('details'); details.append(node('summary',title), node('pre', JSON.stringify(value,null,2))); parent.append(details);
  }
  function metric(parent, label, value) { const dt=node('dt',label), dd=node('dd',value); parent.append(dt,dd); }
  function render(payload) {
    const c = payload.context, r = payload.result, target = $('result-content'); target.replaceChildren();
    target.append(node('p', `Evaluated ${c.evaluation_date} · ${c.timezone || 'America/New_York'} · ${r.selected_status} selected coverage`));
    const summary = node('dl');
    metric(summary,'Full selected reference',dollars(r.full_selected_total)); metric(summary,'Known selected subtotal (partial when incomplete)',dollars(r.known_selected_subtotal));
    metric(summary,'Full lot reference',dollars(r.full_lot_total)); metric(summary,'Priced selected physical units',pair(r.coverage.selected_unit_fraction));
    metric(summary,'Priced selection lines',pair(r.coverage.selected_line_fraction)); metric(summary,'Priced known lot units',pair(r.coverage.lot_unit_fraction));
    metric(summary,'Unpriced selected units',String(r.coverage.unpriced_units)); metric(summary,'Unknown / unselected remainder',r.coverage.unknown_content_units === null ? 'Unknown quantity' : String(r.coverage.unknown_content_units));
    target.append(summary);
    if (r.display_rounding_reconciliation !== null && r.display_rounding_reconciliation !== '0.00') target.append(node('p', `Displayed reference rounding adjustment: ${dollars(r.display_rounding_reconciliation)}. Totals use exact amounts.`));
    if (r.line_display_rounding_reconciliation !== null && r.line_display_rounding_reconciliation !== '0.00' && r.line_display_rounding_reconciliation !== r.display_rounding_reconciliation) target.append(node('p', `Displayed line rounding adjustment: ${dollars(r.line_display_rounding_reconciliation)}.`));
    const values=node('div');
    c.selected_cards.forEach(s => {
      const p=s.captured_identity, box=node('div',undefined,'card');
      box.append(node('strong',`${p.name} · ${p.set_name} #${p.collector_number} × ${s.quantity}`),node('p',`Assumptions: ${s.assumptions || 'Unspecified'} · edition ${s.edition || 'unknown'}, condition ${s.condition || 'unknown'}, grade ${s.grade || 'raw/unknown'} ${s.grader || ''}`), node('p',s.completion_identity_basis));
      const ref=c.value_references.find(v => v.reference_id === s.chosen_value_reference);
      if (ref) {
        box.append(node('p', `${ref.provenance} · ${ref.currency || 'unknown currency'} ${ref.amount ?? 'unknown'} ${ref.value_scope === 'selection_group_total' ? 'group total, counted once' : 'per card'} · original date ${ref.as_of || 'unknown'} · ${r.reference_eligibility[ref.reference_id] || 'inactive alternative'}`));
        if (ref.value_scope === 'per_card') box.append(node('p',`Line display: ${dollars(r.line_displays?.[s.selection_id] ?? r.reference_terms.find(t=>t.selection_ids.length===1 && t.selection_ids[0]===s.selection_id)?.display_amount)}`));
      } else box.append(node('p','Unpriced selection'));
      values.append(box);
    }); target.append(values);
    const comparisons=node('div',undefined,'cost-grid');
    Object.entries(r.comparisons).forEach(([key,v]) => {
      const box=node('div',undefined,'basis'), dl=node('dl'), partial=node('dl');
      box.append(node('h3', key==='planned_bid' ? 'Personal planned bid' : v.price_kind==='current_bid' ? 'Observed current bid' : 'Observed asking price'),node('p',`Original price date: ${v.price_date || 'Unknown'}`));
      metric(dl,'Base price',dollars(v.base_price)); metric(dl,'Full delivered cost',dollars(v.full_delivered_cost)); metric(partial,'Known cost subtotal',dollars(v.known_cost_subtotal));
      metric(dl,'Full selected reference minus base price',dollars(v.full_selected_reference_minus_base_price)); metric(dl,'Full selected reference minus delivered cost',dollars(v.full_selected_reference_minus_delivered_cost));
      metric(partial,'Partial known reference minus base price',dollars(v.known_selected_reference_minus_base_price)); metric(partial,'Partial known reference minus known costs',dollars(v.known_reference_minus_known_costs_partial));
      metric(partial,'Full goal-useful reference minus base price',dollars(v.full_goal_useful_reference_minus_base_price)); metric(partial,'Full goal-useful reference minus delivered cost',dollars(v.full_goal_useful_reference_minus_delivered_cost));
      metric(partial,'Partial useful reference minus known costs',dollars(v.known_goal_useful_reference_minus_known_costs_partial));
      box.append(dl,node('p',`Unknown / ineligible components: ${v.unknown_or_ineligible_components.join(', ') || 'None'}`));
      const more=node('details');more.append(node('summary','Partial and goal-useful differences'),partial);box.append(more);
      detail(box,'Original costs, dates and supplied assumptions',c.delivery_cost_inputs[key]);comparisons.append(box);
    }); target.append(comparisons);
    const goal=node('div',undefined,'card'); goal.append(node('h3','Goal-useful reference and potential gain'));
    if (c.frozen_goal) {
      goal.append(node('p',`${c.frozen_goal.name || c.frozen_goal.goal_id} · ${r.goal.policy} · version ${c.frozen_goal.version}`));
      const dl=node('dl'); metric(dl,'Full useful reference',dollars(r.goal.full_useful_total)); metric(dl,'Known useful subtotal',dollars(r.goal.known_useful_subtotal));
      metric(dl,'Distinct potential completion gain',r.goal.full_distinct_gain === null ? 'Unavailable: unresolved identity' : String(r.goal.full_distinct_gain));
      metric(dl,'Confirmed distinct subset',String(r.goal.confirmed_distinct_gain)); metric(dl,'Allocated useful units',pair(r.goal.useful_unit_fraction));goal.append(dl);
      goal.append(node('p',`Stable representative choices: ${(r.goal.representatives || []).map(v=>{const s=c.selected_cards.find(s=>s.selection_id===v.selection_id);return `${s?.captured_identity.name || 'Selected card'} #${s?.captured_identity.collector_number || '?'} → ${v.item_id}, one unit`;}).join('; ') || 'None'}`),node('p',`Unresolved selections: ${(r.goal.unknown_completion_selection_ids || []).join(', ') || 'None'}`),node('p',`Unallocated group shares: ${(r.goal.unallocated_group_reference_ids || []).join(', ') || 'None'}`));
    } else goal.append(node('p','Select a frozen goal to evaluate useful value and potential gain.'));
    target.append(goal,node('p','Dated reference differences only. These are not profit, resale proceeds or bidding advice. Research and planned bids do not change your collection.','note'));
    if (c.listing_observation.source_url) { const link=node('a','Open captured listing on eBay'); link.href=c.listing_observation.source_url;link.target='_blank';link.rel='noopener noreferrer';target.append(link); }
    (payload.reference_gaps || []).forEach(g=>target.append(node('p',`Reference gap: ${g}`)));
    if (payload.present_reference_age) detail(target,'Present reference age (captured result unchanged)',payload.present_reference_age);
    detail(target,'Provenance, eligibility, captured identities, goal and ownership context',c);
    detail(target,'Exact terms, representative choices and computed results',r);
    $('results').hidden=false;
  }
  if ($('captured-shopping')) { render(JSON.parse($('captured-shopping').textContent)); return; }
  function addCard(p) {
    const sid=crypto.randomUUID(), box=node('div',undefined,'selection'), controls=node('div',undefined,'controls');
    box.dataset.selection=sid;
    box.append(node('h3',`${p.name} · ${p.set_name} #${p.collector_number}`),node('p',`Selection ${sid} · catalog edition ${p.edition || 'unresolved'} · ${p.unresolved_fields.length ? `Unresolved: ${p.unresolved_fields.join(', ')}` : 'Resolved catalog metadata; physical fit needs confirmation'}`));
    const q=input(controls,'Quantity','1','number',{min:'1',max:'100000'}), assumptions=input(controls,'Identity / value assumptions','','text',{placeholder:'Describe recognized identity, edition and condition'});
    const advanced=node('details');advanced.append(node('summary','Edition, condition and grade assumptions'));
    const advancedControls=node('div',undefined,'controls');advanced.append(advancedControls);controls.append(advanced);advanced.className='wide';
    const edition=input(advancedControls,'Reference edition assumption',new FormData($('research')).get('value_edition'));
    const condition=input(advancedControls,'Raw condition assumption',new FormData($('research')).get('condition'));
    const grade=input(advancedControls,'Grade assumption',new FormData($('research')).get('grade'));
    const grader=input(advancedControls,'Grader assumption',new FormData($('research')).get('grader'));
    const completion=input(controls,'Physical identity confirmed for selected policy','','checkbox');completion.parentElement.className='check';
    const included=input(controls,'Include in group','','checkbox');included.parentElement.className='check';
    const mode=select(controls,'Chosen value',[['none','Unpriced'],['manual','Separate manual per-card estimate'],...p.candidates.map(r=>[r.reference_id,`${r.provenance} ${r.currency || '?'} ${r.amount ?? '?'} · ${r.as_of || '?'} · ${r.eligibility}`])]);
    const manual=input(controls,'Manual per-card amount','','text',{inputmode:'decimal',placeholder:'Unknown'}), date=input(controls,'Manual estimate date',today,'date'), currency=input(controls,'Manual currency','USD'), source=input(controls,'Optional estimate source URL','','url');
    p.candidates.forEach(r=>references.set(r.reference_id,{reference_id:r.reference_id,kind:'guide',observation_id:r.observation_id,printing_id:p.id}));
    if (p.guide) mode.value=p.guide.reference_id;
    const showManual=()=>[manual,date,currency,source].forEach(f=>{f.parentElement.hidden=mode.value!=='manual';});mode.addEventListener('change',showManual);showManual();
    box.append(controls);detail(box,'Retained guide candidates and original dates',p.candidates);
    const remove=node('button','Remove card');remove.type='button';remove.addEventListener('click',()=>{selections.delete(sid);box.remove();$('empty-lot').hidden=selections.size>0;status('Card removed. Any captured group containing it requires review.');$('lot-title').focus();});box.append(remove);
    selections.set(sid,{p,q,assumptions,edition,condition,grade,grader,completion,included,mode,manual,date,currency,source,box});$('selections').append(box);$('empty-lot').hidden=true;status(`${p.name} added to the comparison.`);q.focus();
  }
  async function browse(reset=true) {
    if (reset) offset=0;
    try {
      status('Loading indexed cards…');
      const params=new URLSearchParams(new FormData($('research')));params.set('offset',String(offset));
      const data=await request(`/api/shopping/catalog/?${params}`);goals=data.goals;total=data.total;
      const chosen=$('goal').value;$('goal').replaceChildren(option('','No goal'),...goals.map(g=>option(g.id,g.name)));$('goal').value=chosen;
      $('cards').replaceChildren();
      data.cards.forEach(p=>{const box=node('div',undefined,'card');box.append(node('h3',p.name),node('p',`${p.set_name} #${p.collector_number} · ${p.language || '?'} · ${p.edition || 'edition unresolved'} · ${p.variant || 'variant unresolved'}`),node('p',`${p.copy_count} associated physical copies · exact ownership ${p.exact_owned ? 'confirmed' : 'unconfirmed / missing'}`),node('p',p.guide ? `Conditional guide scenario: ${dollars(p.value)} · ${p.guide.as_of}` : 'Guide price unavailable'));
        const button=node('button','Add card');button.type='button';button.addEventListener('click',()=>addCard(p));box.append(button);$('cards').append(box);
      });
      $('catalog-count').textContent=total ? `${offset+1}–${Math.min(offset+40,total)} of ${total} indexed cards` : 'No indexed cards match. Clear a filter and retry.';
      $('previous').disabled=offset===0;$('next').disabled=offset+40>=total;status('Indexed cards ready.');
    } catch(e) {status(e.message,true);}
  }
  $('research').addEventListener('submit',e=>{e.preventDefault();browse();});$('previous').addEventListener('click',()=>{offset=Math.max(0,offset-40);browse(false);});$('next').addEventListener('click',()=>{offset+=40;browse(false);});
  $('lot-title').tabIndex=-1;$('group-date').value=today;
  $('capture-group').addEventListener('click',()=>{
    const members=Array.from(selections).filter(([,s])=>s.included.checked);
    if (!members.length || !$('group-amount').value || !$('group-assumptions').value) {status('Select group members, enter a total and describe its assumptions.',true);return;}
    const rid=crypto.randomUUID(), quantities=Object.fromEntries(members.map(([sid,s])=>[sid,Number(s.q.value)]));
    references.set(rid,{reference_id:rid,kind:'manual',amount:$('group-amount').value,currency:'USD',as_of:$('group-date').value,assumptions:$('group-assumptions').value,value_scope:'selection_group_total',applies_to_quantities:quantities});
    members.forEach(([,s])=>{s.mode.append(option(rid,`Captured group: $${$('group-amount').value} total · ${$('group-date').value}`));s.mode.value=rid;s.mode.dispatchEvent(new Event('change'));s.included.checked=false;});
    $('group-status').textContent=`Captured ${members.length} selection lines, with their current quantities. Group ${rid}.`;status('Group total captured once. Compare to check coverage.');
  });
  function costBasis(key,title) {
    const box=node('div',undefined,'basis');box.append(node('h3',title));
    const fields={};
    if (key==='listing_observation') fields.kind=select(box,'Observed price kind',[['current_bid','Current bid'],['current_asking_price','Asking price']]);
    fields.amount=input(box,title+' amount','','text',{inputmode:'decimal',placeholder:'Unknown'});fields.date=input(box,'Original price date',today,'date');fields.currency=input(box,'Price currency','USD');
    fields.costs={};
    for (const [kind,label] of [['shipping','Shipping'],['tax','Tax'],['other_costs','Other costs (enter 0 only if none apply)']]) {
      const component=node('div'), d=node('details');d.append(node('summary',`${label}: currency, date and assumptions`));
      fields.costs[kind]={amount:input(component,label+' amount','','text',{inputmode:'decimal',placeholder:'Unknown USD'}),currency:input(d,label+' currency','USD'),date:input(d,label+' supplied date',today,'date'),notes:input(d,label+' provenance / assumptions','','text',{placeholder:'How this cost was supplied'})};component.append(d);box.append(component);
    }
    $('costs').append(box);return fields;
  }
  const costs={listing_observation:costBasis('listing_observation','Observed listing'),planned_bid:costBasis('planned_bid','Personal planned bid')};
  $('ebay-query').addEventListener('input',()=>{$('ebay-search').href=`https://www.ebay.com/sch/i.html?_nkw=${encodeURIComponent($('ebay-query').value)}`;});
  function inputs() {
    const cards=[];
    selections.forEach((s,sid)=>{
      let chosen=s.mode.value==='none' ? null : s.mode.value;
      if (chosen==='manual') {
        const value={kind:'manual',amount:s.manual.value,currency:s.currency.value,as_of:s.date.value,source_url:s.source.value || null,assumptions:s.assumptions.value,value_scope:'per_card'};
        const signature=JSON.stringify(value), prior=manualVersions.get(sid);
        chosen=prior?.signature===signature ? prior.id : crypto.randomUUID();manualVersions.set(sid,{signature,id:chosen});references.set(chosen,{...value,reference_id:chosen});
      }
      cards.push({selection_id:sid,printing_id:s.p.id,quantity:Number(s.q.value),assumptions:s.assumptions.value,edition:s.edition.value,condition:s.condition.value,grade:s.grade.value,grader:s.grader.value,completion_confirmed:s.completion.checked,chosen_value_reference:chosen});
    });
    const raw={selected_cards:cards,value_references:Array.from(references.values()).filter(r=>r.kind==='guide' || acceptedReferences.has(r.reference_id) || cards.some(s=>s.chosen_value_reference===r.reference_id)),unknown_contents:{quantity:$('remainder').value==='' ? null : Number($('remainder').value),notes:$('remainder-notes').value},goal_id:$('goal').value,goal_version:goals.find(g=>g.id===$('goal').value)?.version || '',delivery_cost_inputs:{}};
    for (const [key,f] of Object.entries(costs)) {
      const component=(v)=>({amount:v.amount.value || null,currency:v.currency.value,status:v.amount.value==='' ? 'unknown':'known',date:v.date.value,notes:v.notes?.value || 'Manually supplied'});
      raw[key]={...component(f),price_kind:key==='listing_observation' ? f.kind.value : 'personal_planned_bid',source_url:key==='listing_observation' ? $('listing-url').value || null : null};
      raw.delivery_cost_inputs[key]=Object.fromEntries(Object.entries(f.costs).map(([kind,v])=>[kind,component(v)]));
    } return raw;
  }
  $('comparison').addEventListener('submit',async e=>{
    e.preventDefault();const buttons=Array.from($('comparison').querySelectorAll('button')), save=e.submitter?.value==='save';
    buttons.forEach(b=>b.disabled=true);
    try {const result=await request('/api/shopping/compare/',{method:'POST',headers:{'Content-Type':'application/json','X-CSRFToken':$('comparison').querySelector('[name=csrfmiddlewaretoken]').value},body:JSON.stringify({inputs:inputs(),name:$('comparison-name').value,save})});result.request.value_references.forEach(r=>acceptedReferences.add(r.reference_id));render(result);status('Comparison evaluated.');$('results').focus();if (result.saved_url) window.location.assign(result.saved_url);}catch(e){status(e.message,true);}finally{buttons.forEach(b=>b.disabled=false);}
  });
  browse();
})();
