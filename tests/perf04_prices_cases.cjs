'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync('src/pokemon_hunter/beta/static/card-screens.js','utf8');
const bind=source.slice(source.indexOf('  function bindPrices('),source.indexOf('  async function renderDetail('));
(async()=>{
 const disclosure={open:true},body={innerHTML:''},copies=[],calls=[];
 const context={$:s=>s==='#group-prices'?disclosure:body,document:{body:{dataset:{parity:'true'}}},data:{effective_collection:{generation:5}},window:{},account:()=> 'a',copyPrices:()=>'',copyPriceContent:c=>'Guide '+c.id,esc:String,api:async path=>{calls.push(path);return {effective_collection:{user_id:'a',generation:5},valuation:{copies:{one:{conditional:{raw:{value:3}}}}}}}};
 vm.createContext(context);vm.runInContext(bind,context);context.bindPrices(copies,5,()=>true,2);
 await disclosure.ontoggle();assert.equal(calls.length,0);assert.match(body.innerHTML,/Open Recorded copies/);assert.doesNotMatch(body.innerHTML,/No matching/);
 copies.push({id:'one'});await disclosure.ontoggle();assert.equal(calls.length,1);assert.match(body.innerHTML,/1 of 2/);assert.match(body.innerHTML,/Guide one/);
 await disclosure.ontoggle();assert.equal(calls.length,1);
 copies.push({id:'two'});await disclosure.ontoggle();assert.equal(calls.length,2);assert.doesNotMatch(body.innerHTML,/1 of 2/);assert.match(body.innerHTML,/No matching retained guide evidence for this copy/);
 console.log('PASS: unloaded copy evidence is distinct from absent evidence; later pages refresh explicitly.');
})().catch(e=>{console.error(e);process.exitCode=1;});
