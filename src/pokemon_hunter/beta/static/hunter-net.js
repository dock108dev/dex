'use strict';
/* Local USD resale scenario. No prices, listings or calculations are persisted. */
window.DexHunterNet = (() => {
  function cents(value) {
    if (typeof value !== 'string' && typeof value !== 'number') return null;
    if (!/^\d+(?:\.\d{1,2})?$/.test(String(value))) return null;
    const n = Math.round(Number(value) * 100);
    return Number.isSafeInteger(n) && n <= 100000000 ? n : null;
  }
  function rate(value) {const n=cents(value);return n !== null && n <= 10000 ? n : null;}
  const portion = (amount,basisPoints) => Math.round(amount*basisPoints/10000);
  function estimate(row, inputs, now=Date.now()) {
    if (row.ungraded_single !== true) return {reason:'Ungraded singles only'};
    if (row.ends_at && Number.isFinite(Date.parse(row.ends_at)) && Date.parse(row.ends_at)<=now) return {reason:'Listing ended'};
    const ref=row.reference, scenario=row.opportunity?.scenarios?.find(s=>s.kind === row.price_kind || s.kind === 'buy_it_now');
    if (!ref || ref.grade !== 'raw' || ref.currency !== 'USD' || !scenario || scenario.reference_amount == null || !['eligible','conditional'].includes(row.reference_eligibility)) return {reason:'No applicable ungraded price'};
    if (ref.expires_at && (!Number.isFinite(Date.parse(ref.expires_at)) || Date.parse(ref.expires_at)<=now)) return {reason:'Price reference expired'};
    const sale=cents(scenario.reference_amount), buy=cents(row.listing_price), inbound=cents(row.shipping);
    if (sale === null || sale <= 0 || buy === null) return {reason:'Price unavailable'};
    if (inbound === null) return {reason:'Shipping unknown'};
    const purchaseTax=rate(inputs.purchaseTax), resaleTax=rate(inputs.resaleTax), feeRate=rate(inputs.feeRate), postage=cents(inputs.postage), supplies=cents(inputs.supplies), extra=cents(inputs.extra);
    if ([purchaseTax,resaleTax,feeRate,postage,supplies,extra].some(n=>n===null)) return {reason:'Check cost assumptions'};
    // Free shipping to the resale buyer. Their sales tax is not seller revenue,
    // but eBay includes it in its fee base. Standard US non-Store CCG tiers.
    const buyerTax=portion(sale,resaleTax), feeBase=sale+buyerTax;
    const fees=portion(Math.min(feeBase,750000),feeRate)+portion(Math.max(0,feeBase-750000),235)+(feeBase<=1000?30:40);
    const tax=portion(buy+inbound,purchaseTax), cost=buy+inbound+tax+fees+postage+supplies+extra;
    return {net:sale-cost,fees,tax,postage,supplies,extra,buy,inbound,sale,conditional:row.reference_eligibility==='conditional'};
  }
  return {estimate};
})();
