/* Engineering-only timing. No product state is kept by this probe. */
(() => {
  const absolute=()=>performance.timeOrigin+performance.now();
  const selector=()=>location.pathname==='/shopping/check/'?'#listing-preview:not([hidden]) #use-listing:not(:disabled)':'#discovery-cards .review-offer';
  const old=Response.prototype.json;
  const arrival=sessionStorage.getItem('shop-navigation-selector');sessionStorage.removeItem('shop-navigation-selector');
  window.shopProbe={selector:arrival,parses:[],ready:null,previous_server_intervals:JSON.parse(sessionStorage.getItem('shop12-prior-spans')||'[]')};
  addEventListener('pagehide',()=>{
    const action=Number(sessionStorage.getItem('shop12-clock'));
    const intervals=performance.getEntriesByType('resource').filter(r=>performance.timeOrigin+r.responseEnd>=action).flatMap(r=>r.serverTiming.filter(t=>t.name==='application').map(t=>[Math.max(action,performance.timeOrigin+r.responseStart-t.duration),performance.timeOrigin+r.responseStart]));
    sessionStorage.setItem('shop12-prior-spans',JSON.stringify(intervals));
  });
  Response.prototype.json=async function(){const start=performance.now();const value=await old.call(this);window.shopProbe.parses.push({url:this.url,start,end:performance.now()});return value;};
  window.shopMark=(kind,css,destination)=>{if(destination)sessionStorage.setItem('shop-navigation-selector',destination);window.shopProbe.previous_server_intervals=[];sessionStorage.removeItem('shop12-prior-spans');sessionStorage.setItem('shop12-clock',String(absolute()));window.shopProbe.ready=null;window.shopProbe.kind=kind;window.shopProbe.selector=css||'#shop12-navigation-pending';document.documentElement.removeAttribute('data-shop-ready');performance.clearResourceTimings();};
  let queued=false;
  function ready(){
    if(window.shopProbe.ready!==null||queued)return;
    const target=document.querySelector(window.shopProbe.selector||selector());
    if(!target||target.getClientRects().length===0||target.disabled)return;
    queued=true;
    requestAnimationFrame(()=>requestAnimationFrame(()=>{queued=false;
      if(window.shopProbe.ready!==null)return;
      window.shopProbe.ready=performance.now();
      const mark=Number(sessionStorage.getItem('shop12-clock'));
      window.shopProbe.action=mark||performance.timeOrigin;window.shopProbe.elapsed=absolute()-window.shopProbe.action;
      document.documentElement.dataset.shopReady='true';
    }));
  }
  new MutationObserver(ready).observe(document,{childList:true,subtree:true,attributes:true});
  addEventListener('DOMContentLoaded',ready);
})();
