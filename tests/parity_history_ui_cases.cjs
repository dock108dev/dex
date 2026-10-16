'use strict';
// Shipped historical renderer with in-memory responses; no customer/provider access.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync(process.argv[2], 'utf8');
const cases = [];
const snapshot = () => ({
  batch:'saved-batch',id:1,demo:false,created:'2026-01-01T12:00:00Z',note:'Retained dated snapshot.',
  settings:{intent:'missing',pool:'singles',focus:'kanto',budget:'100',offset:0,query:'saved words'},
  coverage:{queries_run:1,queries_total:10,next_offset:1,offset:0},
  goal:{name:'Frozen goal',policy:'species',version:1},
  results:[
    {id:'hidden-one',type:'fixed',label:'Hidden candidate',count:1,confidence:'Seller text',delivered:'5',dex_hits:1,exact_hits:0,duplicate_ratio:0,score:20,score_coverage:0.5,pricing:{reference_total:'10',discount_percent:'50',saving:'5',source_dates:['2026-01-01']}},
    {id:'hidden-two',type:'fixed',label:'Unpriced candidate',count:1,confidence:'Seller text',delivered:'7',dex_hits:0,exact_hits:0,duplicate_ratio:0,score:10,score_coverage:0.2},
  ],
});
const revealed = {title:'PRIVATE SELLER TITLE',confidence:'Seller text',cards:[],url:'https://www.ebay.com/itm/123'};

function setup(responses = [], search = '') {
  const elements = new Map(), calls = [], buttons = new Map();
  let opens = 0;
  class Element {
    constructor(id) {this.id=id;this._html='';this.value='';this.textContent='';this.disabled=false;this.dataset={};}
    set innerHTML(value) {
      this._html=value;
      for (const match of value.matchAll(/\bid="([^"]+)"/g)) if (!elements.has(match[1])) elements.set(match[1],new Element(match[1]));
      for (const [selector,attribute,key] of [['[data-saved]','data-saved','saved'],['[data-reveal-result]','data-reveal-result','revealResult']]) {
        if (this.id !== (key === 'saved' ? 'saved-searches' : 'hunt-results')) continue;
        buttons.set(selector,[...value.matchAll(new RegExp(attribute+'="([^"]+)"','g'))].map(match=>{const button=new Element(key);button.dataset[key]=match[1];return button;}));
      }
    }
    get innerHTML() {return this._html;}
    replaceChildren() {this._html='';}
    close() {this.open=false;}
    focus() {this.focused=true;}
  }
  for (const id of ['content','editor','editor-title','editor-body']) elements.set(id,new Element(id));
  const context = {
    window:{parityData:{cards:{}}},location:{search},data:{goals:[{id:'selected',name:'Retained <goal>'}]},URL,URLSearchParams,Intl,
    $:selector=>elements.get(selector.replace(/^#/,'')) || null,
    esc:value=>String(value??'').replace(/[&<>"']/g,char=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char])),
    document:{querySelectorAll:selector=>buttons.get(selector)||[]},
    status:message=>{throw new Error(message);},
    openDialog:selector=>{assert.equal(selector,'#editor');opens++;elements.get('editor').open=true;},
    api:async(url,body)=>{
      calls.push({url,body});
      const value=responses.shift();
      assert.notEqual(value,undefined,'Unexpected request '+url);
      return await value;
    },
  };
  vm.createContext(context);vm.runInContext(source,context);
  return {context,calls,get:id=>elements.get(id),buttons:selector=>buttons.get(selector)||[],opens:()=>opens};
}
async function flush() {for(let i=0;i<15;i++) await Promise.resolve();}
async function check(name,test) {await test();cases.push(name);}

(async()=>{
  await check('retained hunt and missing routes offer Shopping without acquisition controls or requests',async()=>{
    for (const route of ['/hunt/','/missing/']) {
      const t=setup([], '?goal=selected');
      assert.equal(t.context.window.renderParity(route),true);
      const html=t.get('content').innerHTML;
      assert.match(html,/href="\/shopping\/"/);assert.match(html,/href="\/finds\/"/);
      assert.doesNotMatch(html,/<form|hunt-search|hunt-next|hunt-source|Search eBay|Find sample cards/);
      assert.equal(t.calls.length,0);
      if(route==='/missing/') {assert.match(html,/Retained &lt;goal&gt;/);assert.doesNotMatch(html,/Retained <goal>/);}
      for (const name of ['runHunt','huntChoices','huntProvider','huntBusy','loadHuntProvider']) assert.equal(vm.runInContext('typeof '+name,t.context),'undefined');
    }
  });
  await check('empty historical finds use one read and explain temporary Shopping results',async()=>{
    const t=setup([{hunts:[],search_status:{enabled:true,configured:true}}]);
    assert.equal(t.context.window.renderParity('/finds/'),true);await flush();
    assert.deepEqual(t.calls,[{url:'/api/hunts/',body:undefined}]);
    assert.match(t.get('content').innerHTML,/href="\/shopping\/"/);
    assert.match(t.get('saved-searches').innerHTML,/Shopping results are temporary/);
    assert.doesNotMatch(t.get('saved-searches').innerHTML,/Start an eBay or sample search/);
  });
  await check('saved filtering and reveal preserve spoilers and never offer retired continuation',async()=>{
    const saved=snapshot(),t=setup([{hunts:[saved]},saved,revealed,saved]);
    t.context.window.renderParity('/finds/');await flush();
    await t.buttons('[data-saved]')[0].onclick();
    let html=t.get('hunt-results').innerHTML;
    assert.match(html,/Frozen goal|saved words|2026/);
    assert.match(html,/href="\/shopping\/"/);
    assert.doesNotMatch(html,/hunt-next|Search next eBay batch|PRIVATE SELLER TITLE/);
    assert.match(html,/Showing 2 \/ 2 saved results/);
    t.get('hunt-display').value='below';t.get('hunt-display').onchange();
    assert.equal(t.calls.length,2);assert.match(t.get('hunt-results').innerHTML,/Showing 1 \/ 2 saved results/);
    const button=t.buttons('[data-reveal-result]')[0];await button.onclick();
    assert.equal(t.calls[2].url,'/api/hunts/saved-batch/1/reveal/hidden-one/');
    assert.deepEqual(Object.keys(t.calls[2].body),[]);
    assert.match(t.get('editor-body').innerHTML,/PRIVATE SELLER TITLE/);
    assert.equal(button.disabled,false);assert.equal(button.focused,true);assert.equal(t.opens(),1);
    await t.buttons('[data-saved]')[0].onclick();
    assert.equal(t.get('editor-body').innerHTML,'');assert.equal(t.get('editor').open,false);
    assert.doesNotMatch(t.get('hunt-results').innerHTML,/PRIVATE SELLER TITLE/);
    assert.equal(t.calls[3].body,undefined);
    assert.equal(t.calls.filter(call=>call.url==='/api/hunts/'&&call.body!==undefined).length,0);
  });
  await check('late historical reads cannot replace a Shopping handoff',async()=>{
    let finish;const waiting=new Promise(resolve=>{finish=resolve;}),t=setup([waiting]);
    t.context.window.renderParity('/finds/');t.context.window.renderParity('/hunt/');
    finish({hunts:[snapshot()]});await flush();
    assert.match(t.get('content').innerHTML,/New eBay searches are in Shopping/);
    assert.equal(t.buttons('[data-saved]').length,0);
  });
  await check('late reveal cannot reopen private contents after leaving history',async()=>{
    let finish;const waiting=new Promise(resolve=>{finish=resolve;}),saved=snapshot(),t=setup([{hunts:[saved]},saved,waiting]);
    t.context.window.renderParity('/finds/');await flush();await t.buttons('[data-saved]')[0].onclick();
    const pending=t.buttons('[data-reveal-result]')[0].onclick();
    t.context.window.renderParity('/missing/');finish(revealed);await pending;
    assert.equal(t.opens(),0);assert.equal(t.get('editor-body').innerHTML,'');
    assert.match(t.get('content').innerHTML,/New eBay searches are in Shopping/);
  });
  console.log(JSON.stringify({passed:cases.length,cases,provider_calls:0,customer_data:false}));
})().catch(error=>{console.error(error);process.exitCode=1;});
