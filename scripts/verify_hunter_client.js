'use strict';
// Controlled in-memory DOM/transport contracts; no customer/runtime/provider access.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const sourcePath = path.join(__dirname, '../src/pokemon_hunter/beta/static/hunter.js');
const source = fs.readFileSync(sourcePath, 'utf8');
const clone = value => JSON.parse(JSON.stringify(value));
const auth = {account_id: 'engineering-account', binding: 'engineering-binding', generation: 5};
const RUN = '11111111-1111-4111-8111-111111111111';
const META = {acquisition_available: true, acquisition_unavailable_reason: 'Engineering acquisition disabled'};
function projection(changes = {}) {
  return {authority: auth, run_id: RUN, state: 'complete', running: false, expires_in_seconds: 1800,
    plan: {scope: 'both'}, results: [], result_cursor: null, has_next: false, ...changes};
}
function row(id = 'fixture-single', changes = {}) {
  return {id, title: '<img src=x onerror=alert(1)> controlled seller text', item_url: 'https://www.ebay.com/itm/123456789012',
    discovery_kind: 'single', hunt_status: 'unpriced', proposed_identity: {name: 'Fixture Charizard', set_name: 'Fixture Set', collector_number: '4',
      artwork: {image_url: 'https://assets.tcgdex.net/en/base/base1/4/high.png', alt: 'Controlled reference'}},
    listing_price: {amount: '4.00', currency: 'USD'}, shipping: {amount: null, currency: null}, buying_options: ['FIXED_PRICE'],
    opportunity: {classification: 'unpriced', scenarios: []}, ...changes};
}
function deferred() {let resolve; const promise = new Promise(yes => {resolve = yes;}); return {promise, resolve};}
async function drain() {for (let n = 0; n < 20; n++) await Promise.resolve();}
function matches(node, selector) {
  if (selector.startsWith('#')) return node.id === selector.slice(1);
  const attr = selector.match(/^\[([^=\]]+)(?:="([^"]*)")?\]$/);
  if (attr) return node.getAttribute(attr[1]) !== null && (attr[2] === undefined || node.getAttribute(attr[1]) === attr[2]);
  return node.tagName === selector.toUpperCase();
}
function descendants(parent) {return parent.children.flatMap(child => [child, ...descendants(child)]);}
class Element {
  constructor(tag, doc) {
    this.tagName = tag.toUpperCase(); this.ownerDocument = doc; this.children = []; this.parentElement = null;
    this.listeners = {}; this.attributes = {}; this.dataset = {}; this.value = ''; this._text = ''; this.disabled = false; this.hidden = false;
  }
  get textContent() {return this._text + this.children.map(child => child.textContent).join('');}
  set textContent(value) {this.replaceChildren(); this._text = String(value);}
  set innerHTML(value) {throw Error('HTML rendering is forbidden: ' + value);}
  get isConnected() {return this === this.ownerDocument.body || !!this.parentElement?.isConnected;}
  setAttribute(key, value) {
    this.attributes[key] = String(value);
    if (key === 'id') this.id = String(value);
    if (key === 'class') this.className = String(value);
    if (key === 'type') this.type = String(value);
    if (key === 'value') this.value = String(value);
    if (key.startsWith('data-')) this.dataset[key.slice(5).replace(/-([a-z])/g, (_, letter) => letter.toUpperCase())] = String(value);
  }
  getAttribute(key) {return key === 'id' ? this.id || null : this.attributes[key] ?? null;}
  append(...children) {for (const child of children) {child.parentElement = this; this.children.push(child);}}
  replaceChildren(...children) {
    if (this.contains(this.ownerDocument.activeElement)) this.ownerDocument.activeElement = this.ownerDocument.body;
    for (const child of this.children) child.parentElement = null;
    this.children = []; this._text = ''; this.append(...children);
  }
  remove() {
    if (this.parentElement) this.parentElement.children = this.parentElement.children.filter(child => child !== this);
    this.parentElement = null;
  }
  contains(node) {return node === this || descendants(this).includes(node);}
  closest(selector) {return matches(this, selector) ? this : this.parentElement?.closest(selector) || null;}
  querySelectorAll(selector) {return descendants(this).filter(node => selector.split(',').some(part => matches(node, part)));}
  querySelector(selector) {return this.querySelectorAll(selector)[0] || null;}
  addEventListener(name, handler) {(this.listeners[name] ||= []).push(handler);}
  focus() {this.ownerDocument.activeElement = this;}
  async emit(name, extra = {}) {
    for (const handler of this.listeners[name] || []) await handler({currentTarget: this, preventDefault() {}, ...extra});
    await drain();
  }
  async click() {if (!this.disabled) await this.emit('click');}
}
function setup(responder, {metadata = META, saved = null, usagePolicy} = {}) {
  const calls = [], events = {}, docEvents = {}, historyStates = [], timeouts = new Map(), intervals = new Map(), reviewCalls = [];
  let time = 1800000000000, timerId = 0;
  const doc = {hidden: false, createElement: tag => new Element(tag, doc),
    getElementById: id => [doc.body, ...descendants(doc.body)].find(node => node.id === id) || null,
    addEventListener: (name, fn) => {docEvents[name] = fn;}};
  doc.body = new Element('body', doc); doc.activeElement = doc.body;
  doc.body.dataset = {navigationBinding: auth.binding, navigationAccount: auth.account_id};
  const ids = ['hunter-app', 'hunter-form', 'hunter-initial', 'hunter-scope', 'hunter-start', 'hunter-stop', 'hunter-recheck',
    'hunter-local-next', 'hunter-continue', 'hunter-next-note', 'hunter-status', 'hunter-cards', 'hunter-results',
    'hunter-review', 'hunter-details', 'hunter-progress', 'hunter-window', 'hunter-coverage', 'hunter-limitations',
    'hunter-accounting', 'hunter-filter', 'hunter-results-title', 'hunter-detail-load', 'hunter-detail-stop', 'hunter-detail-status'];
  if (usagePolicy !== undefined) ids.push('hunter-usage-form', 'hunter-usage-status', 'hunter-usage-capacity', 'hunter-usage-settings', 'hunter-usage-enabled', 'hunter-usage-per-hunt', 'hunter-usage-daily', 'hunter-usage-timezone', 'hunter-usage-recurring', 'hunter-usage-expiry-mode', 'hunter-usage-expiry-label', 'hunter-usage-expiry', 'hunter-usage-save', 'hunter-usage-pause', 'hunter-usage-feedback');
  const nodes = new Map(ids.map(id => {const node = doc.createElement(id.includes('form') ? 'form' : id.includes('scope') || id.includes('filter') ? 'select' : id.match(/start|stop|recheck|next|continue|load/) ? 'button' : 'section'); node.id = id; return [id, node];}));
  doc.body.append(nodes.get('hunter-app'));
  for (const [id, node] of nodes) if (id !== 'hunter-app') nodes.get('hunter-app').append(node);
  nodes.get('hunter-initial').textContent = JSON.stringify({metadata, authority: auth, ...(usagePolicy === undefined ? {} : {usage_settings: {owner: true, policy: usagePolicy}})});
  nodes.get('hunter-scope').value = 'both'; nodes.get('hunter-filter').value = 'all';
  nodes.get('hunter-detail-stop').disabled = true; nodes.get('hunter-detail-load').disabled = true;
  const csrf = doc.createElement('input'); csrf.setAttribute('name', 'csrfmiddlewaretoken'); csrf.value = 'fixture-csrf'; nodes.get('hunter-form').append(csrf);
  const history = {state: saved, replaceState(state) {this.state = clone(state); historyStates.push(clone(state));},
    pushState(state) {this.state = clone(state); historyStates.push(clone(state));}};
  const review = {open(value) {reviewCalls.push({kind: 'open', value});}, clear(reason) {reviewCalls.push({kind: 'clear', reason}); nodes.get('hunter-review').replaceChildren();},
    withhold() {reviewCalls.push({kind: 'withhold'});}, refresh() {reviewCalls.push({kind: 'refresh'});}};
  const context = {window: null, document: doc, location: {origin: 'http://fixture.local', pathname: '/shopping/hunter/'},
    history, URL, JSON, Intl, AbortController, scrollY: 120,
    Date: class extends Date {constructor(value) {super(value === undefined ? time : value);} static now() {return time;}},
    setTimeout(fn, ms) {timeouts.set(++timerId, {fn, ms}); return timerId;}, clearTimeout: id => timeouts.delete(id),
    setInterval(fn, ms) {intervals.set(++timerId, {fn, ms}); return timerId;}, clearInterval: id => intervals.delete(id),
    addEventListener: (name, fn) => {events[name] = fn;},
    fetch: async (url, options) => {
      const body = options.body === undefined ? undefined : JSON.parse(options.body);
      calls.push({url, body, options});
      const value = await responder(url, body, calls.length);
      if (value?.httpStatus) return {status: value.httpStatus, ok: false, json: async () => {
        if (value.nonJson) throw new SyntaxError('Controlled HTML error response');
        return clone(value.value || {});
      }};
      return {status: 200, ok: true, json: async () => clone({...value, authority: value?.authority === null ? null : value?.authority || auth})};
    },
    DexHunterReview: {mount(options) {context.reviewOptions = options; return review;}},
    scrollTo(x, y) {context.scrollY = y;}, console};
  context.window = context; vm.createContext(context); vm.runInContext(source, context, {filename: sourcePath});
  const click = async id => {const node = doc.getElementById(id); assert(node, id); await node.click();};
  return {context, calls, events, docEvents, historyStates, reviewCalls, nodes, doc, intervals, timeouts, click,
    async start() {await nodes.get('hunter-form').emit('submit');}, async change(id, value) {nodes.get(id).value = value; await nodes.get(id).emit('change');},
    advance(ms) {time += ms;}, async ready() {await drain();},
    async event(name, extra = {}) {await events[name]?.(extra); await drain();},
    async visibility(hidden) {doc.hidden = hidden; await docEvents.visibilitychange(); await drain();}};
}
const cases = [];
async function check(name, run) {await run(); cases.push({name, status: 'passed'});}
const ordinary = (url, body) => body && url.endsWith('/stop/') ? projection({state: 'stopped'}) : body ? projection() : url.endsWith('/hunter/') ? META : projection({results: [row()]});
(async () => {
  await check('ordinary unconfigured settings select no defaults and never dispatch on incomplete save', async () => {
    const policy = {configured: false, enabled: false, remaining: 0, revision: 0, reason: 'Choose your Hunter usage limits to enable acquisition.'};
    const t = setup(() => ({acquisition_available: false, usage_policy: policy}), {metadata: {acquisition_available: false}, usagePolicy: policy});
    await t.ready(); assert(t.nodes.get('hunter-start').disabled);
    for (const key of ['enabled', 'per-hunt', 'daily', 'timezone', 'recurring', 'expiry-mode']) assert.equal(t.nodes.get('hunter-usage-' + key).value, '');
    await t.nodes.get('hunter-usage-form').emit('submit');
    assert(t.calls.every(call => call.body === undefined)); assert(t.nodes.get('hunter-usage-feedback').textContent.includes('Choose'));
    assert(t.nodes.get('hunter-usage-settings').open);
  });
  await check('deliberate settings select limits without acquisition and immediate Pause uses saved limits', async () => {
    let policy = {configured: false, enabled: false, remaining: 0, revision: 0};
    const t = setup((url, body) => {
      if (url.endsWith('/usage/') && body) { policy = {...body, configured: true, revision: body.revision + 1, used: 0, remaining: body.enabled ? body.daily_limit : 0, reason: body.enabled ? null : 'Hunter acquisition is paused.'}; return policy; }
      return {acquisition_available: policy.enabled, usage_policy: policy};
    }, {usagePolicy: policy});
    await t.ready();
    for (const [key, value] of Object.entries({enabled: 'true', 'per-hunt': '4', daily: '7', timezone: 'America/New_York', recurring: 'true', 'expiry-mode': 'none'})) t.nodes.get('hunter-usage-' + key).value = value;
    await t.nodes.get('hunter-usage-form').emit('submit');
    const saved = t.calls.find(call => call.body)?.body;
    assert.deepEqual(Object.keys(saved).sort(), ['enabled', 'per_hunt_limit', 'daily_limit', 'timezone', 'recurring', 'expires_at', 'revision'].sort());
    assert.equal(saved.per_hunt_limit, 4); assert.equal(saved.daily_limit, 7); assert.equal(saved.revision, 0);
    assert(!t.nodes.get('hunter-start').disabled); assert(t.nodes.get('hunter-usage-capacity').textContent.includes('7 of 7'));
    t.nodes.get('hunter-usage-daily').value = '1000'; await t.click('hunter-usage-pause');
    const paused = t.calls.filter(call => call.body).at(-1).body;
    assert.equal(paused.daily_limit, 7); assert.equal(paused.enabled, false); assert.equal(paused.revision, 1);
    assert(t.nodes.get('hunter-start').disabled); assert(t.calls.filter(call => call.body).every(call => call.url.endsWith('/usage/')));
  });
  await check('unavailable ordinary accounting stays readable without invented numeric capacity', async () => {
    const policy = {configured: true, enabled: false, per_hunt_limit: null, daily_limit: null, timezone: null, remaining: 0, revision: 0, reason: 'Hunter usage settings or accounting are unavailable.'};
    const t = setup(() => ({acquisition_available: false, usage_policy: policy}), {usagePolicy: policy});
    await t.ready(); assert(t.nodes.get('hunter-start').disabled);
    assert(t.nodes.get('hunter-usage-capacity').textContent.includes('cannot be read safely'));
    assert(!t.nodes.get('hunter-usage-capacity').textContent.includes('null'));
    assert.equal(t.nodes.get('hunter-usage-per-hunt').value, '');
  });
  await check('per-Hunt exhaustion leaves a successive independent Hunt available within shared daily capacity', async () => {
    const policy = {configured: true, enabled: true, acquisition_available: true, per_hunt_limit: 3, daily_limit: 7, timezone: 'America/New_York', recurring: false, expires_at: null, used: 3, remaining: 4, revision: 1};
    const meta = {acquisition_available: true, usage_policy: policy, traversal_allowance_enabled: true, traversal_allowance_id: 'ordinary-policy', traversal_remaining: {browse: 3, total: 3}};
    const t = setup((url, body) => !body && url.includes('run_id=') ? projection({results: [row()], usage_policy: policy, traversal_allowance_id: 'ordinary-policy', traversal_remaining: {browse: 0, total: 0}, continuation_blocked_reason: 'per_hunt_limit', has_next: true}) : !body && url.endsWith('/hunter/') ? meta : ordinary(url, body), {metadata: meta, usagePolicy: policy});
    await t.ready(); await t.start();
    assert(!t.nodes.get('hunter-start').disabled); assert(t.nodes.get('hunter-continue').disabled);
    await t.start(); assert.equal(t.calls.filter(call => call.body && call.url.endsWith('/hunter/')).length, 2);
    assert(t.nodes.get('hunter-usage-capacity').textContent.includes('4 of 7'));
  });
  await check('comparison coverage keeps exact-reference matches distinct from complete delivered comparisons', async () => {
    const t = setup((url, body) => !body && url.includes('run_id=') ? projection({results: [row('incomplete', {hunt_status: 'priced', opportunity: {classification: 'comparable', scenarios: []}, comparison_diagnostics: {complete_delivered_comparison: false, reasons: ['Tax and other costs are unknown.']}})],
      coverage: {comparable: 1}, coverage_diagnostics: {denominators: {fetched: 1, retained: 1, eligible_singles: 1, lots: 0, matched_identities: 1, admitted_references: 1, complete_comparisons: 0}, primary_outcomes: {priced: 1}, reason_counts: {unknown_costs: 1}, reason_labels: {unknown_costs: 'Unknown delivered costs'}}}) : ordinary(url, body));
    await t.ready(); await t.start();
    assert(t.nodes.get('hunter-cards').textContent.includes('Reference matched · costs incomplete'));
    assert(t.nodes.get('hunter-cards').textContent.includes('Tax and other costs are unknown.'));
    assert(t.nodes.get('hunter-accounting').textContent.includes('Complete delivered comparisons: 0'));
    assert(t.nodes.get('hunter-accounting').textContent.includes('1 of 1 retained summaries'));
    assert(t.nodes.get('hunter-accounting').textContent.includes('Exact reference matches (costs may be incomplete): 1'));
  });
  await check('disabled acquisition is readable and sends no start or implicit provider action', async () => {
    const t = setup(() => ({acquisition_available: false, acquisition_unavailable_reason: 'No authorized allowance'}), {metadata: {acquisition_available: false}});
    await t.ready(); assert(t.nodes.get('hunter-start').disabled); assert(t.nodes.get('hunter-status').textContent.includes('No authorized allowance'));
    await t.start(); assert(t.calls.every(call => call.body === undefined));
  });
  await check('exhausted captured allowance disables another Hunt while preserving local reads', async () => {
    for (const remaining of [{browse: 0, total: 5}, {browse: 1, total: 0}, {browse: 0, total: 0}]) {
      const metadata = {...META, traversal_allowance_enabled: true, traversal_allowance_id: 'controlled-allowance', traversal_remaining: {browse: 2, total: 3}};
      const t = setup((url, body) => !body && url.includes('run_id=') ? projection({results: [row()],
        traversal_allowance_id: metadata.traversal_allowance_id, traversal_remaining: remaining}) :
        !body && url.endsWith('/hunter/') ? metadata : ordinary(url, body), {metadata});
      await t.ready(); assert(!t.nodes.get('hunter-start').disabled); await t.start();
      assert(t.nodes.get('hunter-start').disabled); assert(t.doc.getElementById('hunter-result-fixture-single'));
      const before = t.calls.length; await t.start(); assert.equal(t.calls.length, before);
      await t.click('hunter-recheck'); assert.equal(t.calls.length, before + 1);
      assert.equal(t.calls.at(-1).body, undefined); assert(t.calls.at(-1).url.includes('run_id=' + RUN));
      assert(t.doc.getElementById('hunter-result-fixture-single'));
      assert.equal(t.calls.filter(call => call.body && call.url.endsWith('/hunter/')).length, 1);
      assert.equal(t.calls.filter(call => /continue|analyze-lot-details/.test(call.url)).length, 0);
    }
  });
  await check('normal result rendering escapes seller text and reveal never acquires', async () => {
    const t = setup(ordinary); await t.ready(); await t.start();
    const before = t.calls.length; const reveal = t.nodes.get('hunter-cards').querySelector('[data-reveal]'); assert(reveal);
    await reveal.click(); assert(t.nodes.get('hunter-cards').textContent.includes('<img src=x onerror=alert(1)>'));
    assert.equal(t.calls.length, before);
    assert.equal(t.nodes.get('hunter-cards').querySelector('img').getAttribute('referrerpolicy'), 'no-referrer');
  });
  await check('filter inspect Back and local paging make only local GET requests', async () => {
    const t = setup((url, body) => !body && url.includes('cursor=') ? projection({results: [row('second')], result_cursor: null}) :
      !body && url.includes('run_id=') ? projection({results: [row()], result_cursor: 'opaque-local'}) : ordinary(url, body));
    await t.ready(); await t.start(); const before = t.calls.length;
    await t.change('hunter-filter', 'unpriced'); await t.click('hunter-inspect-fixture-single'); await t.click('hunter-back'); await t.click('hunter-local-next');
    assert(t.calls.slice(before).every(call => call.body === undefined)); assert(t.calls.some(call => call.url.includes('cursor=opaque-local')));
    assert.equal(t.calls.filter(call => call.body && call.url.endsWith('/hunter/')).length, 1);
  });
  await check('acquisition Continue posts only its captured cursor after explicit click', async () => {
    const t = setup((url, body) => url.includes('/continue/') ? projection() : !body && url.includes('run_id=') ?
      projection({results: [row()], has_next: true, continuation_cursor: 'captured-acquisition'}) : ordinary(url, body));
    await t.ready(); await t.start(); assert.equal(t.calls.filter(call => call.url.includes('/continue/')).length, 0);
    await t.click('hunter-continue'); const continued = t.calls.find(call => call.url.includes('/continue/'));
    assert.deepEqual(continued.body, {cursor: 'captured-acquisition'});
  });
  await check('invalid local cursor discards ranks and reloads first page without acquisition', async () => {
    let reads = 0;
    const t = setup((url, body) => url.includes('cursor=') ? {httpStatus: 400, value: {error: 'Result cursor changed', code: 'invalid_result_cursor'}} :
      !body && url.includes('run_id=') ? projection({results: [row(++reads >= 3 ? 'new-rank' : 'old-rank')], result_cursor: 'invalidated'}) : ordinary(url, body));
    await t.ready(); await t.start(); await t.click('hunter-local-next');
    assert(t.doc.getElementById('hunter-result-new-rank')); assert(!t.doc.getElementById('hunter-result-old-rank'));
    assert.equal(t.calls.filter(call => call.body && call.url.endsWith('/hunter/')).length, 1);
    assert.equal(t.calls.filter(call => call.url.includes('/continue/')).length, 0);
  });
  await check('explicit availability check recovers a conflicted current run with one local GET', async () => {
    let conflicted = false, current = 'before-conflict';
    const t = setup((url, body) => !body && url.includes('run_id=') ?
      conflicted ? {httpStatus: 409, value: {error: 'Hunt changed while preparing local results; read again'}} :
        projection({results: [row(current)]}) : ordinary(url, body));
    await t.ready(); await t.start(); assert(t.doc.getElementById('hunter-result-before-conflict'));
    conflicted = true; const beforeFailure = t.calls.length; await t.visibility(false);
    assert.equal(t.calls.length, beforeFailure + 1); assert(t.nodes.get('hunter-results').hidden);
    assert.equal(t.nodes.get('hunter-cards').children.length, 0);
    assert(t.nodes.get('hunter-status').textContent.includes('Hunt changed'));
    conflicted = false; current = 'after-conflict'; const beforeRecovery = t.calls.length;
    await t.click('hunter-recheck');
    assert.equal(t.calls.length, beforeRecovery + 1);
    assert(t.calls.at(-1).url.includes('run_id=' + RUN)); assert.equal(t.calls.at(-1).body, undefined);
    assert(t.doc.getElementById('hunter-result-after-conflict')); assert(!t.nodes.get('hunter-results').hidden);
    assert.equal(t.calls.filter(call => call.body && call.url.endsWith('/hunter/')).length, 1);
    assert.equal(t.calls.filter(call => /continue|analyze-lot-details/.test(call.url)).length, 0);
  });
  await check('HTML 404 on restored opaque run clears its handle and cannot be overwritten by late boot availability', async () => {
    for (const delayedMetadata of [false, true]) {
      const metadataGate = deferred();
      const saved = {hunter: 1, account: auth.account_id, binding: auth.binding, generation: auth.generation,
        run: RUN, view: 'results', review: null, inspect: null, scope: 'both', filter: 'all', pages: 1, returnContext: null};
      const t = setup(url => url.includes('run_id=') ? {httpStatus: 404, nonJson: true} :
        delayedMetadata ? metadataGate.promise : META, {saved});
      await t.ready();
      assert(t.nodes.get('hunter-status').textContent.includes('unavailable'));
      assert.equal(t.context.history.state.run, null);
      assert(t.nodes.get('hunter-results').hidden); assert(t.nodes.get('hunter-review').hidden);
      assert(t.nodes.get('hunter-continue').hidden); assert(t.nodes.get('hunter-stop').disabled);
      assert.equal(t.nodes.get('hunter-cards').children.length, 0);
      assert(t.calls.every(call => call.body === undefined));
      metadataGate.resolve(META); await drain();
      assert(t.nodes.get('hunter-status').textContent.includes('unavailable'));
      assert.equal(t.context.history.state.run, null);
      assert.equal(t.calls.filter(call => /continue|analyze-lot-details/.test(call.url)).length, 0);
    }
  });
  await check('Stop while start is inflight clears immediately and stops late returned run', async () => {
    const gate = deferred(), t = setup((url, body) => body && url.endsWith('/hunter/') ? gate.promise : ordinary(url, body));
    await t.ready(); await t.start(); assert(!t.nodes.get('hunter-stop').disabled); await t.click('hunter-stop');
    assert.equal(t.nodes.get('hunter-cards').children.length, 0); gate.resolve(projection({running: true})); await drain();
    assert(t.calls.some(call => call.url.endsWith(RUN + '/stop/'))); assert.equal(t.nodes.get('hunter-cards').children.length, 0);
  });
  await check('repeat Hunt submits cannot dispatch concurrent starts', async () => {
    const gate = deferred(), t = setup((url, body) => body && url.endsWith('/hunter/') ? gate.promise : ordinary(url, body));
    await t.ready(); await t.start(); await t.start(); assert.equal(t.calls.filter(call => call.body && call.url.endsWith('/hunter/')).length, 1);
    gate.resolve(projection()); await drain();
  });
  await check('late result response cannot restore content after parent Stop', async () => {
    const gate = deferred(), t = setup((url, body) => !body && url.includes('run_id=') ? gate.promise : ordinary(url, body));
    await t.ready(); await t.start(); await t.click('hunter-stop'); gate.resolve(projection({results: [row('late-result')]})); await drain();
    assert(!t.doc.getElementById('hunter-result-late-result')); assert(t.nodes.get('hunter-status').textContent.includes('stopped'));
  });
  await check('wrong response account or catalog revokes content and prevents later actions', async () => {
    for (const wrong of [{...auth, account_id: 'foreign'}, {...auth, generation: 6}, {...auth, binding: 'foreign'}]) {
      const t = setup((url, body) => !body && url.includes('run_id=') ? projection({authority: wrong, results: [row()]}) : ordinary(url, body));
      await t.ready(); await t.start(); assert.equal(t.nodes.get('hunter-cards').children.length, 0); assert(t.nodes.get('hunter-start').disabled);
      const before = t.calls.length; await t.start(); assert.equal(t.calls.length, before);
    }
  });
  await check('401 response clears private content and uses no fallback acquisition', async () => {
    const t = setup((url, body) => !body && url.includes('run_id=') ? {httpStatus: 401} : ordinary(url, body));
    await t.ready(); await t.start(); assert.equal(t.nodes.get('hunter-cards').children.length, 0); assert(t.nodes.get('hunter-status').textContent.includes('session changed'));
    assert.equal(t.calls.filter(call => call.body && call.url.endsWith('/hunter/')).length, 1);
  });
  await check('tab suspension and resumption clear values then read locally', async () => {
    const t = setup(ordinary); await t.ready(); await t.start(); const before = t.calls.length;
    await t.visibility(true); assert.equal(t.nodes.get('hunter-cards').children.length, 0);
    await t.visibility(false); assert(t.doc.getElementById('hunter-result-fixture-single'));
    assert(t.calls.slice(before).every(call => call.body === undefined));
  });
  await check('a result read finishing while hidden cannot republish withheld values', async () => {
    const gate = deferred(), t = setup((url, body) => !body && url.includes('run_id=') ? gate.promise : ordinary(url, body));
    await t.ready(); await t.start(); await t.visibility(true);
    gate.resolve(projection({results: [row('hidden-stale')]})); await drain();
    assert.equal(t.nodes.get('hunter-cards').children.length, 0);
  });
  await check('second Hunt recreates independent expiry and never renews original lease', async () => {
    const t = setup((url, body) => !body && url.includes('run_id=') ? projection({results: [row()], expires_in_seconds: 1}) : ordinary(url, body));
    await t.ready(); await t.start(); assert.equal(t.intervals.size, 1); await t.click('hunter-stop'); assert.equal(t.intervals.size, 0);
    await t.start(); assert.equal(t.intervals.size, 1); t.advance(1001); [...t.intervals.values()][0].fn(); await drain();
    assert.equal(t.nodes.get('hunter-cards').children.length, 0); assert(t.nodes.get('hunter-status').textContent.includes('expired'));
  });
  await check('unsafe images and seller destinations retain neutral readable fallback', async () => {
    const bad = row('unsafe', {item_url: 'javascript:alert(1)', proposed_identity: {name: 'Readable identity', artwork: {image_url: 'https://evil.example/track.png'}}});
    const t = setup((url, body) => !body && url.includes('run_id=') ? projection({results: [bad]}) : ordinary(url, body));
    await t.ready(); await t.start(); assert(!t.nodes.get('hunter-cards').querySelector('img'));
    await t.nodes.get('hunter-cards').querySelector('[data-reveal]').click(); assert(!t.nodes.get('hunter-cards').querySelector('a'));
    assert(t.nodes.get('hunter-cards').textContent.includes('Readable identity')); assert(t.nodes.get('hunter-cards').textContent.includes('Seller destination unavailable'));
  });
  await check('late image completion after Stop cannot restore cleared results', async () => {
    const t = setup(ordinary); await t.ready(); await t.start(); const img = t.nodes.get('hunter-cards').querySelector('img');
    assert(img); await t.click('hunter-stop'); await img.emit('load'); assert(!img.parentElement); assert.equal(t.nodes.get('hunter-cards').children.length, 0);
  });
  await check('local lot analysis is explicit and detail intent never executes its plan', async () => {
    const t = setup((url, body) => url.includes('/analyze-lots/') ? {reviews: [{review_id: 'fixture-review'}]} :
      url.includes('/lot-detail-intent/') ? {dispatch_allowed: false, reason: 'No detail allowance'} :
      !body && url.includes('run_id=') ? projection({results: [row('lot', {discovery_kind: 'mixed_lot'})]}) : ordinary(url, body));
    await t.ready(); await t.start(); assert.equal(t.calls.filter(call => call.url.includes('analyze-lots')).length, 0);
    await t.click('hunter-inspect-lot'); assert(t.reviewCalls.some(call => call.kind === 'open'));
    await t.context.reviewOptions.onDetailStart({runId: RUN, resultIds: ['lot']}); await drain();
    assert(t.nodes.get('hunter-detail-load').disabled); assert.equal(t.calls.filter(call => call.url.includes('analyze-lot-details')).length, 0);
  });
  await check('independent detail Stop cancels an inflight action and suppresses its late review', async () => {
    const gate = deferred();
    const t = setup((url, body) => url.includes('/lot-detail-intent/') ? {dispatch_allowed: true} :
      url.includes('/analyze-lot-details/') ? gate.promise :
      url.includes('/lot-details/fixture-action/stop/') ? {state: 'stopped'} : ordinary(url, body));
    await t.ready(); await t.start(); await t.context.reviewOptions.onDetailStart({runId: RUN, resultIds: ['lot']});
    const loading = t.click('hunter-detail-load'); await drain(); assert(!t.nodes.get('hunter-detail-stop').disabled);
    await t.click('hunter-detail-stop'); gate.resolve({detail_action_id: 'fixture-action', running: true, reviews: [{review_id: 'late-review'}]});
    await loading; await drain(); assert(t.calls.some(call => call.url.includes('/lot-details/fixture-action/stop/')));
    assert(!t.reviewCalls.some(call => call.kind === 'open')); assert(t.doc.getElementById('hunter-result-fixture-single'));
  });
  await check('account switch while a read waits rejects its late private projection', async () => {
    const gate = deferred(), t = setup((url, body) => !body && url.includes('run_id=') ? gate.promise : ordinary(url, body));
    await t.ready(); await t.start(); t.doc.body.dataset.navigationAccount = 'changed-account';
    gate.resolve(projection({results: [row('forbidden-account')]})); await drain();
    assert(!t.doc.getElementById('hunter-result-forbidden-account')); assert(t.nodes.get('hunter-start').disabled);
  });
  await check('late lot analysis cannot replace results after validated Back navigation', async () => {
    const gate = deferred();
    const t = setup((url, body) => url.includes('/analyze-lots/') ? gate.promise :
      !body && url.includes('run_id=') ? projection({results: [row('lot', {discovery_kind: 'mixed_lot'})]}) : ordinary(url, body));
    await t.ready(); await t.start(); const analysis = t.click('hunter-inspect-lot'); await drain();
    await t.event('popstate', {state: {...t.context.history.state, view: 'results'}});
    gate.resolve({reviews: [{review_id: 'obsolete-review'}]}); await analysis; await drain();
    assert(!t.reviewCalls.some(call => call.kind === 'open')); assert(t.nodes.get('hunter-review').hidden);
  });
  await check('history stores only opaque handles and local UI context', async () => {
    const t = setup(ordinary); await t.ready(); await t.start(); await t.click('hunter-inspect-fixture-single');
    const saved = JSON.stringify(t.historyStates); assert(!saved.includes('Fixture Charizard')); assert(!saved.includes('4.00')); assert(!saved.includes('seller text'));
    for (const call of t.calls) {assert.equal(call.options.cache, 'no-store'); assert.equal(call.options.credentials, 'same-origin'); assert.equal(call.options.redirect, 'error');}
    assert(!/localStorage|sessionStorage|indexedDB|innerHTML\s*=/.test(source));
  });
  process.stdout.write(JSON.stringify({kind: 'hunter-main-client-contracts', engineering_fixtures_only: true,
    customer_root_access: false, provider_operations: 0, passed: cases.length, cases}, null, 2) + '\n');
})().catch(error => {process.stderr.write(error.stack + '\n'); process.exitCode = 1;});
