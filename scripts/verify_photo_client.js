'use strict';
// Engineering-only DOM/transport test. No browser, customer root or provider requests.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const packageRoot=process.env.DEX_TEST_PACKAGE||path.join(__dirname,'../src/pokemon_hunter');
function descendants(e) { return e.children.flatMap(c => [c, ...descendants(c)]); }
function matches(e, selector) {
  if (selector.startsWith('.')) return (e.className || '').split(' ').includes(selector.slice(1));
  if (selector.startsWith('[')) return e.getAttribute(selector.slice(1,-1)) !== null;
  return e.tagName === selector.toUpperCase();
}
class Element {
  constructor(tag) { this.tagName=tag.toUpperCase();this.children=[];this.dataset={};this.attributes={};this.style={};this.value='';this._text='';this.listeners={}; }
  set textContent(v) { this._text=String(v);this.children=[]; }
  get textContent() { return this._text+this.children.map(c=>c.textContent).join(''); }
  setAttribute(k,v) { this.attributes[k]=String(v);if(k==='class')this.className=v;if(k==='value')this.value=v;if(k.startsWith('data-'))this.dataset[k.slice(5).replace(/-([a-z])/g,(_,x)=>x.toUpperCase())]=v; }
  getAttribute(k) { return this.attributes[k]??null; }
  append(...items) { for(const c of items){c.remove();c.parent=this;this.children.push(c);} }
  replaceChildren(...items) { this.children=[];this._text='';this.append(...items); }
  remove() { if(this.parent)this.parent.children=this.parent.children.filter(c=>c!==this); }
  querySelectorAll(q) { return descendants(this).filter(e=>q.split(',').some(s=>matches(e,s))); }
  querySelector(q) { return this.querySelectorAll(q)[0]||null; }
  closest() { return null; }
  addEventListener(k,fn) { (this.listeners[k]??=[]).push(fn); }
  focus() {}
}
(async()=>{
 const ids={},root=new Element('main');ids['photo-entry']=root;const containerIds=['photo-csrf','photo-status','photo-results','photo-summary','photo-cards','photo-sources','photo-report','photo-report-body','photo-saved'];
 for(const id of containerIds){const e=new Element('div');e.id=id;ids[id]=e;root.append(e);}
 for(const id of ['photo-identify','photo-stop','photo-retry','photo-confirm','photo-undo']){const e=new Element('button');e.id=id;ids[id]=e;root.append(e);}
 for(const id of ['photo-file','photo-notes']){const e=new Element('input');e.id=id;ids[id]=e;root.append(e);}ids['photo-csrf'].append(new Element('input'));
 const calls=[],timers=new Map();let serial=0;
 const group={id:'group',name:'Kangaskhan',set_name:'Jungle',collector_number:'5',existing:{present:false},children:[{id:'printing'}]};
 const photo={id:'photo',state:'active',proposal:{}};
 const batch={id:'batch',revision:1,created:1,state:'editing',photos:[photo],crops:[],stages:[],consent_version:'test'};
 const identity={name:'Kangaskhan',set_name:'Jungle',number:'5'};
 const operation={id:'op',state:'confirmed',plan:{photo_report:[{identity,status:'added',first_edition:false}]}};
 async function fetch(url,options){const data=options.body instanceof FormData?options.body:options.body?JSON.parse(options.body):undefined;calls.push({url,data});let result={};
  if(url==='/api/bulk/catalog/')result={groups:[group]};else if(url==='/api/photo-batches/')result={batches:[]};
  else if(url.endsWith('/confirm-cards/'))result={operation};else if(url.endsWith('/undo/'))result={...operation,state:'undone'};
  else {if(url.endsWith('/analyze/'))batch.stages=[{stage:'photo',state:'queued'}];batch.revision++;result={batch:JSON.parse(JSON.stringify(batch))};}
  return {ok:true,status:200,json:async()=>({...result,binding:'binding'})};
 }
 const context={document:{body:{dataset:{navigationBinding:'binding'}},getElementById:id=>ids[id],createElement:tag=>new Element(tag)},window:{addEventListener(){}},history:{replaceState(){}},location:{search:''},URLSearchParams,FormData,crypto:{randomUUID:()=> 'batch'},fetch,setTimeout:fn=>{timers.set(++serial,fn);return serial;},clearTimeout:id=>timers.delete(id),console};
 vm.runInNewContext(fs.readFileSync(path.join(packageRoot,'beta/static/photo_batches.js'),'utf8'),context);
 const drain=async()=>{for(let i=0;i<35;i++)await Promise.resolve();};const click=async id=>{assert.ok(!ids[id].disabled);await ids[id].onclick();await drain();};
 await drain();assert.equal(calls.length,2);await click('photo-identify');assert.equal(calls.length,2,'no request without chosen image');
 ids['photo-file'].files=[new Blob(['engineering fixture'])];ids['photo-notes'].value='Optional details';await click('photo-identify');
 assert.equal(calls.filter(c=>c.url.endsWith('/analyze/')).length,1);const analyzed=calls.find(c=>c.url.endsWith('/analyze/'));assert.equal(analyzed.data.stage,'photo');assert.equal(analyzed.data.notes,'Optional details');assert.ok(!ids['photo-stop'].hidden);
 batch.stages[0].state='completed';batch.crops=[{id:'crop',state:'active',candidates:[{id:'printing'}],row_json:{},proposal:{name:'Kangaskhan',edition:'Unlimited',finish:'Holofoil'}}];
 await [...timers.values()].at(-1)();await drain();assert.ok(!ids['photo-results'].hidden);assert.match(ids['photo-cards'].textContent,/Jungle · #5/);assert.equal(calls.filter(c=>c.url.endsWith('/analyze/')).length,1,'no automatic extra analysis');
 await click('photo-confirm');const commit=calls.find(c=>c.url.endsWith('/confirm-cards/'));assert.deepEqual(commit.data.choices,[{id:'crop',included:true,row:{printing_id:'printing'}}]);assert.match(ids['photo-report-body'].textContent,/Kangaskhan — Jungle #5: Added/);
 await click('photo-undo');assert.match(ids['photo-report-body'].textContent,/undone/);
 console.log('PASS: one explicit photo analysis, optional notes, automatic catalog suggestion, reviewed confirmation, report and Undo; no extra analysis or draft on open.');
})().catch(e=>{console.error(e);process.exitCode=1;});
