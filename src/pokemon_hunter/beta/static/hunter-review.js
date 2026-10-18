/* Leased Hunter lot corrections. No persistence, provider transport or seller HTML. */
(() => {
  'use strict';
  const ATTRIBUTES = ['condition', 'grade', 'grader', 'language', 'edition', 'finish'];
  const COSTS = ['price', 'shipping', 'tax', 'other_costs', 'planned_bid'];
  const LABELS = {
    condition: 'Condition claim', grade: 'Grading claim', grader: 'Grading company claim',
    language: 'Language claim', edition: 'Edition claim', finish: 'Finish claim',
    price: 'Whole-lot asking amount', shipping: 'Shipping', tax: 'Tax',
    other_costs: 'Other costs', planned_bid: 'My planned manual bid',
  };
  const h = (tag, text, className) => {
    const element = document.createElement(tag);
    if (text !== undefined) element.textContent = String(text);
    if (className) element.className = className;
    return element;
  };
  const identityLabel = card => [card?.name || 'Unresolved card', card?.set_name,
    card?.collector_number ? '#' + card.collector_number : '',
    card?.variant_label || card?.attributes?.variant_label || [card?.language, card?.edition, card?.finish, card?.variant].filter(Boolean).join(' / '),
  ].filter(Boolean).join(' · ');
  const money = (amount, currency = 'USD') => amount === null || amount === undefined || amount === '' ? 'Unknown' : amount + ' ' + (currency || 'currency unknown');

  function mount({container, request, current = () => true, image, message = () => {}, onBack, onDetailStart}) {
    let value = null, cards = [], costs = {}, unknown = '', identities = new Map();
    let explicit = new Map(), epoch = 0, editVersion = 0, dirty = false, busy = false;
    let readBusy = false, readTicket = 0, searchTicket = 0, deadline = 0, expiryTimer, readTimer;
    let comparisonArea = null, statusArea = null, form = null, cardArea = null, countArea = null;
    let focusTargets = new Map();
    const alive = expected => expected === epoch && value !== null && current() !== false &&
      Date.now() < deadline && container.isConnected !== false;
    const say = (text, error = false) => {
      if (statusArea) {statusArea.textContent = text; statusArea.setAttribute('role', error ? 'alert' : 'status');}
      message(text, error);
    };
    function clear(reason) {
      ++epoch; ++readTicket; ++searchTicket;
      clearTimeout(expiryTimer); clearTimeout(readTimer);
      value = null; cards = []; costs = {}; unknown = ''; identities.clear(); explicit.clear();
      deadline = 0; dirty = false; busy = false; readBusy = false;
      comparisonArea = null; statusArea = null; form = null; cardArea = null; countArea = null;
      focusTargets.clear();
      container.replaceChildren(); container.hidden = true;
      if (reason) message(reason, true);
    }
    function checkExpiry() {
      if (value && Date.now() >= deadline) clear('This temporary lot review expired. Reopen a current Hunt to continue.');
    }
    function lease(seconds) {
      const incoming = Date.now() + Math.max(0, Number(seconds) || 0) * 1000;
      deadline = deadline ? Math.min(deadline, incoming) : incoming;
      clearTimeout(expiryTimer);
      expiryTimer = setTimeout(checkExpiry, Math.max(0, deadline - Date.now()) + 1);
    }
    function scheduleRead() {
      clearTimeout(readTimer);
      if (!value) return;
      readTimer = setTimeout(async () => {
        if (document.visibilityState !== 'hidden') await refresh();
        scheduleRead();
      }, 10000);
    }
    function invalidate() {
      dirty = true; ++editVersion;
      comparisonArea?.replaceChildren(h('p', 'Inputs changed. Choose Compare corrected contents to update the comparison.', 'notice'));
      updateCount();
    }
    function updateCount() {
      if (!countArea) return;
      const included = cards.reduce((sum, row) => sum + (Number(row.quantity) || 0), 0);
      countArea.textContent = `${included} included cards · Remainder: ${unknown === '' ? 'Unknown' : unknown}. Whole-lot amount counted once.`;
    }
    function withhold() {
      ++readTicket; readBusy = false;
      comparisonArea?.replaceChildren(h('p', dirty ?
        'Inputs changed. Choose Compare corrected contents to update the comparison.' :
        'Checking current local references…', 'notice'));
    }
    function input(parent, label, initial, change, options = {}) {
      const expected = epoch;
      const wrapper = h('label'), caption = h('span', label), element = h('input');
      element.type = options.type || 'text'; element.value = initial ?? '';
      if (options.min !== undefined) element.min = options.min;
      if (options.max !== undefined) element.max = options.max;
      if (options.step !== undefined) element.step = options.step;
      if (options.maxLength !== undefined) element.maxLength = options.maxLength;
      if (options.placeholder) element.placeholder = options.placeholder;
      const focusKey = options.focusKey || label;
      element.setAttribute('data-hunter-review-focus', focusKey); focusTargets.set(focusKey, element);
      wrapper.append(caption, element); parent.append(wrapper);
      element.addEventListener('input', () => {
        if (alive(expected)) {change(element.value); if (options.affectsComparison !== false) invalidate();}
      });
      return element;
    }
    function button(label, action, className = 'secondary') {
      const expected = epoch;
      const element = h('button', label, className); element.type = 'button';
      element.addEventListener('click', event => {if (alive(expected)) return action(event);}); return element;
    }
    function art(parent, card, expected) {
      if (image) {
        const element = image(card?.artwork || card?.image_binding, identityLabel(card), () => alive(expected));
        if (element) parent.append(element);
      } else parent.append(h('div', 'Reference image unavailable', 'hunter-image'));
    }
    function cardTraits(row, parent) {
      const details = h('details', undefined, 'hunter-card-details');
      details.append(h('summary', 'Printing, condition and grading corrections'));
      details.append(h('p', 'Seller claims remain unverified. Only an attribute you explicitly edit or confirm resolves its conflict.'));
      const traits = h('div', undefined, 'hunter-fields');
      const conflicting = new Set((value.proposal?.proposals || []).filter(p =>
        (p.candidates || []).some(candidate => candidate.id === row.printing_id)
      ).flatMap(p => p.conflicting_fields || []));
      for (const key of ATTRIBUTES) {
        const group = h('div');
        const field = input(group, LABELS[key], row[key] ?? (key === 'grade' ? 'raw' : ''), content => {
          row[key] = content;
          if (!explicit.has(row.printing_id)) explicit.set(row.printing_id, new Set());
          explicit.get(row.printing_id).add(key);
          confirmation.textContent = 'Your explicit correction';
        }, {maxLength: 100, focusKey: row.printing_id + ':' + key});
        const confirmation = h('span', explicit.get(row.printing_id)?.has(key) ? 'Your explicit correction' :
          conflicting.has(key) ? 'Seller conflict remains unresolved' : 'Inherited seller claim', 'hunter-attribute-state');
        group.append(confirmation);
        if (conflicting.has(key)) group.append(button('Confirm my ' + LABELS[key].toLowerCase(), () => {
          if (!alive(epoch)) return;
          row[key] = field.value;
          if (!explicit.has(row.printing_id)) explicit.set(row.printing_id, new Set());
          explicit.get(row.printing_id).add(key); confirmation.textContent = 'Your explicit correction'; invalidate();
        }));
        traits.append(group);
      }
      details.append(traits); parent.append(details);
    }
    function renderCards() {
      if (!cardArea || !value) return;
      cardArea.replaceChildren();
      if (!cards.length) cardArea.append(h('p', 'No cards included. Choose a printing and quantity from the proposals, or correct the contents with local card search.'));
      const expected = epoch;
      for (const row of cards) {
        const card = identities.get(row.printing_id) || {id: row.printing_id, name: 'Selected printing ' + row.printing_id};
        const box = h('article', undefined, 'hunter-review-card'), content = h('div', undefined, 'hunter-review-card-content');
        art(box, card, expected);
        content.append(h('h3', identityLabel(card)));
        const fields = h('div', undefined, 'hunter-fields');
        input(fields, 'Included cards inside this one lot', row.quantity, quantity => {row.quantity = quantity;},
          {type: 'number', min: '0', max: '100000', step: '1', focusKey: row.printing_id + ':quantity'});
        content.append(fields); cardTraits(row, content);
        content.append(button('Remove this printing', () => {
          if (!alive(expected)) return;
          cards = cards.filter(cardRow => cardRow !== row); explicit.delete(row.printing_id);
          renderCards(); invalidate(); cardArea.querySelector('input,button')?.focus();
        }));
        box.append(content); cardArea.append(box);
      }
      updateCount();
    }
    function include(card, quantity) {
      if (!alive(epoch)) return false;
      if (!/^\d+$/.test(String(quantity)) || Number(quantity) < 1 || Number(quantity) > 100000) {
        say('Enter the number of cards inside this lot before including this printing.', true); return false;
      }
      if (cards.some(row => row.printing_id === card.id)) {
        say('This printing is already included. Correct its quantity above; repeated mentions do not add more cards.', true); return false;
      }
      identities.set(card.id, card); cards.push({printing_id: card.id, quantity: Number(quantity)});
      explicit.set(card.id, new Set()); renderCards(); invalidate();
      say('Printing included by your decision. Review its quantity, seller conflicts and remainder.'); return true;
    }
    function proposals(parent) {
      const expected = epoch;
      const list = value.proposal?.proposals || [];
      const disclosure = h('details', undefined, 'hunter-proposals');
      disclosure.append(h('summary', 'Seller proposals and printing choices (' + list.length + ')'));
      for (const proposal of list) {
        const box = h('article', undefined, 'hunter-proposal');
        box.append(h('h3', proposal.name || 'Unresolved card identity'));
        box.append(h('p', `Proposed quantity: ${proposal.quantity ?? 'Unknown'} · Automatically included: ${proposal.included_quantity || 0}`));
        for (const reason of proposal.reasons || []) box.append(h('p', reason, 'notice'));
        const choices = proposal.candidates || [], choice = h('select');
        const label = h('label', 'Choose a printing');
        const placeholder = h('option', 'Choose a printing…'); placeholder.value = ''; choice.append(placeholder);
        for (const card of choices) {const option = h('option', identityLabel(card)); option.value = card.id; choice.append(option);}
        label.append(choice); box.append(label);
        const selectedLabel = h('p', 'No printing selected', 'hunter-selected-printing'), preview = h('div');
        box.append(selectedLabel, preview);
        let quantity = proposal.quantity === null || proposal.quantity === undefined ? '' : String(proposal.quantity);
        input(box, 'Cards for this selected printing', quantity, content => {quantity = content;},
          {type: 'number', min: '1', max: '100000', step: '1', affectsComparison: false});
        choice.addEventListener('change', () => {
          if (!alive(expected)) return;
          preview.replaceChildren(); const card = choices.find(candidate => candidate.id === choice.value);
          selectedLabel.textContent = card ? identityLabel(card) : 'No printing selected';
          if (card) art(preview, card, expected);
        });
        const add = button('Include selected printing', () => {
          const card = choices.find(candidate => candidate.id === choice.value);
          if (!card) {say('Choose a printing before including it.', true); choice.focus(); return;}
          include(card, quantity);
        });
        add.disabled = choices.length === 0; box.append(add);
        if ((proposal.candidates_total || 0) > choices.length)
          box.append(h('p', `${proposal.candidates_total} plausible printings; ${choices.length} shown. Use local card search to refine.`));
        const evidence = h('details'); evidence.append(h('summary', 'Seller clues and provenance'));
        for (const mention of proposal.mentions || []) evidence.append(h('p', (mention.source_field || 'Seller text') + ': ' + (mention.text || '')));
        for (const key of ATTRIBUTES) if (proposal.clues?.[key]) evidence.append(h('p', LABELS[key] + ': ' + proposal.clues[key]));
        box.append(evidence); disclosure.append(box);
      }
      for (const row of value.proposal?.unresolved_contents || []) disclosure.append(h('p',
        `Unresolved seller content (${row.source_field || 'summary'}): ${row.text || ''} · Quantity: ${row.quantity ?? 'Unknown'} · ${row.reason || ''}`));
      parent.append(disclosure);
    }
    function search(parent) {
      const expectedSearchView = epoch;
      const details = h('details'), label = h('label', 'Find a card in the local catalog'), query = h('input');
      const results = h('div', undefined, 'hunter-catalog-matches'); query.type = 'search'; query.maxLength = 160;
      label.append(query); details.append(h('summary', 'Correct or add a different card'), label);
      const find = button('Find local printings', async () => {
        if (!alive(epoch)) return;
        const expected = epoch, ticket = ++searchTicket;
        find.disabled = true; results.replaceChildren(h('p', 'Finding local printings…'));
        try {
          const response = await request('/api/shopping/hunter/catalog/?q=' + encodeURIComponent(query.value));
          if (!alive(expected) || ticket !== searchTicket) return;
          results.replaceChildren(h('p', `${response.total ?? response.cards?.length ?? 0} matching printings. Showing at most 40; refine the search if needed.`));
          for (const card of response.cards || []) {
            const box = h('article', undefined, 'hunter-catalog-match'); art(box, card, expected);
            box.append(h('p', identityLabel(card)), button('Include one copy', () => include(card, 1)));
            results.append(box);
          }
        } catch (error) {if (alive(expected) && ticket === searchTicket) results.replaceChildren(h('p', error.message, 'error'));}
        finally {if (alive(expected) && ticket === searchTicket) find.disabled = false;}
      });
      query.addEventListener('input', () => {
        if (!alive(expectedSearchView)) return;
        ++searchTicket; results.replaceChildren(); find.disabled = false;
      });
      query.addEventListener('keydown', event => {if (event.key === 'Enter') {event.preventDefault(); find.click();}});
      details.append(find, results); parent.append(details);
    }
    function comparison() {
      comparisonArea.replaceChildren();
      if (dirty) {comparisonArea.append(h('p', 'Inputs changed. Choose Compare corrected contents to update the comparison.', 'notice')); return;}
      const compared = value.comparison || {}, result = compared.result || {}, observed = result.comparisons?.listing_observation || {};
      comparisonArea.append(h('h3', compared.label || 'Ungraded comparison'),
        h('p', `Priced subtotal: ${money(result.known_selected_subtotal)} · ${compared.priced_card_quantity ?? 0} priced cards · ${compared.unpriced_card_quantity ?? 0} unpriced cards`),
        h('p', `Whole-lot reference total: ${result.full_lot_total == null ? 'Unavailable; incomplete contents or pricing' : money(result.full_lot_total)}`),
        h('p', `Contents reconciled: ${compared.quantities_reconciled ? 'Yes, by review inputs' : 'No'} · Remainder: ${unknown === '' ? 'Unknown' : unknown}`));
      const auction = compared.comparison_kind === 'auction_current_bid_scenario';
      comparisonArea.append(h('p', `${auction ? 'Current bid' : 'Asking amount'}: ${money(observed.base_price)} · Known-cost subtotal: ${money(observed.known_cost_subtotal)} · Complete delivered amount: ${money(observed.full_delivered_cost)}`));
      if (auction) {
        comparisonArea.append(h('p', `Minimum next bid: ${money(compared.minimum_next_bid, compared.minimum_next_bid_currency)} · Final purchase cost: Unknown. Auction values are scenarios, not a recommended maximum bid.`));
        if (compared.buy_now_amount != null) comparisonArea.append(h('p', 'Separate Buy It Now amount: ' + money(compared.buy_now_amount, value.review?.costs?.buy_now_currency)));
      }
      const missing = observed.unknown_or_ineligible_components || [];
      if (missing.length) comparisonArea.append(h('p', 'Missing or ineligible costs: ' + missing.join(', ')));
      if (compared.complete_delivered_comparison)
        comparisonArea.append(h('p', 'Reference minus delivered amount: ' + money(observed.full_selected_reference_minus_delivered_cost)));
      const planned = result.comparisons?.planned_bid;
      if (costs.planned_bid && planned) comparisonArea.append(h('p', `My planned manual bid with delivery: ${money(planned.full_delivered_cost)}. This is a personal scenario; final purchase cost remains unknown.`));
      for (const row of compared.unpriced_matches || []) comparisonArea.append(h('p',
        `${identityLabel(identities.get(row.printing_id))} · ${row.quantity} unpriced: ${row.reason || 'No applicable admitted reference'}`));
      for (const limitation of compared.limitations || []) comparisonArea.append(h('p', limitation));
      for (const reason of compared.comparison_diagnostics?.reasons || []) comparisonArea.append(h('p', reason, 'hunter-comparison-reason'));
      const refs = h('details'); refs.append(h('summary', 'Reference dates, scope and applicability'));
      for (const ref of compared.references || []) refs.append(h('p',
        `${money(ref.amount, ref.currency)} · ${ref.date_basis || 'Reference date'}: ${ref.as_of || 'Unknown'} · Valuation date: ${ref.valuation_as_of || 'Unknown'} · Captured: ${ref.captured_at || 'Unknown'} · Expires: ${ref.expires_at || 'Unknown'} · ${ref.condition || 'Condition unknown'} · ${ref.language || 'Language unknown'} · ${ref.edition || 'Edition unknown'} · ${ref.finish || 'Finish unknown'} · Conditional physical applicability`));
      if (!(compared.references || []).length) refs.append(h('p', 'No applicable admitted references.'));
      comparisonArea.append(refs);
    }
    function payload() {
      const selected = cards.map(row => {
        if (!/^\d+$/.test(String(row.quantity)) || Number(row.quantity) > 100000) throw Error('Use whole quantities from 0 to 100000.');
        const output = {printing_id: row.printing_id, quantity: Number(row.quantity)};
        for (const key of explicit.get(row.printing_id) || []) if (ATTRIBUTES.includes(key)) output[key] = row[key] ?? '';
        return output;
      }).filter(row => row.quantity > 0);
      if (unknown !== '' && (!/^\d+$/.test(String(unknown)) || Number(unknown) > 100000))
        throw Error('Leave the remainder blank for Unknown, or enter a whole quantity from 0 to 100000.');
      const remainder = unknown === '' ? null : Number(unknown);
      if (selected.reduce((sum, row) => sum + row.quantity, 0) + (remainder || 0) > 100000)
        throw Error('Included cards and remainder must total at most 100000.');
      return {revision: value.revision, cards: selected, unknown_contents: remainder,
        costs: Object.fromEntries(COSTS.map(key => [key, costs[key] ?? '']))};
    }
    async function submit(event) {
      event?.preventDefault(); if (busy || !alive(epoch)) return;
      let data; try {data = payload();} catch (error) {say(error.message, true); return;}
      const expected = epoch, version = editVersion, reviewId = value.review_id;
      busy = true; form.querySelector('button[type="submit"]').disabled = true;
      say('Comparing corrected contents with admitted local references…');
      try {
        const response = await request('/api/shopping/hunter/lot-review/' + encodeURIComponent(reviewId) + '/', data);
        if (!alive(expected)) return;
        if (version !== editVersion) {
          value.revision = response.revision; lease(response.expires_in_seconds);
          say('Newer edits remain un-compared. Choose Compare corrected contents when ready.'); return;
        }
        apply(response, false); say('Comparison updated. Corrections are your decisions; seller contents remain unverified.');
      } catch (error) {
        if (!alive(expected)) return;
        comparisonArea.replaceChildren();
        if (error.status === 409 || /review changed|revision|reload before correcting/i.test(error.message)) {
          await refresh(true);
          if (alive(expected)) say('The review changed. Current revision reloaded; review your corrections before comparing again.', true);
        } else if ([401, 403, 404, 410].includes(error.status)) clear('The temporary review is no longer available. Reopen a current Hunt.');
        else say(error.message, true);
      } finally {
        if (alive(expected)) {busy = false; const submitButton = form?.querySelector('button[type="submit"]'); if (submitButton) submitButton.disabled = false;}
      }
    }
    function render(focus) {
      const expected = epoch; focusTargets = new Map(); container.replaceChildren(); container.hidden = false;
      const heading = h('h2', 'Review lot · Ungraded'); heading.tabIndex = -1;
      const back = button('Back to Hunt results', () => {if (!alive(expected)) return; clear(); onBack?.();});
      back.id = 'hunter-back';
      statusArea = h('p', undefined, 'hunter-review-status'); statusArea.setAttribute('aria-live', 'polite');
      container.append(back, heading, h('p', 'Correct the included cards and quantities. Reference scans do not verify seller contents.'), statusArea);
      const proposal = value.proposal || {};
      container.append(h('p', `Seller-stated total: ${proposal.seller_stated_total ?? 'Unknown'} · Listing stock: ${proposal.stock_quantity ?? 'Unknown'} · Lot units: ${proposal.lot_units ?? 'Unknown'}. Stock and lot units do not multiply the card quantities.`));
      for (const issue of proposal.quantity_issues || []) container.append(h('p', issue, 'notice'));
      form = h('form', undefined, 'hunter-review-form');
      form.addEventListener('submit', event => {
        event.preventDefault(); if (alive(expected) && event.currentTarget === form) return submit(event);
      });
      cardArea = h('div', undefined, 'hunter-review-cards'); countArea = h('p', undefined, 'hunter-review-count');
      form.append(cardArea, countArea);
      input(form, 'Unresolved remainder (blank means Unknown; 0 confirms no remaining cards)', unknown,
        remainder => {unknown = remainder;}, {type: 'number', min: '0', max: '100000', step: '1'});
      const costDetails = h('details'); costDetails.append(h('summary', 'Whole-lot amount and optional costs'));
      costDetails.append(h('p', 'Blank costs remain unknown. Enter 0 only when you know the cost is zero. All correction amounts use the captured listing currency: ' + (value.review?.costs?.currency || 'Unknown') + '.'));
      const costGrid = h('div', undefined, 'hunter-fields');
      for (const key of COSTS) input(costGrid,
        key === 'price' && value.review?.costs?.price_kind === 'current_bid' ? 'Whole-lot current bid scenario' : LABELS[key],
        costs[key], content => {costs[key] = content;}, {maxLength: 32, placeholder: 'Unknown'});
      costDetails.append(costGrid); form.append(costDetails);
      const compare = h('button', 'Compare corrected contents'); compare.type = 'submit'; compare.disabled = busy;
      compare.id = 'hunter-review-compare';
      compare.setAttribute('data-hunter-review-focus', 'compare'); focusTargets.set('compare', compare);
      form.append(compare); container.append(form);
      comparisonArea = h('section', undefined, 'hunter-review-comparison'); comparisonArea.setAttribute('aria-live', 'polite');
      container.append(comparisonArea); renderCards(); comparison(); proposals(container); search(container);
      const provenance = h('details'); provenance.append(h('summary', 'Temporary review provenance'));
      provenance.append(h('p', `Source: ${value.provenance?.source === 'authorized_official_detail' ? 'Explicit official details' : 'Already received listing summary'} · Official details fetched: ${value.provenance?.detail_fetched ? 'Yes' : 'No'} · Review revision: ${value.revision}`),
        h('p', 'Reviewing, correcting and returning do not renew the original Hunt lease. No contents or comparison are saved to your collection.'));
      container.append(provenance);
      if (onDetailStart && value.provenance?.origin) container.append(button('Additional official details…', () => {
        if (!alive(expected)) return;
        onDetailStart({runId: value.provenance.origin.run_id, resultIds: [value.provenance.origin.result_id]});
      }));
      if (focus) heading.focus();
    }
    function apply(response, focus) {
      const focused = document.activeElement;
      const focusedKey = !focus && container.contains?.(focused) ? focused?.getAttribute?.('data-hunter-review-focus') : null;
      value = response; lease(response.expires_in_seconds);
      if (Date.now() >= deadline) {checkExpiry(); return;}
      cards = (response.review?.cards || []).map(row => ({...row}));
      costs = Object.fromEntries(COSTS.map(key => [key, response.review?.costs?.[key] ?? '']));
      unknown = response.review?.unknown_contents === null || response.review?.unknown_contents === undefined ? '' : String(response.review.unknown_contents);
      explicit = new Map(Object.entries(response.correction_contract?.explicit_card_attributes || {}).map(([id, keys]) => [id, new Set(keys.filter(key => ATTRIBUTES.includes(key)))]));
      identities = new Map((response.review?.card_identities || []).map(card => [card.id, card]));
      for (const proposal of response.proposal?.proposals || []) for (const card of proposal.candidates || [])
        if (!identities.has(card.id)) identities.set(card.id, card);
      dirty = false; render(focus);
      if (document.visibilityState === 'hidden') withhold();
      if (focusedKey) (focusTargets.get(focusedKey) || focusTargets.get('compare'))?.focus({preventScroll: true});
    }
    function open(response) {
      clear(); if (current() === false || !response?.review_id) return;
      ++epoch; apply(response, true); scheduleRead();
    }
    async function refresh(force = false) {
      if (!value || !alive(epoch) || ((readBusy || busy) && !force)) return;
      withhold();
      const expected = epoch, ticket = ++readTicket, reviewId = value.review_id;
      readBusy = true;
      try {
        const response = await request('/api/shopping/hunter/lot-review/' + encodeURIComponent(reviewId) + '/');
        if (!alive(expected) || ticket !== readTicket) return;
        lease(response.expires_in_seconds);
        if (Date.now() >= deadline) {checkExpiry(); return;}
        if (force || response.revision !== value.revision) {
          apply(response, false);
          if (!force) say('Current review revision loaded. Review its contents before further corrections.');
        } else {
          value.comparison = response.comparison;
          if (!dirty) comparison();
        }
      } catch (error) {
        if (!alive(expected) || ticket !== readTicket) return;
        comparisonArea?.replaceChildren();
        if ([401, 403, 404, 410].includes(error.status)) clear('The temporary review is no longer available. Reopen a current Hunt.');
        else say('Current references could not be checked. Comparison cleared. ' + error.message, true);
      } finally {if (expected === epoch && ticket === readTicket) readBusy = false;}
    }
    return {open, refresh, clear, withhold, hasReview: () => value !== null, isDirty: () => dirty};
  }
  window.DexHunterReview = {mount};
})();
