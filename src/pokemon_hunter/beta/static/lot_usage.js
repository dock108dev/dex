/* Contextual owner controls. Reads and saves never start provider work. */
(() => {
  const $=id=>document.getElementById(id), host=$('hunter-usage');if(!host)return;
  const page=document.body,binding=page.dataset.navigationBinding,account=page.dataset.navigationAccount;
  const api='/api/shopping/hunter/';let active=true,usagePolicy=null,usageBusy=false;
  const usageOwner=true,authority=()=>active && !window.navigationAuthorityDiscarded && page===document.body && page.dataset.navigationBinding===binding;
  const h=(tag,text,attrs)=>{const n=document.createElement(tag);n.textContent=text;Object.assign(n,attrs);return n;};
  window.addEventListener('dex:authority-revoked',()=>{active=false;host.replaceChildren();usagePolicy=null;});
  async function request(url,data){
    const response=await fetch(url,{credentials:'same-origin',cache:'no-store',headers:{'X-Dex-Shopping-Binding':binding,...(data===undefined?{}:{'Content-Type':'application/json','X-CSRFToken':document.querySelector('[name=csrfmiddlewaretoken]').value})},...(data===undefined?{}:{method:'POST',body:JSON.stringify(data)})});
    if(!response.ok)throw Error('Allowance could not be confirmed. Refresh to check current settings.');
    const value=await response.json();if(!authority() || String(value.authority?.account_id)!==String(account) || value.authority?.binding!==binding)throw Error('Session changed. Reload the page.');return value;
  }
  function usageDate(value, timezone) {
    const date = new Date(value);
    if (!value || !Number.isFinite(date.getTime())) return 'Unavailable';
    try { return date.toLocaleString(undefined, {timeZone: timezone || undefined, timeZoneName: 'short'}); }
    catch { return date.toLocaleString(); }
  }
  function expiryMode() {
    if (!usageOwner) return;
    const required = $('hunter-usage-expiry-mode').value === 'at';
    $('hunter-usage-expiry-label').hidden = !required;
    $('hunter-usage-expiry').required = required;
  }
  function renderUsage(value, fill = false) {
    if (!usageOwner || !authority()) return;
    
    usagePolicy = value || {configured: false, enabled: false};
    const p = usagePolicy;
    const hasSettings = p.configured && Number.isInteger(p.per_hunt_limit) && Number.isInteger(p.daily_limit) && typeof p.timezone === 'string';
    const timezoneControl = $('hunter-usage-timezone');
    if (hasSettings && ![...timezoneControl.querySelectorAll('option')].some(option => option.value === p.timezone)) timezoneControl.append(h('option', 'Current timezone (' + p.timezone.replaceAll('_', ' ') + ')', {value: p.timezone}));
    const timezoneLabel = hasSettings ? [...timezoneControl.querySelectorAll('option')].find(option => option.value === p.timezone)?.textContent || p.timezone : '';
    $('hunter-usage-status').textContent = p.reason || (!p.configured ? 'Acquisition is disabled. Choose your usage settings to enable it.' : !p.enabled ? 'Acquisition is paused.' : p.remaining > 0 ? 'Acquisition is enabled within your selected limits.' : 'Your daily capacity is exhausted.');
    $('hunter-usage-capacity').textContent = hasSettings ? `${p.remaining ?? 0} of ${p.daily_limit} daily operations remaining · ${p.used ?? 0} consumed · up to ${p.per_hunt_limit} per Hunt.` : p.configured ? 'Capacity cannot be read safely. Acquisition remains disabled; existing local Shopping tools remain available.' : 'Select limits below. Saving settings does not start a search.';
    if ($('hunter-usage-window')) $('hunter-usage-window').textContent = hasSettings ? `${p.recurring ? 'Next daily window: ' + usageDate(p.next_window_at, p.timezone) + '.' : 'This window only; a new day does not renew capacity.'} Timezone: ${timezoneLabel}.${p.expires_at ? ' Policy expires ' + usageDate(p.expires_at, p.timezone) + '.' : ''}` : '';
    $('hunter-usage-status').hidden = hasSettings && p.enabled && p.remaining > 0;
    if (!p.configured) $('hunter-usage-settings').open = true;
    if (fill) {
      $('hunter-usage-enabled').value = hasSettings ? String(p.enabled) : '';
      $('hunter-usage-per-hunt').value = hasSettings ? String(p.per_hunt_limit) : '';
      $('hunter-usage-daily').value = hasSettings ? String(p.daily_limit) : '';
      $('hunter-usage-timezone').value = hasSettings ? p.timezone : '';
      $('hunter-usage-recurring').value = hasSettings ? String(p.recurring) : '';
      $('hunter-usage-expiry-mode').value = hasSettings ? p.expires_at ? 'at' : 'none' : '';
      const expiry = p.expires_at ? new Date(p.expires_at) : null;
      $('hunter-usage-expiry').value = expiry && Number.isFinite(expiry.getTime()) ? new Date(expiry.getTime() - expiry.getTimezoneOffset() * 60000).toISOString().slice(0, 16) : '';
      expiryMode();
    }
    buttons();
  }
  function selectedUsage() {
    const boolean = id => { const value = $(id).value; if (!['true', 'false'].includes(value)) throw new Error('Choose enabled or paused and whether capacity repeats each day.'); return value === 'true'; };
    const integer = (id, max) => { const value = $(id).value; if (!/^[1-9][0-9]*$/.test(value) || Number(value) > max) throw new Error('Choose whole-number limits: 1–15 per Hunt and 1–1,000 per day.'); return Number(value); };
    const timezone = $('hunter-usage-timezone').value.trim();
    if (!timezone) throw new Error('Choose the timezone for your daily windows.');
    const mode = $('hunter-usage-expiry-mode').value;
    if (!['none', 'at'].includes(mode)) throw new Error('Choose until paused or a specific expiry.');
    const expiry = mode === 'at' ? new Date($('hunter-usage-expiry').value) : null;
    if (expiry && (!Number.isFinite(expiry.getTime()) || expiry.getTime() <= Date.now())) throw new Error('Choose a future expiry in your browser’s local time.');
    return {enabled: boolean('hunter-usage-enabled'), per_hunt_limit: integer('hunter-usage-per-hunt', 15), daily_limit: integer('hunter-usage-daily', 1000), timezone, recurring: boolean('hunter-usage-recurring'), expires_at: expiry ? expiry.toISOString() : null, revision: usagePolicy?.revision || 0};
  }
  async function saveUsage(pause = false) {
    if (!usageOwner || usageBusy || !authority()) return;
    const feedback = $('hunter-usage-feedback');
    try {
      const fields = pause ? {enabled: false, per_hunt_limit: usagePolicy.per_hunt_limit, daily_limit: usagePolicy.daily_limit, timezone: usagePolicy.timezone, recurring: usagePolicy.recurring, expires_at: usagePolicy.expires_at || null, revision: usagePolicy.revision} : selectedUsage();
      usageBusy = true; feedback.textContent = 'Saving your selected usage settings…'; feedback.dataset.error = 'false'; buttons();
      const value = await request(api + 'usage/', fields);
      if (!authority()) return;
      renderUsage(value, true); feedback.textContent = pause ? 'Acquisition paused. Already attempted operations remain consumed; local review and Stop remain available.' : 'Usage settings saved. Hunt is a separate explicit action; no marketplace search has run.';
      
    } catch (error) { if (authority()) { feedback.textContent = error.message + ' Settings were not changed unless confirmed above. Check availability before trying again.'; feedback.dataset.error = 'true'; } }
    finally { usageBusy = false; buttons(); }
  }
  function buttons(){
    $('hunter-usage-save').disabled=!authority() || usageBusy;
    $('hunter-usage-pause').disabled=!authority() || usageBusy || !usagePolicy?.configured || !usagePolicy?.enabled;
    $('lot-usage-refresh').disabled=!authority() || usageBusy;
  }
  async function refresh(){if(!authority() || usageBusy)return;usageBusy=true;buttons();try{renderUsage(await request(api+'usage/'),true);}catch(e){$('hunter-usage-feedback').textContent=e.message;}finally{usageBusy=false;buttons();}}
  $('hunter-usage-form').onsubmit=e=>{e.preventDefault();saveUsage();};
  $('hunter-usage-pause').onclick=()=>saveUsage(true);
  $('hunter-usage-expiry-mode').onchange=expiryMode;
  $('lot-usage-refresh').onclick=refresh;
  refresh();
})();
