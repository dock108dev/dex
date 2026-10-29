'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync('src/pokemon_hunter/beta/static/collection.js','utf8');
const mutate=source.slice(source.indexOf('async function mutate(action)'),source.indexOf('async function recoverPendingOperation'));
(async()=>{
 const nodes=new Map(),calls=[],receipts=[];
 const context={busy:false,currentOperation:{id:'operation',state:'preview'},location:{href:'http://localhost/card-groups/g/'},data:{effective_collection:{user_id:'a'}},window:{},sessionStorage:{setItem(){},removeItem(){}},$:(id)=>{if(!nodes.has(id))nodes.set(id,{disabled:false,open:true,textContent:''});return nodes.get(id);},api:async(path,payload)=>{calls.push({path,payload});return {id:'operation',user_id:'a',state:'confirmed'};},showReview:receipt=>{receipts.push(receipt);context.currentOperation=receipt;},refresh:async()=>{throw Error('Explicit preparation required.');},restoreCollectionFocus(){},recoverPendingOperation:async()=>{},status(){}};
 vm.createContext(context);vm.runInContext(mutate,context);await context.mutate('confirm');
 assert.equal(calls.length,1);assert.match(calls[0].path,/confirm/);assert.equal(context.currentOperation.state,'confirmed');assert.equal(receipts.at(-1).state,'confirmed');assert.match(nodes.get('#review-error').textContent,/Change saved.*preparation/);console.log('PASS: confirmation receipt survives unavailable derived reads with one mutation request.');
})().catch(e=>{console.error(e);process.exitCode=1;});
