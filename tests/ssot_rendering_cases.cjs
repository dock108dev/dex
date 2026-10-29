'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const root = process.argv[2];
const script = name => fs.readFileSync(path.join(root, 'src/pokemon_hunter/beta/static', name), 'utf8');
const collection = script('collection.js');
const render = collection.slice(collection.indexOf('async function render()'), collection.indexOf('function renderCollection()'));
assert.ok(render.startsWith('async function render()'));

function setup(route) {
  const calls = [];
  const context = {
    window: {}, location: {pathname: route},
    renderCollection: () => calls.push('copies'),
    renderGoals: () => calls.push('goals'),
    renderDeclaration: () => calls.push('declarations'),
    renderSettings: () => calls.push('settings'),
  };
  vm.createContext(context);
  vm.runInContext(render, context);
  return {context, calls};
}

(async () => {
  const cases = [];
  async function check(name, test) { await test(); cases.push(name); }
  await check('initial refresh waits until all deferred renderer scripts have executed', async () => {
    const calls = [], listeners = [];
    const start = collection.lastIndexOf("document.querySelectorAll('[data-close]')");
    assert.ok(start >= 0);
    const context = {
      document: {
        readyState: 'interactive',
        querySelectorAll: () => [],
        addEventListener: (type, callback, options) => listeners.push({type, callback, options}),
      },
      refresh: () => {calls.push('refresh'); return Promise.resolve();},
      recoverPendingOperation: () => calls.push('recover'),
    };
    vm.createContext(context);
    vm.runInContext(collection.slice(start), context);
    assert.deepEqual(calls, [], 'A fast API response must not outrun deferred renderers');
    assert.equal(listeners.length, 1);
    assert.equal(listeners[0].type, 'DOMContentLoaded');
    assert.equal(listeners[0].options.once, true);
    listeners[0].callback();
    await Promise.resolve();
    assert.deepEqual(calls, ['refresh', 'recover']);
  });
  const routes = [
    ['/pokedex/', 'renderSpeciesScreen'], ['/pokedex/2/', 'renderSpeciesScreen'],
    ['/cards/', 'renderCardScreens'], ['/card-library/', 'renderCardScreens'],
    ['/card-groups/dg1-current/', 'renderCardScreens'],
  ];
  for (const [route, owner] of routes) {
    await check(route + ' delegates only to its required renderer and awaits it', async () => {
      const t = setup(route);
      let finish;
      t.context.window[owner] = value => { t.calls.push(value); return new Promise(resolve => {finish = resolve;}); };
      t.context.window.renderParity = () => {throw Error('alternate renderer');};
      let complete = false;
      const pending = t.context.render().then(() => {complete = true;});
      await Promise.resolve();
      assert.equal(complete, false);
      finish(true); await pending;
      assert.deepEqual(t.calls, [route]);
    });
    for (const failure of ['missing', 'declined', 'rejected']) {
      await check(route + ' fails explicitly when renderer is ' + failure, async () => {
        const t = setup(route);
        if (failure === 'declined') t.context.window[owner] = async () => false;
        if (failure === 'rejected') t.context.window[owner] = async () => {throw Error('read unavailable');};
        t.context.window.renderParity = () => {t.calls.push('alternate'); return true;};
        await assert.rejects(t.context.render(), /screen unavailable|read unavailable/);
        assert.deepEqual(t.calls, []);
      });
    }
  }
  await check('parity refuses all core collection routes', async () => {
    const context = {window: {parityData: {}}, location: {}};
    vm.createContext(context); vm.runInContext(script('parity.js'), context);
    for (const [route] of routes) assert.equal(context.window.renderParity(route), false);
    assert.equal(context.window.renderParity('/cards/legacy-id/'), false);
    for (const name of ['dexView', 'printingRows', 'wirePrintings', 'showSpecies', 'showPrinting', 'printingPage', 'editionDialog']) {
      assert.equal(vm.runInContext('typeof ' + name, context), 'undefined');
    }
    const renderer = context.window.renderParity;
    vm.runInContext(script('pokedex.js'), context);
    assert.equal(context.window.renderParity, renderer);
    for (const name of ['dexChoices', 'indexedCards', 'printingLabel', 'dexScope', 'declaredCards', 'eraOf', 'legacyParityRenderer']) {
      assert.equal(vm.runInContext('typeof ' + name, context), 'undefined');
    }
    assert.equal(typeof context.window.renderSpeciesSourceTools, 'function');
    for (const name of ['dexGoal', 'dexImport', 'dexJsonImport']) assert.equal(typeof context[name], 'function');
  });
  await check('overview ownership requires current effective presence and never uses copy fallback', async () => {
    const context = {window: {parityData: {totals: {total: 42}}}};
    vm.createContext(context); vm.runInContext(script('parity.js'), context);
    assert.equal(vm.runInContext('cardPresent({effective_card_present:false,owned:true})', context), false);
    assert.equal(vm.runInContext('cardPresent({effective_card_present:true,owned:false})', context), true);
    assert.throws(() => vm.runInContext('cardPresent({owned:true})', context), /ownership is unavailable/);
    assert.throws(() => context.window.renderParity('/overview/'), /collection status is unavailable/);
  });
  await check('overview displays effective species counts independently of qualified copies', async () => {
    const content = {innerHTML: ''};
    const context = {
      window: {parityData: {
        totals: {kanto: 42, johto: 0, total: 42, physical_copies: 1, exact_cards: 1, unavailable_species: 250},
        owner_collection: {basis: 'effective-current-collection', kanto: 1, johto: 1, total: 2},
        cards: {current: {supertype: 'Pokémon', rarity: 'Common', effective_card_present: true, owned: false}},
      }}, data: {sets: []}, $: () => content, esc: value => String(value),
    };
    vm.createContext(context); vm.runInContext(script('parity.js'), context);
    vm.runInContext("valueSummary=()=>''", context);
    assert.equal(context.window.renderParity('/overview/'), true);
    assert.match(content.innerHTML, /2 \/ 251/);
    assert.match(content.innerHTML, /1 \/ 1/);
    assert.doesNotMatch(content.innerHTML, /42 \/ 251/);
  });
  for (const route of ['/overview/', '/hunt/', '/missing/', '/finds/']) {
    await check(route + ' retains the supported parity entry', async () => {
      const t = setup(route);
      t.context.window.renderParity = value => {t.calls.push(value); return true;};
      await t.context.render(); assert.deepEqual(t.calls, [route]);
    });
  }
  await check('goals await the bounded renderer without legacy projection', async () => {
    const t = setup('/goals/'); let finish, completed = false;
    t.context.window.renderBoundedGoals = () => new Promise(resolve => {finish = resolve; t.calls.push('bounded goals');});
    const pending = t.context.render().then(() => {completed = true;});
    await Promise.resolve(); assert.equal(completed, false);
    finish(); await pending; assert.deepEqual(t.calls, ['bounded goals']);
  });
  for (const [route, expected] of [['/collection/', ['copies']], ['/settings/', ['settings']]]) {
    await check(route + ' retains supported collection tools', async () => {
      const t = setup(route); await t.context.render(); assert.deepEqual(t.calls, expected);
    });
  }
  console.log(JSON.stringify({passed: cases.length, cases, customer_data: false, provider_calls: 0}));
})().catch(error => {console.error(error); process.exitCode = 1;});
