'use strict';
/* Explicit local analysis. Seller text and suggestions remain in temporary memory only. */
(() => {
  const mounted = new WeakSet(), active = new Set();
  function mount(parent, origin, valid) {
    if (mounted.has(parent)) return;
    mounted.add(parent);
    const binding = document.body.dataset.navigationBinding, account = document.body.dataset.navigationAccount;
    const box = document.createElement('section'), start = document.createElement('button'), stop = document.createElement('button'), output = document.createElement('div');
    box.className = 'listing-analysis'; output.className = 'listing-analysis-output';
    const actions = document.createElement('div'); actions.className = 'listing-analysis-actions';
    start.className = 'secondary'; stop.className = 'secondary';
    start.type = stop.type = 'button'; start.textContent = 'Interpret listing with local AI'; stop.textContent = 'Stop analysis'; stop.hidden = true;
    output.setAttribute('role', 'status'); actions.append(start, stop); box.append(actions, output); parent.append(box);
    let job = null, timer = null, epoch = 0, rendered = false;
    const usable = () => parent.isConnected && valid() && !window.navigationAuthorityDiscarded && !window.navigationReauthorizing && document.body.dataset.navigationBinding === binding && document.body.dataset.navigationAccount === account;
    async function request(path, body, keepalive = false) {
      const response = await fetch('/api/listing-interpretation/' + path, {method:body === undefined ? 'GET' : 'POST', credentials:'same-origin', redirect:'error', cache:'no-store', keepalive,
        headers:{'X-Dex-Shopping-Binding':binding, ...(body === undefined ? {} : {'Content-Type':'application/json','X-CSRFToken':document.querySelector('[name=csrfmiddlewaretoken]')?.value || ''})},
        ...(body === undefined ? {} : {body:JSON.stringify(body)})});
      const data = await response.json();
      if (!response.ok) throw Error(data.error || 'Analysis unavailable. Manual review is available.');
      if (data.authority?.binding !== binding || data.authority?.account_id !== account) throw Error('Your session changed.');
      return data;
    }
    function finish() { clearTimeout(timer); active.delete(cancel); start.disabled = false; stop.hidden = true; }
    function cancel() {
      epoch++; rendered = false; finish();
      const old = job; job = null;
      if (old) request(old + '/stop/', {}, true).catch(() => {});
      output.replaceChildren();
    }
    function render(result) {
      output.replaceChildren();
      const title = document.createElement('h4'); title.textContent = 'Review seller claims'; output.append(title);
      const notice = document.createElement('p'); notice.textContent = result.notice; output.append(notice);
      const fields = document.createElement('div'); fields.className = 'listing-analysis-fields'; output.append(fields);
      const readable = value => value.replaceAll('_', ' ').replace(/^./, letter => letter.toUpperCase());
      const original = document.createElement('details'), heading = document.createElement('summary');
      heading.textContent = 'Original seller text'; original.append(heading);
      if (result.listing_id) { const id = document.createElement('p'); id.textContent = 'Listing: ' + result.listing_id; original.append(id); }
      for (const [field, text] of Object.entries(result.source_fields || {})) { const p = document.createElement('p'); p.textContent = field + ': ' + text; original.append(p); }
      for (const fact of result.facts || []) {
        const label = document.createElement('label'), input = document.createElement('input'), quote = document.createElement('p');
        const field = document.createElement('div'); field.className = 'listing-analysis-field';
        label.textContent = readable(fact.field); input.value = fact.value; input.maxLength = 500;
        input.setAttribute('aria-label', 'Review ' + fact.field); label.append(input);
        quote.className = 'listing-analysis-evidence';
        quote.textContent = readable(fact.source) + ': “' + fact.quote + '”'; field.append(label, quote); fields.append(field);
      }
      if (result.warnings?.length) {
        const warnings = document.createElement('ul'); warnings.className = 'listing-analysis-warnings'; warnings.setAttribute('aria-label', 'Review warnings');
        for (const warning of result.warnings) { const item = document.createElement('li'); item.textContent = warning; warnings.append(item); }
        output.append(warnings);
      }
      if (result.unknown_fields?.length) { const missing = document.createElement('p'); missing.textContent = 'Not established: ' + result.unknown_fields.join(', '); output.append(missing); }
      output.append(original);
      for (const match of result.catalog_matches || []) { const p = document.createElement('p'); p.textContent = (match.name || 'Unresolved card') + ': ' + (match.printing_id ? 'local catalog match from seller evidence; verify the printing' : 'printing unresolved') + (match.reasons.length ? ' · ' + match.reasons.join('; ') : ''); output.append(p); }
      const note = document.createElement('p'); note.textContent = 'Edits stay in this temporary review. Your collection and prices are unchanged.'; output.append(note);
    }
    async function poll(token) {
      if (token !== epoch || !usable()) { cancel(); return; }
      try {
        const value = await request(job + '/');
        if (token !== epoch || !usable()) return cancel();
        if (value.state === 'running') { timer = setTimeout(() => poll(token), 700); return; }
        finish();
        if (value.state === 'complete') { if (!rendered) { render(value.result); rendered = true; } }
        else { job = null; output.textContent = value.error || 'Analysis stopped.'; }
      } catch (error) { if (token === epoch) { finish(); job = null; output.textContent = error.message; } }
    }
    start.addEventListener('click', async () => {
      if (!usable()) { cancel(); return; }
      cancel(); const token = epoch; start.disabled = true; stop.hidden = false; active.add(cancel); output.textContent = 'Analyzing existing seller text…';
      try {
        const value = await request('', origin);
        if (token !== epoch || !usable()) { request(value.id + '/stop/', {}, true).catch(() => {}); return; }
        job = value.id; await poll(token);
      } catch (error) { if (token === epoch) { finish(); job = null; output.textContent = error.message; } }
    });
    stop.addEventListener('click', () => { cancel(); output.textContent = 'Analysis stopped.'; start.focus(); });
    // Completed content also expires/revokes; never retain a result after its source lease.
    const observer = setInterval(() => {
      if (!usable()) { cancel(); clearInterval(observer); }
      else if (job && !start.disabled) poll(epoch);
    }, 1500);
  }
  addEventListener('pagehide', () => { for (const cancel of [...active]) cancel(); });
  window.DexInterpretation = {mount};
})();
