'use strict';
const money=v=>v==null?'Unavailable':new Intl.NumberFormat('en-US',{style:'currency',currency:'USD'}).format(Number(v));
const gradeLabel=g=>g==='raw'?'Ungraded':`Grade ${g}`;
let savedHunt;
const huntChoices={demo:false,pool:'singles',focus:'all',budget:'150',goal_id:'',intent:'value',query:''};
let huntDisplayFilter='all';
let huntSequence=0,huntBusy=false,huntProvider=null;
const poolLabel=p=>({known_lots:'Known lots',singles:'Individual cards',mystery:'Mystery / repacks'}[p]||p);
const focusLabel=f=>({all:'All cards',kanto:'Kanto',johto:'Johto',rares:'Missing rares',bulk:'Cheap bulk'}[f]||f);
const displayDate=v=>Number.isNaN(Date.parse(v))?v:new Date(v).toLocaleString();
const cardPresent=c=>{if(typeof c.effective_card_present!=='boolean')throw new Error('Current card ownership is unavailable. Reload to try again.');return c.effective_card_present;};
function rarityTable(cards){
 const groups={};for(const c of cards){const g=groups[c.rarity]??={owned:0,total:0};g.total++;g.owned+=Number(cardPresent(c));}
 return `<div class="table-scroll"><table><thead><tr><th>Rarity</th><th>Owned / catalog</th><th>Missing</th></tr></thead><tbody>${Object.entries(groups).map(([k,v])=>`<tr><th>${esc(k)}</th><td>${v.owned} / ${v.total}</td><td>${v.total-v.owned}</td></tr>`).join('')}</tbody></table></div>`;
}
function valueSummary(){const v=window.parityData.valuation;return `<section class="panel"><h2>Collection estimates</h2><p>Confirmed variant estimates: ${v.confirmed.raw.priced} / ${v.confirmed.raw.owned} physical copies priced · ${money(v.confirmed.raw.subtotal)}${v.confirmed.raw.total===null?' (incomplete)':''}.</p><p class="muted">Guide dates: ${esc(v.source_dates.join(', ')||'None available')}. Records older than ${v.max_age_days} days are excluded.</p><details><summary>View estimates by assumed grade</summary><p>Other estimates assume a card variant and grade; they are not confirmed values.</p><p class="notice">These scenarios assume each copy matches its selected first-edition guide variant, or the standard guide variant when edition is unresolved. They do not establish your copies’ identity or confirmed value.</p><div class="value-grid">${Object.entries(v.conditional).map(([g,r])=>`<div><h3>${gradeLabel(g)}</h3><strong>${money(r.subtotal)}</strong><p>${r.priced} / ${r.owned} copies covered${r.total===null?' · incomplete':''}<br>${r.estimated} interpolated estimates</p></div>`).join('')}</div><p>Totals count every physical copy, including intentional duplicates. Set and species progress count unique entries. Missing estimates are excluded, never zero. Grade scenarios assume every covered copy receives that grade; they are separate from recorded slab grades and exclude grading fees.</p><p>Grade 7–8 gaps retain geometric interpolation labels; Grade 10 uses the PSA 10 guide. Per-copy source links and dates appear in My Cards.</p></details><p>Recorded purchase cost: ${Object.entries(v.purchase_subtotals).map(([c,n])=>`${esc(n)} ${esc(c)}`).join(' · ')||'Unknown'} · ${v.purchase_known} / ${v.confirmed.raw.owned} copies have a purchase amount. Currencies are kept separate.</p></section>`;}
function overview(){const p=window.parityData;if(p.owner_collection?.basis!=='effective-current-collection')throw new Error('Current collection status is unavailable. Reload to try again.');const t={...p.totals,...p.owner_collection};$('#content').innerHTML=`<div class="page-title"><h1>Overview</h1><div class="actions"><a href="/hunt/">Find eBay bargains</a><a href="/missing/">Find missing singles</a></div></div><p>My collection · Current species presence across Kanto and Johto.</p><div class="stats">${[['Kanto',t.kanto,151],['Johto',t.johto,100],['Total',t.total,251]].map(([name,n,max])=>`<article class="stat"><span>${name}</span><strong>${n} / ${max}</strong><progress value="${n}" max="${max}" aria-label="${name} progress"></progress></article>`).join('')}</div><p>${t.physical_copies} physical copies · ${t.exact_cards} unique catalog entries · ${251-t.total} missing species · ${t.unavailable_species} unavailable species.</p>${valueSummary()}<details class="panel"><summary>Pokémon rarity breakdown</summary>${rarityTable(Object.values(p.cards).filter(c=>c.supertype==='Pokémon'))}</details><h2>Sets</h2><div class="grid">${data.sets.map(s=>{const cards=Object.values(p.cards).filter(c=>p.catalog.find(x=>x.id===c.printing_id)?.set_id===s.id);const owned=cards.filter(cardPresent).length;return `<a class="card" href="/cards/?set=${esc(s.id)}">${esc(s.name)} · ${owned} / ${cards.length} owned · ${cards.length-owned} missing</a>`;}).join('')}</div>`;}
function copyPrices(copy){const v=window.parityData.valuation.copies[copy.id];if(!v)return '';return `<details><summary>Guide scenarios for this copy</summary><p class="notice">Conditional: ${esc(v.assumption||v.reason)}. Unresolved: ${esc(v.reason)}. These are not confirmed variant estimates.</p>${['raw','7','8','9','10'].map(g=>{const r=v.conditional[g];return r?`<p>${gradeLabel(g)}: <a href="${esc(r.source_url)}" target="_blank" rel="noopener noreferrer">${money(r.value)}</a> · ${esc(r.as_of)} · ${esc(r.basis)}${r.estimated?' · Interpolated':''}</p>`:`<p>${gradeLabel(g)}: Unavailable — no matching fresh guide evidence.</p>`;}).join('')}<p>Recorded slab: ${esc([copy.grading_company,copy.grade].filter(Boolean).join(' ')||'Unknown')} · Purchase cost: ${esc(copy.purchase_amount||'Unknown')} ${esc(copy.purchase_currency||'')}</p></details>`;}
function huntAvailable(){return !!(huntProvider?.enabled&&huntProvider?.configured);}
function huntSourceLabel(h){return h.demo?'Sample':(h.coverage?.environment||h.environment)==='sandbox'?'eBay sandbox snapshot':'eBay search snapshot';}
function closeHuntReveal(){$('#editor').close();$('#editor-body').replaceChildren();}
function updateHuntControls(){
 const form=$('#parity-hunt');
 if(form){
  form.querySelectorAll('input,select,button').forEach(el=>el.disabled=huntBusy);
  const sample=$('#hunt-source').value==='sample',button=$('#hunt-search');
  button.disabled=huntBusy||(!sample&&!huntAvailable());
  button.textContent=huntBusy?'Searching…':sample?'Find sample cards':huntProvider?.environment==='sandbox'?'Search eBay sandbox':'Search eBay';
  $('#hunt-provider').textContent=sample?'Sample cards are synthetic examples. Choose eBay search to search listings.':huntProvider?.note||'Checking eBay search availability…';
  $('#hunt-source option[value="live"]').textContent=huntProvider?.environment==='sandbox'?'eBay · Sandbox':huntProvider?.environment==='production'?'eBay · Production':'eBay search';
  if(!sample&&huntProvider?.environment==='sandbox')$('#hunt-provider').textContent=$('#hunt-provider').textContent.replace('Live eBay','Sandbox eBay')+' Sandbox results are test listings.';
 }
 const next=$('#hunt-next');if(next)next.disabled=huntBusy||!huntAvailable();
 const check=$('#hunt-check');if(check)check.disabled=huntBusy;
}
async function loadHuntProvider(sequence){
 try{const response=await api('/api/hunts/');if(sequence!==huntSequence)return;huntProvider=response.search_status||{enabled:false,configured:false,note:'eBay search is unavailable in this environment.'};}
 catch(e){if(sequence!==huntSequence)return;huntProvider={enabled:false,configured:false,note:'eBay search availability could not load. Refresh the search status to retry.'};}
 updateHuntControls();
}
function captureHuntChoices(){
 huntChoices.demo=$('#hunt-source').value==='sample';
 for(const field of ['pool','focus','budget','goal_id','intent','query'])huntChoices[field]=$('#hunt-'+field.replace('_id','')).value;
}
function huntView(single){
 const sequence=++huntSequence;savedHunt=null;huntProvider=null;closeHuntReveal();
 if(single){huntChoices.pool='singles';huntChoices.intent='missing';}
 const goalParam=new URLSearchParams(location.search).get('goal');
 if(goalParam&&data.goals.some(g=>g.id===goalParam))huntChoices.goal_id=goalParam;
 if(huntChoices.goal_id&&!data.goals.some(g=>g.id===huntChoices.goal_id))huntChoices.goal_id='';
 $('#content').innerHTML=`<h1>${single?'Missing singles':'Hunts'}</h1><p>Listing identities stay hidden until you reveal them.</p><div id="hunt-results" aria-live="polite"></div><h2 id="hunt-settings" hidden>Search settings</h2><form id="parity-hunt" class="form-grid"><div><label for="hunt-intent">Search purpose</label><select id="hunt-intent"><option value="value">Find bargains</option><option value="missing">Fill a collection goal</option></select></div><div><label for="hunt-source">Search source</label><select id="hunt-source"><option value="live">eBay search</option><option value="sample">Sample cards</option></select></div><p id="hunt-provider" class="notice full" role="status">Checking eBay search availability…</p><div class="full"><label for="hunt-query">eBay search words (optional)</label><input id="hunt-query" type="search" maxlength="200" placeholder="Blank uses your catalog and goal"></div><div><label for="hunt-pool">Search pool</label><select id="hunt-pool"><option value="known_lots">Known lots · hidden contents</option><option value="singles">Individual cards</option><option value="mystery">Mystery / repacks · contents unknown</option></select></div><div><label for="hunt-goal">Collection goal</label><select id="hunt-goal"><option value="">Vintage 251 · all eligible cards</option>${data.goals.map(g=>`<option value="${esc(g.id)}">${esc(g.name)}${g.definition.lineage?' · version '+g.definition.lineage.number:''} · ${g.satisfied} / ${g.total}</option>`).join('')}</select></div><div><label for="hunt-focus">Focus</label><select id="hunt-focus">${['all','kanto','johto','rares','bulk'].map(f=>`<option value="${f}">${{all:'All',kanto:'Kanto · 1–151',johto:'Johto · 152–251',rares:'Missing rares',bulk:'Cheap bulk'}[f]}</option>`).join('')}</select></div><div><label for="hunt-budget">Delivered budget (USD)</label><input id="hunt-budget" type="number" min="0" max="10000" step="0.01" required></div><p class="full search-help">Budget includes shipping, before tax.</p><div class="full actions"><button id="hunt-search" disabled>Search eBay</button></div></form><details><summary>How search works</summary><p>Bargain searches include owned and missing cards; goal searches look for missing targets. Leave search words blank for catalog suggestions. Results compare delivered prices with available guide references; each search saves a private, bounded snapshot.</p></details><div class="actions"><button id="hunt-check" class="secondary" type="button">Refresh eBay status</button><a href="/finds/">Open saved finds</a><a href="/pokedex/">Build a collection goal</a></div>`;
 $('#hunt-source').value=huntChoices.demo?'sample':'live';
 for(const field of ['pool','focus','budget','goal_id','intent','query'])$('#hunt-'+field.replace('_id','')).value=huntChoices[field];
 $('#parity-hunt').onchange=()=>{captureHuntChoices();updateHuntControls();};
 $('#parity-hunt').onsubmit=e=>{e.preventDefault();captureHuntChoices();const request={pool:huntChoices.pool,focus:huntChoices.focus,budget:huntChoices.budget,demo:huntChoices.demo,offset:0,intent:huntChoices.intent,query:huntChoices.query};if(huntChoices.goal_id)request.goal_id=huntChoices.goal_id;runHunt(request);};
 $('#hunt-check').onclick=()=>{huntProvider=null;updateHuntControls();loadHuntProvider(sequence);};
 updateHuntControls();loadHuntProvider(sequence);
}
async function runHunt(request){
 if(huntBusy||(!request.demo&&!huntAvailable()))return;
 const sequence=huntSequence;huntBusy=true;closeHuntReveal();updateHuntControls();status(request.demo?'Loading sample cards…':'Searching eBay and saving this batch…');
 try{const found=await api('/api/hunts/',request);if(sequence!==huntSequence)return;savedHunt=found;renderHunt();status(`${found.results.length} ${found.demo?'sample finds':'eBay results'} saved. Open Saved finds to reopen this batch.`);}
 catch(e){if(sequence===huntSequence)status(e.message,true);}
 finally{huntBusy=false;updateHuntControls();}
}
function guideComparison(r){
 const p=r.pricing;
 if(!p||p.reference_total==null)return `<p><strong>Guide comparison unavailable</strong></p><p>${esc(p?.note||'A supported guide reference is not available for this listing.')}</p>`;
 const labels={ungraded_guide:'Ungraded guide reference',graded_guide:'Matched graded guide reference',identified_subtotal:'Identified-card guide subtotal',catalog_average_benchmark:'Catalog average benchmark'};
 const states={matched:'Matched reference',conditional:'Conditional reference',partial:'Partial contents priced',benchmark:'Average benchmark'};
 const discount=Number(p.discount_percent),saving=Number(p.saving),percentage=new Intl.NumberFormat('en-US',{maximumFractionDigits:1}).format(Math.abs(discount));
 const subject=r.type==='auction'?'Current bid + shipping':'Delivered price';
 let comparison='Difference unavailable';
 if(p.discount_percent!=null&&Number.isFinite(discount))comparison=discount===0?`${subject} is at the reference`:`${subject} is ${p.saving!=null&&Number.isFinite(saving)?money(Math.abs(saving))+' · ':''}${percentage}% ${discount>0?'below':'above'} ${p.status==='benchmark'?'benchmark':'reference'}`;
 const counts=p.status==='benchmark'?`${money(p.average_per_card)} average per card × ${p.lot_count??'unknown'} stated cards`:`${p.priced_cards??0} / ${p.identified_cards??0} identified cards priced${p.lot_count!=null?' · '+p.lot_count+' stated cards':''}`;
 return `<div class="notice"><strong>${esc(labels[p.basis]||'Guide reference')}: ${money(p.reference_total)}</strong><p>${esc(comparison)}</p><small>${esc(states[p.status]||p.status)} · ${esc((p.source_dates||[]).join(', ')||'Guide date unavailable')}</small><p>${esc(counts)} · ${Math.round((p.coverage??0)*100)}% price coverage</p><p>${esc(p.note||'')}</p></div>`;
}
function belowGuide(r){return r.pricing?.reference_total!=null&&Number(r.pricing.discount_percent)>0;}
function revealedGuides(r){
 const evidence=r.pricing?.evidence;if(!Array.isArray(evidence)||!evidence.length)return '';
 return `<h3>Matched guide evidence</h3>${evidence.map(e=>{const card=window.parityData.cards[e.card_id];let url;try{const candidate=new URL(e.source_url);if(candidate.protocol==='https:')url=candidate.href;}catch{}return `<article class="panel"><strong>${esc(card?.name||e.card_id)}</strong><p>${esc(card?.set||'')} ${card?.number?'#'+esc(card.number):''} · ${e.grade==='raw'?'Ungraded':'Grade '+esc(e.grade)} reference · ${e.edition==='first_edition'?'First-edition guide':'Standard guide'}</p><p>${url?`<a href="${esc(url)}" target="_blank" rel="noopener noreferrer">${money(e.guidevalue)} · View guide</a>`:money(e.guidevalue)} · ${esc(e.as_of)}</p></article>`;}).join('')}`;
}
function renderHunt(){
 const h=savedHunt,target=$('#hunt-results');if(!h||!target)return;
 const coverage=h.coverage||{},nextOffset=coverage.next_offset,canContinue=!h.demo&&Number.isInteger(nextOffset)&&nextOffset>h.settings.offset;
 const rows=huntDisplayFilter==='below'?h.results.filter(belowGuide):h.results;
 const referenced=h.results.filter(r=>r.pricing?.reference_total!=null).length;
 const speciesLabel=h.goal?.policy==='species'?'Missing goal species':'Missing species';
 const goalLabel=h.settings.intent==='value'?'Guide comparison scope':'Goal';
 target.innerHTML=`<h2>${rows.length} ${h.demo?'sample finds':'eBay results'}</h2><p>${esc(h.note)} Collection fit uses your current copies.</p>${h.goal?`<p>${goalLabel}: <strong>${esc(h.goal.name)}</strong>${h.settings.intent==='missing'?' · '+(h.goal.policy==='species'?'missing species':'missing printings'):''} · Frozen search scope${h.goal.version?' · Version '+esc(h.goal.version):''}. Current account ownership is compared separately.</p>`:''}<p>${h.settings.intent==='missing'?'Missing targets':'Bargain search'} · ${esc(poolLabel(h.settings.pool))} · ${esc(focusLabel(h.settings.focus))} · budget ${money(h.settings.budget)} before tax · ${esc(displayDate(h.created))}</p>${h.settings.query?`<p>Search words: ${esc(h.settings.query)}</p>`:''}<details><summary>Search coverage and saved settings</summary><p>This batch searched ${coverage.queries_run??0} queries · ${coverage.queries_total??'unknown'} planned overall · prices before tax.</p><p>Each next batch keeps this saved search’s words, purpose, goal, pool, focus and budget, and is saved separately.</p></details>${coverage.limited?'<p class="notice">This search reached its listing limit. The saved results cover a bounded snapshot.</p>':''}<div class="toolbar"><div><label for="hunt-display">Price filter</label><select id="hunt-display"><option value="all">All search results</option><option value="below">Below guide reference</option></select></div><p id="hunt-shown">Showing ${rows.length} / ${h.results.length} saved results · ${referenced} guide comparisons · ${h.results.length-referenced} unavailable.</p></div><div class="grid">${rows.map(r=>`<article class="card"><span class="pill">${huntSourceLabel(h)} · ${r.type==='auction'?'Auction':'Fixed price'}</span><h3>${esc(r.label)}</h3><p>${r.count??'Unknown number of'} cards · ${esc(r.confidence)}</p><h3>${money(r.delivered)} ${r.type==='auction'?'current bid + shipping':'delivered'}</h3>${guideComparison(r)}${r.type==='auction'?`<p>Final auction price may rise · ends ${esc(r.end_time)}.</p>`:''}<button data-reveal-result="${esc(r.id)}">Reveal contents</button><details><summary>Collection fit</summary><p>${speciesLabel}: ${r.confidence==='Contents unknown'?'Unknown':r.dex_hits+' candidates'} · ${h.goal?'Missing goal printings':'New printings'}: ${r.confidence==='Contents unknown'?'Unknown':r.exact_hits+' candidates'}</p><p>Duplicate share: ${r.duplicate_ratio==null?'Unknown':Math.round(r.duplicate_ratio*100)+'% of identified cards'}</p><p>Evidence score: ${r.score??'Unknown'} / 100 · ${Math.round(r.score_coverage*100)}% coverage</p></details></article>`).join('')||(h.results.length&&huntDisplayFilter==='below'?'<p>No listings in this batch are below an available reference. Choose All search results to see above-reference and unpriced listings.</p>':'<p>No matching results in this batch. Try other search words, budget, focus or pool, or continue to the next batch when available. Unknown prices/shipping and unavailable listings are excluded.</p>')}</div>${canContinue?'<div class="actions"><button id="hunt-next" class="secondary">Search next eBay batch</button><a href="/finds/">Earlier saved batches</a></div>':!h.demo?Number.isInteger(coverage.offset)?'<p class="muted">This saved search has no further query batches.</p>':'<p class="muted">Reopen this snapshot, or start a new search for fresh listings.</p>':''}`;
 if($('#hunt-settings'))$('#hunt-settings').hidden=false;
 $('#hunt-display').value=huntDisplayFilter;
 $('#hunt-display').onchange=()=>{huntDisplayFilter=$('#hunt-display').value;closeHuntReveal();renderHunt();};
 if(canContinue)$('#hunt-next').onclick=()=>runHunt({...h.settings,demo:false,offset:nextOffset,continuation_batch:h.batch});
 updateHuntControls();
 document.querySelectorAll('[data-reveal-result]').forEach(b=>b.onclick=async()=>{
  const sequence=huntSequence;b.disabled=true;
  try{const r=await api(`/api/hunts/${h.batch}/${h.id}/reveal/${b.dataset.revealResult}/`,{});if(sequence!==huntSequence||savedHunt!==h)return;$('#editor-title').textContent='Revealed contents';$('#editor-body').innerHTML=`<h3>${esc(r.title)}</h3><p>${esc(r.confidence)} · Candidates only; no inventory is added.</p>${guideComparison(r)}${revealedGuides(r)}${r.cards.map(k=>{const c=window.parityData.cards[k];return `<p>${esc(c?.name||k)} · ${esc(c?.set)} #${esc(c?.number)}</p>`;}).join('')||'<p>Exact contents unknown; no specific species yield is claimed.</p>'}${r.url?`<p>The seller’s page reveals photos and names.</p><a href="${esc(r.url)}" target="_blank" rel="noopener noreferrer">Open on eBay</a>`:'<p>No purchase link for samples.</p>'}`;
  // Native dialog focus handback needs an enabled opener at showModal time.
  b.disabled=false;b.focus({preventScroll:true});openDialog('#editor');}
  catch(e){if(sequence===huntSequence&&savedHunt===h)status(e.message,true);}
  finally{b.disabled=false;}
 });
}
async function findsView(){
 const sequence=++huntSequence;savedHunt=null;huntProvider=null;closeHuntReveal();
 $('#content').innerHTML='<div class="page-title"><h1>Saved finds</h1><a href="/hunt/">Start an eBay search</a></div><p>Reopening hides identities again. Collection fit uses your current copies.</p><div id="hunt-results" aria-live="polite"></div><details class="panel" open><summary>Saved search history</summary><div class="history" id="saved-searches"></div></details>';
 try{
  const response=await api('/api/hunts/');if(sequence!==huntSequence||!$('#saved-searches'))return;const rows=response.hunts;huntProvider=response.search_status||null;
  $('#saved-searches').innerHTML=rows.map((r,i)=>{const goal=r.goal?.name||data.goals.find(g=>g.id===r.settings.goal_id)?.name;return `<button data-saved="${i}">${huntSourceLabel(r)} · ${r.settings.intent==='missing'?'Missing targets':'Bargains'} · ${esc(poolLabel(r.settings.pool))} · ${esc(focusLabel(r.settings.focus))} · ${money(r.settings.budget)}${r.settings.query?' · '+esc(r.settings.query):''}${goal?' · '+esc(goal):''}<br><small>${esc(displayDate(r.created))}</small></button>`;}).join('')||'<p>No saved searches yet. Start an eBay or sample search to save your first batch.</p>';
  document.querySelectorAll('[data-saved]').forEach(b=>b.onclick=async()=>{const openSequence=++huntSequence;b.disabled=true;try{const r=rows[Number(b.dataset.saved)];closeHuntReveal();const found=await api(`/api/hunts/${r.batch}/${r.id}/`);if(openSequence!==huntSequence)return;savedHunt=found;renderHunt();}catch(e){if(openSequence===huntSequence)status(e.message,true);}finally{b.disabled=false;}});
 }catch(e){if(sequence===huntSequence)status(e.message,true);}
}
window.renderParity=route=>{const routes={'/overview/':overview,'/hunt/':()=>huntView(false),'/missing/':()=>huntView(true),'/finds/':findsView};if(!routes[route]||!window.parityData)return false;routes[route]();return true;};
