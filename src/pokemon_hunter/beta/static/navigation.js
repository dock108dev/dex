'use strict';
/* Read-only home memory and explicit Shopping links. Stored UI state is never authority. */
(() => {
  const root=document.body, actor=root.dataset.navigationAccount||'', binding=root.dataset.navigationBinding||'';
  const key='dex-navigation-home:'+location.origin+':'+binding;
  let successful=false, discarded=false;
  let authChannel=null;
  try{if(actor&&binding&&typeof BroadcastChannel==='function')authChannel=new BroadcastChannel('dex-auth-lifecycle');}catch{/* Optional cross-tab notification. Server checks still authorize every request. */}
  function clearPrivateView(){window.invalidateCollectionRequests?.();window.invalidateCardScreens?.();window.invalidateSpeciesScreens?.();document.querySelector('main')?.replaceChildren();document.querySelectorAll('dialog').forEach(dialog=>{if(dialog.open)dialog.close();dialog.replaceChildren();});}
  function safeDestination(value,depth=0) {
    if(typeof value!=='string'||!value.startsWith('/')||value.startsWith('//')||value.length>4096||value!==value.trim()||/[\x00-\x1f\x7f]/.test(value)||depth>2)return null;
    try {
      const url=new URL(value,location.origin), group=/^\/card-groups\/dg1-[0-9a-f]{64}\/$/.test(url.pathname), species=/^\/pokedex\/([1-9][0-9]{0,2})\/$/.exec(url.pathname);
      if(url.origin!==location.origin||url.hash||!['/cards/','/card-library/','/pokedex/'].includes(url.pathname)&&!group&&!species||species&&Number(species[1])>251)return null;
      if(window.safeSpeciesReturn&&url.pathname.startsWith('/pokedex/'))return window.safeSpeciesReturn(value);
      if([...url.searchParams].some(([field,value])=>url.searchParams.getAll(field).length!==1||/[\x00-\x1f\x7f]/.test(field+value)||value.length>(field==='return'?4096:160)))return null;
      if(group){
        if([...url.searchParams.keys()].some(field=>!['child','generation','return'].includes(field)))return null;
        if(url.searchParams.has('return')){const nested=safeDestination(url.searchParams.get('return'),depth+1);if(!nested||nested.startsWith('/card-groups/'))return null;}
      }else if(window.safeSpeciesReturn&&url.pathname.startsWith('/pokedex/'))return window.safeSpeciesReturn(value);
      else if(window.safeCardReturn&&['/cards/','/card-library/'].includes(url.pathname))return window.safeCardReturn(value);
      return url.pathname+url.search;
    }catch{return null;}
  }
  window.discardNavigationAuthority=(announce=true)=>{
    if(discarded)return;
    discarded=true;successful=false;window.navigationAuthorityDiscarded=true;window.invalidateCollectionRequests?.();
    try{for(const name of Object.keys(sessionStorage))if(/^dex-(navigation-home:|card-|species-|shopping-)/.test(name))sessionStorage.removeItem(name);}catch{/* Optional storage. */}
    window.dispatchEvent(new Event('dex:authority-revoked'));
    if(announce!==false)try{authChannel?.postMessage({kind:'revoked',binding});}catch{/* Optional cross-tab notification. */}
  };
  if(authChannel)authChannel.onmessage=event=>{
    if(event.data?.kind!=='revoked'||event.data?.binding!==binding||discarded)return;
    window.discardNavigationAuthority(false);clearPrivateView();location.replace('/login/?next='+encodeURIComponent(location.pathname+location.search));
  };
  addEventListener('pageshow',event=>{
    if(!event.persisted||!actor||!binding||window.navigationReauthorizing)return;
    window.navigationReauthorizing=true;clearPrivateView();location.reload();
  });
  document.querySelectorAll('form[action="/logout/"]').forEach(form=>form.addEventListener('submit',window.discardNavigationAuthority));
  function section() {
    const path=location.pathname;
    if(path.startsWith('/pokedex/'))return 'pokedex';
    if(path.startsWith('/shopping/')||path.startsWith('/packs/')||path==='/lookup/'||['/hunt/','/missing/','/finds/'].includes(path))return 'shopping';
    if(path.startsWith('/card-groups/')){
      const back=safeDestination(new URLSearchParams(location.search).get('return'));
      return back?.startsWith('/pokedex/')?'pokedex':back?.startsWith('/card-library/')?'library':'cards';
    }
    return path==='/card-library/'?'library':['/cards/','/collection-tools/','/collection/','/goals/','/overview/'].includes(path)?'cards':'';
  }
  window.updateCollectionNavigation=()=>{
    const current=section();
    document.querySelectorAll('.app-header [data-navigation-section]').forEach(link=>{
      link.removeAttribute('aria-current');if(link.dataset.navigationSection===current)link.setAttribute('aria-current','page');
    });
    const libraryLink=document.querySelector('.app-header [data-navigation-tab="/card-library/"]');
    if(current==='library')libraryLink?.setAttribute('aria-current','page');else libraryLink?.removeAttribute('aria-current');
    for(const path of ['/cards/','/card-library/']){
      let saved;
      try{saved=safeDestination(sessionStorage.getItem('dex-card-tab:'+actor+':'+path));}catch{/* Optional storage. */}
      if(saved&&new URL(saved,location.origin).pathname===path){
        const selector=path==='/cards/'?'[data-navigation-section="cards"]':'[data-navigation-tab="/card-library/"]';
        document.querySelector('.app-header '+selector)?.setAttribute('href',saved);
      }
    }
    try{
      const saved=safeDestination(sessionStorage.getItem(key+':tab:pokedex'));
      if(saved&&new URL(saved,location.origin).pathname==='/pokedex/')document.querySelector('.app-header [data-navigation-section="pokedex"]')?.setAttribute('href',saved);
    }catch{/* Optional storage. */}
  };
  function remember() {
    if(discarded||window.navigationReauthorizing||!actor||!binding||typeof data==='undefined'||data?.effective_collection?.user_id!==actor)return;
    let url=new URL(location.href);
    if(['/cards/','/card-library/','/pokedex/'].includes(url.pathname)||/^\/pokedex\/[0-9]+\/$/.test(url.pathname))url.searchParams.set('scroll',String(Math.min(10000000,Math.max(0,Math.round(scrollY)))));
    const destination=safeDestination(url.pathname+url.search);if(!destination)return;
    try{
      sessionStorage.setItem(key,JSON.stringify({v:1,account:actor,binding,destination}));
      let dex=destination;
      for(let depth=0;depth<3&&dex;depth++){
        const current=new URL(dex,location.origin);
        if(current.pathname==='/pokedex/'){sessionStorage.setItem(key+':tab:pokedex',dex);break;}
        dex=safeDestination(current.searchParams.get('return'));
      }
    }catch{/* Missing storage falls back to My Cards. */}
    successful=true;window.updateCollectionNavigation();
  }
  window.rememberCollectionDestination=remember;
  addEventListener('pagehide',()=>{if(successful)remember();});
  window.collectionShoppingDestination=(identity,scope,returnTo)=>{
    const params=new URLSearchParams();
    if(identity.species)params.set('species',String(identity.species));
    else if(identity.group){params.set('group',identity.group);if(identity.child)params.set('child',identity.child);}
    if(scope?.goal_id&&scope?.version){params.set('goal',scope.goal_id);params.set('version',scope.version);}
    if(typeof data!=='undefined'&&Number.isSafeInteger(data?.effective_collection?.generation))params.set('generation',data.effective_collection.generation);
    const safe=safeDestination(returnTo);if(safe)params.set('return',safe);
    return '/shopping/?'+params;
  };
  window.navigationReady=(async()=>{
    window.updateCollectionNavigation();
    if(location.pathname!=='/'||!actor||!binding)return;
    const active=()=>!discarded&&!window.navigationReauthorizing&&location.pathname==='/'&&document.body===root&&root.dataset.navigationAccount===actor&&root.dataset.navigationBinding===binding&&(typeof data==='undefined'||!data?.effective_collection||data.effective_collection.user_id===actor);
    let destination='/cards/';
    try{
      const saved=JSON.parse(sessionStorage.getItem(key)||'null');
      if(saved?.v===1&&saved.account===actor&&saved.binding===binding&&safeDestination(saved.destination)){
        const response=await fetch('/api/navigation/home/?'+new URLSearchParams({destination:saved.destination}),{credentials:'same-origin'});
        if(!active())return;
        if(response.redirected||response.status===403){window.discardNavigationAuthority();location.replace('/login/?next=%2Fcards%2F');return;}
        if(response.ok){const checked=await response.json();if(active()&&checked.account_id===actor&&checked.navigation_binding===binding)destination=safeDestination(checked.destination)||destination;}
      }
    }catch{/* Corrupt, inaccessible or unavailable storage uses the ordinary entry. */}
    if(active())location.replace(destination);
  })();
})();
