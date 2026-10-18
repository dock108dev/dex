'use strict';
// Isolated renderer contracts. Every value below is an engineering fixture;
// no runtime, customer installation, image host or provider is contacted.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const sourcePath = path.join(__dirname, '../src/pokemon_hunter/beta/static/hunter-review.js');
const source = fs.readFileSync(sourcePath, 'utf8');
const clone = value => JSON.parse(JSON.stringify(value));
class Element {
  constructor(tag) {
    this.tagName = tag.toUpperCase(); this.children = []; this.listeners = {}; this.attributes = {};
    this.value = ''; this._text = ''; this.className = ''; this.hidden = false; this.disabled = false; this.isConnected = true;
  }
  get textContent() {return this._text + this.children.map(child => child.textContent || '').join('');}
  set textContent(value) {this._text = String(value); this.children = [];}
  set innerHTML(value) {throw Error('Seller/provider HTML may never be rendered: ' + value);}
  append(...nodes) {this.children.push(...nodes);}
  replaceChildren(...nodes) {this._text = ''; this.children = nodes;}
  setAttribute(key, value) {this.attributes[key] = value;}
  getAttribute(key) {return this.attributes[key] ?? null;}
  contains(node) {return node === this || walk(this).includes(node);}
  addEventListener(name, handler) {(this.listeners[name] ||= []).push(handler);}
  focus() {this.focused = true; if (this.ownerDocument) this.ownerDocument.activeElement = this;}
  querySelector(selector) {return walk(this).find(node => selector.split(',').some(part => {
    const match = part.match(/^([a-z]+)(?:\[type="([a-z]+)"\])?$/);
    return match && node.tagName === match[1].toUpperCase() && (!match[2] || node.type === match[2]);
  })) || null;}
  click() {if (!this.disabled) return emit(this, 'click');}
}
function walk(parent) {return parent.children.flatMap(node => [node, ...walk(node)]);}
async function emit(node, type, extra = {}) {
  for (const handler of node.listeners[type] || []) await handler({currentTarget: node, preventDefault() {}, ...extra});
}
function deferred() {let resolve; const promise = new Promise(yes => {resolve = yes;}); return {promise, resolve};}
const identity = {id: 'fixture-charizard', name: 'Charizard', set_name: 'Base Set', collector_number: '4/102',
  language: 'en', edition: 'unlimited', finish: 'normal', image_binding: {printing_id: 'fixture-charizard'}, artwork: null};
function response(changes = {}) {
  return {
    review_id: 'fixture-review', revision: 1, expires_in_seconds: 1800,
    provenance: {source: 'authorized_summary', detail_fetched: false, origin: {run_id: 'fixture-run', result_id: 'fixture-result'}},
    correction_contract: {explicit_card_attributes: {}},
    proposal: {seller_stated_total: 2, stock_quantity: 99, lot_units: 3, quantity_issues: [],
      proposals: [{name: 'Charizard', quantity: 2, included_quantity: 2, candidates: [clone(identity)],
        candidates_total: 1, conflicting_fields: ['condition'], reasons: ['Conflicting seller condition'],
        clues: {condition: 'Near Mint'}, mentions: [{source_field: 'summary', text: '<img src=x onerror=alert(1)> seller fixture'}]}],
      unresolved_contents: [{source_field: 'summary', text: '<script>never execute</script>', quantity: 1, reason: 'No local card identity'}]},
    review: {cards: [{printing_id: identity.id, quantity: 2, condition: 'Near Mint', grade: 'raw', language: 'en'}],
      card_identities: [clone(identity)], unknown_contents: null,
      costs: {price: '4.00', currency: 'USD', price_kind: 'current_asking_price', shipping: '1.00', tax: '', other_costs: '', planned_bid: ''}},
    comparison: {label: 'Priced subtotal; incomplete lot comparison', priced_card_quantity: 2, unpriced_card_quantity: 0,
      complete_delivered_comparison: false, quantities_reconciled: false, comparison_kind: 'buy_it_now_reference_comparison',
      result: {known_selected_subtotal: '20.00', full_lot_total: null, comparisons: {listing_observation: {
        base_price: '4.00', known_cost_subtotal: '5.00', full_delivered_cost: null,
        unknown_or_ineligible_components: ['tax', 'other_costs']}}}, references: [{amount: '10.00', as_of: '2026-10-16'}], limitations: []},
    ...changes,
  };
}
function setup(responder) {
  const container = new Element('section'), calls = [], messages = [], imageGuards = [], timers = new Map();
  let active = true, time = 1000000, timerId = 0, detailStarts = 0, backs = 0;
  const document = {createElement: tag => {const element = new Element(tag); element.ownerDocument = document; return element;}, visibilityState: 'visible'};
  container.ownerDocument = document;
  const context = {window: {}, document,
    Date: {now: () => time}, setTimeout: (fn, ms) => {timers.set(++timerId, {fn, ms}); return timerId;},
    clearTimeout: id => timers.delete(id), console};
  vm.createContext(context); vm.runInContext(source, context, {filename: sourcePath});
  const client = context.window.DexHunterReview.mount({container,
    request: async (url, body) => {calls.push({url, body: body === undefined ? undefined : clone(body)}); return clone(await responder(url, body));},
    current: () => active,
    image: (binding, title, guard) => {imageGuards.push(guard); const image = new Element('div'); image.textContent = title; return image;},
    message: (text, error) => messages.push({text, error}), onBack: () => ++backs, onDetailStart: () => ++detailStarts});
  const nodes = () => walk(container), input = label => {
    const wrapper = nodes().find(node => node.tagName === 'LABEL' && node.children.some(child => child.tagName === 'SPAN' && child.textContent === label));
    assert(wrapper, label); return wrapper.children.find(node => node.tagName === 'INPUT');
  };
  const button = label => {const result = nodes().find(node => node.tagName === 'BUTTON' && node.textContent === label); assert(result, label); return result;};
  const submit = () => emit(nodes().find(node => node.tagName === 'FORM'), 'submit');
  const edit = async (label, value) => {const field = input(label); field.value = value; await emit(field, 'input');};
  return {client, container, calls, messages, imageGuards, timers, input, button, submit, edit, nodes, document,
    advance(ms) {time += ms;}, setActive(value) {active = value;}, detailStarts: () => detailStarts, backs: () => backs};
}
const cases = [];
async function check(name, run) {await run(); cases.push({name, status: 'passed'});}
(async () => {
  await check('lot comparison explains overlapping missing-input diagnostics with ordinary text', async () => {
    const value = response();
    value.comparison.comparison_diagnostics = {reasons: ['Loose-lot contents still need review.', 'Tax and other costs remain unknown.']};
    const t = setup(() => value); t.client.open(value);
    assert(t.container.textContent.includes('Loose-lot contents still need review.'));
    assert(t.container.textContent.includes('Tax and other costs remain unknown.'));
    assert.equal(t.calls.length, 0);
  });
  await check('opening review is local and seller text cannot execute markup', async () => {
    const t = setup(() => response()); t.client.open(response());
    assert.equal(t.calls.length, 0); assert(t.container.textContent.includes('<img src=x onerror=alert(1)>'));
    assert(t.container.textContent.includes('<script>never execute</script>'));
    assert(t.container.textContent.includes('Listing stock: 99')); assert(t.container.textContent.includes('Lot units: 3'));
    assert.equal(t.input('Included cards inside this one lot').value, 2);
    assert.equal(t.detailStarts(), 0);
  });
  await check('unknown remainder and inherited seller conflict keys are preserved', async () => {
    const t = setup((url, body) => body ? response({revision: 2}) : response()); t.client.open(response()); await t.submit();
    assert.equal(t.calls[0].body.unknown_contents, null);
    assert.deepEqual(t.calls[0].body.cards, [{printing_id: identity.id, quantity: 2}]);
  });
  await check('explicit zero remainder is sent as zero without resolving attributes', async () => {
    const t = setup(() => response({revision: 2})); t.client.open(response());
    await t.edit('Unresolved remainder (blank means Unknown; 0 confirms no remaining cards)', '0'); await t.submit();
    assert.equal(t.calls[0].body.unknown_contents, 0); assert(!('condition' in t.calls[0].body.cards[0]));
  });
  await check('only edited relevant attribute is supplied for seller conflict correction', async () => {
    const t = setup(() => response({revision: 2})); t.client.open(response());
    await t.edit('Condition claim', 'LP'); await t.submit();
    assert.deepEqual(t.calls[0].body.cards[0], {printing_id: identity.id, quantity: 2, condition: 'LP'});
  });
  await check('explicit confirmation supports correcting unchanged inherited values', async () => {
    const t = setup(() => response({revision: 2})); t.client.open(response());
    await t.button('Confirm my condition claim').click(); await t.submit();
    assert.equal(t.calls[0].body.cards[0].condition, 'Near Mint'); assert(!('language' in t.calls[0].body.cards[0]));
  });
  await check('server correction provenance survives reopening and reference reads', async () => {
    const initial = response({correction_contract: {explicit_card_attributes: {[identity.id]: ['condition']}}});
    const t = setup(() => initial); t.client.open(initial); await t.client.refresh(); await t.submit();
    assert.equal(t.calls[1].body.cards[0].condition, 'Near Mint'); assert(!('grade' in t.calls[1].body.cards[0]));
  });
  await check('every changed input removes visible old reference derivatives immediately', async () => {
    const t = setup(() => response()); t.client.open(response()); assert(t.container.textContent.includes('20.00 USD'));
    await t.edit('Included cards inside this one lot', '3'); assert(!t.container.textContent.includes('20.00 USD'));
    assert(t.container.textContent.includes('Inputs changed.')); assert.equal(t.calls.length, 0);
  });
  await check('repeated Compare clicks create one correction request', async () => {
    const gate = deferred(), t = setup(() => gate.promise); t.client.open(response());
    const first = t.submit(); await t.submit(); assert.equal(t.calls.length, 1);
    gate.resolve(response({revision: 2})); await first; assert.equal(t.calls.length, 1);
  });
  await check('inputs changed during pending correction never display its obsolete comparison', async () => {
    const gate = deferred(), t = setup(() => gate.promise); t.client.open(response());
    await t.edit('Included cards inside this one lot', '3'); const first = t.submit();
    await t.edit('Included cards inside this one lot', '4'); gate.resolve(response({revision: 2})); await first;
    assert.equal(t.input('Included cards inside this one lot').value, '4'); assert(!t.container.textContent.includes('20.00 USD'));
    assert(t.client.isDirty());
  });
  await check('stale revision reloads once and never retries a correction automatically', async () => {
    const t = setup((url, body) => {if (body) {const error = Error('Lot review changed; reload before correcting'); error.status = 409; throw error;} return response({revision: 7});});
    t.client.open(response()); await t.edit('Included cards inside this one lot', '8'); await t.submit();
    assert.equal(t.calls.length, 2); assert(t.calls[0].body); assert.equal(t.calls[1].body, undefined);
    assert.equal(t.input('Included cards inside this one lot').value, 2); assert(t.container.textContent.includes('Current revision reloaded'));
    await t.submit(); assert.equal(t.calls[2].body.revision, 7);
  });
  await check('parent Stop invalidates late corrections and image callbacks', async () => {
    const gate = deferred(), t = setup(() => gate.promise); t.client.open(response()); const first = t.submit();
    const guard = t.imageGuards[0]; assert(guard()); t.client.clear(); assert(!guard());
    gate.resolve(response({revision: 2})); await first; assert.equal(t.container.children.length, 0); assert(!t.client.hasReview());
  });
  await check('authority change rejects late lifecycle read', async () => {
    const gate = deferred(), t = setup(() => gate.promise); t.client.open(response()); const first = t.client.refresh();
    t.setActive(false); t.client.clear(); gate.resolve(response()); await first;
    assert.equal(t.container.children.length, 0);
  });
  await check('obsolete detached controls cannot edit a newer review', async () => {
    const t = setup(() => response()); t.client.open(response()); const old = t.input('Included cards inside this one lot');
    t.client.open(response({review_id: 'new-review'})); old.value = '99'; await emit(old, 'input');
    assert.equal(t.input('Included cards inside this one lot').value, 2); assert(!t.client.isDirty());
  });
  await check('reference withdrawal removes old subtotal and references', async () => {
    const withdrawn = response(); withdrawn.comparison.result.known_selected_subtotal = null;
    withdrawn.comparison.priced_card_quantity = 0; withdrawn.comparison.unpriced_card_quantity = 2;
    withdrawn.comparison.references = [];
    const t = setup(() => withdrawn); t.client.open(response()); await t.client.refresh();
    assert(!t.container.textContent.includes('20.00 USD')); assert(!t.container.textContent.includes('10.00 USD'));
    assert(t.container.textContent.includes('0 priced cards'));
  });
  await check('tab resumption withholds previous reference values before awaiting read', async () => {
    const gate = deferred(), t = setup(() => gate.promise); t.client.open(response());
    t.client.withhold(); assert(!t.container.textContent.includes('20.00 USD'));
    const read = t.client.refresh(); assert(!t.container.textContent.includes('10.00 USD'));
    assert(t.container.textContent.includes('Checking current local references'));
    gate.resolve(response()); await read; assert(t.container.textContent.includes('20.00 USD'));
    await t.edit('Included cards inside this one lot', '4'); t.client.withhold();
    assert(t.container.textContent.includes('Inputs changed.')); assert(!t.container.textContent.includes('20.00 USD'));
  });
  await check('read failure clears references while retaining unsaved corrections', async () => {
    const t = setup(() => {throw Error('Offline fixture');}); t.client.open(response());
    await t.edit('Included cards inside this one lot', '7'); await t.client.refresh();
    assert(!t.container.textContent.includes('20.00 USD')); assert.equal(t.input('Included cards inside this one lot').value, '7');
  });
  await check('expired source clears content and refresh does not renew original lease', async () => {
    const t = setup(() => response({expires_in_seconds: 1800})); t.client.open(response({expires_in_seconds: 1}));
    t.advance(500); await t.client.refresh(); t.advance(501);
    const expiry = [...t.timers.values()].find(timer => timer.ms < 1000); assert(expiry); expiry.fn();
    assert(!t.client.hasReview()); assert.equal(t.container.children.length, 0);
  });
  await check('quantity bounds fail before POST and preserve editable inputs', async () => {
    const t = setup(() => response()); t.client.open(response()); await t.edit('Included cards inside this one lot', '1.5'); await t.submit();
    assert.equal(t.calls.length, 0); assert(t.container.textContent.includes('Use whole quantities'));
  });
  await check('additional details require separate explicit control and Back clears data', async () => {
    const t = setup(() => response()); t.client.open(response()); await t.button('Additional official details…').click();
    assert.equal(t.detailStarts(), 1); assert.equal(t.calls.length, 0); await t.button('Back to Hunt results').click();
    assert.equal(t.backs(), 1); assert(!t.client.hasReview()); assert.equal(t.container.children.length, 0);
  });
  await check('obsolete local search results cannot return after its query changes', async () => {
    const gate = deferred(), t = setup(() => gate.promise); t.client.open(response());
    const query = t.nodes().find(node => node.type === 'search'); query.value = 'first';
    const first = t.button('Find local printings').click(); query.value = 'changed'; await emit(query, 'input');
    gate.resolve({cards: [{...identity, name: 'Obsolete search printing'}], total: 1}); await first;
    assert(!t.container.textContent.includes('Obsolete search printing')); assert.equal(t.calls.length, 1);
    assert(t.calls[0].url.startsWith('/api/shopping/hunter/catalog/'));
  });
  await check('repeated seller mentions never multiply an already included printing', async () => {
    const t = setup(() => response()); t.client.open(response());
    const choice = t.nodes().find(node => node.tagName === 'SELECT'); choice.value = identity.id; await emit(choice, 'change');
    await t.button('Include selected printing').click();
    assert.equal(t.input('Included cards inside this one lot').value, 2);
    assert(t.container.textContent.includes('already included')); assert(!t.client.isDirty());
  });
  await check('external review revision preserves keyboard focus on its matching card field', async () => {
    const t = setup(() => response({revision: 7})); t.client.open(response());
    const old = t.input('Condition claim'); old.focus(); await t.client.refresh();
    assert.notEqual(t.input('Condition claim'), old);
    assert.equal(t.document.activeElement, t.input('Condition claim'));
  });
  await check('withholding invalidates pending reference read before tab resumption', async () => {
    const gate = deferred(), t = setup(() => gate.promise); t.client.open(response());
    const read = t.client.refresh(); t.client.withhold(); gate.resolve(response()); await read;
    assert(!t.container.textContent.includes('20.00 USD')); assert(!t.container.textContent.includes('10.00 USD'));
    await t.client.refresh(); assert(t.container.textContent.includes('20.00 USD'));
  });
  await check('setting an included quantity to zero excludes that printing from corrections', async () => {
    const t = setup(() => response({revision: 2})); t.client.open(response());
    await t.edit('Included cards inside this one lot', '0'); await t.submit();
    assert.deepEqual(t.calls[0].body.cards, []);
  });
  assert(!/localStorage|sessionStorage|indexedDB|innerHTML\s*=/.test(source));
  process.stdout.write(JSON.stringify({kind: 'hunter-review-renderer-contracts', engineering_fixtures_only: true,
    customer_root_access: false, provider_operations: 0, passed: cases.length, cases}, null, 2) + '\n');
})().catch(error => {process.stderr.write(error.stack + '\n'); process.exitCode = 1;});
