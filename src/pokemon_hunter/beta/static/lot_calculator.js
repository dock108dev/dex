/* Four independent scenarios. All amounts and eligibility come from the server. */
(() => {
  const $ = id => document.getElementById(id), rows = new Map();
  const columns = [['raw', 'Ungraded'], ['8', 'Grade 8'], ['9', 'Grade 9'], ['10', 'Grade 10']];
  const today = new Intl.DateTimeFormat('en-CA', {timeZone: 'America/New_York', year: 'numeric', month: '2-digit', day: '2-digit'}).format(new Date());
  let offset = 0, total = 0, busy = false, searchVersion = 0, lockWrites = Promise.resolve(), statusTimer;
  const node = (tag, text) => { const n = document.createElement(tag); if (text !== undefined) n.textContent = text; return n; };
  const dollars = v => v === null || v === undefined ? 'Unavailable' : `$${v}`;
  const field = (parent, label, value = '', type = 'text') => {
    const l = node('label', label), i = node('input'); i.type = type; i.value = value;
    l.append(i); parent.append(l); return i;
  };
  function status(message, error = false) {
    clearTimeout(statusTimer); $('status').textContent = message; $('status').setAttribute('role', error ? 'alert' : 'status');
    if (error) $('status').focus();
    else statusTimer = setTimeout(() => { $('status').textContent = ''; }, 5000);
  }
  function details(parent, title, value) {
    const d = node('details'); d.append(node('summary', title), node('pre', JSON.stringify(value, null, 2))); parent.append(d);
  }
  async function request(url, body) {
    const response = await fetch(url, {credentials: 'same-origin', ...(body ? {
      method: 'POST', headers: {'Content-Type': 'application/json', 'X-CSRFToken': $('comparison').querySelector('[name=csrfmiddlewaretoken]').value}, body: JSON.stringify(body)
    } : {})});
    if (response.redirected) throw Error('Sign in again to continue. Your entries remain here.');
    if (!response.headers.get('content-type')?.includes('application/json')) throw Error('The request could not finish. Keep your entries and retry; sign in again if your session has expired.');
    const data = await response.json();
    if (!response.ok) {
      const message = data.message || data.error;
      const generic = !message || message === 'Invalid request. Check the fields and import format.' || message === 'Invalid request field types';
      throw Error(generic ? 'Check card quantities, USD amounts, dates and the listing URL. Your entries remain here.' : message);
    }
    return data;
  }
  function updateLot() {
    const included = [...rows.values()].reduce((sum, r) => sum + (Number(r.q.value) || 0), 0);
    const wanted = [...rows.values()].filter(r => r.lock.checked).length;
    $('lot-count').textContent = rows.size === 0 ? '' : `${rows.size} card ${rows.size === 1 ? 'type' : 'types'} · ${included} included${wanted ? ` · ${wanted} locked` : ''}`;
    $('empty-lot').hidden = rows.size > 0;
  }
  function invalidate() {
    if ($('captured-lot')) return;
    const hadResults = !$('results').hidden;
    $('results').hidden = true;
    if (hadResults) $('compare-note').textContent = 'Inputs changed. Compare again to update the totals.';
    updateLot();
  }
  function render(payload) {
    $('summary').replaceChildren(); $('results').hidden = false;
    if ($('compare-note')) $('compare-note').textContent = 'Only included quantities count.';
    for (const [key, title] of columns) {
      const r = payload.scenarios[key].result, c = r.comparisons.listing_observation, b = r.comparisons.planned_bid;
      const n = node('div'); n.className = 'scenario'; n.dataset.scenario = key;
      const coverage = node('p', `${r.selected_status === 'full' ? 'Total' : r.selected_status === 'partial' ? 'Partial subtotal' : 'Unavailable'} · ${r.coverage.priced_units} of ${r.coverage.selected_units} units priced`);
      coverage.className = 'coverage-note';
      const difference = node('div'); difference.className = 'difference';
      difference.append(node('span', `${r.selected_status === 'full' ? 'Difference' : 'Partial difference'} vs lot price`), node('strong', dollars(c.full_selected_reference_minus_base_price ?? c.known_selected_reference_minus_base_price)));
      n.append(node('h3', title), node('strong', dollars(r.full_selected_total ?? r.known_selected_subtotal)), coverage, difference);
      const d = node('details');
      d.append(node('summary', 'Costs and bid'), node('p', `Lot price: ${dollars(c.base_price)}`), node('p', `Delivered cost: ${dollars(c.full_delivered_cost)}`),
        node('p', `Full delivered difference: ${dollars(c.full_selected_reference_minus_delivered_cost)}`), node('p', `Missing costs: ${c.unknown_or_ineligible_components.join(', ') || 'None'}`),
        node('p', `Planned bid: ${dollars(b.base_price)}`), node('p', `Difference vs planned bid: ${dollars(b.full_selected_reference_minus_base_price ?? b.known_selected_reference_minus_base_price)}`),
        node('p', `Planned delivered cost: ${dollars(b.full_delivered_cost)}`));
      n.append(d); $('summary').append(n);
    }
    if ($('captured-lot')) {
      for (const c of payload.context.cards) {
        const box = node('div'); box.className = 'selection';
        box.append(node('h3', `${c.captured_identity.name} · ${c.captured_identity.set_name} #${c.captured_identity.collector_number} × ${c.quantity}`));
        const grid = node('div'); grid.className = 'value-columns';
        for (const [g, title] of columns) {
          const ref = payload.scenarios[g].references.find(r => r.printing_id === c.printing_id || r.reference_id === c.printing_id + ':' + g), cell = node('div'); cell.className = 'value-cell';
          cell.append(node('h4', title), node('strong', ref ? dollars(ref.amount) : 'No price'));
          if (ref) cell.append(node('p', `Per card · ${ref.as_of} · ${ref.grader || 'No certified grader'}`), node('p', ref.provenance));
          grid.append(cell);
        }
        box.append(grid); $('captured-rows').append(box);
      }
      details($('captured-rows'), 'Original inputs, results and provenance', payload);
    }
  }
  if ($('captured-lot')) { render(JSON.parse($('captured-lot').textContent)); return; }
  function persistLocks() {
    const wants = [...rows.values()].filter(r => r.lock.checked).map(r => ({printing_id: r.p.id, quantity: Number(r.wanted.value)}));
    const write = lockWrites.catch(() => {}).then(() => request('/api/shopping/wants/', {wants})); lockWrites = write; return write;
  }
  function addCard(p, quantity = 1, wanted = 1, locked = false, restoring = false) {
    if (rows.has(p.id)) { const r = rows.get(p.id); r.q.value = Number(r.q.value) + quantity; invalidate(); status(`${p.name} quantity increased.`); return; }
    const box = node('div'), heading = node('div'), identity = node('div'), controls = node('div');
    box.className = 'selection'; box.dataset.printing = p.id; heading.className = 'selection-heading'; controls.className = 'row-controls';
    const meta = node('p', `${p.set_name} #${p.collector_number}`); meta.className = 'card-meta';
    identity.append(node('h3', p.name), meta);
    const remove = node('button', 'Remove'); remove.type = 'button'; remove.className = 'remove-card'; remove.setAttribute('aria-label', `Remove ${p.name} from this lot`);
    remove.onclick = async () => {
      if (busy) return; const was = lock.checked; lock.checked = false;
      try { await persistLocks(); rows.delete(p.id); box.remove(); invalidate(); status(`${p.name} removed.`); $('query').focus({preventScroll: true}); }
      catch (e) { lock.checked = was; status(e.message, true); }
    };
    heading.append(identity, remove);
    const q = field(controls, 'In this lot', quantity, 'number'), want = field(controls, 'Wanted quantity', wanted, 'number');
    const lock = field(controls, 'Lock wanted card', '', 'checkbox'); lock.parentElement.className = 'lock-control'; lock.checked = locked;
    want.min = '1'; want.max = '100000'; q.min = '0'; q.max = '100000';
    const grid = node('div'); grid.className = 'value-columns'; const values = {}, sources = {};
    for (const [g, title] of columns) {
      const cell = node('div'), guide = p.cells?.[g]; cell.className = 'value-cell';
      const amount = node('strong', guide ? dollars(guide.amount) : 'No price'); if (!guide) amount.className = 'unpriced';
      cell.append(node('h4', title), amount);
      if (guide) cell.append(node('p', `Guide · ${guide.as_of}`));
      values[g] = {mode: guide ? 'guide' : 'none'}; sources[title] = guide || 'No eligible guide for this printing.'; grid.append(cell);
    }
    const sourceDetails = node('details'); sourceDetails.className = 'price-details';
    sourceDetails.append(node('summary', 'Price sources'), node('p', 'Guide values depend on edition and condition. Graded values retain their source’s grader; they do not grade your card.'), node('pre', JSON.stringify(sources, null, 2)));
    box.append(heading, controls, grid, sourceDetails); rows.set(p.id, {p, box, lock, wanted: want, q, values}); $('selections').append(box);
    box.classList.toggle('locked', locked); updateLot();
    lock.onchange = async () => {
      if (busy) return; const selected = lock.checked; lock.disabled = true;
      try { await persistLocks(); box.classList.toggle('locked', selected); updateLot(); status(selected ? 'Wanted card locked for the next lot.' : 'Wanted card unlocked.'); }
      catch (e) { lock.checked = !selected; status(e.message, true); } finally { lock.disabled = false; }
    };
    want.onchange = async () => { if (lock.checked) { try { await persistLocks(); status('Wanted quantity retained.'); } catch (e) { status(e.message, true); } } };
    q.addEventListener('input', invalidate);
    if (!restoring) { invalidate(); status(`${p.name} added to this lot.`); }
  }
  function pagination() { $('previous').disabled = busy || offset === 0; $('next').disabled = busy || offset + 40 >= total; }
  async function browse(reset = true) {
    if (reset) offset = 0; const version = ++searchVersion;
    try {
      const data = await request('/api/shopping/lot-catalog/?' + new URLSearchParams({q: $('query').value, offset: String(offset)}));
      if (version !== searchVersion) return null;
      $('cards').replaceChildren(); total = data.total;
      for (const p of data.cards) {
        const box = node('div'); box.className = 'card';
        const meta = node('p', `${p.set_name} #${p.collector_number} · ${p.copy_count} owned copies`); meta.className = 'card-meta';
        const controls = node('div'); controls.className = 'catalog-actions';
        box.append(node('h3', p.name), meta);
        const q = field(controls, 'Quantity to add', '1', 'number'); q.min = '1'; q.max = '100000'; q.className = 'lookup-quantity';
        const b = node('button', 'Add card'); b.type = 'button'; b.className = 'secondary';
        b.onclick = () => {
          if (!Number.isInteger(Number(q.value)) || Number(q.value) < 1 || Number(q.value) > 100000) { status('Enter a whole quantity from 1 to 100,000.', true); return; }
          addCard(p, Number(q.value));
        };
        controls.append(b); box.append(controls); $('cards').append(box);
      }
      if (!data.cards.length) { const empty = node('p', 'No matching cards. Try a name, set or collector number.'); empty.className = 'catalog-empty'; $('cards').append(empty); }
      $('catalog-count').textContent = `${data.total} vintage ${data.total === 1 ? 'printing' : 'printings'}`; pagination(); return data;
    } catch (e) { if (version === searchVersion) status(e.message, true); return null; }
  }
  const costs = {};
  for (const [key, title] of [['listing_observation', 'Lot delivery costs'], ['planned_bid', 'Personal planned bid']]) {
    const box = node('div'); box.className = 'basis'; box.append(node('h3', title));
    const amount = key === 'listing_observation' ? $('lot-price') : field(box, 'Planned bid, USD');
    const date = field(box, `${title} price date`, today, 'date'), components = {};
    for (const [name, label] of [['shipping', 'Shipping'], ['tax', 'Tax'], ['other_costs', 'Other costs']]) {
      const a = field(box, `${title}: ${label}, USD`); a.inputMode = 'decimal'; a.placeholder = 'Unknown; 0 only if known'; components[name] = a;
    }
    costs[key] = {amount, date, components}; $('costs').append(box);
  }
  function inputs() {
    return {cards: [...rows.values()].filter(r => Number(r.q.value) !== 0).map(r => ({printing_id: r.p.id, quantity: Number(r.q.value), values: Object.fromEntries(columns.map(([g]) => [g, {mode: r.values[g].mode}]))})),
      ...Object.fromEntries(Object.entries(costs).map(([key, f]) => [key, {amount: f.amount.value || null, currency: 'USD', status: f.amount.value === '' ? 'unknown' : 'known', date: f.date.value, price_kind: key === 'listing_observation' ? 'current_asking_price' : 'personal_planned_bid', source_url: key === 'listing_observation' ? $('listing-url').value || null : null}])),
      delivery_cost_inputs: Object.fromEntries(Object.entries(costs).map(([key, f]) => [key, Object.fromEntries(Object.entries(f.components).map(([name, a]) => [name, {amount: a.value || null, currency: 'USD', status: a.value === '' ? 'unknown' : 'known', date: f.date.value, notes: 'Manually supplied; independent costs'}]))]))};
  }
  function blocked(value) {
    busy = value; document.querySelectorAll('.lot-calculator button,.lot-calculator input,.lot-calculator select').forEach(n => n.disabled = value);
    if (!value && $('save-lot').dataset.unavailable === 'true') $('save-lot').disabled = true;
    pagination();
  }
  $('save-lot').dataset.unavailable = String($('save-lot').disabled);
  $('comparison').onsubmit = async e => {
    e.preventDefault(); if (busy) return; const control = e.submitter || document.activeElement, save = e.submitter?.value === 'save'; blocked(true);
    try { await lockWrites; const result = await request('/api/shopping/lot-compare/', {inputs: inputs(), save, name: $('comparison-name').value}); render(result); status('Comparison updated.'); if (result.saved_url) location.href = result.saved_url; }
    catch (e) { status(e.message, true); } finally { blocked(false); if ($('status').getAttribute('role') !== 'alert' && control?.isConnected) control.focus({preventScroll: true}); }
  };
  $('clear-lot').onclick = async () => {
    if (busy) return; blocked(true);
    try {
      await persistLocks(); for (const [id, r] of rows) { if (!r.lock.checked) { r.box.remove(); rows.delete(id); } else r.q.value = 0; }
      for (const f of Object.values(costs)) { f.amount.value = ''; f.date.value = today; for (const a of Object.values(f.components)) a.value = ''; }
      $('listing-url').value = ''; $('comparison-name').value = ''; $('query').value = ''; $('compare-note').textContent = 'Only included quantities count.';
      invalidate(); status('Lot cleared. Locked wants remain; no cards are included.'); await browse();
    } catch (e) { status(e.message, true); } finally { blocked(false); if ($('status').getAttribute('role') !== 'alert') $('clear-lot').focus({preventScroll: true}); }
  };
  document.querySelector('.lot-calculator').addEventListener('input', e => {
    if (e.target.closest('#comparison') || e.target.closest('#costs') || e.target.id === 'listing-url') invalidate();
  });
  document.querySelector('.lot-help-link').onclick = e => {
    e.preventDefault(); $('lot-help').open = true; $('lot-help').scrollIntoView({block: 'center'});
    $('lot-help').querySelector('summary').focus({preventScroll: true});
  };
  $('lookup').onsubmit = async e => {
    e.preventDefault(); const data = await browse();
    if (data && matchMedia('(max-width: 760px)').matches) $('search-matches').scrollIntoView({block: 'start'});
  };
  $('previous').onclick = () => { offset = Math.max(0, offset - 40); browse(false); };
  $('next').onclick = () => { offset += 40; browse(false); };
  async function initialize() {
    blocked(true);
    try {
      const wants = JSON.parse($('wanted-cards').textContent);
      for (const w of wants) {
        const exact = await request('/api/shopping/lot-catalog/?' + new URLSearchParams({printing: w.printing_id})), p = exact.cards.find(p => p.id === w.printing_id);
        if (p) addCard(p, 0, w.quantity, true, true);
        else { addCard({id: w.printing_id, name: 'Unavailable printing', set_name: 'Retained wanted identity', collector_number: 'Unknown', cells: {}}, 0, w.quantity, true, true); status('A retained wanted card has a catalog gap. Its lock remains in this session.', true); }
      }
      await browse(); invalidate();
    } catch (e) { status(e.message, true); } finally { blocked(false); }
  }
  initialize();
})();
