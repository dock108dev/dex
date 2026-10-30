'use strict';
/* Private, leased projections stay in memory. History contains opaque handles and UI context only. */
(() => {
  const $ = id => document.getElementById(id), page = document.body;
  if (!$('hunter-app')) return;
  const simple = $('hunter-app').dataset.simple === 'true';
  const api = '/api/shopping/hunter/', binding = page.dataset.navigationBinding || '', account = page.dataset.navigationAccount || '';
  const initial = JSON.parse($('hunter-initial')?.textContent || '{}');
  const generation = initial.authority?.generation;
  const usageOwner = initial.usage_settings?.owner === true && Boolean($('hunter-usage-form'));
  let usagePolicy = initial.usage_settings?.policy || null, usageBusy = false;
  let metadata = initial.metadata || {}, run = null, rows = [], epoch = 0, viewEpoch = -1, requestId = 0;
  let busy = false, revoked = false, stopped = false, reading = false, statusTimer = null, detailTimer = null;
  let deadline = Infinity, leaseTimer = null, wantedPages = 1, reviewId = null, inspectedId = null;
  let returnContext = null, detail = null, detailIntent = null, detailEpoch = 0, detailBusy = false;
  let lastRead = 0, view = 'results', navigationEpoch = 0, readOperation = null, retainedFocus = null, detailNavigation = -1;
  const revealed = new Set();
  const authority = () => !revoked && document.body === page && page.dataset.navigationBinding === binding && page.dataset.navigationAccount === account && !window.navigationAuthorityDiscarded && !window.navigationReauthorizing;
  const active = token => authority() && token === epoch && !stopped;
  const text = value => typeof value === 'string' || typeof value === 'number' ? String(value) : '';
  const pretty = value => text(value).replaceAll('_', ' ');
  function h(tag, value, attrs = {}) {
    const el = document.createElement(tag);
    if (value !== undefined && value !== null) el.textContent = String(value);
    for (const [key, val] of Object.entries(attrs)) if (val != null) el.setAttribute(key, String(val));
    return el;
  }
  function money(value) {
    const amount = value && typeof value === 'object' ? value.amount : value;
    if (amount == null || amount === '' || !Number.isFinite(Number(amount))) return 'Unknown';
    return new Intl.NumberFormat('en-US', {style: 'currency', currency: 'USD'}).format(Number(amount));
  }
  function message(value, error = false) {
    if (!authority()) return;
    $('hunter-status').textContent = value;
    $('hunter-status').dataset.error = String(error);
    if (usageOwner) $('hunter-usage-status').hidden = Boolean(usagePolicy?.enabled && usagePolicy?.remaining > 0) || simple && !usagePolicy?.configured || value === $('hunter-usage-status').textContent;
  }
  async function request(url, body) {
    if (!authority()) throw new Error('Your session changed. Reload Shopping to continue.');
    const controller = new AbortController(), timeout = setTimeout(() => controller.abort(), 85000);
    let response;
    try {
      response = await fetch(url, {method: body === undefined ? 'GET' : 'POST', credentials: 'same-origin', redirect: 'error', cache: 'no-store', signal: controller.signal,
        headers: {'X-Dex-Shopping-Binding': binding, ...(generation == null ? {} : {'X-Dex-Shopping-Generation': String(generation)}), ...(body === undefined ? {} : {'Content-Type': 'application/json', 'X-CSRFToken': $('hunter-form').querySelector('[name=csrfmiddlewaretoken]')?.value || ''})},
        ...(body === undefined ? {} : {body: JSON.stringify(body)})});
    } finally { clearTimeout(timeout); }
    if ([401, 403].includes(response.status)) {
      invalidate(); window.discardNavigationAuthority?.();
      const error = new Error('Your session is unavailable. Sign in again to continue.'); error.status = response.status; throw error;
    }
    let value;
    try { value = await response.json(); } catch {
      const error = new Error(response.status === 404 ? 'This temporary Hunter content is unavailable. It may have expired or been cleared.' : 'Price Hunter returned an unreadable response. Check availability to continue.');
      error.status = response.status; throw error;
    }
    if (!response.ok) { const error = new Error(typeof value.error === 'string' ? value.error : 'This action is unavailable. Check the current Hunt.'); error.status = response.status; error.code = value.code; throw error; }
    if (!authority() || !account || !binding || value.authority?.account_id !== account || value.authority?.binding !== binding || generation != null && value.authority?.generation !== generation) {
      invalidate(); throw new Error('Your session or catalog changed. Reload Shopping to continue.');
    }
    return value;
  }
  function image(descriptor, title, guard = () => true) {
    const box = h('span', null, {class: 'hunter-image'}), fallback = h('span', 'Card reference unavailable');
    box.append(fallback);
    let url;
    try {
      url = new URL(descriptor?.image_url || '', location.origin);
      if (!descriptor?.image_url || url.username || url.password || url.port || url.protocol !== 'https:' || !['assets.tcgdex.net', 'raw.githubusercontent.com'].includes(url.hostname)) return box;
    } catch { return box; }
    const img = h('img', null, {alt: descriptor.alt || title || 'Catalog card reference', loading: 'lazy', decoding: 'async', referrerpolicy: 'no-referrer'});
    img.addEventListener('load', () => { if (guard() && box.isConnected) fallback.hidden = true; else img.remove(); });
    img.addEventListener('error', () => { img.remove(); if (guard()) fallback.hidden = false; });
    img.src = url.href; box.append(img); return box;
  }
  function sellerLink(value) {
    try {
      const url = new URL(value);
      if (url.protocol !== 'https:' || url.username || url.password || url.port || !/(^|\.)ebay\.com$/i.test(url.hostname)) return null;
      return h('a', 'Open seller listing on eBay', {href: url.href, target: '_blank', rel: 'noopener noreferrer'});
    } catch { return null; }
  }
  const review = window.DexHunterReview.mount({container: $('hunter-review'), request, current: () => active(viewEpoch), image, message, onBack: () => backToResults(), onDetailStart: prepareDetails});
  function ready() {
    const left = metadata.traversal_remaining || {};
    if (usageOwner && (!usagePolicy?.configured || !usagePolicy.enabled || !(usagePolicy.remaining > 0))) return false;
    return metadata.acquisition_available === true || metadata.acquisition_available == null && metadata.traversal_allowance_enabled && left.browse > 0 && left.total > 0;
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
    const wasConfigured=usagePolicy?.configured;
    usagePolicy = value || {configured: false, enabled: false};
    const p = usagePolicy;
    const hasSettings = p.configured && Number.isInteger(p.per_hunt_limit) && Number.isInteger(p.daily_limit) && typeof p.timezone === 'string';
    const timezoneControl = $('hunter-usage-timezone');
    if (hasSettings && ![...timezoneControl.querySelectorAll('option')].some(option => option.value === p.timezone)) timezoneControl.append(h('option', 'Current timezone (' + p.timezone.replaceAll('_', ' ') + ')', {value: p.timezone}));
    const timezoneLabel = hasSettings ? [...timezoneControl.querySelectorAll('option')].find(option => option.value === p.timezone)?.textContent || p.timezone : '';
    $('hunter-usage-status').textContent = p.reason || (!p.configured ? 'Acquisition is disabled. Choose your usage settings to enable it.' : !p.enabled ? 'Acquisition is paused.' : p.remaining > 0 ? 'Acquisition is enabled within your selected limits.' : 'Your daily capacity is exhausted.');
    $('hunter-usage-capacity').textContent = hasSettings ? `${p.remaining ?? 0} of ${p.daily_limit} daily operations remaining · ${p.used ?? 0} consumed · up to ${p.per_hunt_limit} per Hunt.` : p.configured ? 'Capacity cannot be read safely. Acquisition remains disabled; existing local Shopping tools remain available.' : simple ? '' : 'Select limits below. Saving settings does not start a search.';
    if ($('hunter-usage-window')) $('hunter-usage-window').textContent = hasSettings ? `${p.recurring ? 'Next daily window: ' + usageDate(p.next_window_at, p.timezone) + '.' : 'This window only; a new day does not renew capacity.'} Timezone: ${timezoneLabel}.${p.expires_at ? ' Policy expires ' + usageDate(p.expires_at, p.timezone) + '.' : ''}` : '';
    $('hunter-usage-status').hidden = hasSettings && p.enabled && p.remaining > 0;
    if (!p.configured) $('hunter-usage-settings').open = true;
    if (simple) {
      $('hunter-usage').hidden=Boolean(p.configured && p.enabled && p.remaining>0);
      $('hunter-usage-settings').hidden=!p.configured;
      if (!wasConfigured && p.configured) $('hunter-usage-settings').open=false;
      $('hunter-poc-enable').hidden=Boolean(p.configured);
    }
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
      await availability();
    } catch (error) { if (authority()) { feedback.textContent = error.message + ' Settings were not changed unless confirmed above. Check availability before trying again.'; feedback.dataset.error = 'true'; } }
    finally { usageBusy = false; buttons(); }
  }
  function buttons() {
    $('hunter-start').disabled = !authority() || !ready() || busy || reading || usageBusy || Boolean(run?.running);
    if (simple) { $('hunter-scope').value='singles'; $('hunter-stop').hidden=!busy&&!run?.running; $('hunter-recheck').hidden=ready(); }
    $('hunter-scope').disabled = busy || Boolean(run?.running);
    $('hunter-stop').disabled = !authority() || stopped || !busy && !run;
    $('hunter-recheck').disabled = !authority() || busy;
    $('hunter-local-next').hidden = !run?.result_cursor || view !== 'results';
    $('hunter-local-next').disabled = busy || reading;
    $('hunter-continue').hidden = !run?.has_next || view !== 'results';
    $('hunter-continue').disabled = busy || reading || usageBusy || usageOwner && !ready() || run?.running || Boolean(run?.continuation_blocked_reason) || !run?.continuation_cursor || $('hunter-scope').value !== (run?.plan?.scope || 'singles');
    if (usageOwner) {
      $('hunter-usage-save').disabled = !authority() || usageBusy;
      $('hunter-usage-pause').disabled = !authority() || usageBusy || !usagePolicy?.configured || !usagePolicy.enabled;
      if (!ready() || usageBusy) $('hunter-detail-load').disabled = true;
    }
    $('hunter-next-note').textContent = run?.has_next ? $('hunter-scope').value !== (run?.plan?.scope || 'singles') ? 'Scope changed. Start a new Hunt to use it.' : run.continuation_blocked_reason ? 'Acquisition cannot continue: ' + pretty(run.continuation_blocked_reason) + '.' : 'Continue acquisition makes an explicit request within this Hunt’s captured plan. Showing received results uses no provider requests.' : run ? 'Partial marketplace coverage · received results only.' : '';
  }
  function remember(push = false) {
    if (!authority()) return;
    const state = {hunter: 1, account, binding, generation, run: run?.run_id || null, view, review: reviewId, inspect: inspectedId, scope: $('hunter-scope').value, filter: $('hunter-filter').value, pages: wantedPages, returnContext};
    history[push ? 'pushState' : 'replaceState'](state, '', location.pathname);
  }
  function clearContent(reason) {
    ++epoch; ++requestId; ++detailEpoch; ++navigationEpoch; viewEpoch = -1; reading = false; busy = false; readOperation = null;
    clearTimeout(statusTimer); clearTimeout(detailTimer); clearInterval(leaseTimer); leaseTimer = null;
    rows = []; run = null; deadline = Infinity; detail = null; detailIntent = null; detailBusy = false;
    reviewId = null; inspectedId = null; view = 'results'; review.clear(reason);
    $('hunter-cards').replaceChildren(); $('hunter-results').hidden = true; $('hunter-review').hidden = true;
    $('hunter-details').hidden = true; $('hunter-progress').hidden = true;
    revealed.clear(); retainedFocus = null; $('hunter-detail-open')?.remove(); buttons();
  }
  function invalidate() {
    if (revoked) return;
    clearContent('Your session changed.'); revoked = true;
    $('hunter-status').textContent = 'Your session changed. Reload Shopping and sign in to continue.';
    if (usageOwner) { $('hunter-usage-status').textContent = 'Your session changed. Reload Shopping to check your usage settings.'; $('hunter-usage-capacity').textContent = ''; }
    buttons();
  }
  function bindLease(value) {
    if (!run || !Number.isFinite(Number(value.expires_in_seconds))) return;
    deadline = Math.min(deadline, Date.now() + Math.max(0, Number(value.expires_in_seconds)) * 1000);
    if (!leaseTimer) leaseTimer = setInterval(() => {
      if (Date.now() >= deadline) { stopped = true; clearContent('The original Hunt lease expired.'); message('This Hunt expired. Its temporary results and reviews were cleared. Start a new Hunt when acquisition is available.'); remember(); }
    }, 250);
  }
  function coverage(value) {
    if (value.usage_policy) renderUsage(value.usage_policy);
    $('hunter-progress').hidden = false;
    const w = value.window || {}, fmt = date => { const d = new Date(date); return Number.isFinite(d.getTime()) ? d.toLocaleString() : 'Unknown'; };
    $('hunter-window').textContent = `${pretty(value.plan?.scope || 'singles')} · auctions ${fmt(w.start)} to ${fmt(w.end)} · available Buy It Now offers.`;
    const c = value.traversal_coverage || {}, counts = value.counts || {}, local = value.coverage || {};
    $('hunter-coverage').textContent = `${c.fetched ?? counts.received ?? 0} fetched · ${c.unique ?? local.unique ?? 0} unique · ${c.retained ?? local.unique ?? 0} retained · ${c.remaining_pages ?? 0} planned pages remaining.`;
    $('hunter-limitations').textContent = `${value.running ? 'Hunt is working through its captured pages. ' : 'Partial marketplace coverage. '}${c.truncated || counts.truncated_pages ? 'Some pages report further results. ' : ''}References retain their original dates.`;
    const accounting = $('hunter-accounting'); accounting.replaceChildren();
    for (const [label, val] of [['Fetched observations', c.fetched ?? counts.received], ['Unique identities', c.unique ?? local.unique], ['Duplicate observations', c.duplicates ?? counts.duplicates], ['Retained summaries', c.retained ?? local.unique], ['Skipped by limits', c.skipped], ['Malformed identity rejections', c.rejected ?? counts.invalid_identity], ['Locally rejected offers', local.rejected], ['Truncated pages (advisory)', c.truncated ?? counts.truncated_pages]]) accounting.append(h('p', `${label}: ${val ?? 'Unknown'}`));
    for (const [key, val] of Object.entries(local)) if (!['unique', 'results', 'rejected'].includes(key)) accounting.append(h('p', key === 'comparable' ? `Exact reference matches (costs may be incomplete): ${val}` : `${pretty(key)} results: ${val}`));
    for (const [key, val] of Object.entries(c.reasons || {})) accounting.append(h('p', `${pretty(key)}: ${val}`));
    const diagnostic = value.coverage_diagnostics;
    if (diagnostic) {
      const d = diagnostic.denominators || {};
      accounting.append(h('h3', 'Comparison coverage'));
      for (const [key, label] of Object.entries({fetched: 'Fetched observations', retained: 'Retained summaries', eligible_singles: 'Eligible singles', lots: 'Loose lots', matched_identities: 'Matched catalog identities', admitted_references: 'Admitted references', complete_comparisons: 'Complete delivered comparisons'})) accounting.append(h('p', `${label}: ${d[key] ?? 'Unknown'}`));
      accounting.append(h('p', 'Reasons below may overlap. Each reason counts retained summaries, so they do not add up to the primary outcomes.'));
      for (const [key, count] of Object.entries(diagnostic.reason_counts || {})) accounting.append(h('p', `${diagnostic.reason_labels?.[key] || pretty(key)}: ${count} of ${d.retained ?? 'Unknown'} retained summaries`));
      const outcomes = Object.entries(diagnostic.primary_outcomes || {}).map(([key, count]) => `${pretty(key)} ${count}`).join(' · ');
      if (outcomes) accounting.append(h('p', 'Primary outcomes: ' + outcomes + '.'));
      $('hunter-limitations').append(h('span', ` ${d.admitted_references ?? 0} retained offers have an admitted reference; ${d.complete_comparisons ?? 0} have complete delivered comparisons.`));
    }
    accounting.append(h('p', 'Duplicates are repeat observations; skipped identities were not retained. Rejections and reference coverage have separate meanings. Provider totals are advisory.'));
  }
  function field(dl, label, value, className) { const wrap = h('div', null, {class: className}); wrap.append(h('dt', label), h('dd', value)); dl.append(wrap); }
  function scenario(value) {
    const box = h('section', null, {class: 'hunter-scenario'});
    const labels = {buy_it_now: 'Buy It Now', current_bid: 'Auction · current bid', minimum_next_bid: 'Auction · minimum next bid', planned_manual_bid: 'Auction · planned manual bid'};
    box.append(h('h4', labels[value.kind] || pretty(value.kind)));
    const dl = h('dl', null, {class: 'hunter-amounts'});
    field(dl, 'Listing / scenario amount', money(value.listing_amount)); field(dl, 'Known shipping', money(value.shipping));
    field(dl, pretty(value.cost_basis || 'comparison cost'), money(value.comparison_cost)); field(dl, 'Dated reference', money(value.reference_amount));
    box.append(dl);
    box.append(h('p', `Reference date: ${value.reference_as_of || 'Unknown'} · provider valuation date: ${value.reference_valuation_as_of || 'Unavailable'}.`));
    if (value.gap?.amount != null) box.append(h('p', `Reference gap: ${money(value.gap.amount)}${value.gap.percent == null ? '' : ' · ' + value.gap.percent + '%'} · ${pretty(value.cost_basis)}.`));
    if (value.rank != null) box.append(h('p', `Rank ${value.rank} among equivalent ${pretty(value.applicability)} ${pretty(value.kind)} comparisons with the same known costs.`));
    if (value.unknown_cost_components?.length) box.append(h('p', 'Unknown costs: ' + value.unknown_cost_components.map(pretty).join(', ') + '.'));
    if (value.kind !== 'buy_it_now') box.append(h('p', 'Auction scenario only. The final price may rise; this gap is not a recommended maximum bid.'));
    if (value.applicability === 'conditional') box.append(h('p', 'Conditional reference: verify the printing and seller applicability.'));
    return box;
  }
  function countdown(row) {
    if (!row.buying_options?.includes('AUCTION')) return row.buying_options?.includes('FIXED_PRICE') ? 'Buy It Now · currently available when observed' : 'Unsupported offer';
    return window.DexAuctionTime?.(row.ends_at) || 'Auction · end time unknown';
  }
  function netInputs() {
    return Object.fromEntries(Object.entries({purchaseTax:'net-purchase-tax',resaleTax:'net-resale-tax',feeRate:'net-fee-rate',postage:'net-postage',supplies:'net-supplies',extra:'net-extra'}).map(([key,id])=>[key,$(id).value]));
  }
  function simpleCard(row) {
    const identity=row.proposed_identity, ref=row.reference, token=epoch;
    const article=h('article',null,{class:'hunter-card hunter-single',id:`hunter-result-${row.id}`,tabindex:'-1','data-result':row.id});
    const head=h('div',null,{class:'hunter-card-head'}), info=h('div');
    head.append(image(identity?.artwork,identity?.name,()=>active(token)),info);
    info.append(h('h3',identity?.name || row.title || 'Unmatched card'));
    if (identity) info.append(h('p',[identity.set_name,identity.collector_number && '#'+identity.collector_number,identity.finish,identity.edition].filter(Boolean).join(' · ')));
    info.append(h('p',countdown(row),{'data-countdown':row.id}));article.append(head);
    const amounts=h('dl',null,{class:'hunter-amounts'});
    field(amounts,row.price_kind==='current_bid'?'Current bid':'Buy It Now',money(row.listing_price),'hunter-metric-primary');
    field(amounts,'Shipping to you',money(row.shipping));
    const result=window.DexHunterNet.estimate(row,netInputs());
    const raw=ref?.grade==='raw' && row.opportunity?.scenarios?.some(s=>s.reference_amount!=null);
    field(amounts,'Ungraded reference',raw?money(ref.amount):'Unavailable');
    field(amounts,result.conditional?'Conditional net estimate':'Potential net',result.net===undefined?'Unavailable':money(result.net/100),result.net===undefined?'hunter-metric-unavailable':'hunter-metric-net');article.append(amounts);
    const evidence=h('details',null,{class:'hunter-cost-breakdown'});
    evidence.append(h('summary','Reference & costs'));
    if (raw) {
      const stamp=ref.captured_at?new Date(ref.captured_at):null;
      const captured=stamp && Number.isFinite(stamp.getTime())?stamp.toLocaleString():'not recorded';
      article.append(h('p',`Reference dated ${ref.valuation_as_of || ref.as_of || 'unknown'}${ref.condition ? ' · ' + ref.condition : ''}`,{class:'hunter-note'}));
      evidence.append(h('p',`Captured ${captured}.`,{class:'hunter-note'}));
      try {const url=new URL(ref.source_url);if(url.protocol==='https:' && !url.username && !url.password) evidence.append(h('a','Price source',{href:url.href,target:'_blank',rel:'noopener noreferrer'}));} catch {}
    }
    if (result.net!==undefined) {
      const breakdown=h('dl',null,{class:'hunter-cost-lines'});
      for (const [label,key] of [['Selling fees','fees'],['Purchase tax','tax'],['Resale postage','postage'],['Supplies','supplies'],['Other costs','extra']]) field(breakdown,label,money(result[key]/100));
      evidence.append(breakdown);
    }
    else article.append(h('p',result.reason || 'Estimate unavailable.',{class:'hunter-note'}));
    if (raw || result.net!==undefined) article.append(evidence);
    if (result.conditional) article.append(h('p','Verify the printing and condition before relying on this estimate.',{class:'hunter-note'}));
    if (identity || !row.title) article.append(h('p',row.title || 'Seller title unavailable.',{class:'hunter-seller-title'}));
    const link=sellerLink(row.item_url);if(link)article.append(link);
    if (run?.run_id && row.hunt_status !== 'rejected') window.DexInterpretation?.mount(article, {kind:'hunter',run_id:run.run_id,result_id:row.id}, () => active(token));
    return article;
  }
  function card(row, inspect = false) {
    if (simple) return simpleCard(row);
    const token = epoch, id = row.id, identity = row.proposed_identity;
    const article = h('article', null, {class: 'hunter-card', id: `hunter-result-${id}`, tabindex: '-1', 'data-result': id});
    const head = h('div', null, {class: 'hunter-card-head'}), info = h('div');
    head.append(image(identity?.artwork, identity?.name, () => active(token)), info);
    const classification = row.opportunity?.classification || row.hunt_status || row.classification || 'unpriced';
    const badge = ['comparable', 'priced'].includes(classification) && !row.comparison_diagnostics?.complete_delivered_comparison ? 'Reference matched · costs incomplete' : pretty(classification);
    info.append(h('span', badge, {class: `hunter-badge ${classification.includes('conditional') ? 'conditional' : ''}`}), h('h3', identity?.name || row.label || 'Unresolved card identity'));
    if (identity) info.append(h('p', [identity.set_name, identity.collector_number, identity.edition, identity.finish, identity.variant_label].filter(Boolean).join(' · ')));
    info.append(h('p', countdown(row), {'data-countdown': id})); article.append(head);
    const amounts = h('dl', null, {class: 'hunter-amounts'});
    field(amounts, row.price_kind === 'current_bid' ? 'Current bid' : 'Listing amount', money(row.listing_price)); field(amounts, 'Shipping', money(row.shipping)); article.append(amounts);
    if (row.reason) article.append(h('p', row.reason));
    if (row.comparison_diagnostics?.reasons?.length) {
      const why = h(inspect ? 'section' : 'details', null, {class: 'hunter-comparison-reasons', 'aria-label': 'Comparison coverage reasons'});
      why.append(h(inspect ? 'h4' : 'summary', row.comparison_diagnostics.complete_delivered_comparison ? 'Comparison basis' : 'Why this comparison is incomplete'));
      for (const reason of row.comparison_diagnostics.reasons) why.append(h('p', reason));
      article.append(why);
    }
    const scenarios = row.opportunity?.scenarios || [];
    if (scenarios.length) { article.append(scenario(scenarios[0])); if (scenarios.length > 1) { const more = h('details'); more.append(h('summary', 'Other auction / buying scenarios')); for (const s of scenarios.slice(1)) more.append(scenario(s)); article.append(more); } }
    if (!scenarios.length || scenarios.every(s => s.reference_amount == null)) article.append(h('p', 'No applicable admitted reference. A value or gap is unavailable.'));
    const candidates = row.identity_candidates || [];
    if (!identity && candidates.length) {
      const choices = h('details'); choices.append(h('summary', `${row.identity_candidates_total || candidates.length} unresolved printing candidates`));
      for (const candidate of candidates) { const item = h('div', null, {class: 'hunter-candidate'}); item.append(image(candidate.artwork, candidate.name, () => active(token)), h('p', [candidate.name, candidate.set_name, candidate.collector_number, candidate.variant_label, candidate.printing_id].filter(Boolean).join(' · '))); choices.append(item); } article.append(choices);
    }
    const seller = h('div', null, {class: 'hunter-seller'}), show = () => {
      seller.replaceChildren(h('p', row.title || 'Seller text unavailable.'));
      const link = sellerLink(row.item_url); if (link) seller.append(link); else seller.append(h('p', 'Seller destination unavailable.'));
    };
    if (revealed.has(id)) show();
    else { const reveal = h('button', 'Reveal seller listing', {type: 'button', class: 'secondary', 'data-reveal': id}); reveal.addEventListener('click', () => { if (active(token)) { revealed.add(id); show(); (seller.querySelector('a') || article).focus({preventScroll: true}); } }); seller.append(reveal); }
    article.append(seller);
    if (!inspect && row.hunt_status !== 'rejected') {
      const actions = h('div', null, {class: 'hunter-actions'}), lot = row.discovery_kind === 'mixed_lot' || row.contents_review_required;
      const button = h('button', lot ? 'Analyze lot' : 'Inspect card', {type: 'button', class: 'secondary', 'data-inspect': id, id: `hunter-inspect-${id}`});
      button.addEventListener('click', () => lot ? analyze(row, button.id) : inspectCard(id, button.id)); actions.append(button); article.append(actions);
    }
    if (run?.run_id && row.hunt_status !== 'rejected') window.DexInterpretation?.mount(article, {kind:'hunter',run_id:run.run_id,result_id:row.id}, () => active(token));
    return article;
  }
  function retainFocus() {
    const el = document.activeElement;
    if (!$('hunter-cards').contains(el)) { if (el !== document.body) retainedFocus = null; return; }
    retainedFocus = {id: el.id, result: el.closest('[data-result]')?.dataset.result, reveal: el.getAttribute('data-reveal'), href: el.getAttribute('href')};
  }
  function restoreFocus() {
    if (!retainedFocus || ![document.body, $('hunter-cards')].includes(document.activeElement)) return;
    const saved = retainedFocus; retainedFocus = null;
    const article = document.getElementById('hunter-result-' + saved.result);
    const dest = document.getElementById(saved.id) || (saved.reveal && article?.querySelector('[data-reveal]')) || (saved.href && [...(article?.querySelectorAll('a') || [])].find(a => a.getAttribute('href') === saved.href)) || article || $('hunter-results-title');
    if (view === 'results') dest?.focus({preventScroll: true});
  }
  function renderCards() {
    retainFocus();
    const target = $('hunter-cards'), filter = $('hunter-filter').value;
    target.replaceChildren();
    const selected = rows.filter(row => !simple || row.ungraded_single === true).filter(row => simple || filter === 'all' || filter === 'priced' && row.reference != null || filter === 'unpriced' && row.reference == null || row.discovery_kind === filter);
    for (const row of selected) target.append(card(row));
    if (!selected.length) target.append(h('p', rows.length ? 'No received results match this local view. Show all results to continue browsing.' : 'No eligible results were received in these captured pages. Coverage is limited; an empty batch does not authorize more requests.'));
    $('hunter-results').hidden = view !== 'results'; buttons(); restoreFocus();
  }
  function schedule() {
    clearTimeout(statusTimer);
    if (!run || stopped || !authority() || document.hidden) return;
    statusTimer = setTimeout(() => readResults({quiet: true}), run.running ? 700 : 5000);
  }
  function readResults(options = {}) {
    if (readOperation) return readOperation;
    const pending = doReadResults(options).finally(() => { if (readOperation === pending) readOperation = null; });
    readOperation = pending; return pending;
  }
  async function doReadResults({more = false, quiet = false} = {}) {
    if (!run || stopped || !authority() || reading || busy) return;
    const token = epoch, serial = ++requestId, runId = run.run_id, wasRunning = run.running;
    reading = true; buttons();
    const pages = more ? Math.min(800, wantedPages + 1) : wantedPages;
    let loadedPages = 1, failed = false;
    try {
      let value = await request(api + '?run_id=' + encodeURIComponent(runId)), received = [...(value.results || [])];
      if (!active(token) || serial !== requestId) return;
      let pageValue = value;
      for (let n = 1; n < pages && pageValue.result_cursor; n++) {
        try { pageValue = await request(api + '?run_id=' + encodeURIComponent(runId) + '&cursor=' + encodeURIComponent(pageValue.result_cursor)); }
        catch (error) {
          if (error.code === 'invalid_result_cursor' || error.status === 400 && /cursor/i.test(error.message)) {
            rows = []; $('hunter-cards').replaceChildren(); wantedPages = 1; loadedPages = 1;
            value = await request(api + '?run_id=' + encodeURIComponent(runId)); pageValue = value; received = [...(value.results || [])];
            message('Results changed. Reloaded the first local page with current ranks; no acquisition was made.'); break;
          }
          throw error;
        }
        if (!active(token) || serial !== requestId) return;
        received.push(...(pageValue.results || [])); loadedPages++;
      }
      if (!active(token) || serial !== requestId) return;
      if (['stopped', 'expired', 'superseded'].includes(value.state) || value.expires_in_seconds <= 0) {
        stopped = true; clearContent('The original Hunt is no longer available.'); message('This Hunt stopped or expired. Its temporary results and reviews were cleared.'); remember(); return;
      }
      if (usageOwner && value.usage_policy) {
        metadata.acquisition_available = value.usage_policy.acquisition_available === true;
        metadata.acquisition_unavailable_reason = value.usage_policy.reason;
      } else if (!usageOwner && value.traversal_remaining && value.traversal_allowance_id === metadata.traversal_allowance_id) {
        metadata.traversal_remaining = value.traversal_remaining;
        metadata.acquisition_available = metadata.traversal_allowance_enabled === true && value.traversal_remaining.browse > 0 && value.traversal_remaining.total > 0;
        if (!metadata.acquisition_available) metadata.acquisition_unavailable_reason = 'Acquisition is unavailable because the captured allowance is consumed. Received results remain available locally.';
      }
      run = {...value, result_cursor: pageValue.result_cursor}; rows = received; wantedPages = loadedPages; bindLease(value); coverage(value); renderCards(); lastRead = Date.now();
      if (view === 'single') renderSingle();
      if (!quiet || wasRunning && !value.running) message(value.running ? 'Hunting… Stop remains available independently.' : value.error ? 'The Hunt ended with limited results: ' + value.error : 'Results ready.', Boolean(value.error));
      remember();
    } catch (error) {
      if (active(token) && serial === requestId) {
        rows = []; $('hunter-cards').replaceChildren(); review.clear('Current references could not be checked.'); $('hunter-review').hidden = true; $('hunter-results').hidden = true;
        message(error.message, true); failed = true; clearTimeout(statusTimer);
        if (error.status === 404) { stopped = true; clearContent('This temporary Hunt is unavailable.'); remember(); }
        return;
      }
    } finally { if (token === epoch && serial === requestId) { reading = false; buttons(); if (!failed) schedule(); } }
  }
  async function availability() {
    if (busy || !authority()) return;
    const token = epoch;
    try {
      const value = await request(api); if (!authority() || token !== epoch) return;
      metadata = value;
      if (usageOwner) {
        const policy = value.usage_policy || await request(api + 'usage/');
        if (!authority() || token !== epoch) return;
        renderUsage(policy);
      }
      message(ready() ? (simple ? '' : 'Choose Singles, Lots or Both, then Hunt. No goal or card entry is needed.') : simple && usageOwner && !usagePolicy?.configured ? 'Price Hunter is not enabled.' : usageOwner && usagePolicy?.reason || metadata.acquisition_unavailable_reason || 'Hunt is unavailable: choose your usage settings when available. Existing Shopping tools remain available.'); buttons();
    }
    catch (error) { if (authority() && token === epoch) { message(error.message, true); buttons(); } }
  }
  async function start(continuation = false) {
    if (busy || reading || usageBusy || !authority() || continuation && (!run?.continuation_cursor || $('hunter-continue').disabled) || !continuation && !ready()) return;
    const old = run;
    if (continuation) { review.clear(); rows = []; $('hunter-cards').replaceChildren(); view = 'results'; }
    else { clearContent(); stopped = false; wantedPages = 1; returnContext = null; }
    const token = ++epoch; viewEpoch = -1; busy = true; ++requestId; clearTimeout(statusTimer); buttons();
    message(continuation ? 'Continuing the captured acquisition… Stop remains available.' : 'Starting your Hunt… Stop remains available.');
    try {
      if (!continuation && old?.run_id) await request(api + old.run_id + '/stop/', {});
      if (!active(token)) return;
      const value = await request(continuation ? api + old.run_id + '/continue/' : api, continuation ? {cursor: old.continuation_cursor} : {scope: simple ? 'singles' : $('hunter-scope').value});
      if (!active(token)) { if (value.run_id && authority()) await request(api + value.run_id + '/stop/', {}).catch(() => {}); return; }
      run = value; busy = false; deadline = continuation ? deadline : Infinity; bindLease(value); coverage(value); remember(); buttons(); await readResults();
    } catch (error) { if (active(token)) { busy = false; message(error.message, true); buttons(); } }
  }
  async function stop() {
    if ($('hunter-stop').disabled) return;
    const id = run?.run_id;
    stopped = true; clearContent('Hunt stopped. Temporary results and reviews cleared.'); const stoppedEpoch = epoch; remember(); message('Hunt stopped. Temporary results and reviews cleared.');
    if (id && authority()) try { await request(api + id + '/stop/', {}); } catch (error) { if (authority() && epoch === stoppedEpoch) message('Results are cleared. Stop could not be confirmed: ' + error.message, true); }
  }
  function enterReview(id, focus, kind, push) {
    ++navigationEpoch;
    returnContext = {focus: focus || `hunter-inspect-${id}`, scroll: Math.min(10000000, Math.max(0, Math.round(scrollY)))};
    view = kind; viewEpoch = epoch; $('hunter-results').hidden = true; $('hunter-review').hidden = false;
    reviewId = null; inspectedId = kind === 'single' ? id : null; remember(push); buttons();
  }
  function renderSingle() {
    const area = $('hunter-review'), row = rows.find(item => item.id === inspectedId);
    const focused = document.activeElement, preserve = area.contains(focused), focusId = focused?.id, focusHref = focused?.getAttribute?.('href');
    area.replaceChildren();
    const back = h('button', 'Back to results', {id: 'hunter-back', type: 'button'}); back.addEventListener('click', () => backToResults()); area.append(back, h('h2', 'Card inspection · temporary', {tabindex: '-1'}));
    if (row) area.append(card(row, true)); else area.append(h('p', 'This card is no longer available in the current received results. Return to review current results.'));
    if (preserve) (document.getElementById(focusId) || [...area.querySelectorAll('a')].find(a => a.getAttribute('href') === focusHref) || back).focus({preventScroll: true});
  }
  async function inspectCard(id, focus, push = true) {
    if (!run || busy || !authority()) return;
    enterReview(id, focus, 'single', push); renderSingle(); $('hunter-review').querySelector('h2')?.focus(); window.scrollTo(0, 0);
    await readResults({quiet: true});
  }
  async function analyze(row, focus) {
    if (!run || busy || reading || !authority()) return;
    const token = epoch, nav = navigationEpoch, id = run.run_id; busy = true; buttons(); message('Analyzing already received lot text locally…');
    try {
      const value = await request(api + id + '/analyze-lots/', {result_ids: [row.id]});
      if (!active(token) || nav !== navigationEpoch) return;
      const first = value.reviews?.[0]; if (!first) throw new Error('No temporary lot review was returned.');
      enterReview(row.id, focus, 'lot', true); reviewId = first.review_id; review.open(first); remember(); message('Ungraded lot review uses already received text. Correct proposed contents where needed.');
      window.scrollTo(0, 0);
    } catch (error) { if (active(token)) message(error.message, true); }
    finally { if (active(token)) { busy = false; buttons(); } }
  }
  async function backToResults(fromHistory = false) {
    if (!authority()) return;
    const saved = returnContext, token = epoch, nav = ++navigationEpoch;
    review.clear(); $('hunter-review').hidden = true;
    if (!detail && !detailBusy) { ++detailEpoch; clearTimeout(detailTimer); detailIntent = null; $('hunter-details').hidden = true; }
    view = 'results'; reviewId = null; inspectedId = null; viewEpoch = -1;
    rows = []; $('hunter-cards').replaceChildren(); $('hunter-results').hidden = true;
    if (run) await readResults({quiet: true});
    if (!active(token) || nav !== navigationEpoch || view !== 'results') return;
    $('hunter-results').hidden = false;
    if (!fromHistory) remember();
    const dest = document.getElementById(saved?.focus || '') || $('hunter-results-title');
    dest?.focus({preventScroll: true}); window.scrollTo(0, Math.max(0, Math.min(10000000, saved?.scroll || 0))); buttons();
  }
  async function prepareDetails({runId, resultIds}) {
    if (!run || busy || detailBusy || !authority() || runId !== run.run_id) return;
    if (detail?.running) { message('Official details are still loading. Use Stop details before preparing another action.'); return; }
    const token = epoch, serial = ++detailEpoch; detailBusy = true; detailIntent = null;
    $('hunter-details').hidden = false; $('hunter-detail-load').disabled = true;
    $('hunter-detail-status').textContent = 'Preparing an official detail plan. This does not acquire details.';
    try {
      const value = await request(api + runId + '/lot-detail-intent/', {result_ids: resultIds});
      if (!active(token) || serial !== detailEpoch) return;
      detailIntent = {runId, resultIds};
      $('hunter-detail-status').textContent = value.dispatch_allowed ? 'Plan prepared. Load official details is a separate explicit acquisition within the captured allowance.' : value.reason || 'Official details are unavailable without an authorized captured allowance.';
      $('hunter-detail-load').disabled = value.dispatch_allowed !== true || usageOwner && !ready();
    } catch (error) { if (active(token) && serial === detailEpoch) $('hunter-detail-status').textContent = error.message; }
    finally { if (serial === detailEpoch) detailBusy = false; }
  }
  async function loadDetails() {
    if (!detailIntent || detailBusy || $('hunter-detail-load').disabled || !authority()) return;
    const token = epoch, serial = ++detailEpoch, intent = detailIntent; detailNavigation = navigationEpoch; detailBusy = true; $('hunter-detail-load').disabled = true; $('hunter-detail-stop').disabled = false;
    $('hunter-detail-status').textContent = 'Loading explicitly selected official details…';
    try {
      const value = await request(api + intent.runId + '/analyze-lot-details/', {result_ids: intent.resultIds});
      if (!active(token) || serial !== detailEpoch) { if (value.detail_action_id && authority()) await request(api + 'lot-details/' + value.detail_action_id + '/stop/', {}).catch(() => {}); return; }
      detail = value; detailBusy = false; pollDetails(token, serial);
    } catch (error) { if (active(token) && serial === detailEpoch) { detailBusy = false; $('hunter-detail-stop').disabled = true; $('hunter-detail-status').textContent = error.message; } }
  }
  async function pollDetails(token, serial) {
    if (!detail || !active(token) || serial !== detailEpoch || document.hidden) return;
    try {
      const value = await request(api + 'lot-details/' + detail.detail_action_id + '/');
      if (!active(token) || serial !== detailEpoch || document.hidden) return;
      detail = value; $('hunter-detail-status').textContent = value.running ? 'Official details are loading. Stop details remains independent of Hunt Stop.' : value.error || 'Official detail action ' + value.state + '.';
      $('hunter-detail-stop').disabled = ['stopped', 'expired', 'failed'].includes(value.state);
      if (value.reviews?.[0]) {
        const openCurrent = async () => {
          const reviewToken = epoch, nav = ++navigationEpoch, id = value.reviews[0].review_id;
          const fresh = await request(api + 'lot-review/' + encodeURIComponent(id) + '/');
          if (!active(reviewToken) || nav !== navigationEpoch || serial !== detailEpoch) return;
          view = 'lot'; viewEpoch = epoch; reviewId = id; inspectedId = null; $('hunter-results').hidden = true; $('hunter-review').hidden = false; review.open(fresh); remember();
        };
        if (view === 'lot' && navigationEpoch === detailNavigation) { await openCurrent(); }
        else {
          $('hunter-detail-open')?.remove();
          const open = h('button', 'Open official detail review', {id: 'hunter-detail-open', type: 'button'});
          open.addEventListener('click', () => openCurrent().catch(error => message(error.message, true))); $('hunter-details').append(open);
        }
      }
      if (value.running) detailTimer = setTimeout(() => pollDetails(token, serial), 700);
    } catch (error) { if (active(token) && serial === detailEpoch) { $('hunter-detail-status').textContent = error.message; $('hunter-detail-stop').disabled = true; } }
  }
  async function stopDetails() {
    if ($('hunter-detail-stop').disabled) return;
    const id = detail?.detail_action_id; ++detailEpoch; clearTimeout(detailTimer); detail = null; detailIntent = null; detailBusy = false; $('hunter-detail-open')?.remove();
    review.clear('Official details stopped. Reopen local analysis from received results.'); $('hunter-review').hidden = true; reviewId = null; view = 'results';
    $('hunter-detail-stop').disabled = true; $('hunter-detail-load').disabled = true; $('hunter-detail-status').textContent = 'Official details stopped. Hunt results remain available.';
    if (id && authority()) try { await request(api + 'lot-details/' + id + '/stop/', {}); } catch (error) { if (authority()) $('hunter-detail-status').textContent = 'Detail content cleared; Stop could not be confirmed: ' + error.message; }
    if (run && authority()) await readResults({quiet: true});
  }
  $('hunter-form').addEventListener('submit', event => { event.preventDefault(); start(); });
  if (usageOwner) {
    $('hunter-usage-form').addEventListener('submit', event => { event.preventDefault(); saveUsage(); });
    $('hunter-usage-pause').addEventListener('click', () => saveUsage(true));
    $('hunter-usage-expiry-mode').addEventListener('change', expiryMode);
    renderUsage(usagePolicy, true);
  }
  $('hunter-stop').addEventListener('click', stop); $('hunter-recheck').addEventListener('click', () => run ? readResults() : availability());
  $('hunter-continue').addEventListener('click', () => start(true)); $('hunter-local-next').addEventListener('click', () => readResults({more: true}));
  $('hunter-filter').addEventListener('change', () => { renderCards(); remember(); }); $('hunter-scope').addEventListener('change', () => { buttons(); if (run) message('Scope changed. Start a new explicit Hunt to use it; received results keep the captured scope.'); });
  $('hunter-detail-load').addEventListener('click', loadDetails); $('hunter-detail-stop').addEventListener('click', stopDetails);
  addEventListener('dex:authority-revoked', invalidate);
  addEventListener('pagehide', () => { ++epoch; ++requestId; ++detailEpoch; clearTimeout(statusTimer); clearTimeout(detailTimer); clearInterval(leaseTimer); review.clear(); rows = []; $('hunter-cards').replaceChildren(); $('hunter-review').replaceChildren(); });
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) { ++requestId; reading = false; readOperation = null; clearTimeout(statusTimer); clearTimeout(detailTimer); retainFocus(); rows = []; $('hunter-cards').replaceChildren(); if (view === 'single') $('hunter-review').replaceChildren(); else if (view === 'lot') review.withhold?.(); }
    else if (authority()) { if (Date.now() >= deadline) { stopped = true; clearContent('The original lease expired.'); message('This Hunt expired. Temporary results and reviews were cleared.'); } else { retainFocus(); rows = []; $('hunter-cards').replaceChildren(); readResults({quiet: true}); if (view === 'lot') review.refresh(); if (detail?.running) pollDetails(epoch, detailEpoch); } }
  });
  addEventListener('focus', () => { if (authority() && run && Date.now() - lastRead > 1000) { retainFocus(); rows = []; $('hunter-cards').replaceChildren(); if (view === 'lot') review.withhold?.(); readResults({quiet: true}); if (view === 'lot') review.refresh(); } });
  addEventListener('popstate', async event => {
    if (!authority()) return;
    const state = event.state;
    if (!state || state.hunter !== 1 || state.account !== account || state.binding !== binding || state.generation !== generation || state.run !== run?.run_id) { clearContent(); stopped = false; availability(); return; }
    if (state.view === 'results') await backToResults(true);
    else if (state.view === 'single' && state.inspect) await inspectCard(state.inspect, state.returnContext?.focus, false);
    else if (state.view === 'lot' && state.review) {
      const nav = ++navigationEpoch, token = epoch, expectedReview = state.review;
      view = 'lot'; viewEpoch = epoch; reviewId = state.review; $('hunter-results').hidden = true; $('hunter-review').hidden = false;
      try { const value = await request(api + 'lot-review/' + encodeURIComponent(reviewId) + '/'); if (active(token) && nav === navigationEpoch && view === 'lot' && reviewId === expectedReview) review.open(value); } catch (error) { if (active(token) && nav === navigationEpoch) { message(error.message, true); backToResults(true); } }
    }
  });
  const saved = history.state;
  if (saved?.hunter === 1 && saved.account === account && saved.binding === binding && saved.generation === generation && /^[0-9a-f-]{36}$/.test(saved.run || '')) {
    $('hunter-scope').value = simple ? 'singles' : ['singles', 'lots', 'both'].includes(saved.scope) ? saved.scope : 'both';
    $('hunter-filter').value = ['all', 'single', 'mixed_lot', 'priced', 'unpriced'].includes(saved.filter) ? saved.filter : 'all';
    wantedPages = Math.min(800, Math.max(1, saved.pages | 0)); returnContext = saved.returnContext; run = {run_id: saved.run};
    readResults().then(async () => { if (!run || stopped || !authority()) return; if (saved.view === 'single') await inspectCard(saved.inspect, saved.returnContext?.focus, false); if (saved.view === 'lot' && saved.review) { const nav = ++navigationEpoch, token = epoch, expectedReview = saved.review; view = 'lot'; viewEpoch = epoch; reviewId = saved.review; $('hunter-results').hidden = true; $('hunter-review').hidden = false; try { const value = await request(api + 'lot-review/' + encodeURIComponent(saved.review) + '/'); if (active(token) && nav === navigationEpoch && view === 'lot' && reviewId === expectedReview) review.open(value); } catch (error) { if (active(token) && nav === navigationEpoch) { message(error.message, true); backToResults(true); } } } });
  }
  if (simple && usageOwner) $('hunter-poc-enable').addEventListener('click',()=>{
    $('hunter-usage-enabled').value='true';$('hunter-usage-per-hunt').value='3';$('hunter-usage-daily').value='3';
    $('hunter-usage-timezone').value='America/New_York';$('hunter-usage-recurring').value='false';$('hunter-usage-expiry-mode').value='none';
    saveUsage();
  });
  if (simple) $('hunter-net-inputs').addEventListener('input',()=>{if(run && !stopped && authority()) renderCards();});
  availability(); buttons();
})();
