'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync('src/pokemon_hunter/beta/static/collection.js','utf8');
const tools=source.slice(source.indexOf('async function withCollectionTools('),source.indexOf('async function render()'));
const refresh=source.slice(source.indexOf('async function refresh('),source.indexOf('async function withCollectionTools('));
function setup(){
  const data={context_only:true,effective_collection:{user_id:'owner',generation:7,cards:[]}};
  const calls=[],messages=[],context={data,location:{pathname:'/pokedex/',search:''},window:{},api:async path=>{calls.push(path);return {effective_collection:{user_id:'owner',generation:7,cards:[{present:true}]},goal_options:{}};},status:m=>messages.push(m),refreshSequence:0,document:{body:{dataset:{parity:'false'}}},render:async()=>{},console};
  vm.createContext(context);vm.runInContext(tools+refresh,context);return {context,calls,messages,data};
}
(async()=>{
 const results=[];
 async function check(name,fn){await fn();results.push(name);}
 await check('ordinary card browsing lets the V2 renderer load primary data without bootstrap',async()=>{const t=setup();t.context.location.pathname='/cards/';await t.context.refresh();assert.deepEqual(t.calls,[]);});
 await check('settings retains explicit full tool load',async()=>{const t=setup();t.context.location.pathname='/settings/';await t.context.refresh();assert.deepEqual(t.calls,['/api/collection/']);});
 await check('explicit tool request loads once and preserves authority identity',async()=>{const t=setup();let opened=0;await t.context.withCollectionTools(()=>opened++);assert.deepEqual(t.calls,['/api/collection/']);assert.equal(t.context.data,t.data);assert.equal(t.data.context_only,false);await t.context.withCollectionTools(()=>opened++);assert.equal(t.calls.length,1);assert.equal(opened,2);});
 for(const change of ['route','account','refresh','logout'])await check('late tools cannot open after '+change,async()=>{const t=setup();let resolve,opened=false;t.context.api=()=>new Promise(r=>resolve=r);const pending=t.context.withCollectionTools(()=>opened=true);if(change==='route')t.context.location.pathname='/cards/';if(change==='account')t.context.data={effective_collection:{user_id:'other',generation:7}};if(change==='refresh')t.context.data={...t.data};if(change==='logout')t.context.window.navigationAuthorityDiscarded=true;resolve({effective_collection:{user_id:'owner',generation:7,cards:[]}});await pending;assert.equal(opened,false);assert.equal(t.data.context_only,true);});
 for(const field of ['user_id','generation'])await check('mismatched tool '+field+' blocks merge and dialog',async()=>{const t=setup();let opened=false;t.context.api=async()=>({effective_collection:{user_id:'owner',generation:7,[field]:field==='user_id'?'other':8}});await t.context.withCollectionTools(()=>opened=true);assert.equal(opened,false);assert.equal(t.data.context_only,true);assert.match(t.messages[0],/Collection changed/);});
 await check('latest explicit tool intent wins overlapping requests',async()=>{const t=setup(),pending=[],opened=[];t.context.api=()=>new Promise(r=>pending.push(r));const first=t.context.withCollectionTools(()=>opened.push('first'));const second=t.context.withCollectionTools(()=>opened.push('second'));pending[1]({effective_collection:{user_id:'owner',generation:7}});await second;pending[0]({effective_collection:{user_id:'owner',generation:7}});await first;assert.deepEqual(opened,['second']);});
 console.log(JSON.stringify({passed:results.length,cases:results,customer_data:false,provider_calls:0},null,2));
})().catch(e=>{console.error(e);process.exitCode=1;});
