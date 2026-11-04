'use strict';
// Disposable DOM engineering checks only; no browser/customer/provider content.
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
class Element {
  constructor(tag='div'){this.tagName=tag;this.children=[];this.value='';this.hidden=false;this.disabled=false;this.listeners={};this.dataset={};this._text='';this.open=false;}
  append(...items){for(const child of items){child.parentElement=this;this.children.push(child);}}
  prepend(child){child.parentElement=this;this.children.unshift(child);}
  replaceChildren(...items){this.children=[];this._text='';this.append(...items);}
  remove(){if(this.parentElement)this.parentElement.children=this.parentElement.children.filter(c=>c!==this);}
  get textContent(){return this._text+this.children.map(c=>c.textContent).join(' ');}
  set textContent(value){this._text=String(value);this.children=[];}
  get lastChild(){return this.children.at(-1);}
  addEventListener(event,fn){this.listeners[event]=fn;}
  setAttribute(key,value){this[key]=value;}
  querySelector(){return {value:'engineering-csrf'};}
  querySelectorAll(){return [];}
  focus(){this.focused=true;}
  scrollIntoView(){this.scrolled=true;}
}
const source=fs.readFileSync(process.argv[2],'utf8'),display=fs.readFileSync(process.argv[3],'utf8');
const sample={item_id:'v1|123456789012|0',item_url:'https://www.ebay.com/itm/123456789012',title:'Engineering mixed lot <script>text only</script>',seller_image:'https://i.ebayimg.com/images/g/Engineering/s-l1600.jpg',price:{amount:'12.00',currency:'USD'},shipping:{amount:null,currency:null},price_kind:'current_bid',ends_at:null,aspects:[],clues:{conflicts:[],graded:false},proposals:[],seller_lot_size:null,api_lot_size:null,stock_quantity:null,discovery_origin:{run_id:'engineering-run',result_id:'engineering-result'}};
function setup(overrides={},control={}){
  let now=100000;const nodes=new Map(),events={},intervals=[],calls=[],timeouts=[];
  const get=id=>{if(!nodes.has(id))nodes.set(id,new Element());return nodes.get(id);};
  get('check-binding').textContent='"binding"';get('check-account').textContent='"account"';get('check-entry').textContent=JSON.stringify({discovery_run:'engineering-run',item_id:'engineering-result'});
  const window={addEventListener:(name,fn)=>events[name]=fn,DexAuctionTime:()=> 'Auction · end time unknown'};
  const context={crypto:require('node:crypto').webcrypto,history:{replaceState(){}},window,document:{getElementById:get,createElement:tag=>new Element(tag),addEventListener:(name,fn)=>events[name]=fn},addEventListener:(name,fn)=>events[name]=fn,Date:{now:()=>now,parse:Date.parse},URL,URLSearchParams,Intl,setTimeout:fn=>{timeouts.push(fn);return timeouts.length;},clearTimeout(){},setInterval:fn=>intervals.push(fn),location:{reload(){},href:'http://local.test/shopping/check/'},fetch:async(url,options)=>{
    calls.push({url,method:options.method||'GET',body:options.body});let payload;
    if(url.includes('/candidate/'))payload={listing:structuredClone({...sample,...overrides}),restore_cards:structuredClone(control.restoreCards || []),expires_in_seconds:30,context:{scope_label:'Named engineering search'}};
    else payload={review:null,lease:'lease',expires_in_seconds:30,context:null};
    if(options.method==='POST' && control.post) await control.post(JSON.parse(options.body));
    if(control.request)payload=await control.request(url,options,payload);
    return {status:200,ok:true,redirected:false,headers:{get:()=> 'application/json'},json:async()=>({...payload,authority:{binding:'binding',account_id:'account'}})};
  }};
  vm.createContext(context);vm.runInContext(display,context);vm.runInContext(source,context);
  return {get,events,intervals,calls,timeouts,location:context.location,advance:ms=>now+=ms};
}
async function flush(){for(let i=0;i<100;i++)await Promise.resolve();}
const passed=[];async function test(name,fn){await fn();passed.push(name);}
(async()=>{
 await test('selected offer leads with admitted photo, title, bid, seller link and unknown shipping',async()=>{
  const t=setup();await flush();assert.equal(t.get('offer-overview').hidden,false);
  assert.match(t.get('offer-summary').textContent,/Engineering mixed lot/);assert.match(t.get('offer-summary').textContent,/Shipping Unknown/);
  const photo=t.get('offer-summary').children[0];assert.equal(photo.children.find(c=>c.tagName==='img').src,sample.seller_image);
  assert.equal(photo.href,sample.item_url);assert.equal(t.get('listing-tools').open,false);assert.equal(t.get('review-editor').open,false);
  assert.ok(t.calls.every(c=>c.method==='GET'));assert.ok(!t.calls.some(c=>c.url==='/api/shopping/listing/'));
 });
 const identity={id:'printing-one',name:'Checked card',set_name:'Checked set',collector_number:'1'};
 const savedReview={title:'My saved review',currency:'USD',unknown_contents:null,cards:[{printing_id:identity.id,quantity:2,grade:'8',grader:'PSA'}]};
 const restore=(url,payload,review=savedReview)=>url==='/api/shopping/listing/review/'?{...payload,review}:url.includes('/catalog/')?{cards:[identity]}:payload;
 await test('selected admitted identities restore authored cards without a duplicate catalog read',async()=>{
  const t=setup({proposals:[{...identity,quantity:99}]},{restoreCards:[identity],request:async(url,options,payload)=>restore(url,payload)});await flush();
  assert.ok(!t.calls.some(c=>c.url.includes('/catalog/')));
  assert.match(t.get('review-cards').textContent,/Checked card/);
  assert.match(t.get('review-count').textContent,/2 individually identified cards/);
  assert.match(t.get('review-cards').textContent,/Grade 8/);
  assert.equal(t.get('review-title').value,'My saved review');
  assert.equal(t.get('offer-overview').hidden,false);
  assert.equal(t.calls.filter(c=>c.url.includes('/candidate/')).length,1);
 });
 await test('a retained card absent from candidate identities keeps the checked catalog restore',async()=>{
  const t=setup({}, {restoreCards:[{...identity,id:'another-printing',name:'Other card'}],request:async(url,options,payload)=>restore(url,payload)});await flush();
  assert.equal(t.calls.filter(c=>c.url.includes('/catalog/')).length,1);
  assert.match(t.get('review-cards').textContent,/Checked card/);
  assert.doesNotMatch(t.get('review-cards').textContent,/Other card/);
 });
 await test('candidate failure still restores the saved review for recovery',async()=>{
  const t=setup({}, {request:async(url,options,payload)=>{if(url.includes('/candidate/'))throw Error('Offer unavailable');return restore(url,payload);}});await flush();
  assert.equal(t.get('review-title').value,'My saved review');
  assert.match(t.get('review-cards').textContent,/Checked card/);
  assert.match(t.get('check-status').textContent,/Offer unavailable/);
 });
 await test('revocation while selecting cannot restore saved private fields',async()=>{
  let release;
  const t=setup({}, {request:async(url,options,payload)=>{if(url.includes('/candidate/'))await new Promise(resolve=>release=resolve);return restore(url,payload);}});await flush();
  t.events['dex:authority-revoked']();release();await flush();
  assert.equal(t.get('review-title').value,'');assert.equal(t.get('review-cards').children.length,0);
  assert.equal(t.get('offer-overview').hidden,true);
 });
 await test('slow identity restoration does not extend an already received offer deadline',async()=>{
  let release;
  const t=setup({}, {request:async(url,options,payload)=>{if(url.includes('/catalog/'))await new Promise(resolve=>release=resolve);return restore(url,payload);}});await flush();
  t.advance(31000);release();await flush();
  assert.match(t.get('check-status').textContent,/offer expired/);
  assert.ok(!t.get('offer-summary').children.length);
 });
 await test('unsafe image stays a readable fallback',async()=>{
  const t=setup({seller_image:'https://evil.invalid/photo.jpg'});await flush();const photo=t.get('offer-summary').children[0];assert.ok(!photo.children.some(c=>c.tagName==='img'));assert.match(photo.textContent,/Seller photo unavailable/);
 });
 await test('explicit review keeps offer above editor and original photo expiry still clears it',async()=>{
  const t=setup();await flush();await t.get('use-listing').onclick();assert.equal(t.get('review-editor').open,true);assert.equal(t.get('offer-overview').hidden,false);
  t.advance(31000);await t.intervals[0]();assert.equal(t.get('offer-overview').hidden,true);assert.equal(t.get('offer-summary').children.length,0);
 });
 for(const event of ['dex:authority-revoked','pagehide'])await test(event+' removes offer photos and seller content',async()=>{const t=setup();await flush();t.events[event]();await flush();assert.equal(t.get('offer-overview').hidden,true);assert.equal(t.get('offer-summary').children.length,0);});
 await test('Stop and discard remove preview photo immediately',async()=>{for(const id of ['stop-listing','discard-listing']){const t=setup();await flush();await t.get(id).onclick();assert.equal(t.get('offer-overview').hidden,true);assert.equal(t.get('offer-summary').children.length,0);}});
 await test('manual entry opens optional editor locally',async()=>{const t=setup();await flush();const count=t.calls.length;t.get('manual-entry').listeners.click();assert.equal(t.get('review-editor').open,true);assert.equal(t.calls.length,count);});
 await test('Back from unchanged selected offer restores navigation without saving a review',async()=>{
  const t=setup();await flush();let prevented=false;const anchor={href:'http://127.0.0.1:8011/shopping/',hash:'',target:''};
  await t.events.click({target:{closest:()=>anchor},preventDefault(){prevented=true;}});
  assert.equal(prevented,true);assert.equal(t.calls.filter(c=>c.method==='POST').length,0);
 });
 await test('seller link keeps its separate tab without saving or intercepting',async()=>{
  const t=setup();await flush();let prevented=false;
  await t.events.click({target:{closest:()=>({href:sample.item_url,target:'_blank'})},preventDefault(){prevented=true;}});
  assert.equal(prevented,false);assert.equal(t.calls.filter(c=>c.method==='POST').length,0);
 });
 await test('Back saves genuine changes once and repeat navigation does not resave',async()=>{
  const t=setup();await flush();t.get('review-title').value='My engineering notes';t.get('review-title').listeners.input();
  const event={target:{closest:()=>({href:'http://127.0.0.1:8011/shopping/',hash:'',target:''})},preventDefault(){}};
  await t.events.click(event);await t.events.click(event);
  const posts=t.calls.filter(c=>c.method==='POST');assert.equal(posts.length,1);assert.equal(JSON.parse(posts[0].body).review.title,'My engineering notes');
 });
 const backEvent=()=>({target:{closest:()=>({href:'http://127.0.0.1:8011/shopping/',hash:'',target:''})},preventDefault(){}});
 await test('autosave and Back share one writer and coalesce queued intermediate edits',async()=>{
  const held=[];const t=setup({}, {post:()=>new Promise(resolve=>held.push(resolve))});await flush();
  const edit=text=>{t.get('review-title').value=text;t.get('review-title').listeners.input();};
  edit('first');t.timeouts.at(-1)();await flush();assert.equal(held.length,1);
  edit('intermediate');t.timeouts.at(-1)();await flush();
  edit('latest');const navigation=t.events.click(backEvent());await flush();
  assert.equal(t.calls.filter(c=>c.method==='POST').length,1);assert.equal(t.location.href,'http://local.test/shopping/check/');
  held[0]();await flush();assert.equal(held.length,2);
  const posts=t.calls.filter(c=>c.method==='POST');assert.equal(JSON.parse(posts[1].body).review.title,'latest');
  assert.equal(t.get('review-title').value,'latest');assert.equal(t.location.href,'http://local.test/shopping/check/');
  held[1]();await navigation;assert.equal(t.location.href,'http://127.0.0.1:8011/shopping/');
  await t.events.click(backEvent());assert.equal(t.calls.filter(c=>c.method==='POST').length,2);
 });
 await test('Back after completed autosave does not submit again',async()=>{
  const t=setup();await flush();t.get('review-title').value='saved';t.get('review-title').listeners.input();
  t.timeouts.at(-1)();await flush();await t.events.click(backEvent());
  assert.equal(t.calls.filter(c=>c.method==='POST').length,1);assert.ok(t.location.href);
 });
 await test('failed save keeps the latest input and blocks navigation until a successful retry',async()=>{
  let fail=true;const t=setup({}, {post:async()=>{if(fail)throw Error('Save unavailable');}});await flush();
  t.get('review-title').value='keep this edit';t.get('review-title').listeners.input();
  await t.events.click(backEvent());assert.equal(t.location.href,'http://local.test/shopping/check/');assert.equal(t.get('review-title').value,'keep this edit');
  assert.match(t.get('check-status').textContent,/Save unavailable/);
  fail=false;await t.events.click(backEvent());assert.ok(t.location.href);
  assert.equal(JSON.parse(t.calls.filter(c=>c.method==='POST').at(-1).body).review.title,'keep this edit');
 });
 await test('revocation during a held save clears private fields and blocks navigation',async()=>{
  let release;const t=setup({}, {post:()=>new Promise(resolve=>release=resolve)});await flush();
  t.get('review-title').value='private edit';t.get('review-title').listeners.input();
  const pending=t.events.click(backEvent());await flush();t.get('listing-check').querySelectorAll=()=>[t.get('review-title')];t.events['dex:authority-revoked']();release();await pending;
  assert.equal(t.location.href,'http://local.test/shopping/check/');assert.equal(t.get('offer-summary').children.length,0);
  assert.ok(t.get('review-title').disabled);
 });
 await test('lost detail response disables acquisition and reload only reconciles',async()=>{
  const t=setup({}, {request:async(url,options,payload)=>{
    if(url==='/api/shopping/listing/' && options.method==='POST')throw Error('Lost response');
    if(url.includes('request_id='))return {run_id:'detail-run',running:false,state:'complete',expires_in_seconds:20};
    return payload;
  }});await flush();
  await t.get('listing-load').onsubmit({preventDefault(){}});await flush();
  assert.equal(t.get('load-listing').disabled,true);assert.equal(t.get('stop-listing').disabled,false);
  await t.get('listing-load').onsubmit({preventDefault(){}});
  assert.equal(t.calls.filter(c=>c.url==='/api/shopping/listing/' && c.method==='POST').length,1);
  await t.get('check-reload').listeners.click();await flush();
  assert.ok(t.calls.some(c=>c.url.includes('request_id=') && c.method==='GET'));
  assert.equal(t.get('load-listing').disabled,false);
 });
 await test('unresolved detail status remains locked and Stop is not falsely confirmed',async()=>{
  const t=setup({}, {request:async(url,options,payload)=>{
    if(url==='/api/shopping/listing/' && options.method==='POST')throw Error('Lost response');
    if(url.includes('request_id='))return {outcome_unknown:true};
    return payload;
  }});await flush();await t.get('listing-load').onsubmit({preventDefault(){}});await flush();
  await t.get('stop-listing').onclick();await flush();
  assert.match(t.get('check-status').textContent,/outcome is unknown/);
  assert.equal(t.get('load-listing').disabled,true);assert.equal(t.get('stop-listing').disabled,false);
 });
 process.stdout.write(JSON.stringify({passed:passed.length,cases:passed,provider_calls:0,customer_data:false})+'\n');
})().catch(e=>{console.error(e);process.exitCode=1;});
