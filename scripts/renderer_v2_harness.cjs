'use strict';
const {JSDOM}=require('jsdom'),vm=require('node:vm'),fs=require('node:fs'),path=require('node:path');
const helper=fs.readFileSync(path.join(__dirname,'../src/pokemon_hunter/beta/static/bounded-reads.js'),'utf8');
const settle=()=>new Promise(resolve=>setImmediate(resolve));
module.exports=function setup(route,responder,source,{storage=new Map(),preferences=new Map(),species=false}={}){
 const dom=new JSDOM('<body><header class="app-header"><a data-navigation-section="cards" href="/cards/"></a><a data-navigation-tab="/card-library/" href="/card-library/"></a></header><main id="content"></main><dialog id="editor"><div id="editor-body"></div></dialog></body>',{url:'http://localhost'+route});
 const document=dom.window.document;document.body.dataset.parity='true';
 const originalAdd=dom.window.EventTarget.prototype.addEventListener;
 dom.window.EventTarget.prototype.addEventListener=function(name,handler,...args){this.listeners??={};this.listeners[name]=handler;return originalAdd.call(this,name,handler,...args);};
 const events={},calls=[],resources=new Map(),created=[];
 const create=document.createElement.bind(document);document.createElement=(...args)=>{const el=create(...args);created.push(el);return el;};
 const location={origin:'http://localhost',href:'http://localhost'+route,pathname:route.split('?')[0],search:route.includes('?')?'?'+route.split('?').slice(1).join('?'):'',assign(url){context.assigned=url;this.assigned=url;},replace(url){context.replaced=url;},reload(){}};
 const decorate=body=>({read_version:2,public:false,catalog_revision:'catalog-a',account_revision:'revision-a',page:1,pages:1,page_size:40,...body});
 const context={window:{},document,location,URL,URLSearchParams,AbortController,DOMException,Option:dom.window.Option,Event:dom.window.Event,FormData:dom.window.FormData,crypto:global.crypto,setTimeout,clearTimeout,scrollY:species?80:0,scrollTo(x,y){context.restoredScroll=y;context.restored=y;},requestAnimationFrame(fn){fn();},addEventListener(name,fn){const old=events[name];events[name]=()=>{old?.();fn();};},sessionStorage:{getItem:k=>storage.get(k)??null,setItem:(k,v)=>storage.set(k,String(v)),removeItem:k=>storage.delete(k)},localStorage:{getItem:k=>preferences.get(k)??null,setItem:(k,v)=>preferences.set(k,String(v))},history:{replaceState(state,title,url){const u=new URL(url,location.origin);location.pathname=u.pathname;location.search=u.search;location.href=u.href;}},data:{read_state:{account_id:'account-a',generation:5,catalog_revision:'catalog-a',account_revision:'revision-a'},effective_collection:{user_id:'account-a',generation:5},binders:[],goals:[]},$:s=>document.querySelector(s),esc:v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])),cardImage:()=>'<span class="image-frame"></span>',speciesImage:()=>'<span class="species-artwork image-frame compact unavailable"></span>',photoLink:()=>'',dexImport(){},dexJsonImport(){},dexGoal(){}};
 context.window.renderCardGroupTile=(g,back)=>'<a class="owned-card-tile" data-group-id="'+g.id+'" href="/card-groups/'+g.id+'/?return='+encodeURIComponent(back)+'">'+g.name+'</a>';
 context.api=async url=>{calls.push(url);return responder(url);};
 context.fetch=async url=>{
  calls.push(url);const u=new URL(url,location.origin);let body;
  if(resources.has(u.pathname))body=resources.get(u.pathname);
  else {
   body=await responder(url);body={...body};
   if(u.pathname==='/api/v2/labels/'){
    const options=await responder('/api/v2/card-group-filters/?field=set');
    body={...options,labels:JSON.parse(u.searchParams.get('items')).map(i=>{const found=(options[i.kind==='set'?'sets':i.kind+'s']||[]).find(v=>(typeof v==='string'?v:v.id)===i.id);return {...i,label:typeof found==='string'?found:found?.name,available:!!found};})};
   }
   if(body.group){for(const field of ['variants','copies','history','unresolved']){const rows=body[field]||[];if(!Array.isArray(rows))continue;const resource='/api/v2/card-groups/'+body.group.id+'/'+(field==='unresolved'?'evidence':field)+'/';resources.set(resource,{...body,[field==='unresolved'?'evidence':field]:rows,total:rows.length});body[field]={total:rows.length,url:resource};}body.group={...body.group,recorded_copy_count:body.copies.total};}
   else if(body.groups&&Array.isArray(body.unresolved)){const resource='/api/v2/evidence/';const rows=body.unresolved;resources.set(resource,{...body,evidence:rows,total:rows.length});body.unresolved={total:rows.length,url:resource};}
   if(u.pathname.endsWith('/card-group-filters/')){const f=u.searchParams.get('field')||'set';const values=body[f==='set'?'sets':f+'s']||[];body.options=values.map(v=>typeof v==='string'?{value:v,label:v}:{value:v.id,label:v.name});body.total=body.options.length;body.next=null;}
   if(body.owned){body={...body,...body.owned,scope_groups:body.scope_groups||{},total:body.owned.groups.length};}
   if(body.species){const query=u.searchParams.get('q');let rows=body.species;if(/^#\d+$/.test(query||''))rows=rows.filter(r=>r.dex===Number(query.slice(1)));const page=Number(u.searchParams.get('page')||1),size=Number(u.searchParams.get('page_size')||40);body={...body,total:rows.length,page,page_size:size,pages:Math.ceil(rows.length/size),species:rows.slice((page-1)*size,page*size)};}
  }
  return {ok:true,status:200,redirected:false,json:async()=>decorate(body)};
 };
 vm.createContext(context);vm.runInContext(helper,context);context.BoundedReads=context.window.BoundedReads;vm.runInContext(source,context);
 const render=async()=>{await (species?context.window.renderSpeciesScreen:context.window.renderCardScreens)(location.pathname);await settle();};
 const expand=async kind=>{const el=document.querySelector('#group-'+kind)||[...document.querySelectorAll('details')].find(d=>d.querySelector('summary')?.textContent.toLowerCase().includes(kind.toLowerCase()));if(!el)throw Error('Missing disclosure '+kind);el.open=true;await el.ontoggle?.();await settle();const button=[...el.querySelectorAll('button')].find(b=>b.textContent==='Load records');if(button)await button.onclick();await settle();};
 return {context,content:document.querySelector('#content'),calls,storage,preferences,events,created,headerLinks:[...document.querySelectorAll('.app-header a')],node:s=>document.querySelector(s),render,expand,settle};
};
