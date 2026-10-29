"""Browser-local readiness clocks and network isolation for engineering measurements."""

import json
import re

# The clock starts at the browser navigation origin and ends after the same visible
# primary selector has had two animation-frame opportunities. Driver polling and
# acknowledgement happen afterward and cannot change the recorded timestamp.
NAVIGATION_CLOCK = r"""(() => {
 const selectors=SELECTORS;
 const selector=selectors[location.pathname];
 window.dexNavigation={ready_ms:null,visible_ms:null,visibility:document.visibilityState};
 if(!selector)return;
 const visible=()=>{const e=document.querySelector(selector),r=e&&e.getBoundingClientRect();return r&&r.width>0&&r.height>0&&getComputedStyle(e).visibility==='visible';};
 let scheduled=false;
 const observer=new MutationObserver(check);
 function check(){
  if(scheduled||dexNavigation.ready_ms!==null||!visible())return;
  scheduled=true;dexNavigation.visible_ms=performance.now();
  requestAnimationFrame(()=>requestAnimationFrame(()=>{
   if(!visible()){scheduled=false;check();return;}
   dexNavigation.ready_ms=performance.now();observer.disconnect();document.documentElement.dataset.dexNavigationReady='true';
  }));
 }
 observer.observe(document,{childList:true,subtree:true,attributes:true});
 addEventListener('DOMContentLoaded',check);check();
})();"""


def navigation_clock(context, selectors):
    context.add_init_script(script=NAVIGATION_CLOCK.replace("SELECTORS", json.dumps(selectors)))


def isolated_network(page, base):
    """Abort external requests; local traffic never waits for a Python route callback."""
    cdp = page.context.new_cdp_session(page)
    cdp.send("Network.enable")
    cdp.send("Network.setCacheDisabled", {"cacheDisabled": True})
    blocked = []

    def deny(route):
        blocked.append(route.request.url)
        route.abort()

    page.route(re.compile(r"^(?!" + re.escape(base) + r"(?:/|$))"), deny)
    return blocked


def navigation_sample(page):
    page.locator("html[data-dex-navigation-ready]").wait_for(state="attached", timeout=5000)
    return page.evaluate("({...dexNavigation})")
