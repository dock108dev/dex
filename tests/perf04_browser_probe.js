/* Engineering-only timestamps: no application data is retained. */
(() => {
 const absolute=()=>performance.timeOrigin+performance.now();
 window.probe={parses:[],ready:null};
 const original=Response.prototype.json;
 Response.prototype.json=async function(){const start=performance.now(),value=await original.call(this);window.probe.parses.push({path:new URL(this.url||location.href).pathname,start,end:performance.now()});return value;};
 for(const kind of ['submit','click'])addEventListener(kind,e=>{
  if(kind==='submit'||e.target.closest('a[rel],nav[aria-label="Result pages"] a'))sessionStorage.setItem('perf04-action',String(absolute()));
 },true);
 const observer=new MutationObserver(()=>{
  if(window.probe.ready!==null)return;
  if(document.querySelector('#card-group-list,#browse-results nav'))requestAnimationFrame(()=>{
   if(window.probe.ready!==null)return;
   window.probe.ready=performance.now();document.documentElement.dataset.perfReady="true";window.probe.action=Number(sessionStorage.getItem('perf04-action'))||performance.timeOrigin;
  });
 });
 observer.observe(document,{subtree:true,childList:true});
})();
