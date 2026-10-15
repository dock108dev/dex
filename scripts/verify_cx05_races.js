'use strict';
// Isolated consumer renderer contracts. No server, customer root or provider access.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const sourcePath = path.join(__dirname,'../src/pokemon_hunter/beta/static/card-screens.js');
const source = fs.readFileSync(sourcePath,'utf8');
const group = {id:'dg1-card-a',name:'Ivysaur',set_name:'Base Set',collector_number:'30',present:true,established_total_quantity:null,identity_status:'resolved',language:'en',recorded_copy_count:0,current_copy_count:0,pokemon_dex:2,catalog_available:true};
const options = {account_id:'account-a',generation:5,sets:[{id:'base',name:'Base Set'}],languages:[],editions:[],finishes:[],variants:[]};
const list = (changes={}) => ({account_id:'account-a',generation:5,total:1,page:1,pages:1,groups:[group],unresolved:[],...changes});
const detail = (changes={}) => ({account_id:'account-a',generation:5,group,selected_child:null,variants:[],copies:[],history:[],...changes});
function deferred() { let resolve,reject;const promise=new Promise((yes,no)=>{resolve=yes;reject=no;});return {promise,resolve,reject}; }
function setup(route,responder,{storage=new Map()}={}) {
  const content={innerHTML:''},nodes=new Map(),calls=[],events={};
  const element=tag=>({tagName:tag.toUpperCase(),children:[],listeners:{},append(...children){this.children.push(...children);},addEventListener(name,handler){this.listeners[name]=handler;}});
  const summary=element('div');
  const headerLinks=['/cards/','/card-library/'].map(path=>({dataset:path==='/cards/'?{navigationSection:'cards'}:{navigationTab:path},attrs:{},setAttribute(key,value){this.attrs[key]=value;if(key==='href')this.href='http://localhost'+value;},getAttribute(key){return this.attrs[key];}}));
  const context={window:{},data:{effective_collection:{user_id:'account-a',generation:5},binders:[]},location:{origin:'http://localhost',href:'http://localhost'+route,pathname:route.split('?')[0],search:route.includes('?')?'?'+route.split('?')[1]:'',assign(url){context.assigned=url;},replace(url){context.replaced=url;},reload(){}},URL,URLSearchParams,Number,Set,Map,JSON,Math,Error,String,FormData:global.FormData,crypto:global.crypto,scrollY:0,scrollTo(x,y){context.restoredScroll=y;},requestAnimationFrame(fn){fn();},addEventListener(name,handler){events[name]=handler;},sessionStorage:{getItem(key){return storage.get(key)??null;},setItem(key,value){storage.set(key,value);}},document:{body:{dataset:{parity:'true'}},querySelectorAll(selector){return selector.includes('data-navigation-section')?headerLinks:[];},createElement(tag){return element(tag);},querySelector(selector){return selector==='.card-detail-summary'?summary:null;}},$:selector=>selector==='#content'?content:(nodes.get(selector)||nodes.set(selector,{}).get(selector)),esc:value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])),cardImage:()=>'<span class="image-frame"></span>',photoLink:()=>'',api:async url=>{calls.push(url);return responder(url);}};
  vm.createContext(context);vm.runInContext(source,context,{filename:sourcePath});
  return {context,content,calls,storage,events,headerLinks,render:()=>context.window.renderCardScreens(context.location.pathname)};
}
const cases=[];
async function check(name,run){await run();cases.push({name,status:'passed'});}
(async()=>{
  await check('owned fixed endpoint and UI parameters excluded',async()=>{
    const t=setup('/cards/?q=Ivysaur&scroll=80',url=>url.includes('filters')?options:list());await t.render();
    const request=t.calls.find(url=>url.startsWith('/api/my-card-groups/'));
    assert(request);assert(!request.includes('scope'));assert(!request.includes('scroll'));assert(request.includes('generation=5'));assert(t.content.innerHTML.includes('Ivysaur'));assert(!t.content.innerHTML.includes('Quantity 0'));
  });
  await check('separate library, matching children and canonical null-child tile',async()=>{
    const t=setup('/card-library/?edition=first_edition',url=>url.includes('filters')?options:list({groups:[{...group,matching_child_ids:['child-2']}]}));await t.render();
    assert(t.calls.some(url=>url.startsWith('/api/card-groups/?edition=first_edition')));assert(t.content.innerHTML.includes('data-matching-child-ids="[&quot;child-2&quot;]"'));assert(!t.content.innerHTML.includes('?child='));assert(t.content.innerHTML.includes('Card Library'));
  });
  await check('retained long card filter values have escaped readable descriptions without altering scoped requests',async()=>{
    const values={set:'long-set',language:'long-language',edition:'long-edition',finish:'long-finish',variant:'long-variant'};
    const labels={set:'Wizards Black Star Promos & retained expansion <img src=x onerror=evil>',language:'Supported retained language',edition:'A long literal edition <untrusted>',finish:'A long literal finish & treatment',variant:'Literal variant <img src=x onerror=evil> & retained identity'};
    const longOptions={...options,sets:[{id:values.set,name:labels.set}],languages:[values.language],editions:[values.edition],finishes:[values.finish],variants:[values.variant]};
    const query=new URLSearchParams({...values,sort:'number',page:'2'});
    const t=setup('/card-library/?'+query,url=>url.includes('filters')?longOptions:list({page:2,pages:3}));await t.render();
    for(const key of [...Object.keys(values),'sort']){
      assert(t.content.innerHTML.includes('aria-describedby="cards-'+key+'-value"'),key+' must describe its selected value');
      assert(t.content.innerHTML.includes('id="cards-'+key+'-value"'),key+' must retain readable caption');
    }
    assert(t.content.innerHTML.includes('Wizards Black Star Promos &amp; retained expansion'));
    assert(t.content.innerHTML.includes('&lt;img src=x onerror=evil&gt;'));assert(!t.content.innerHTML.includes('<img src=x onerror=evil>'));
    const request=t.calls.find(url=>url.startsWith('/api/card-groups/?'));
    for(const [key,value] of Object.entries(values))assert.equal(new URL(request,'http://localhost').searchParams.get(key),value,key+' request remains literal');
    assert.equal(new URL(request,'http://localhost').searchParams.get('page'),'2');
    assert(t.content.innerHTML.includes('Collector number'));
  });
  await check('card selected captions update before submit and hide on reset; unavailable retained value stays readable',async()=>{
    const t=setup('/cards/?set=missing-reviewed-set&variant=long-retained-variant',url=>url.includes('filters')?options:list());await t.render();
    assert(t.content.innerHTML.includes('missing-reviewed-set · unavailable filter'));
    assert(t.content.innerHTML.includes('long-retained-variant · unavailable filter'));
    const select=t.context.$('#cards-set'),caption=t.context.$('#cards-set-value');
    assert.equal(typeof select.onchange,'function');
    select.value='long-new-set';select.selectedOptions=[{textContent:'A new complete expansion & literal edition',text:'A new complete expansion & literal edition'}];select.onchange();
    assert.equal(caption.textContent,'A new complete expansion & literal edition');assert.equal(caption.hidden,false);
    select.value='';select.selectedOptions=[{textContent:'All sets',text:'All sets'}];select.onchange();
    assert.equal(caption.hidden,true);
    const sort=t.context.$('#cards-sort'),sortCaption=t.context.$('#cards-sort-value');
    assert.equal(typeof sort.onchange,'function');sort.value='name';sort.selectedOptions=[{textContent:'Card name',text:'Card name'}];sort.onchange();
    assert.equal(sortCaption.textContent,'Card name');assert.equal(sortCaption.hidden,false);
  });
  await check('focused default detail, unknown quantity and closed disclosures',async()=>{
    const t=setup('/card-groups/dg1-card-a/',()=>detail());await t.render();
    assert(t.content.innerHTML.includes('Quantity not recorded.'));assert(!/<details[^>]*\sopen/.test(t.content.innerHTML));assert(t.content.innerHTML.includes('data-selected-child=""'));assert(!t.content.innerHTML.includes('dialog'));assert(t.content.innerHTML.includes('id="group-copies"'));
    const appended=t.context.document.querySelector('.card-detail-summary').children[0].children[0];assert.equal(appended.id,'card-shopping');assert.equal(appended.textContent,'Find cards in Shopping');assert.equal(typeof appended.listeners.click,'function');
  });
  await check('explicit archived child stays selected and exact image unavailable',async()=>{
    const variant={id:'archived-child',edition:'first_edition',finish:'holo',available:false};
    const t=setup('/card-groups/dg1-card-a/?child=archived-child',()=>detail({variants:[variant],selected_child:variant}));await t.render();
    assert(t.calls[0].includes('child=archived-child'));assert(t.content.innerHTML.includes('data-selected-child="archived-child"'));assert(t.content.innerHTML.includes('Selected variant image unavailable'));assert(!t.content.innerHTML.includes('id="group-add-copy"'));
  });
  await check('matching-child context uses authoritative scoped IDs without inferring archived matches',async()=>{
    const variants=[{id:'visible',edition:'first_edition',available:true},{id:'archived',edition:'first_edition',available:false}];
    const back='/card-library/?edition=first_edition&page=2';
    const t=setup('/card-groups/dg1-card-a/?return='+encodeURIComponent(back),url=>url.startsWith('/api/card-groups/?')?list({groups:[{...group,matching_child_ids:['visible']}]}):detail({variants}));await t.render();
    assert(t.calls.some(url=>url.startsWith('/api/card-groups/?edition=first_edition&page=2&generation=5')));
    assert(t.content.innerHTML.includes('data-variant="visible" data-filter-match="true"'));assert(!t.content.innerHTML.includes('data-variant="archived" data-filter-match="true"'));assert(t.content.innerHTML.includes('data-selected-child=""'));
  });
  await check('optional prices closed by default and core detail does not load parity',async()=>{
    const t=setup('/card-groups/dg1-card-a/',()=>detail());await t.render();assert(t.content.innerHTML.includes('<details id="group-prices"><summary>Prices and sources</summary>'));assert(!t.calls.includes('/api/parity/'));
  });
  await check('B2 and staging prices explicitly unavailable without a request',async()=>{
    for(const profile of ['b2','staging']){
      const t=setup('/card-groups/dg1-card-a/',()=>detail());if(profile==='b2')t.context.document.body.dataset.parity='false';else t.context.document.body.dataset.staging='true';t.context.copyPrices=()=>'<p>Retained guide</p>';await t.render();const disclosure=t.context.$('#group-prices');disclosure.open=true;await disclosure.ontoggle();assert(t.context.$('#group-prices-body').innerHTML.includes('unavailable in this installation'));assert(!t.calls.includes('/api/parity/'));
    }
  });
  await check('optional checked prices preserve per-copy renderer and edition action',async()=>{
    const copy={id:'copy-a',printing_id:'child-a',condition:'Good'};
    const prices={effective_collection:{user_id:'account-a',generation:5},valuation:{copies:{'copy-a':{conditional:{raw:{value:3}}}}}};
    const t=setup('/card-groups/dg1-card-a/',url=>url==='/api/parity/'?prices:detail({copies:[copy]}));t.context.copyPrices=c=>'<details><summary>Guide scenarios for this copy</summary><p>Retained guide for '+c.id+'</p></details>';await t.render();assert(t.content.innerHTML.includes('data-group-edition="copy-a"'));assert(!t.calls.includes('/api/parity/'));const disclosure=t.context.$('#group-prices');disclosure.open=true;await disclosure.ontoggle();assert(t.context.$('#group-prices-body').innerHTML.includes('Retained guide for copy-a'));assert(!t.context.$('#group-prices-body').innerHTML.includes('<details>'));assert.equal(t.context.window.parityData,prices);assert(t.context.$('#group-prices-body').innerHTML.includes('not a valuation multiplier'));
  });
  await check('optional prices reject foreign or stale authority without publishing valuation',async()=>{
    for(const authority of [{user_id:'foreign',generation:5},{user_id:'account-a',generation:6}]){
      const t=setup('/card-groups/dg1-card-a/',url=>url==='/api/parity/'?{effective_collection:authority,valuation:{copies:{}}}:detail());t.context.copyPrices=()=>'';await t.render();const disclosure=t.context.$('#group-prices');disclosure.open=true;await disclosure.ontoggle();assert(t.context.$('#group-prices-body').innerHTML.includes('Collection changed'));assert.equal(t.context.window.parityData,undefined);assert(t.content.innerHTML.includes('id="canonical-card"'));
    }
  });
  await check('late optional pricing cannot overwrite new card state',async()=>{
    const gate=deferred();const t=setup('/card-groups/dg1-card-a/',url=>url==='/api/parity/'?gate.promise:detail());t.context.copyPrices=()=>'';await t.render();const disclosure=t.context.$('#group-prices');disclosure.open=true;const pending=disclosure.ontoggle();t.context.window.invalidateCardScreens();t.context.$('#group-prices-body').innerHTML='Newer card state';gate.resolve({effective_collection:{user_id:'account-a',generation:5},valuation:{copies:{}}});await pending;assert.equal(t.context.$('#group-prices-body').innerHTML,'Newer card state');assert.equal(t.context.window.parityData,undefined);
  });
  await check('optional no-evidence and error states stay separate from card availability',async()=>{
    for(const failure of [false,true]){
      const t=setup('/card-groups/dg1-card-a/',url=>{if(url!=='/api/parity/')return detail();if(failure)throw new Error('Price response unavailable');return {effective_collection:{user_id:'account-a',generation:5},valuation:{copies:{}}};});t.context.copyPrices=()=>'';await t.render();const disclosure=t.context.$('#group-prices');disclosure.open=true;await disclosure.ontoggle();assert(t.context.$('#group-prices-body').innerHTML.includes(failure?'Price response unavailable':'No matching retained guide evidence'));assert(t.content.innerHTML.includes('id="canonical-card"'));
    }
  });
  await check('missing authoritative generation fails visibly before card or price requests',async()=>{
    const t=setup('/card-groups/dg1-card-a/',()=>detail());delete t.context.data.effective_collection.generation;await t.render();assert.equal(t.calls.length,0);assert(t.content.innerHTML.includes('Collection version is unavailable'));assert(!t.content.innerHTML.includes('id="edit-group-card"'));
  });
  await check('optional prices expose missing version instead of silently keeping placeholder',async()=>{
    const t=setup('/card-groups/dg1-card-a/',()=>detail());t.context.copyPrices=()=>'';await t.render();delete t.context.data.effective_collection.generation;const disclosure=t.context.$('#group-prices');disclosure.open=true;await disclosure.ontoggle();assert(t.context.$('#group-prices-body').innerHTML.includes('version changed or is unavailable'));assert(!t.calls.includes('/api/parity/'));
  });
  await check('each local tab restores its own validated filters page and scroll',async()=>{
    const storage=new Map();
    const library=setup('/card-library/?q=Mew&page=2&scroll=345',url=>url.includes('filters')?options:list({page:2,pages:3}),{storage});await library.render();assert.equal(library.context.restoredScroll,345);
    const owned=setup('/cards/?set=base&page=2',url=>url.includes('filters')?options:list({page:2,pages:3}),{storage});await owned.render();assert.equal(owned.headerLinks[1].getAttribute('href'),'/card-library/?q=Mew&page=2&scroll=345');assert.equal(owned.headerLinks[0].getAttribute('href'),'/cards/?set=base&page=2');
    owned.context.scrollY=720;owned.events.pagehide();assert.equal(storage.get('dex-card-tab:account-a:/cards/'),'/cards/?set=base&page=2&scroll=720');
    const back=setup('/card-library/?q=Mew&page=2&scroll=345',url=>url.includes('filters')?options:list({page:2,pages:3}),{storage});await back.render();assert.equal(back.headerLinks[0].getAttribute('href'),'/cards/?set=base&page=2&scroll=720');
  });
  await check('tab history is account isolated and cannot restore a foreign or wrong-tab URL',async()=>{
    const storage=new Map([['dex-card-tab:account-a:/card-library/','/card-library/?q=Private&page=2&scroll=100']]);
    const t=setup('/cards/',url=>url.includes('filters')?{...options,account_id:'account-b'}:list({account_id:'account-b'}),{storage});t.context.data.effective_collection.user_id='account-b';await t.render();assert.equal(t.headerLinks[1].getAttribute('href'),'/card-library/');
    for(const value of ['https://evil.example/','/cards/?q=wrong-tab','/card-library/?page=invalid','/card-library/?q=one&q=two']){
      storage.set('dex-card-tab:account-a:/card-library/',value);const invalid=setup('/cards/',url=>url.includes('filters')?options:list(),{storage});await invalid.render();assert.equal(invalid.headerLinks[1].getAttribute('href'),'/card-library/');
    }
  });
  await check('pagehide tab scroll remains bounded and URL state stays local',async()=>{
    const t=setup('/cards/?q=Ivysaur',url=>url.includes('filters')?options:list());await t.render();t.context.scrollY=20000000;t.events.pagehide();assert.equal(t.storage.get('dex-card-tab:account-a:/cards/'),'/cards/?q=Ivysaur&scroll=10000000');
  });
  await check('stale dashboard versus detail blocks editing',async()=>{
    const t=setup('/card-groups/dg1-card-a/',()=>detail({generation:6}));await t.render();assert(t.content.innerHTML.includes('Collection changed'));assert(!t.content.innerHTML.includes('id="edit-group-card"'));
  });
  await check('mutually stale list/filter authority blocks tiles',async()=>{
    const t=setup('/cards/',url=>url.includes('filters')?{...options,generation:6}:list({generation:6}));await t.render();assert(t.content.innerHTML.includes('Collection changed'));assert(!t.content.innerHTML.includes('class="owned-card-tile"'));
  });
  await check('filter/list generation mismatch blocks mixed snapshot',async()=>{
    const t=setup('/cards/',url=>url.includes('filters')?{...options,generation:6}:list());await t.render();assert(t.content.innerHTML.includes('Collection changed'));
  });
  await check('foreign account response blocks private detail',async()=>{
    const t=setup('/card-groups/dg1-card-a/',()=>detail({account_id:'foreign'}));await t.render();assert(t.content.innerHTML.includes('Account changed'));assert(!t.content.innerHTML.includes('id="canonical-card"'));
  });
  await check('loading state and failed request never claim empty collection',async()=>{
    const gate=deferred();const t=setup('/cards/',url=>url.includes('filters')?options:gate.promise);const pending=t.render();assert(t.content.innerHTML.includes('Loading cards'));gate.reject(new Error('Authorization unavailable (403).'));await pending;assert(t.content.innerHTML.includes('Cards unavailable'));assert(!t.content.innerHTML.includes('Your collection is empty'));
  });
  await check('empty collection distinguished from no filter matches',async()=>{
    const empty=setup('/cards/',url=>url.includes('filters')?options:list({total:0,pages:0,groups:[]}));await empty.render();assert(empty.content.innerHTML.includes('Your collection is empty'));
    const filtered=setup('/cards/?q=Missing',url=>url.includes('filters')?options:list({total:0,pages:0,groups:[]}));await filtered.render();assert(filtered.content.innerHTML.includes('No matching cards'));assert(!filtered.content.innerHTML.includes('Your collection is empty'));
  });
  await check('unresolved-only retains evidence without fabricated tiles or global conflicts',async()=>{
    const mark={kind:'unresolved-species-mark',evidence:{name:'Mew',pokemon_dex:151,source_set:'Retained set'}};
    const t=setup('/cards/',url=>url.includes('filters')?options:list({total:0,pages:0,groups:[],unresolved:[mark,mark,{kind:'incomplete-catalog-identity',label:'Global catalog conflict'}]}));await t.render();assert(t.content.innerHTML.includes('Your card evidence is retained'));assert(t.content.innerHTML.includes('Card details needed (1)'));assert(!t.content.innerHTML.includes('Your collection is empty'));assert(!t.content.innerHTML.includes('Global catalog conflict'));assert(!t.content.innerHTML.includes('class="owned-card-tile"'));
  });
  await check('complete multiple-card group results displayed once each without source duplicate list',async()=>{
    const b={...group,id:'dg1-card-b',set_name:'Base Set 2',collector_number:'44',established_total_quantity:3};
    const t=setup('/cards/',url=>url.includes('filters')?options:list({total:2,groups:[group,b]}));await t.render();assert.equal((t.content.innerHTML.match(/class="owned-card-tile"/g)||[]).length,2);assert.equal((t.content.innerHTML.match(/Quantity 3/g)||[]).length,1);assert.equal((t.content.innerHTML.match(/data-group-id="dg1-card-a"/g)||[]).length,1);assert(!t.content.innerHTML.includes('collection declaration'));
  });
  await check('final page removal recovers page one and keeps filters',async()=>{
    const t=setup('/cards/?page=9&q=Ivysaur',url=>url.includes('filters')?options:list({total:0,page:9,pages:0,groups:[]}));await t.render();assert(t.context.replaced.includes('page=1'));assert(t.context.replaced.includes('q=Ivysaur'));
  });
  await check('unsafe return falls back to local owned destination',async()=>{
    const t=setup('/card-groups/dg1-card-a/?return=https%3A%2F%2Fevil.example%2F',()=>detail());await t.render();assert(t.content.innerHTML.includes('id="card-back" href="/cards/"'));assert(!t.content.innerHTML.includes('evil.example'));
  });
  await check('safe library return preserves filters page and scroll without API contamination',async()=>{
    const value='/card-library/?q=Ivysaur&set=base&page=3&scroll=280';const t=setup('/card-groups/dg1-card-a/?return='+encodeURIComponent(value),()=>detail());await t.render();assert(t.content.innerHTML.includes('href="/card-library/?q=Ivysaur&amp;set=base&amp;page=3&amp;scroll=280"'));assert(!t.calls[0].includes('return='));assert(!t.calls[0].includes('scroll='));
  });
  await check('invalidated response cannot overwrite newer navigation or edits',async()=>{
    const gate=deferred();const t=setup('/card-groups/dg1-card-a/',()=>gate.promise);const pending=t.render();t.context.window.invalidateCardScreens();t.content.innerHTML='Newer screen';gate.resolve(detail());await pending;assert.equal(t.content.innerHTML,'Newer screen');
  });
  await check('response cannot overwrite switched account or authority object',async()=>{
    const gate=deferred();const t=setup('/card-groups/dg1-card-a/',()=>gate.promise);const pending=t.render();t.context.data={effective_collection:{user_id:'account-b',generation:5},binders:[]};t.content.innerHTML='Current account';gate.resolve(detail());await pending;assert.equal(t.content.innerHTML,'Current account');
  });
  await check('older request cannot overwrite newer response on same route',async()=>{
    const first=deferred();let count=0;const t=setup('/card-groups/dg1-card-a/',()=>++count===1?first.promise:detail({group:{...group,name:'Current card'}}));const old=t.render();await t.render();assert(t.content.innerHTML.includes('Current card'));first.resolve(detail({group:{...group,name:'Old card'}}));await old;assert(t.content.innerHTML.includes('Current card'));assert(!t.content.innerHTML.includes('Old card'));
  });
  process.stdout.write(JSON.stringify({kind:'isolated-renderer-contracts',customer_root_access:false,provider_requests:0,passed:cases.length,cases},null,2)+'\n');
})().catch(error=>{process.stderr.write(error.stack+'\n');process.exitCode=1;});
