'use strict';
// Engineering fixtures exercise the shipped adapter; no provider or customer data.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync(process.argv[2], 'utf8');
const runId = '11111111-1111-4111-8111-111111111111';
const nextId = '22222222-2222-4222-8222-222222222222';
const baseChoices = {intent:'deals',goal_id:null,missing_basis:'species',focus:'all',budget:null,query:'',set_id:null,product_type:'both',sort:'ending_soonest',english_vintage:true,species:null,group_id:null,printing_id:null,goal_version:null,generation:7,browse_requests:1};
const row = {id:'one',proposed_identity:{name:'Engineering card',set_name:'Engineering set',collector_number:'1',artwork_url:null},listing_price:'10',shipping:null,delivered_total:null,classification:'conditional',reason:'Shipping is unknown.',basis:'Raw condition scenario.',reference:{amount:'20',as_of:'2020-01-01',valuation_as_of:null,captured_at:'2021-01-01',grade:'raw'},comparison:{reference_minus_listing_price:'10',reference_minus_delivered_total:null},revealed:false,save_allowed:false,save_reason:'Temporary comparison; saving unavailable.'};
const complete = (id=runId, rows=[row]) => ({run_id:id,state:'complete',running:false,choices:baseChoices,scope_label:'Deals include owned cards',expires_in_seconds:1800,results:structuredClone(rows),counts:{summary_count:1},has_next:true,note:'Temporary results.'});
class Element {
  constructor(id) {this.id=id;this.value='';this.dataset={};this.listeners={};this.disabled=false;this.hidden=false;this.textContent='';this._html='';}
  addEventListener(type, fn) {(this.listeners[type] ||= []).push(fn);}
  async emit(type,extra={}) {for (const fn of this.listeners[type] || []) await fn({target:this,preventDefault(){},...extra});}
  focus() {this.focused=true;}
  remove() {this._html='';}
  after() {}
  insertAdjacentHTML(where,html) {this._html+=html;}
  setAttribute(key,value) {this[key]=value;}
  querySelector() {return {value:'csrf-test'};}
  querySelectorAll() {
    const matches=[...this._html.matchAll(/data-discovery-reveal="([^"]+)"/g)];
    this.buttons=matches.map(match=>{const e=new Element('reveal');e.dataset.discoveryReveal=match[1];return e;});
    return this.buttons;
  }
  set innerHTML(value) {this._html=value;}
  get innerHTML() {return this._html;}
  replaceChildren() {this._html='';}
}
function setup(responses, search='') {
  const elements=new Map(),calls=[],localCalls=[],localResponses=[],timers=new Map(),intervals=new Map(),events={};let timerId=0,clockNow=Date.now();
  const get=id=>{if(!elements.has(id)) elements.set(id,new Element(id));return elements.get(id);};
  get('discovery-focus').value='all';get('discovery-missing-basis').value='species';get('discovery-filter').value='all';
  const initial=Object.fromEntries(new URLSearchParams(search));get('discovery-context').textContent=JSON.stringify({generation:7,species:initial.species?Number(initial.species):null,group:initial.group||null,child:initial.child||null});get('discovery-initial').textContent=JSON.stringify(initial);get('discovery-goals').textContent='[]';get('discovery-product-type').value='both';get('discovery-sort').value='ending_soonest';get('discovery-english-vintage').checked=true;
  const location={origin:'http://local.test',href:'http://local.test/shopping/'+search,search,reload(){calls.push({reload:true});}};
  const window={scrollY:0,scrollTo(){},addEventListener(type,fn){events[type]=fn;}};
  const context={document:{createElement:()=>({getContext:()=>null}),getElementById:get,querySelector:()=>get('local-explorer'),body:{dataset:{navigationBinding:'binding-test',navigationAccount:'account-test'}},addEventListener(type,fn){events[type]=fn;}},window,location,requestAnimationFrame:fn=>fn(),history:{replaceState(a,b,url){location.href=location.origin+url;}},URL,URLSearchParams,Intl,Date:{now:()=>clockNow,parse:Date.parse},setInterval(fn){intervals.set(++timerId,fn);return timerId;},clearInterval(id){intervals.delete(id);},setTimeout(fn){timers.set(++timerId,fn);return timerId;},clearTimeout(id){timers.delete(id);},fetch:async(url,init)=>{
    if (url.startsWith('/api/shopping/discovery/catalog/')) {localCalls.push({url,init});const reply=await (localResponses.shift() || {mode:'cards',results:[],total:0,offset:0,sets:[],has_more:false});return {ok:true,status:200,json:async()=>({...reply,authority:{account_id:'account-test',binding:'binding-test'}})};}
    calls.push({url,init,body:init.body?JSON.parse(init.body):undefined});
    const response=responses.shift();if(response instanceof Error) throw response;
    const data=typeof response==='function'?await response(calls.at(-1)):await response;
    return {ok:true,status:200,json:async()=>({...data,provider:{enabled:true,configured:true,...data.provider},authority:{account_id:'account-test',binding:'binding-test',...data.authority}})};
  }};
  vm.createContext(context);vm.runInContext(source,context);
  return {get,calls,localCalls,localResponses,timers,intervals,events,window,location,context,advance(ms){clockNow+=ms;},now:()=>clockNow};
}
async function flush() {for(let i=0;i<80;i++) await Promise.resolve();}
async function check(name,test) {await test();passed.push(name);}
const passed=[];
(async()=>{
  await check('lot finder requires a name and ignores hidden legacy refinements',async()=>{
    const t=setup([{goals:[],sets:[]},complete()]);await flush();
    t.get('discovery-form').dataset.lotSearch='true';
    await t.get('discovery-form').emit('submit');await flush();
    assert.equal(t.calls.length,1);
    t.get('discovery-query').value='Venusaur';t.get('discovery-set').value='Base Set';
    t.get('discovery-product-type').value='singles';t.get('discovery-budget').value='1';
    t.get('discovery-focus').value='bulk';
    await t.get('discovery-form').emit('submit');await flush();
    assert.deepEqual(t.calls[1].body,{...baseChoices,query:'Venusaur',set_id:'Base Set',product_type:'mixed_lots',english_vintage:false});
    assert.equal(t.get('discovery-stop').hidden,true);
  });
  await check('lot finder preserves provider order without guessing a single-card identity',async()=>{
    const result=complete(runId,[{...row,id:'broad',title:'Binder collection'},{...row,id:'target',title:'VenusaurHOLO15/102 three card lot'}]);
    result.choices={...baseChoices,query:'Venusaur'};
    const t=setup([{goals:[],sets:[]},result]);await flush();
    t.get('discovery-form').dataset.lotSearch='true';t.get('discovery-query').value='Venusaur';
    await t.get('discovery-form').emit('submit');await flush();
    const html=t.get('discovery-cards').innerHTML;
    assert.ok(html.indexOf('offer-broad') < html.indexOf('offer-target'));
    assert.doesNotMatch(html,/Other lots returned by eBay/);
    assert.doesNotMatch(html,/Proposed:/);
  });
  await check('opening uses local metadata only; deals require neither goal nor card',async()=>{
    const t=setup([{goals:[],sets:[]}]);await flush();
    assert.equal(t.calls.length,1);assert.equal(t.calls[0].init.method,'GET');
    assert.equal(t.get('discovery-search').disabled,false);
    assert.match(t.get('intent-description').textContent,/including cards you own/);
    assert.equal(t.timers.size,0);
  });
  await check('explicit start captures defaults and preserves unknown shipping and dates',async()=>{
    const t=setup([{goals:[]},complete()]);await flush();await t.get('discovery-form').emit('submit');await flush();
    assert.deepEqual(t.calls[1].body,baseChoices);
    const html=t.get('discovery-cards').innerHTML;
    assert.match(html,/Conditional comparison/);assert.match(html,/Shipping<\/dt><dd[^>]*>Unknown/);
    assert.match(html,/Delivered · before tax<\/dt><dd[^>]*>Unknown/);
    assert.match(html,/Provider valuation date: Unknown/);assert.match(html,/2020-01-01/);
    assert.doesNotMatch(html,/\$10\.00 below reference/);
    assert.match(t.location.href,/run_id=/);assert.equal(t.timers.size,0);
  });
  await check('local filter and choice edits do not fetch; next uses captured choices',async()=>{
    const t=setup([{goals:[]},complete(),complete(nextId)]);await flush();await t.get('discovery-form').emit('submit');await flush();
    t.get('discovery-filter').value='below';await t.get('discovery-filter').emit('change');
    assert.equal(t.calls.length,2);assert.match(t.get('discovery-cards').innerHTML,/No results match this filter/);
    t.get('discovery-query').value='changed';await t.get('discovery-form').emit('input');
    assert.equal(t.get('discovery-next').disabled,true);assert.equal(t.calls.length,2);
    t.get('discovery-query').value='';await t.get('discovery-form').emit('input');
    assert.equal(t.get('discovery-next').disabled,false);await t.get('discovery-next').emit('click');await flush();
    assert.deepEqual(t.calls[2].body,{continuation_run:runId});
  });
  await check('More keeps received listings visible while awaiting its response',async()=>{
    let finish;const pending=new Promise(resolve=>{finish=resolve;});
    const first=complete();first.choices={...baseChoices,query:'Hypno Fossil'};
    const t=setup([{goals:[]},first,pending,{...complete(),choices:first.choices}]);await flush();
    t.get('discovery-query').value='Hypno Fossil';await t.get('discovery-form').emit('submit');await flush();
    const before=t.get('discovery-cards').innerHTML;
    const more=t.get('discovery-next').emit('click');await flush();
    assert.equal(t.get('discovery-results').hidden,false);
    assert.equal(t.get('discovery-cards').innerHTML,before);
    assert.equal(t.get('discovery-stop').disabled,false);
    assert.match(t.get('discovery-next-note').textContent,/keep browsing/);
    finish({...complete(runId,[]),choices:first.choices,running:true,state:'running'});await more;await flush();
    assert.equal(t.get('discovery-cards').innerHTML,before);
    assert.equal(t.get('discovery-results').hidden,false);
    assert.equal(t.get('discovery-next').disabled,true);
    for(const fn of [...t.timers.values()]) await fn();await flush();
    assert.equal(t.get('discovery-next').disabled,false);
  });
  await check('Stop after received results closes continuation without acquiring',async()=>{
    const t=setup([{goals:[]},complete(),{...complete(runId,[]),state:'stopped',has_next:false}]);await flush();await t.get('discovery-form').emit('submit');await flush();
    assert.equal(t.get('discovery-stop').disabled,false);
    await t.get('discovery-stop').emit('click');await flush();
    assert.equal(t.get('discovery-next').disabled,true);assert.equal(t.get('discovery-stop').disabled,true);
    assert.match(t.calls[2].url,/stop/);assert.doesNotMatch(t.get('discovery-cards').innerHTML,/Engineering card/);
  });
  await check('current missing policy and explicit frozen goal remain distinct',async()=>{
    const t=setup([{goals:[{id:'frozen',name:'Retained goal',version:3,policy:'species'}]},complete()]);await flush();
    await t.get('find-missing').emit('click');assert.match(t.get('missing-policy').textContent,/My current collection · missing Pokémon species/);
    t.get('discovery-missing-basis').value='species';await t.get('discovery-form').emit('change');assert.match(t.get('missing-policy').textContent,/missing Pokémon species/);
    t.get('discovery-goal').value='frozen';await t.get('discovery-form').emit('change');
    assert.equal(t.get('missing-basis-label').hidden,true);assert.match(t.get('missing-policy').textContent,/Frozen goal: Retained goal/);
    await t.get('discovery-form').emit('submit');await flush();
    assert.equal(t.calls[1].body.goal_id,'frozen');assert.equal(t.calls[1].body.intent,'missing');
  });
  await check('title identity and checked seller appear immediately without reveal',async()=>{
    const visible={...row,title:'Seller engineering title',item_url:'https://www.ebay.com/itm/123',revealed:false};
    const t=setup([{goals:[]},complete(runId,[visible])]);await flush();await t.get('discovery-form').emit('submit');await flush();
    assert.match(t.get('discovery-cards').innerHTML,/Seller engineering title/);
    assert.match(t.get('discovery-cards').innerHTML,/Open seller listing on eBay/);
    assert.match(t.get('discovery-cards').innerHTML,/Assess lot/);
    assert.doesNotMatch(t.get('discovery-cards').innerHTML,/data-discovery-reveal/);
    assert.equal(t.calls.length,2);
  });
  await check('stop during admission waits for new run id, never stops a prior run',async()=>{
    let admit;const admission=new Promise(resolve=>{admit=resolve;});
    const stopped={...complete(nextId,[]),state:'stopped',has_next:false};
    const t=setup([{goals:[]},complete(),admission,stopped]);await flush();
    await t.get('discovery-form').emit('submit');await flush();t.get('discovery-next').emit('click');await flush();
    assert.equal(t.get('discovery-results').hidden,true);
    assert.doesNotMatch(t.get('discovery-cards').innerHTML,/Engineering card/);
    await t.get('discovery-stop').emit('click');await flush();assert.equal(t.calls.length,3);
    admit({...complete(nextId),running:true,state:'running'});await flush();
    assert.match(t.calls[3].url,new RegExp(nextId+'/stop/'));assert.doesNotMatch(t.calls[3].url,new RegExp(runId+'/stop/'));
    assert.match(t.get('discovery-status').textContent,/Search stopped/);assert.equal(t.timers.size,0);
    assert.doesNotMatch(t.get('discovery-cards').innerHTML,/Engineering card/);
  });
  await check('reopening reads the temporary run without acquiring; account revocation clears private results',async()=>{
    const t=setup([{goals:[]},complete()],'?run_id='+runId);await flush();
    assert.equal(t.calls.length,2);assert.ok(t.calls.every(call=>call.init.method==='GET'));
    assert.match(t.get('discovery-cards').innerHTML,/Engineering card/, t.get('discovery-status').textContent);
    t.events['dex:authority-revoked']();assert.equal(t.get('discovery-cards').innerHTML,'');assert.equal(t.get('discovery-search').disabled,true);
  });
  await check('ambiguous identities and malicious text remain unpriced escaped text',async()=>{
    const bad={...row,classification:'unpriced',proposed_identity:null,reference:null,reason:'<script>bad</script>',revealed:true,title:'<img src=x onerror=bad()>',item_url:'javascript:bad()'};
    const t=setup([{goals:[]},complete(runId,[bad])]);await flush();await t.get('discovery-form').emit('submit');await flush();
    const html=t.get('discovery-cards').innerHTML;assert.doesNotMatch(html,/Proposed:/);assert.match(html,/No applicable reference/);
    assert.match(html,/&lt;script&gt;/);assert.doesNotMatch(html,/<script>|javascript:|<img src=x/);
  });
  await check('session mismatch and restored page cannot publish private data',async()=>{
    const t=setup([{goals:[]}, {...complete(),authority:{binding:'other-session'}}]);await flush();
    await t.get('discovery-form').emit('submit');await flush();
    assert.equal(t.get('discovery-cards').innerHTML,'');assert.equal(t.get('discovery-search').disabled,true);
    assert.match(t.get('discovery-status').textContent,/session changed/);
    const restored=setup([{goals:[]},complete()],'?run_id='+runId);await flush();
    restored.events.pagehide();assert.equal(restored.get('discovery-cards').innerHTML,'');
    restored.events.pageshow({persisted:true});assert.equal(restored.calls.at(-1).reload,true);
  });
  await check('late in-flight status cannot publish after Stop',async()=>{
    let finish;const late=new Promise(resolve=>{finish=resolve;});
    const active={...complete(),running:true,state:'running'};
    const stopped={...complete(runId,[]),state:'stopped',has_next:false};
    const t=setup([{goals:[]},active,late,stopped]);await flush();await t.get('discovery-form').emit('submit');await flush();
    const poll=[...t.timers.values()][0];poll();await flush();
    await t.get('discovery-stop').emit('click');await flush();
    finish(complete(runId,[{...row,revealed:true,title:'Late private listing'}]));await flush();
    assert.match(t.get('discovery-status').textContent,/Search stopped/);
    assert.doesNotMatch(t.get('discovery-cards').innerHTML,/Late private listing|Engineering card/);
    assert.equal(t.timers.size,0);
  });
  await check('reviewed HTTPS and local artwork render; malicious or hidden image URLs are denied',async()=>{
    const reviewed=['https://assets.tcgdex.net/en/base/base1/1/high.webp','https://raw.githubusercontent.com/engineering/fixture/main/card.png','/collection-assets/engineering-card.png'];
    const denied=['javascript:alert(1)','data:image/svg+xml,bad','http://assets.tcgdex.net/card.png','https://assets.tcgdex.net.evil.test/card.png','https://assets.tcgdex.net@evil.test/card.png','https://evil.test/card.png','https://assets.tcgdex.net:444/card.png','//evil.test/card.png','/\\\\evil.test/card.png'];
    const imageRow=(url,i,revealed=true)=>({...row,id:'art'+i,revealed,proposed_identity:{...row.proposed_identity,artwork_url:url}});
    const rows=[...reviewed.map((url,i)=>imageRow(url,i)),...denied.map((url,i)=>imageRow(url,i+10)),imageRow(reviewed[0],99,false)];
    const t=setup([{goals:[]},complete(runId,rows)]);await flush();await t.get('discovery-form').emit('submit');await flush();
    const html=t.get('discovery-cards').innerHTML;assert.equal([...html.matchAll(/<img /g)].length,reviewed.length+1);
    for (const url of reviewed) assert.ok(html.includes('src="'+url+'"'));
    assert.doesNotMatch(html,/<img[^>]+src="(?:javascript:|data:|http:|https:\/\/evil|\/\/evil)/);
    assert.match(html,/referrerpolicy="no-referrer"/);
  });
  await check('local reference expiry removes cached values and derivatives without another request',async()=>{
    const input={...row,revealed:true,classification:'comparable',shipping:'0',delivered_total:'10',reference:{...row.reference,amount:'777.77',expires_at:new Date(Date.now()+1000).toISOString()},comparison:{below_reference:true,reference_minus_delivered_total:'767.77'}};
    const response=complete(runId,[input]);const t=setup([{goals:[]},response]);await flush();await t.get('discovery-form').emit('submit');await flush();
    assert.match(t.get('discovery-cards').innerHTML,/777.77|767.77/);
    t.advance(1001);for(const tick of t.intervals.values()) tick();await flush();
    const html=t.get('discovery-cards').innerHTML;assert.doesNotMatch(html,/777.77|767.77|Below reference/);assert.match(html,/Reference expired/);assert.match(html,/\$10.00/);
    assert.equal(response.results[0].reference,null);assert.deepEqual(Object.keys(response.results[0].comparison),[]);
    await t.get('discovery-filter').emit('change');assert.doesNotMatch(t.get('discovery-cards').innerHTML,/777.77|767.77/);assert.equal(t.calls.length,2);
  });
  await check('withdrawn managed source or conflict removes comparisons using only private metadata',async()=>{
    for(const conflict of [false,true]) {
      const ref={...row.reference,amount:'777.77',snapshot_version:'version-a',source_contract:'source-a',conflicts:conflict?[{source_contract:'source-conflict'}]:[]};
      const input={...row,revealed:true,classification:'comparable',shipping:'0',delivered_total:'10',reference:ref,comparison:{below_reference:true,reference_minus_delivered_total:'767.77'}};
      const response=complete(runId,[input]);const t=setup([{goals:[]},response,{versions:['version-a'],sources:['source-a','source-conflict']},{versions:conflict?['version-a']:[],sources:['source-a']}]);await flush();await t.get('discovery-form').emit('submit');await flush();
      assert.match(t.get('discovery-cards').innerHTML,/777.77/);
      for(const tick of t.intervals.values()) tick();await flush();
      assert.equal(t.calls.at(-1).url,'/api/shopping/price-source-status/');assert.equal(t.calls.at(-1).init.method,'GET');
      assert.doesNotMatch(t.get('discovery-cards').innerHTML,/777.77|767.77|Below reference/);assert.match(t.get('discovery-cards').innerHTML,/withdrawn or replaced/);
      assert.equal(response.results[0].reference,null);assert.deepEqual(Object.keys(response.results[0].comparison),[]);
      t.get('discovery-filter').value='below';await t.get('discovery-filter').emit('change');assert.match(t.get('discovery-cards').innerHTML,/No results match/);
    }
  });
  await check('unavailable managed lifecycle fails closed and later filtering cannot restore values',async()=>{
    const input={...row,revealed:true,reference:{...row.reference,amount:'777.77',snapshot_version:'version-a',source_contract:'source-a'}};
    const response=complete(runId,[input]);const t=setup([{goals:[]},response,new Error('local unavailable')]);await flush();await t.get('discovery-form').emit('submit');await flush();
    assert.match(t.get('discovery-cards').innerHTML,/lifecycle could not be checked/);assert.doesNotMatch(t.get('discovery-cards').innerHTML,/777.77/);
    assert.equal(response.results[0].reference,null);await t.get('discovery-filter').emit('change');assert.doesNotMatch(t.get('discovery-cards').innerHTML,/777.77/);
    assert.equal(t.calls.length,3);assert.equal(t.calls[2].url,'/api/shopping/price-source-status/');
  });
  await check('run TTL removes all cached listing data and visibility cannot republish it',async()=>{
    const response={...complete(runId,[{...row,revealed:true,title:'Private temporary title'}]),expires_in_seconds:2};
    const t=setup([{goals:[]},response]);await flush();await t.get('discovery-form').emit('submit');await flush();
    assert.match(t.get('discovery-cards').innerHTML,/Private temporary title/);const cached=response.results[0];
    t.advance(2001);t.events.visibilitychange();await flush();
    assert.deepEqual(Object.keys(cached),[]);assert.ok(response.results.every(result=>Object.keys(result).length===0));
    assert.doesNotMatch(t.get('discovery-cards').innerHTML,/Private temporary title|Engineering card|\$10.00/);
    assert.match(t.get('discovery-status').textContent,/temporary search has expired/);assert.equal(t.get('discovery-next').disabled,true);
    await t.get('discovery-filter').emit('change');assert.doesNotMatch(t.get('discovery-cards').innerHTML,/Private temporary title/);assert.equal(t.calls.length,2);
  });
  await check('local run TTL is never renewed by filtering',async()=>{
    const original={...complete(),expires_in_seconds:2};
    const t=setup([{goals:[]},original]);await flush();await t.get('discovery-form').emit('submit');await flush();
    t.advance(1500);await t.get('discovery-filter').emit('change');await flush();
    t.advance(501);for(const tick of t.intervals.values()) tick();await flush();
    assert.match(t.get('discovery-status').textContent,/temporary search has expired/);assert.equal(t.calls.length,2);
  });
  await check('filtering cannot restore a locally withdrawn comparison',async()=>{
    const input={...row,reference:{...row.reference,amount:'777.77',snapshot_version:'version-a',source_contract:'source-a'}};
    const initial=complete(runId,[input]);
    const t=setup([{goals:[]},initial,{versions:['version-a'],sources:['source-a']},{versions:[],sources:[]}]);await flush();await t.get('discovery-form').emit('submit');await flush();
    for(const tick of t.intervals.values()) tick();await flush();assert.doesNotMatch(t.get('discovery-cards').innerHTML,/777.77/);
    await t.get('discovery-filter').emit('change');await flush();
    assert.doesNotMatch(t.get('discovery-cards').innerHTML,/777.77/);assert.equal(initial.results[0].reference,null);
  });
  await check('an unresponsive lifecycle read drops managed values within a bounded local wait',async()=>{
    let finish;const pending=new Promise(resolve=>{finish=resolve;});
    const input={...row,reference:{...row.reference,amount:'777.77',snapshot_version:'version-a',source_contract:'source-a'}};
    const response=complete(runId,[input]);const t=setup([{goals:[]},response,pending]);await flush();await t.get('discovery-form').emit('submit');await flush();
    assert.match(t.get('discovery-cards').innerHTML,/777.77/);t.advance(2001);for(const tick of [...t.timers.values()]) tick();await flush();
    assert.match(t.get('discovery-cards').innerHTML,/lifecycle could not be checked/);assert.doesNotMatch(t.get('discovery-cards').innerHTML,/777.77/);assert.equal(response.results[0].reference,null);
    finish({versions:['version-a'],sources:['source-a']});await flush();assert.doesNotMatch(t.get('discovery-cards').innerHTML,/777.77/);assert.equal(t.calls.length,3);
  });
  await check('local submit, typing and stale catalog responses never acquire listings',async()=>{
    const t=setup([{goals:[]}]);await flush();
    const before=t.localCalls.length;await t.get('catalog-search').emit('click');await flush();
    assert.equal(t.calls.length,1);assert.equal(t.localCalls.length,before+1);
    let finish;const stale=new Promise(resolve=>{finish=resolve;});t.localResponses.push(stale);
    t.get('discovery-query').value='Hypno';await t.get('discovery-query').emit('input');
    let timer=[...t.timers.entries()].at(-1);t.timers.delete(timer[0]);timer[1]();await flush();
    t.get('discovery-query').value='Gengar';await t.get('discovery-query').emit('input');
    t.localResponses.push({mode:'species',results:[{dex:94,name:'Gengar',current_present:false,matching_cards:2,species_artwork:null}],total:1,sets:[]});
    timer=[...t.timers.entries()].at(-1);t.timers.delete(timer[0]);timer[1]();await flush();
    assert.match(t.get('catalog-cards').innerHTML,/Gengar/);assert.match(t.get('catalog-cards').innerHTML,/Pokémon artwork unavailable/);
    finish({mode:'species',results:[{dex:97,name:'Hypno',current_present:true,matching_cards:1}],total:1,sets:[]});await flush();
    assert.match(t.get('catalog-cards').innerHTML,/Gengar/);assert.doesNotMatch(t.get('catalog-cards').innerHTML,/Hypno/);
    assert.equal(t.calls.length,1);assert.ok(t.localCalls.every(call=>call.init.method==='GET'));
  });
  await check('Back restores edited local choices, filters, target and focus without acquisition',async()=>{
    const query='?run_id='+runId+'&q=Gengar&set_id=Fossil&intent=missing&missing_basis=species&scope=kanto&result_filter=conditional&species=94&focus=offer-one&scroll=200';
    const t=setup([{goals:[]},complete()],query);await flush();
    assert.equal(t.get('discovery-query').value,'Gengar');assert.equal(t.get('discovery-set').value,'Fossil');
    assert.equal(t.get('discovery-filter').value,'conditional');assert.equal(t.get('find-missing')['aria-pressed'],'true');
    assert.equal(t.get('offer-one').focused,true);assert.equal(t.get('discovery-next').disabled,true);
    assert.equal(t.calls.length,2);assert.ok(t.calls.every(call=>call.init.method==='GET'));
    assert.equal(t.localCalls.length,0);t.get('local-explorer').open=true;await t.get('local-explorer').emit('toggle');await flush();
    assert.match(t.localCalls.at(-1).url,/species=94/);assert.match(t.localCalls.at(-1).url,/intent=missing/);
  });
  await check('Back restores offers and focus without a closed explorer read; explicit opening stays usable',async()=>{
    let release;const held=new Promise(resolve=>{release=resolve;});
    const t=setup([{goals:[]},complete()],'?run_id='+runId+'&focus=offer-one&scroll=1500');
    t.localResponses.push(held);await flush();
    assert.match(t.get('discovery-cards').innerHTML,/Engineering card/);
    assert.equal(t.get('offer-one').focused,true);
    assert.equal(t.localCalls.length,0);assert.equal(t.calls.length,2);
    t.get('local-explorer').open=true;await t.get('local-explorer').emit('toggle');await flush();
    assert.equal(t.localCalls.length,1);assert.equal(t.get('offer-one').focused,true);
    assert.ok(t.calls.every(c=>c.init.method==='GET'));
    release({mode:'cards',results:[],total:0,offset:0,sets:[],has_more:false});await flush();
    assert.equal(t.localCalls.length,1);
  });
  await check('return starts metadata and local run revalidation together and rejects late revoked content',async()=>{
    let release;const held=new Promise(resolve=>{release=resolve;});
    const t=setup([held,complete()],'?run_id='+runId);await flush();
    assert.equal(t.calls.length,2);assert.match(t.calls[1].url,/run_id=/);
    assert.equal(t.get('discovery-cards').innerHTML,'');
    t.events['dex:authority-revoked']();release({goals:[]});await flush();
    assert.equal(t.get('discovery-cards').innerHTML,'');assert.equal(t.localCalls.length,0);
  });
  await check('an initially open explorer uses one local request across toggle and bootstrap',async()=>{
    const t=setup([{goals:[]},complete()],'?run_id='+runId+'&focus=catalog-one');
    await t.get('local-explorer').emit('toggle');await flush();
    assert.equal(t.localCalls.length,1);assert.equal(t.calls.length,2);
    assert.match(t.get('discovery-cards').innerHTML,/Engineering card/);
  });
  await check('reopening typed preferences preserves explicit English and local spelling assistance',async()=>{
    const t=setup([{goals:[]}],'?q=Venasaur&english_vintage=1');await flush();
    assert.equal(t.get('discovery-english-vintage').checked,true);
    assert.match(t.get('discovery-suggestions').innerHTML,/Use Venusaur/);
    assert.match(t.get('discovery-suggestions').innerHTML,/Keep Venasaur as typed/);
    assert.equal(t.calls.length,1);assert.equal(t.calls[0].init.method,'GET');
  });
  assert.doesNotMatch(source,/localStorage|sessionStorage|indexedDB/);
  console.log(JSON.stringify({passed:passed.length,cases:passed,provider_calls:0,customer_data:false}));
})().catch(error=>{console.error(error);process.exitCode=1;});
