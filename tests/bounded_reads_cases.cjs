'use strict';
const assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
const source=fs.readFileSync('src/pokemon_hunter/beta/static/bounded-reads.js','utf8');
const response=(body,status=200)=>({ok:status===200,status,json:async()=>body});
const state={read_version:2,public:false,account_id:'a',generation:7,catalog_revision:'c',account_revision:'r'};
function setup(){const calls=[],pending=[],window={},context={window,document:{querySelector:()=>null,getElementById:()=>null},location:{origin:'http://localhost'},URL,URLSearchParams,AbortController,DOMException,Error,Option:function(){},Event,fetch:(url,options)=>{calls.push({url,options});return new Promise(resolve=>pending.push(resolve));}};vm.createContext(context);vm.runInContext(source,context);return {...context,calls,pending,api:window.BoundedReads};}
(async()=>{
 let count=0;
 const check=async(name,fn)=>{await fn();count++;};
 await check('explicit public and private mapping',async()=>{for(const publicRead of [false,true]){const t=setup(),r=new t.api.Reader({publicRead});const p=r.get(publicRead?'/api/v2/public/catalog/':'/api/v2/catalog/');t.pending[0](response({...state,public:publicRead,[publicRead?'cards':'printings']:[{id:'p'}]}));const v=await p;assert.equal(v[publicRead?'cards':'printings'][0].id,'p');}});
 await check('revision selectors bind subsequent reads',async()=>{const t=setup(),r=new t.api.Reader({seed:state});const p=r.get('/api/v2/card-groups/?q=x');assert.match(t.calls[0].url,/account_revision=r/);assert.match(t.calls[0].url,/catalog_revision=c/);t.pending[0](response(state));await p;});
 await check('same channel aborts and rejects obsolete response',async()=>{const t=setup(),r=new t.api.Reader();const first=r.get('/api/v2/catalog/?q=a','search').catch(e=>e);const second=r.get('/api/v2/catalog/?q=b','search');assert.equal(t.calls[0].options.signal.aborted,true);t.pending[1](response(state));await second;t.pending[0](response(state));assert.equal((await first).name,'AbortError');});
 await check('route departure rejects late response',async()=>{const t=setup();let active=true;const r=new t.api.Reader({active:()=>active}),p=r.get('/api/v2/catalog/').catch(e=>e);active=false;t.pending[0](response(state));assert.equal((await p).name,'AbortError');});
 for(const key of ['account_id','account_revision','catalog_revision','generation'])await check('reject changed '+key,async()=>{const t=setup(),r=new t.api.Reader({seed:state}),p=r.get('/api/v2/catalog/').catch(e=>e);t.pending[0](response({...state,[key]:'different'}));assert.equal((await p).status,key==='account_id'?403:409);});
 for(const status of [403,404,409,503])await check('bounded error '+status,async()=>{const t=setup();let cleared=false;t.window.discardNavigationAuthority=()=>cleared=true;const r=new t.api.Reader(),p=r.get('/api/v2/catalog/').catch(e=>e);t.pending[0](response({code:status===503?'read_state_unavailable':'failure'},status));const error=await p;assert.equal(error.status,status);assert.equal(t.calls.length,1);if(status===403)assert.equal(cleared,true);if(status===503)assert.match(error.message,/preparation/);});
 await check('explicit page continuation preserves selectors',async()=>{const t=setup();assert.equal(t.api.next('/api/v2/catalog/?q=abc',{page:1,pages:2,page_size:40}),'/api/v2/catalog/?q=abc&page=2&page_size=40');assert.equal(t.api.next('/api/v2/catalog/',{next:null}),null);});
 console.log(JSON.stringify({passed:count}));
})().catch(e=>{console.error(e);process.exitCode=1;});
