/* Executes the shipped navigation adapter against observable browser boundaries. */
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const source=fs.readFileSync(process.argv[2],'utf8');
const origin='http://127.0.0.1:8011',binding='auth-bound',actor='account-one';
const key='dex-navigation-home:'+origin+':'+binding;
async function browser({path='/',memory,unavailable=false,reply,account=actor,authority=binding,onFetch,channels}={}) {
  const replacements=[],fetches=[],events={},logout={},trace=[];
  const main={children:['private collection'],replaceChildren(){this.children=[];trace.push('main-clear');}};
  const dialogs=[true,false].map((open,index)=>({open,children:['private dialog '+index],close(){this.open=false;trace.push('dialog-close:'+index);},replaceChildren(){this.children=[];trace.push('dialog-clear:'+index);}}));
  const storage={getItem(k){if(unavailable)throw new Error('blocked');return this[k]??null;},setItem(k,v){if(unavailable)throw new Error('blocked');this[k]=String(v);},removeItem(k){if(unavailable)throw new Error('blocked');delete this[k];}};
  if(memory!==undefined)storage[key]=typeof memory==='string'?memory:JSON.stringify(memory);
  const location={origin,pathname:path,search:'',href:origin+path,replace(value){trace.push('redirect');replacements.push(value);},reload(){trace.push('reload');events.reload=(events.reload||0)+1;}};
  const ctx={URL,URLSearchParams,Promise,JSON,Number,Object,String,Math,Event,dispatchEvent(){},location,sessionStorage:storage,scrollY:54,
    document:{body:{dataset:{navigationAccount:account,navigationBinding:authority}},querySelector(selector){return selector==='main'?main:null;},querySelectorAll(selector){return selector==='dialog'?dialogs:selector==='form[action="/logout/"]'?[{addEventListener(name,fn){logout[name]=fn;}}]:[];}},
    invalidateCollectionRequests(){trace.push('invalidate-shared');},invalidateCardScreens(){trace.push('invalidate-cards');},invalidateSpeciesScreens(){trace.push('invalidate-species');},
    addEventListener(name,fn){events[name]=fn;},
    data:{effective_collection:{user_id:account,generation:12}},
    fetch:async(url)=>{fetches.push(url);if(onFetch)onFetch(ctx);return reply||{ok:true,status:200,redirected:false,json:async()=>({destination:'/pokedex/?owned=missing',account_id:actor,navigation_binding:binding})};}};
  if(channels)ctx.BroadcastChannel=class{constructor(){channels.push(this);}postMessage(message){for(const channel of channels)if(channel!==this)channel.onmessage?.({data:message});}};
  ctx.window=ctx;vm.runInNewContext(source,ctx);await ctx.navigationReady;
  return {ctx,storage,replacements,fetches,events,logout,main,dialogs,trace};
}
(async()=>{
  for(const memory of [undefined,'broken','null',{v:2,account:actor,binding,destination:'/pokedex/'},{v:1,account:'other',binding,destination:'/pokedex/'},{v:1,account:actor,binding:'old',destination:'/pokedex/'},{v:1,account:actor,binding,destination:'/'},{v:1,account:actor,binding,destination:'/settings/'},{v:1,account:actor,binding,destination:'/shopping/'},{v:1,account:actor,binding,destination:'//host/cards/'}]) {
    const b=await browser({memory});assert.deepEqual(b.replacements,['/cards/']);assert.equal(b.fetches.length,0);
  }
  const blocked=await browser({unavailable:true});assert.deepEqual(blocked.replacements,['/cards/']);
  const valid={v:1,account:actor,binding,destination:'/pokedex/?owned=missing'};
  const retained=await browser({memory:valid});assert.deepEqual(retained.replacements,[valid.destination]);assert.equal(retained.fetches.length,1);
  const invalid=await browser({memory:valid,reply:{ok:false,status:400}});assert.deepEqual(invalid.replacements,['/cards/']);
  const revoked=await browser({memory:valid,reply:{ok:false,status:403}});assert.deepEqual(revoked.replacements,['/login/?next=%2Fcards%2F']);assert.equal(revoked.storage[key],undefined);
  const late=await browser({memory:valid,reply:{ok:true,status:200,json:async()=>({destination:'/pokedex/',account_id:'other',navigation_binding:binding})}});assert.deepEqual(late.replacements,['/cards/']);
  const routeChanged=await browser({memory:valid,onFetch(ctx){ctx.location.pathname='/settings/';}});assert.equal(routeChanged.replacements.length,0);
  const accountChanged=await browser({memory:valid,onFetch(ctx){ctx.data.effective_collection.user_id='other';}});assert.equal(accountChanged.replacements.length,0);
  const explicit=await browser({path:'/card-library/',memory:valid});assert.equal(explicit.fetches.length,0);assert.equal(explicit.replacements.length,0);
  const guest=await browser({account:'',authority:''});assert.equal(guest.replacements.length,0);
  const card=await browser({path:'/cards/'});assert.equal(card.storage[key],undefined);card.ctx.rememberCollectionDestination();assert.equal(JSON.parse(card.storage[key]).destination,'/cards/?scroll=54');
  card.ctx.data.effective_collection.user_id='other';delete card.storage[key];card.ctx.rememberCollectionDestination();assert.equal(card.storage[key],undefined);
  const settings=await browser({path:'/settings/'});settings.ctx.rememberCollectionDestination();assert.equal(settings.storage[key],undefined);
  const shopping=explicit.ctx.collectionShoppingDestination({species:2,quantity:99},{goal_id:'saved',version:'a'.repeat(64)},'/pokedex/2/');
  const parsed=new URL(shopping,origin);assert.equal(parsed.searchParams.get('species'),'2');assert.equal(parsed.searchParams.get('quantity'),null);assert.equal(parsed.searchParams.get('generation'),'12');
  const group=explicit.ctx.collectionShoppingDestination({group:'dg1-'+'a'.repeat(64)},null,'/cards/');assert.equal(new URL(group,origin).searchParams.has('child'),false);
  const signed=await browser({path:'/cards/',memory:valid});signed.storage['dex-card-tab:'+actor+':/cards/']='/cards/?q=Ivy';signed.storage['dex-species-selection:'+actor]='[2]';signed.storage['dex-shopping-draft:'+binding]='private';signed.logout.submit();
  assert.equal(Object.keys(signed.storage).filter(k=>k.startsWith('dex-')).length,0);signed.ctx.rememberCollectionDestination();assert.equal(signed.storage[key],undefined);
  const back=await browser({path:'/shopping/',memory:valid});back.storage['dex-shopping-draft:'+binding]='permitted draft inputs';back.events.pageshow({persisted:true});assert.equal(back.events.reload,1);assert.equal(back.storage[key],JSON.stringify(valid));assert.equal(back.storage['dex-shopping-draft:'+binding],'permitted draft inputs');assert.deepEqual(back.main.children,[]);assert.ok(back.dialogs.every(dialog=>!dialog.open&&dialog.children.length===0));assert.ok(back.trace.indexOf('invalidate-shared')<back.trace.indexOf('reload'));assert.ok(back.trace.indexOf('main-clear')<back.trace.indexOf('reload'));assert.ok(back.trace.indexOf('dialog-clear:1')<back.trace.indexOf('reload'));back.events.pageshow({persisted:true});assert.equal(back.events.reload,1);
  const channels=[],tabOne=await browser({path:'/cards/',channels}),tabTwo=await browser({path:'/shopping/',channels}),otherSession=await browser({path:'/cards/',authority:'new-auth',channels});
  tabTwo.storage['dex-shopping-draft:'+binding]='private';tabTwo.ctx.rememberCollectionDestination();tabOne.logout.submit();assert.equal(tabTwo.replacements[0],'/login/?next=%2Fshopping%2F');assert.deepEqual(tabTwo.main.children,[]);assert.ok(tabTwo.dialogs.every(dialog=>!dialog.open&&dialog.children.length===0));assert.ok(tabTwo.trace.indexOf('invalidate-shared')<tabTwo.trace.indexOf('redirect'));assert.ok(tabTwo.trace.indexOf('invalidate-cards')<tabTwo.trace.indexOf('redirect'));assert.ok(tabTwo.trace.indexOf('invalidate-species')<tabTwo.trace.indexOf('redirect'));assert.ok(tabTwo.trace.indexOf('main-clear')<tabTwo.trace.indexOf('redirect'));assert.ok(tabTwo.trace.indexOf('dialog-clear:1')<tabTwo.trace.indexOf('redirect'));assert.equal(tabTwo.ctx.navigationAuthorityDiscarded,true);assert.equal(tabTwo.storage['dex-shopping-draft:'+binding],undefined);assert.equal(otherSession.replacements.length,0);assert.equal(otherSession.main.children.length,1);assert.equal(otherSession.dialogs[0].open,true);
  console.log('CX-07 browser adapter: storage fallback, finite destinations, deep links, account/auth boundaries, logout and non-mutating link contracts passed.');
})().catch(error=>{console.error(error);process.exitCode=1;});
