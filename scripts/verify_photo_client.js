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
async function verify(recognitionEnabled){
 const ids={},root=new Element('main');ids['photo-entry']=root;root.dataset.recognitionEnabled=String(recognitionEnabled);const containerIds=['photo-csrf','photo-status','photo-results','photo-summary','photo-cards','photo-sources','photo-report','photo-report-body','photo-saved'];
 for(const id of containerIds){const e=new Element('div');e.id=id;ids[id]=e;root.append(e);}
 for(const id of ['photo-identify','photo-stop','photo-retry','photo-confirm','photo-undo']){const e=new Element('button');e.id=id;ids[id]=e;root.append(e);}
 for(const id of ['photo-file','photo-notes']){const e=new Element('input');e.id=id;ids[id]=e;root.append(e);}ids['photo-csrf'].append(new Element('input'));
 const calls=[],timers=new Map();let serial=0;
 const group={id:'group',name:'Kangaskhan',set_name:'Jungle',collector_number:'5',existing:{present:false},children:[{id:'printing'}]};
 const photo={id:'photo',state:'active',proposal:{}};
 const batch={id:'batch',revision:1,created:1,state:'editing',photos:[photo],crops:[],stages:[],consent_version:'test'};
 if(!recognitionEnabled){batch.recognition_enabled=false;batch.crops=[{id:'crop',state:'active',candidates:[{id:'printing'}],row_json:{},proposal:{name:'Kangaskhan'}}];}
 const identity={name:'Kangaskhan',set_name:'Jungle',number:'5'};
 const operation={id:'op',state:'confirmed',plan:{photo_report:[{identity,status:'added',first_edition:false}]}};
 async function fetch(url,options){const data=options.body instanceof FormData?options.body:options.body?JSON.parse(options.body):undefined;calls.push({url,data});let result={};
  if(url.startsWith('/api/v2/selection-groups/'))result={groups:[{...group,present:false}],candidates:[{id:'printing',group_id:'group'}],read_version:2,public:false,account_id:'account',catalog_revision:'c',account_revision:'a',generation:1};else if(url==='/api/photo-batches/')result={batches:recognitionEnabled?[]:[{id:'batch',state:'editing',created:1}]};
  else if(url.endsWith('/confirm-cards/'))result={operation};else if(url.endsWith('/undo/'))result={...operation,state:'undone'};
  else {if(url.endsWith('/analyze/'))batch.stages=[{stage:'photo',state:'queued'}];batch.revision++;result={batch:JSON.parse(JSON.stringify(batch))};}
  return {ok:true,status:200,json:async()=>({...result,binding:'binding'})};
 }
 const context={document:{body:{dataset:{navigationBinding:'binding'}},getElementById:id=>ids[id],querySelector:()=>null,createElement:tag=>new Element(tag)},window:{addEventListener(){}},history:{replaceState(){}},location:{search:'',origin:'http://127.0.0.1:8011'},URL,AbortController,DOMException,URLSearchParams,FormData,crypto:{randomUUID:()=> 'batch'},fetch,setTimeout:fn=>{timers.set(++serial,fn);return serial;},clearTimeout:id=>timers.delete(id),console};
 vm.runInNewContext(fs.readFileSync(path.join(packageRoot,'beta/static/bounded-reads.js'),'utf8'),context);context.BoundedReads=context.window.BoundedReads;
 vm.runInNewContext(fs.readFileSync(path.join(packageRoot,'beta/static/photo_batches.js'),'utf8'),context);
 const drain=async()=>{for(let i=0;i<35;i++)await Promise.resolve();};const click=async id=>{assert.ok(!ids[id].disabled);await ids[id].onclick();await drain();};
 await drain();
 if(!recognitionEnabled){
  assert.ok(!fs.readFileSync(path.join(packageRoot,'beta/static/photo_batches.js'),'utf8').includes("action('analyze'"));
  assert.ok(!ids['photo-results'].hidden);assert.match(ids['photo-cards'].textContent,/Kangaskhan/);
  assert.equal(calls.filter(c=>c.url.endsWith('/analyze/')).length,0);
  await click('photo-confirm');assert.match(ids['photo-report-body'].textContent,/Added/);
  await click('photo-undo');assert.match(ids['photo-report-body'].textContent,/undone/);
  assert.equal(calls.filter(c=>c.url.endsWith('/analyze/')).length,0);
  console.log('PASS: recognition transport removed; previous review, manual confirmation and Undo survive without analysis.');
  return;
 }

}
(async()=>{await verify(false);})().catch(e=>{console.error(e);process.exitCode=1;});
