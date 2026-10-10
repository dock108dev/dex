/* Four independent scenarios. All amounts and eligibility come from the server. */
(() => {
  const $ = id => document.getElementById(id), rows = new Map();
  const columns = [['raw', 'Ungraded'], ['8', 'Grade 8'], ['9', 'Grade 9'], ['10', 'Grade 10']];
  const today = new Intl.DateTimeFormat('en-CA', {timeZone: 'America/New_York', year: 'numeric', month: '2-digit', day: '2-digit'}).format(new Date());
  let offset = 0, total = 0, busy = false, searchVersion = 0, lockWrites = Promise.resolve(), statusTimer;
  let missingMode = Boolean($('missing-goal')), missingItem = '';
  const node = (tag, text) => { const n = document.createElement(tag); if (text !== undefined) n.textContent = text; return n; };
  const dollars = v => v === null || v === undefined ? 'Unavailable' : `$${v}`;
  const hasValue = v => v !== null && v !== undefined;
  function printingVariant(p) {
    let variants = [p.variant];
    try {
      const value = JSON.parse(p.variant);
      if (value && typeof value === 'object' && !Array.isArray(value)) variants = Object.values(value).flat();
    } catch { /* Literal variant labels are already readable. */ }
    return [...new Set([p.edition, p.finish, ...variants].filter(Boolean))].join(' · ');
  }
  function priceNotes(sources) {
    const notes = node('div'); notes.className = 'price-notes';
    notes.append(node('p', 'References depend on edition and condition. Graded values retain the source’s grader.'));
    for (const [title, ref] of Object.entries(sources)) {
      if (!hasValue(ref?.amount)) continue;
      notes.append(node('p', ref.date_basis === 'publisher_build'
        ? `${title}: publisher build ${ref.as_of}; provider valuation date unavailable.`
        : `${title}: ${ref.as_of} · ${ref.grader || 'No certified grader'}`));
      if (ref.match_status === 'conditional') notes.append(node('p', ref.assumptions.join(' ')));
      if (ref.source_url) { const link = node('a', `${title} source`); link.href = ref.source_url; link.target = '_blank'; link.rel = 'noopener noreferrer'; notes.append(link); }
    }
    return notes;
  }
  function priceDetails(sources) {
    const d = node('details'); d.className = 'price-details';
    d.append(node('summary', 'Price details'), priceNotes(sources));
    details(d, 'Source record', sources); return d;
  }
  function updatePriceDetails(box, sources) {
    const d = box.querySelector('.price-details'), pre = d.querySelector('pre'), text = JSON.stringify(sources, null, 2);
    if (pre.textContent === text) return;
    d.querySelector('.price-notes').replaceWith(priceNotes(sources)); pre.textContent = text;
  }
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
    document.querySelectorAll('[data-lock-printing]').forEach(b => { b.textContent = rows.get(b.dataset.lockPrinting)?.lock.checked ? 'Locked' : 'Lock'; });
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
      if (key !== 'raw' && r.coverage.priced_units === 0) continue;
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
        const grid = node('div'); grid.className = 'value-columns'; const sources = {};
        for (const [g, title] of columns) {
          const ref = payload.scenarios[g].references.find(r => r.printing_id === c.printing_id || r.reference_id === c.printing_id + ':' + g), cell = node('div'); cell.className = 'value-cell';
          const priced = hasValue(ref?.amount); cell.hidden = g !== 'raw' && !priced;
          cell.append(node('h4', title), node('strong', priced ? dollars(ref.amount) : 'No price'));
          sources[title] = ref || 'No price for this printing.';
          grid.append(cell);
        }
        box.append(grid, priceDetails(sources)); $('captured-rows').append(box);
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
    for (const control of [q, want, lock, remove]) control.disabled = busy;
    want.min = '1'; want.max = '100000'; q.min = '0'; q.max = '100000';
    const grid = node('div'); grid.className = 'value-columns'; const values = {}, sources = {};
    for (const [g, title] of columns) {
      const cell = node('div'), guide = p.cells?.[g]; cell.className = 'value-cell'; cell.dataset.grade = g;
      const priced = hasValue(guide?.amount); cell.hidden = g !== 'raw' && !priced;
      const amount = node('strong', priced ? dollars(guide.amount) : 'No price'); if (!priced) amount.className = 'unpriced';
      cell.append(node('h4', title), amount);
      values[g] = {mode: guide ? 'guide' : 'none'}; sources[title] = guide || p.price_reasons?.[g] || 'Missing snapshot or observation for this printing.'; grid.append(cell);
    }
    const sourceDetails = priceDetails(sources);
    box.append(heading, controls, grid, sourceDetails); rows.set(p.id, {p, box, lock, wanted: want, q, values, sources}); $('selections').append(box);
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
  // Drop current-source values and their displayed derivatives at expiry while keeping inputs and wants.
  setInterval(() => {
    let expired = false;
    for (const r of rows.values()) {
      for (const [g, title] of columns) {
        const guide = r.p.cells?.[g];
        if (guide?.conflicts?.some(c => c.expires_at && Date.parse(c.expires_at) <= Date.now())) {
          guide.conflicts = guide.conflicts.filter(c => !c.expires_at || Date.parse(c.expires_at) > Date.now());
          updatePriceDetails(r.box, r.sources);
        }
        if (!guide?.expires_at || Date.parse(guide.expires_at) > Date.now()) continue;
        delete r.p.cells[g]; r.values[g] = {mode: 'none'}; r.sources[title] = 'Snapshot expired; price removed.';
        const cell = r.box.querySelector(`[data-grade="${g}"]`);
        cell?.replaceChildren(node('h4', title), node('strong', 'No price'));
        if (cell) cell.hidden = g !== 'raw';
        expired = true;
      }
      if (expired) updatePriceDetails(r.box, r.sources);
    }
    if (expired) { $('summary').replaceChildren(); invalidate(); status('Snapshot prices expired and were removed. Your cards, quantities and locks remain.'); }
  }, 1000);
  // Local status only; this never refreshes or acquires provider prices.
  let checkingSources = false;
  setInterval(async () => {
    if (checkingSources || ![...rows.values()].some(r => Object.values(r.p.cells || {}).some(c => c?.snapshot_version))) return;
    checkingSources = true;
    try {
      const state = await request('/api/shopping/price-source-status/'); let removed = false;
      for (const r of rows.values()) {
        for (const [g, title] of columns) {
          const guide = r.p.cells?.[g]; if (!guide?.snapshot_version) continue;
          if (!state.versions.includes(guide.snapshot_version) || !state.sources.includes(guide.source_contract || guide.raw_record?._contract_sha256)) {
            delete r.p.cells[g]; r.values[g] = {mode: 'none'}; r.sources[title] = 'Source removed; review current prices.';
            const cell = r.box.querySelector(`[data-grade="${g}"]`);
            cell?.replaceChildren(node('h4', title), node('strong', 'No price'));
            if (cell) cell.hidden = g !== 'raw';
            removed = true;
          } else if (guide.conflicts) {
            guide.conflicts = guide.conflicts.filter(c => state.sources.includes(c.source_contract));
          }
        }
        updatePriceDetails(r.box, r.sources);
      }
      if (removed) { $('summary').replaceChildren(); invalidate(); status('A price source was removed. Your cards, quantities and locks remain.'); }
    } catch { /* Server unavailable: existing expiry timers still apply. */ }
    finally { checkingSources = false; }
  }, 1000);
  function pagination() { $('previous').disabled = busy || offset === 0; $('next').disabled = busy || offset + 40 >= total; $('previous').parentElement.hidden = total <= 40; }
  async function addAndLock(p, quantity) {
    if (busy) return;
    const existed = rows.has(p.id);
    if (!existed) addCard(p, 0, quantity);
    const r = rows.get(p.id), wasLocked = r.lock.checked, wasWanted = r.wanted.value;
    r.lock.checked = true; r.wanted.value = quantity; r.box.classList.add('locked'); blocked(true);
    try { await persistLocks(); updateLot(); r.box.scrollIntoView({block:'nearest'}); status(`${p.name} locked as wanted. Set “In this lot” when it is included.`); }
    catch (e) {
      if (!existed) { r.box.remove(); rows.delete(p.id); }
      else { r.lock.checked = wasLocked; r.wanted.value = wasWanted; r.box.classList.toggle('locked', wasLocked); }
      updateLot(); status(e.message, true);
    } finally { blocked(false); }
  }
  function missingPicker(items) {
    if (!$('missing-cards')) return;
    $('missing-picker').hidden = !missingMode;
    $('show-missing').setAttribute('aria-pressed', String(missingMode)); $('show-all').setAttribute('aria-pressed', String(!missingMode));
    $('catalog-scope').textContent = missingMode ? 'Choose a missing card, then its printing.' : 'Base Set through Neo Destiny · owned cards included';
    if (missingMode) $('show-missing').textContent = `Missing (${items.length})`;
    $('missing-count').textContent = `${items.length} missing ${items.length === 1 ? 'card' : 'cards'}`;
    $('missing-cards').replaceChildren();
    if (!missingMode) return;
    for (const item of items) {
      const option = node('option', item.label.replace(/^#\d+\s+/, '')); option.value = item.id; $('missing-cards').append(option);
    }
    if (!items.length) $('missing-cards').append(node('option', 'No missing cards'));
    $('missing-cards').value = missingItem;
  }
  async function browse(reset = true) {
    if (reset) offset = 0; const version = ++searchVersion;
    try {
      const data = await request('/api/shopping/lot-catalog/?' + new URLSearchParams({q: $('query').value, offset: String(offset), ...(missingMode ? {goal: $('missing-goal').value, missing_item: missingItem, pick_first: missingItem ? '0' : '1'} : {})}));
      if (version !== searchVersion) return null;
      missingItem = data.selected_missing_item || '';
      missingPicker(data.missing_items);
      $('query').placeholder = 'Search cards';
      $('cards').replaceChildren(); total = data.total;
      const choice = node('select'); choice.setAttribute('aria-label', 'Printing'); choice.id = 'printing-choice';
      for (const p of data.cards) {
        const variant = printingVariant(p), option = node('option', `${p.name} · ${p.set_name} #${p.collector_number}${variant ? ' · ' + variant : ''}`);
        option.value = p.id; choice.append(option);
      }
      const selectedCard = node('div');
      if (data.cards.length) $('cards').append(choice, selectedCard);
      function showPrinting(p) {
        selectedCard.replaceChildren();
        const box = node('div'); box.className = 'card';
        const variant = printingVariant(p);
        const note = [variant, p.copy_count ? p.copy_count + ' owned' : ''].filter(Boolean).join(' · ');
        const meta = node('p', note); meta.className = 'card-meta';
        const controls = node('div'); controls.className = 'catalog-actions';
        if (note) box.append(meta);
        const q = field(controls, 'Qty', '1', 'number'); q.min = '1'; q.max = '100000'; q.className = 'lookup-quantity';
        q.setAttribute('aria-label', `Quantity for ${p.name}`);
        const b = node('button', 'Add'); b.type = 'button'; b.className = 'secondary';
        b.onclick = () => {
          if (!Number.isInteger(Number(q.value)) || Number(q.value) < 1 || Number(q.value) > 100000) { status('Enter a whole quantity from 1 to 100,000.', true); return; }
          addCard(p, Number(q.value));
        };
        const lock = node('button', rows.get(p.id)?.lock.checked ? 'Locked' : 'Lock'); lock.type = 'button'; lock.className = 'secondary'; lock.dataset.lockPrinting = p.id;
        lock.setAttribute('aria-label', `Add and lock ${p.name} ${p.set_name} #${p.collector_number}`);
        lock.onclick = () => {
          if (!Number.isInteger(Number(q.value)) || Number(q.value) < 1 || Number(q.value) > 100000) { status('Enter a whole quantity from 1 to 100,000.', true); return; }
          addAndLock(p, Number(q.value));
        };
        controls.append(b, lock); box.append(controls); selectedCard.append(box);
      }
      choice.onchange = () => showPrinting(data.cards.find(p => p.id === choice.value));
      if (data.cards.length) showPrinting(data.cards[0]);
      else { const empty = node('p', 'No matching cards.'); empty.className = 'catalog-empty'; $('cards').append(empty); }
      $('catalog-count').textContent = `${data.total} ${data.total === 1 ? 'printing' : 'printings'}`; pagination(); return data;
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
  if ($('missing-goal')) {
    $('missing-cards').onchange = () => { missingItem = $('missing-cards').value; $('query').value = ''; browse(); };
    $('missing-goal').onchange = () => { missingItem = ''; $('query').value = ''; browse(); };
    $('show-missing').onclick = () => { missingMode = true; missingItem = ''; $('query').value = ''; browse(); };
    $('show-all').onclick = () => { missingMode = false; missingItem = ''; $('query').value = ''; browse(); };
  }
  async function initialize() {
    blocked(true);
    try {
      const wants = JSON.parse($('wanted-cards').textContent);
      const wantedCards = wants.length ? (await request('/api/shopping/lot-catalog/?wanted=1')).cards : [];
      for (const w of wants) {
        const p = wantedCards.find(p => p.id === w.printing_id);
        if (p) addCard(p, 0, w.quantity, true, true);
        else { addCard({id: w.printing_id, name: 'Unavailable printing', set_name: 'Retained wanted identity', collector_number: 'Unknown', cells: {}}, 0, w.quantity, true, true); status('A retained wanted card has a catalog gap. Its lock remains in this session.', true); }
      }
      await browse(); invalidate();
    } catch (e) { status(e.message, true); } finally { blocked(false); }
  }
  initialize();
})();
