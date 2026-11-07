'use strict';
/* Local result presentation. Never acquires listings, details, images or prices. */
window.DexLotValues = (() => {
  const number = value => value == null || value === '' || !Number.isFinite(Number(value)) ? null : Number(value);
  const auction = row => row.price_kind === 'current_bid' || row.type === 'auction';
  const references = row => [...(row.lot_value?.references || []),
    ...(row.lot_value?.native_guides || []).flatMap(group => group.references || []),
    ...(row.lot_value?.alternatives || []).flatMap(line => line.alternatives.map(choice => choice.reference).filter(Boolean))];
  function invalidate(row, unavailable) {
    const value = row.lot_value;
    if (!value) return;
    if ((value.references || []).some(unavailable)) {
      Object.assign(value, {subtotal:null,total:null,basis:null,basis_label:null,bid_difference:null,buy_now_difference:null});
      // Summaries retain unit counts per shared lifecycle dependency. Keep unaffected units.
      if (value.priced_coverage) {
        value.priced_coverage = value.priced_coverage.filter(([,ids])=>ids.every(i=>!unavailable(value.references[i])));
        const surviving = new Set(value.priced_coverage.flatMap(([,ids])=>ids));
        value.references = value.references.map((ref,i)=>surviving.has(i) ? ref : {});
      } else value.references = value.references.filter(ref => !unavailable(ref));
      value.cards = (value.cards || []).map(card => card.reference && !unavailable(card.reference) ? card : {...card,reference:null,reference_subtotal:null});
      value.priced_quantity = value.normalized_priced_quantity = value.priced_coverage ? value.priced_coverage.reduce((sum,[n])=>sum+n,0) : value.cards.filter(card => card.reference).reduce((sum,card) => sum + card.quantity,0);
      value.identified_unpriced_quantity = (value.identified_quantity || 0) - value.priced_quantity;
      for (const cost of Object.values(value.benchmark_costs || {})) {cost.difference=null;cost.subtotal_difference=null;}
      if (row.value_order) {
        for (const order of Object.values(row.value_order.lanes)) {order.rank=null;order.combined_rank=null;order.score=null;order.group='unpriced';}
        row.value_order.combined=null;
      }
    }
    value.native_guides = (value.native_guides || []).filter(group => !(group.references || []).some(unavailable));
    value.native_priced_quantity = row.evidence_version ? value.native_guides.reduce((sum,g)=>sum+g.priced_quantity,0) : Array.from(new Map(value.native_guides.flatMap(group => (group.lines || []).map(line => [line.printing_id,line.quantity]))).values()).reduce((sum,count) => sum + count,0);
    if (row.value_order) row.value_order.native = row.value_order.native.filter(order => value.native_guides.some(group => group.cohort === order.cohort));
    for (const line of value.alternatives || []) for (const choice of line.alternatives) if (choice.reference && unavailable(choice.reference)) choice.reference = null;
    if (row.assessment_state === 'ready' && value.total == null && !value.native_guides.some(g=>g.complete)) row.assessment_state='partial';
    value.reason = 'Some references are unavailable. Reload local values; catalog alternatives remain unchanged.';
  }
  function unpack(run) {
    for (const row of run.results || []) {
      const value = row.lot_value;
      if (!value?.cohort_rows) continue;
      for (const [cohort,label,reference_date,date_basis,priced_quantity,subtotal,complete,deps,bid,bin] of value.cohort_rows) {
        value.native_guides.push({cohort,provider:run.cohort_labels[label],reference_date,date_basis,
          priced_quantity,subtotal,complete,total:complete ? subtotal : null,references:deps.map(i=>run.cohort_sources[i])});
        for (const [lane,rank] of [['auction',bid],['buy_it_now',bin]]) {
          if (rank != null) row.value_order.native.push({cohort,lane,rank});
        }
      }
      delete value.cohort_rows;
    }
  }
  const laneFor = mode => mode === 'auction' ? 'auction' : mode === 'buy_now' ? 'buy_it_now' : null;
  const orderFor = (row, mode) => laneFor(mode) ? row.value_order?.lanes?.[laneFor(mode)] : row.value_order?.combined;
  const labels = {complete:'Complete assessments',partial:'Partially assessed',unknown_cost:'Unknown delivered cost',unpriced:'Assessed without a normalized value',unprocessed:'Unprocessed'};
  function select(rows, {hours = '72', mode = 'both', sort = 'value', basis = 'all', now = Date.now()} = {}) {
    const cutoff = now + Math.min(Number(hours) || 72,72) * 3600000;
    const selected = rows.filter(row => {
      const end = Date.parse(row.ends_at);
      const lanes = row.value_order?.lanes;
      const bid = (lanes ? Boolean(lanes.auction) : auction(row)) && Number.isFinite(end) && end > now && end <= cutoff;
      const bin = (lanes ? Boolean(lanes.buy_it_now) : number(row.buy_now_price) !== null) && (!Number.isFinite(end) || end > now);
      return (mode === 'auction' ? bid : mode === 'buy_now' ? bin : bid || bin) &&
        (basis === 'all' || row.lot_value?.basis === basis || basis === 'native' && row.lot_value?.native_guides?.length);
    });
    // Money and tie-breaking are server-owned. No fallback financial ranking.
    return selected.sort((a,b) => {
      if (sort === 'ending') return (Date.parse(a.ends_at) || Infinity) - (Date.parse(b.ends_at) || Infinity);
      const x=orderFor(a,mode),y=orderFor(b,mode), key=laneFor(mode) ? 'rank' : 'combined_rank';
      return ((x?.[key] ?? Infinity) - (y?.[key] ?? Infinity)) || String(a.id || '').localeCompare(String(b.id || ''));
    });
  }
  function groups(rows, {mode = 'both', sort = 'value'} = {}) {
    if (sort === 'native') {
      const cohorts = new Map(), remaining = [];
      for (const row of rows) {
        const lane = laneFor(mode) || (row.value_order?.lanes?.buy_it_now ? 'buy_it_now' : 'auction');
        const orders = (row.value_order?.native || []).filter(o => o.lane === lane && o.rank != null);
        if (!orders.length) remaining.push(row);
        for (const order of orders) {
          const guide = row.lot_value?.native_guides?.find(g => g.cohort === order.cohort);
          if (!guide) continue;
          if (!cohorts.has(order.cohort)) cohorts.set(order.cohort,{key:'native-'+order.cohort,label:`Publisher guide contents · ${guide.provider} · ${guide.reference_date}`,note:'Larger publisher contents sums first within this source/date group. Shipping/tax basis unknown; condition unspecified. This is not best-deal ranking.',items:[]});
          cohorts.get(order.cohort).items.push({row,rank:order.rank});
        }
      }
      return [...[...cohorts.values()].sort((a,b)=>a.key.localeCompare(b.key)).map(g=>({...g,rows:g.items.sort((a,b)=>a.rank-b.rank).map(i=>i.row)})),...(remaining.length ? [{key:'no-native',label:'No compatible publisher guide',rows:remaining}] : [])];
    }
    return Object.entries(labels).map(([key,label]) => ({key,label,rows:rows.filter(r=>(r.assessment_state === 'unprocessed' ? 'unprocessed' : orderFor(r,mode)?.group || 'unpriced')===key)})).filter(g=>g.rows.length);
  }
  function progress(run) {
    const states = {queued:'Hunt queued',discovering:'Discovering offers',fetching_details:'Fetching selected seller details',assessing:'Assessing supplied contents',success:'Assessment complete',partial:'Hunt finished with limited coverage',busy:'Dex is busy; this Hunt did not start',exhausted:'Available capacity is exhausted',failed:'Hunt ended after a failure',stopped:'Hunt stopped; results cleared',expired:'Temporary results expired',conflict:'The account, catalog or contents changed',unauthorized:'This session is no longer authorized',restart_uncertain:'Worker state is unavailable after restart; no requests were replayed'};
    const reasons = {candidate_limit:'Only one detail slot per lane is available; other summaries were not assessed',summary_request_failed:'A search page failed',detail_request_failed:'Selected seller details could not be fetched',assessment_unavailable:'Supplied contents could not be assessed',contents_or_references_unavailable:'Some supplied contents or admitted references are unavailable',current_assessment_unavailable:'Some current references are unavailable'};
    const p=run.progress || {}, n=k=>p[k] ?? 0;
    const recovery=run.running ? 'Stop prevents later requests.' : ['stopped','expired','conflict','restart_uncertain','busy','exhausted','failed'].includes(run.state) ? 'A new Find lots action requires remaining permitted capacity. Reads do not retry or restore work.' : 'No automatic retries or further detail requests.';
    return `${states[run.state] || 'Hunt status unavailable'}. ${n('searched')}/2 pages searched · ${n('received')} summaries received · ${n('enriched')}/2 enriched · ${n('assessed')} assessed · ${n('unprocessed')} unprocessed. ${Object.keys(run.reasons || {}).map(k=>reasons[k]).filter(Boolean).join('. ')}${run.error ? '. '+run.error : ''}. ${recovery}`;
  }
  function html(row, {esc, money, link, correction = ''}) {
    const value = row.lot_value;
    if (!value) return `<section class="lot-value"><strong>Ungraded value unavailable</strong><p>${row.evidence_kind === 'seller_details' ? 'Details were fetched; supplied contents could not be assessed.' : 'Full details have not been assessed within this Hunt’s finite allowance.'}</p><p>${esc(row.reason || '')}</p></section>`;
    const basisLabel = ref => ({sold_estimate:'Sold estimate',guide:'Guide',publisher_native_guide:'Publisher-native guide'})[ref?.basis] || 'Guide';
    const count = n => esc(n ?? 'Unknown');
    const native = (value.native_guides || []).map(group => `<section class="native-guide"><strong>${esc(money(group.total ?? group.subtotal))} publisher guide ${group.complete ? 'total' : 'subtotal · partially assessed'}</strong><p>Shipping/tax basis unknown · condition unspecified · ${count(group.priced_quantity)} physical cards · ${esc(group.provider)} · ${esc(group.date_basis)} ${esc(group.reference_date)}</p><p>Separate source/date group. Guide-content sorting puts larger publisher sums first within this group; it is not best-deal ranking, savings or a bid ceiling.</p></section>`).join('');
    const heading = value.total != null ? `${money(value.total)} ungraded lot value` : value.subtotal != null ? `${money(value.subtotal)} ungraded subtotal · identified cards only` : native ? 'Publisher guide references' : 'Ungraded value unavailable';
    const differences = [['Bid + shipping',value.bid_difference],['Buy It Now + shipping',value.buy_now_difference]].filter(([,v])=>v!=null).map(([label,v])=>`<p class="difference${Number(v)<0?' is-over-reference':''}">${esc(label)}: ${esc(money(Math.abs(Number(v))))} ${Number(v)>=0?'below':'above'} reference · before tax</p>`).join('');
    const partial = value.total == null ? Object.entries(value.benchmark_costs || {}).filter(([,c])=>c.subtotal_difference!=null).map(([lane,c])=>`<p class="partial-difference">Identified-card subtotal minus ${lane==='auction'?'bid':'Buy It Now'} + shipping: ${esc(money(c.subtotal_difference))} before tax. This is not a whole-lot bargain score; the remaining cards are unvalued.</p>`).join('') : '';
    function evidence(ref) {
      if (!ref) return 'Reference unavailable';
      const sample=ref.sample;
      return `${esc(basisLabel(ref))} · ${esc(money(ref.amount))} per card · ${esc(ref.condition || 'condition unspecified')} · ${esc(ref.provider || ref.source || 'Admitted reference')} · reference date ${esc(ref.as_of || 'unknown')} (${esc(ref.date_basis || 'date basis unknown')}) · valuation date ${esc(ref.valuation_as_of || 'unknown')} · publisher build ${esc(ref.publisher_built_at || 'unknown')} · captured ${esc(ref.captured_at || 'unknown')} · expires ${esc(ref.expires_at || 'unknown')}${ref.method ? ' · method '+esc(typeof ref.method==='string'?ref.method:ref.method.method)+' '+esc(ref.method.version || '') : ''}${sample ? ' · '+count(sample.unique_sales)+' comparable sales · effective sample '+count(sample.effective_sample_size)+' · sold '+esc(sample.sold_from)+' through '+esc(sample.sold_through)+' · exclusions: '+esc(Object.entries(sample.excluded || {}).map(([k,v])=>k.replaceAll('_',' ')+': '+v).join(', ') || 'none')+' · observed spread '+esc(JSON.stringify(sample.spread || {}))+' (descriptive, not a lot interval)' : ''}${link(ref.source_url) ? ` · <a href="${esc(link(ref.source_url))}" target="_blank" rel="noopener noreferrer">Source (new tab)</a>` : ''}`;
    }
    const cards = (value.cards || []).map(card=>`<li><strong>${count(card.quantity)} × ${esc(card.name || card.printing_id)} · ${esc(card.set_name || '')} #${esc(card.collector_number || '')}</strong><p>${card.reference_subtotal==null?'Normalized reference unavailable':esc(money(card.reference_subtotal))+' · '+esc(basisLabel(card.reference))}</p><p>${card.reference ? evidence(card.reference) : (value.native_guides || []).flatMap(g=>g.references || []).filter(r=>r.printing_id===card.printing_id).map(evidence).join('</p><p>') || 'No current admitted guide for this physical printing'}</p></li>`).join('');
    const mentions = line => [...(line.mentions || []),...(line.scope_mentions || [])].map(m=>`<blockquote>${esc(m.text || m.quote || '')}<cite>Seller ${esc((m.source_field || '').replaceAll('_',' '))}</cite></blockquote>`).join('');
    const contents = (value.contents || []).map(line=>`<li>${count(line.quantity)} × ${esc(line.name || 'Seller contents')} · ${esc((line.reasons || []).join('; '))}${mentions(line)}${!line.included_quantity ? `<ul>${(line.candidates || []).map(c=>`<li>${esc(c.name)} · ${esc(c.set_name)} #${esc(c.collector_number)} · ${esc(c.language || 'language unknown')} · ${esc(c.edition || 'edition unknown')} · ${esc(c.finish || 'finish unknown')}</li>`).join('')}</ul>` : ''}</li>`).join('');
    const alternatives=(value.alternatives || []).map(line=>`<li>${count(line.quantity)} physical cards · ${line.selected_child_id?'seller-selected variant':'variant unresolved'} · alternatives are not additional cards or an automatic price range<ul>${line.alternatives.map(c=>`<li>${esc(c.name)} · ${esc(c.language || 'language unknown')} · ${esc(c.edition || 'edition unknown')} · ${esc(c.finish || 'finish unknown')} · ${esc(c.variant_label || '')}: ${evidence(c.reference)}</li>`).join('')}</ul></li>`).join('');
    const nativeEvidence=(value.native_guides || []).map(g=>`<li>${esc(g.provider)} · ${esc(g.reference_date)}<ul>${(g.references || []).map(r=>`<li>${esc((value.cards || []).find(c=>c.printing_id===r.printing_id)?.name || r.printing_id)} · ${evidence(r)}</li>`).join('')}</ul></li>`).join('');
    const unmatched = (value.unresolved_contents || []).map(line => `<li>${esc(line.text)} · ${esc(line.reason)}</li>`).join('');
    const seller=Object.entries(value.source_fields || {}).map(([field,text])=>`<p>${esc(value.aspect_names?.[field] || field.replaceAll('_',' '))}</p><blockquote>${esc(text)}</blockquote>`).join('');
    const disclosure = row.evidence_version && !row.evidenceLoaded
      ? '<details class="lot-evidence" data-local-evidence><summary>Cards and value evidence</summary><p role="status">Loading local evidence…</p></details>'
      : `<details class="lot-evidence"><summary>Cards and value evidence</summary><p>Seller assertions are not authentication or a condition guarantee. All supplied cards are considered, including those outside the search target.</p><p>${count(value.parent_identified_quantity)} numbered cards identified · ${count(value.physically_selected_quantity ?? value.identified_quantity)} physically selected · ${count(value.normalized_priced_quantity ?? value.priced_quantity)} normalized-priced · ${count(value.native_priced_quantity)} native-priced · ${count(value.identified_unpriced_quantity)} identified cards without normalized prices · ${count(value.unidentified_quantity)} unresolved physical cards. These measures overlap and must not be added.</p><p>Seller-stated contents ${value.contents_state==='resolved'?'resolved':'unresolved'}. Stock ${count(value.stock_quantity)} · offered lot units ${count(value.lot_units)}; these are not card counts.</p><ul>${cards}</ul><ul>${contents}</ul><ul>${unmatched}</ul><ul>${alternatives}</ul><ul>${nativeEvidence}</ul>${seller}<p>${esc([...(value.gaps || []),...(value.quantity_issues || [])].join(' · '))}</p>${correction}</details>`;
    return `<section class="lot-value"><strong>${esc(heading)}</strong><p>${count(value.priced_quantity)} normalized-priced / ${count(value.stated_quantity)} seller-stated cards · ${count(value.physically_selected_quantity ?? value.identified_quantity)} physical variants selected${value.basis_label?' · '+esc(value.basis_label):''}</p><p>${esc(value.reason || value.gaps?.[0] || 'Current local references are unavailable.')}</p>${differences}${partial}${native}${disclosure}</section>`;
  }
  function costs(row, {esc, money}) {
    const costs=row.lot_value?.benchmark_costs;
    if (costs) return Object.entries(costs).filter(([lane,c])=>c.base!=null || row.value_order?.lanes?.[lane]).map(([lane,c])=>`<div><dt>${lane==='auction'?'Current bid':'Buy It Now'}</dt><dd>${esc(money(c.base))}</dd></div><div><dt>Shipping</dt><dd>${esc(money(c.shipping))}</dd></div><div><dt>${lane==='auction'?'Bid':'Buy It Now'} + shipping · before tax</dt><dd>${esc(money(c.delivered_before_tax))}</dd></div>`).join('');
    return `<div><dt>${auction(row)?'Current bid':'Buy It Now'}</dt><dd>${esc(money(row.listing_price))}</dd></div><div><dt>Shipping</dt><dd>${esc(money(row.shipping))}</dd></div><div><dt>Delivered · before tax</dt><dd>${esc(money(row.delivered_total))}</dd></div>${auction(row)&&row.buy_now_price!=null?`<div><dt>Buy It Now</dt><dd>${esc(money(row.buy_now_price))}</dd></div><div><dt>Buy It Now + shipping · before tax</dt><dd>${esc(money(row.buy_now_delivered_total))}</dd></div>`:''}`;
  }
  return {select, groups, progress, html, costs, references, invalidate, unpack};
})();
