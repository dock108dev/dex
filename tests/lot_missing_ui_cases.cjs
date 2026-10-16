'use strict';
// Execute the entire shipped controller with real rendered template elements.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync(process.argv[2], 'utf8');
const trees = JSON.parse(fs.readFileSync(process.argv[3], 'utf8'));
const origin = 'http://engineering.test', account = 'engineering-account', binding = 'engineering-binding';
const goal = 'engineering-frozen', goalVersion = 'a'.repeat(64);
const draftKey = `dex-shopping-draft-v1:${origin}:${binding}`;

class Element {
  constructor(tag, attrs = {}) {
    this.tagName = tag; this.attrs = {...attrs}; this.children = []; this.parentElement = null;
    this.dataset = Object.fromEntries(Object.entries(attrs).filter(([key]) => key.startsWith('data-'))
      .map(([key, value]) => [key.slice(5).replace(/-([a-z])/g, (_, c) => c.toUpperCase()), value]));
    this.id = attrs.id || ''; this.className = attrs.class || ''; this.disabled = 'disabled' in attrs;
    this.hidden = 'hidden' in attrs; this.selected = 'selected' in attrs; this.checked = 'checked' in attrs;
    this._value = attrs.value; this.listeners = {}; this.isConnected = true;
    this.classList = {
      contains: name => this.className.split(/\s+/).includes(name),
      toggle: (name, force) => {
        const classes = new Set(this.className.split(/\s+/).filter(Boolean));
        const enabled = force === undefined ? !classes.has(name) : force;
        if (enabled) classes.add(name); else classes.delete(name);
        this.className = [...classes].join(' '); return enabled;
      },
      add: name => this.classList.toggle(name, true),
    };
  }
  get textContent() { return this.children.map(child => typeof child === 'string' ? child : child.textContent).join(''); }
  set textContent(value) { this.replaceChildren(String(value)); }
  get value() {
    if (this.tagName === 'select') return this.selectedOptions[0]?.value || '';
    return this._value === undefined ? (this.tagName === 'option' ? this.textContent : '') : String(this._value);
  }
  set value(value) {
    this._value = String(value);
    if (this.tagName === 'select') for (const option of this.options) option.selected = option.value === this._value;
  }
  get options() { return this.children.filter(child => typeof child !== 'string' && child.tagName === 'option'); }
  get selectedOptions() {
    const explicit = this.options.filter(option => option.selected);
    if (explicit.length) return explicit;
    return this._value === undefined && this.options.length ? [this.options[0]] : [];
  }
  append(...children) {
    for (const child of children) { if (typeof child !== 'string') child.parentElement = this; this.children.push(child); }
  }
  replaceChildren(...children) { this.children = []; this.append(...children); }
  remove() { if (this.parentElement) this.parentElement.children = this.parentElement.children.filter(child => child !== this); }
  setAttribute(key, value) { this.attrs[key] = String(value); }
  getAttribute(key) { return this.attrs[key] ?? null; }
  addEventListener(type, fn) { (this.listeners[type] ||= []).push(fn); }
  async emit(type, extra = {}) {
    const event = {target: this, preventDefault() {}, ...extra};
    if (this['on' + type]) await this['on' + type](event);
    for (const fn of this.listeners[type] || []) await fn(event);
  }
  focus() {} scrollIntoView() {}
  matches(selector) {
    if (selector.startsWith('#')) return this.id === selector.slice(1);
    if (selector.startsWith('.')) return this.classList.contains(selector.slice(1));
    const attr = selector.match(/^\[([^=]+)="([^"]+)"\]$/);
    if (attr) return attr[1].startsWith('data-')
      ? this.dataset[attr[1].slice(5).replace(/-([a-z])/g, (_, c) => c.toUpperCase())] === attr[2]
      : this.attrs[attr[1]] === attr[2];
    return this.tagName === selector;
  }
  descendants() {
    return this.children.flatMap(child => typeof child === 'string' ? [] : [child, ...child.descendants()]);
  }
  querySelectorAll(selector) {
    return [...new Set(selector.split(',').flatMap(part => {
      const segments = part.trim().split(/\s+/), last = segments.pop();
      return this.descendants().filter(element => element.matches(last) && segments.every(segment => {
        for (let parent = element.parentElement; parent; parent = parent.parentElement) if (parent.matches(segment)) return true;
        return false;
      }));
    }))];
  }
  querySelector(selector) { return this.querySelectorAll(selector)[0] || null; }
  closest(selector) {
    for (let element = this; element; element = element.parentElement) if (element.matches(selector)) return element;
    return null;
  }
}
function build(tree) {
  if (typeof tree === 'string') return tree;
  const element = new Element(tree.tag, tree.attrs); element.append(...tree.children.map(build)); return element;
}
async function flush() { for (let index = 0; index < 80; index++) await Promise.resolve(); }
function setup({template = 'default', saved} = {}) {
  const document = build(trees[template]), calls = [], events = {}, memory = new Map();
  const get = id => document.querySelector('#' + id);
  document.getElementById = get; document.createElement = tag => new Element(tag);
  const context = JSON.parse(get('shopping-context').textContent);
  const sessionStorage = {getItem: key => memory.get(key) ?? null, setItem: (key, value) => memory.set(key, String(value)), removeItem: key => memory.delete(key)};
  if (saved) memory.set(draftKey, JSON.stringify(saved));
  const printing = {id: 'engineering-printing', name: 'Engineering Venusaur', set_name: 'Engineering set', collector_number: '3', cells: {}, price_reasons: {}};
  const sandbox = {
    document, location: {origin, href: origin + '/shopping/calculator/'}, sessionStorage,
    URL, URLSearchParams, Intl, Date, setTimeout() { return 1; }, clearTimeout() {}, setInterval() { return 1; },
    matchMedia: () => ({matches: false}), addEventListener: (name, fn) => { events[name] = fn; },
    fetch: async (url, init) => {
      assert.ok(url.startsWith('/api/shopping/lot-catalog/?'), 'Only local catalog GETs are allowed');
      assert.equal(init.method || 'GET', 'GET');
      const parsed = new URL(url, origin), params = parsed.searchParams;
      calls.push({url, params, headers: init.headers});
      const frozen = params.has('goal'), current = params.get('missing') === 'species';
      const items = frozen ? [{id: '#094 Gengar', label: '#094 Gengar'}] : current ? [{id: '#003 Venusaur', label: '#003 Venusaur'}] : [];
      const active = {...context, kind: frozen ? 'goal' : current ? 'missing' : 'all', label: frozen ? 'Saved goal: Retained engineering goal' : current ? 'Current collection · Original 151' : 'All cards', goal_version: frozen ? goalVersion : null};
      const payload = {
        context: active, authority: {binding, account_id: account, generation: 12},
        missing_items: items, selected_missing_item: items[0]?.id || '',
        cards: params.has('restore') ? [printing] : [], total: 0,
      };
      return {ok: true, status: 200, redirected: false, headers: {get: () => 'application/json'}, json: async () => payload};
    },
  };
  sandbox.window = sandbox;
  vm.runInNewContext(source, sandbox);
  return {get, calls, events, memory, document, saved: () => JSON.parse(memory.get(draftKey))};
}
function existingDraft(schema = 'dex-shopping-inputs-v1') {
  const costs = {
    listing_observation: {amount: '42.50', date: '2026-10-15', components: {shipping: '5', tax: '', other_costs: '0'}},
    planned_bid: {amount: '30', date: '2026-10-14', components: {shipping: '', tax: '1.25', other_costs: ''}},
  };
  return {schema, account, rows: [{id: 'engineering-printing', included: '2', wanted: '3', locked: false}], costs,
    listing: 'https://www.ebay.com/itm/123456789012', name: 'Retained engineering lot',
    ui: {query: '', missing: true, item: '#094 Gengar', goal, printing: '', contextual: false, offset: 0, target: '{}'}};
}
function scope(call, mode) {
  assert.equal(call.params.get('generation'), '12');
  assert.equal(call.headers['X-Dex-Shopping-Binding'], binding);
  if (mode === 'current') {
    assert.equal(call.params.get('missing'), 'species');
    for (const key of ['goal', 'version']) assert.equal(call.params.has(key), false);
    for (const key of ['X-Dex-Shopping-Goal', 'X-Dex-Shopping-Version']) assert.equal(key in call.headers, false);
  } else if (mode === 'goal') {
    assert.equal(call.params.get('goal'), goal); assert.equal(call.params.get('version'), goalVersion);
    assert.equal(call.params.has('missing'), false);
    assert.equal(call.headers['X-Dex-Shopping-Goal'], goal); assert.equal(call.headers['X-Dex-Shopping-Version'], goalVersion);
  } else {
    for (const key of ['missing', 'missing_item', 'pick_first', 'goal', 'version']) assert.equal(call.params.has(key), false);
    assert.equal('X-Dex-Shopping-Goal' in call.headers, false);
  }
}
const passed = [];
async function check(name, run) { await run(); passed.push(name); }
(async () => {
  await check('existing saved goals do not replace current missing default', async () => {
    const t = setup(); await flush(); assert.equal(t.calls.length, 1); scope(t.calls[0], 'current');
    assert.equal(t.get('missing-goal').value, '');
    assert.equal(t.get('context-label').textContent, 'Current collection · Original 151');
    assert.equal(t.get('show-missing').textContent, 'Missing (1)'); assert.equal(t.get('show-all').getAttribute('aria-pressed'), 'false');
  });
  await check('current missing works without any saved goal', async () => {
    const t = setup({template: 'no_goals'}); await flush(); scope(t.calls[0], 'current');
    assert.equal(t.get('missing-goal').options.length, 1); assert.equal(t.get('missing-picker').hidden, false);
  });
  await check('explicit saved goal selection sends its exact version and authority', async () => {
    const t = setup(); await flush(); t.get('missing-goal').value = goal; await t.get('missing-goal').emit('change'); await flush();
    scope(t.calls.at(-1), 'goal'); assert.match(t.get('catalog-scope').textContent, /retained membership/);
    t.get('missing-goal').value = ''; await t.get('missing-goal').emit('change'); await flush(); scope(t.calls.at(-1), 'current');
  });
  await check('incoming explicit goal is selected by the rendered template', async () => {
    const t = setup({template: 'explicit_goal'}); await flush(); scope(t.calls[0], 'goal');
    assert.equal(t.get('missing-goal').value, goal);
  });
  await check('All cards clears missing and saved goal request scope', async () => {
    const t = setup(); await flush(); t.get('missing-goal').value = goal; await t.get('missing-goal').emit('change'); await flush();
    await t.get('show-all').emit('click'); await flush(); scope(t.calls.at(-1), 'all');
    assert.equal(t.get('missing-picker').hidden, true); assert.equal(t.get('show-all').getAttribute('aria-pressed'), 'true');
    assert.equal(t.get('context-label').textContent, 'All cards');
  });
  await check('legacy draft retains authored lot and costs while resetting automatic frozen picker', async () => {
    const saved = existingDraft(), t = setup({saved}); await flush();
    assert.equal(t.calls.length, 2); assert.deepEqual(t.calls[0].params.getAll('restore'), ['engineering-printing']);
    scope(t.calls[1], 'current'); assert.equal(t.calls[1].params.get('missing_item'), '');
    const restored = t.saved(); assert.equal(restored.schema, 'dex-shopping-inputs-v2');
    for (const key of ['rows', 'costs', 'listing', 'name']) assert.deepEqual(restored[key], saved[key]);
    assert.equal(restored.ui.goal, ''); assert.equal(restored.ui.item, '#003 Venusaur');
    assert.equal(t.get('lot-price').value, '42.50'); assert.match(t.get('lot-count').textContent, /2 included/);
    assert.equal(t.get('results').hidden, true); assert.match(t.get('draft-note').textContent, /Draft restored/);
  });
  await check('new explicit saved-goal draft retains goal version and lot inputs', async () => {
    const saved = existingDraft('dex-shopping-inputs-v2'), t = setup({saved}); await flush();
    scope(t.calls.at(-1), 'goal'); assert.equal(t.calls.at(-1).params.get('missing_item'), '#094 Gengar');
    const restored = t.saved(); for (const key of ['rows', 'costs', 'listing', 'name']) assert.deepEqual(restored[key], saved[key]);
    assert.equal(restored.ui.goal, goal); assert.equal(t.get('missing-goal').value, goal);
  });
  console.log(JSON.stringify({passed: passed.length, cases: passed, provider_calls: 0, customer_data: false}));
})().catch(error => { console.error(error); process.exitCode = 1; });
