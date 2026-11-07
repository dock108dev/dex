const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const context = {window:{},Date,Number,Math};
vm.createContext(context);
vm.runInContext(fs.readFileSync(process.argv[2],'utf8'),context);
const display = context.window.DexLotValues;
const now = Date.parse('2026-11-04T12:00:00Z');
const row = (id,hours,value,extras={}) => ({id,price_kind:'current_bid',ends_at:new Date(now+hours*3600000).toISOString(),lot_value:{bid_difference:value,total:'100'},...extras});
const rows = [row('lower',24,'10'),row('higher',47,'30'),row('late',49,'90'),row('ended',-1,'100'),row('unknown',3,null),row('bin',500,null,{price_kind:'fixed_price',buy_now_price:'50',lot_value:{buy_now_difference:'40',total:'90'}})];
const ids = options => Array.from(display.select(rows,{now,hours:'48',...options}),r=>r.id);
assert.deepEqual(ids({}),['bin','higher','lower','unknown']);
assert.deepEqual(ids({mode:'auction'}),['higher','lower','unknown']);
assert.deepEqual(ids({mode:'buy_now'}),['bin']);
assert.deepEqual(ids({hours:'24',mode:'auction'}),['lower','unknown']);
assert.deepEqual(ids({sort:'ending',mode:'auction'}),['unknown','lower','higher']);
assert.deepEqual(ids({hours:'all',mode:'auction'}),['higher','late','lower','unknown']);
const dual = row('dual',49,'999',{buy_now_price:'80',lot_value:{bid_difference:'999',buy_now_difference:'1'}});
assert.deepEqual(Array.from(display.select([dual,rows[0]],{now,hours:'48'}),r=>r.id),['dual','lower']);
const escaped = {esc:s=>String(s).replaceAll('<','&lt;'),money:v=>v==null?'Unknown':'$'+v,link:()=>''};
const html = display.html({lot_value:{subtotal:'25',total:null,priced_quantity:3,identified_quantity:3,stated_quantity:37,cards:[],references:[],reason:'Partial contents'}},escaped);
assert.match(html,/ungraded subtotal/);assert.doesNotMatch(html,/ungraded lot value/);
assert.match(display.costs({price_kind:'current_bid',buy_now_price:'50',buy_now_delivered_total:null},escaped),/Unknown/);
console.log('Time windows, buying modes, value sorting, partial coverage and unknown shipping passed.');
// Authored native cohorts: guide-content ordering, never differences or shared bases.
const native = (id,cohort,total,complete=true) => row(id,12,null,{item_id:id,lot_value:{subtotal:null,total:null,references:[],native_guides:[{cohort,provider:'Authored',date_basis:'valuation',reference_date:'2026-11-04',priced_quantity:3,complete,subtotal:total,total:complete?total:null,references:[{basis:'publisher_native_guide',source_contract:cohort,amount:'10',as_of:'2026-11-04',grade:'raw'}]}]}});
const na=native('a','cohort-a','70'),nb=native('b','cohort-a','50'),nc=native('c','cohort-b','999');
for (const [r,rank] of [[na,1],[nb,2],[nc,1]]) r.value_order={lanes:{auction:{rank}},native:[{lane:'auction',cohort:r.lot_value.native_guides[0].cohort,rank}]};
assert.deepEqual(Array.from(display.groups(display.select([nc,nb,na],{now,sort:'native'}),{sort:'native'})).flatMap(g=>Array.from(g.rows,r=>r.id)),['a','b','c']);
const nativeHtml=display.html(na,escaped);
assert.match(nativeHtml,/publisher guide total/);assert.match(nativeHtml,/Shipping\/tax basis unknown/);
assert.doesNotMatch(nativeHtml,/below reference|above reference|difference-percent/);
const partialHtml=display.html(native('partial','cohort-a','500',false),escaped);
assert.match(partialHtml,/partially assessed/);assert.doesNotMatch(partialHtml,/publisher guide total/);
na.lot_value.alternatives=[{quantity:2,selected_child_id:null,alternatives:[{child_id:'first',reference:{source_contract:'cohort-a',amount:'30'}},{child_id:'other',reference:null}]}];
assert.equal(display.references(na).length,2);
// Remove only dependent values; identities and valid unrelated normalized references survive.
na.lot_value.references=[{source_contract:'normalized'}];na.lot_value.total='40';
display.invalidate(na,ref=>ref.source_contract==='cohort-a');
assert.equal(na.lot_value.native_guides.length,0);assert.equal(na.lot_value.total,'40');
assert.equal(na.lot_value.alternatives[0].alternatives.length,2);
assert.equal(na.lot_value.alternatives[0].selected_child_id,null);
assert.equal(na.lot_value.alternatives[0].alternatives[0].reference,null);
console.log('Native cohorts, partial groups, no savings and source-specific invalidation passed.');
// LV-04 keeps unpriced seller contents separate from unenriched summaries.
assert.match(display.html({assessment_state:'unprocessed'},escaped),/not been assessed/);
const identified = {lot_value:{contents_state:'resolved',identified_quantity:2,identified_unpriced_quantity:2,unidentified_quantity:0,stated_quantity:2,cards:[{quantity:2,name:'Authored <Card>',set_name:'Authored',collector_number:'1',reference_subtotal:null}],references:[],reason:'References unavailable'}};
assert.match(display.html(identified,escaped),/Authored &lt;Card>/);
assert.match(display.html(identified,escaped),/reference unavailable/);
assert.match(display.html(identified,escaped),/contents resolved/);
identified.lot_value.references=[{source_contract:'expired'}];
identified.lot_value.cards[0].reference_subtotal='20';
display.invalidate(identified,()=>true);
assert.equal(identified.lot_value.cards.length,1);
assert.equal(identified.lot_value.cards[0].reference_subtotal,null);
assert.equal(identified.lot_value.identified_unpriced_quantity,2);
assert.equal(identified.lot_value.contents_state,'resolved');
console.log('LV-04 unpriced identities, escaped text and unenriched distinction passed.');
// LV-05 consumes server-issued ranks, including negative and partial groups.
const ranked = (id,binRank,bidRank,group='complete') => row(id,12,'999',{buy_now_price:'50',value_order:{schema:'dex-lot-order-v1',lanes:{buy_it_now:{rank:binRank,combined_rank:binRank,group,score:'-10'},auction:{rank:bidRank,group,score:'999'}},combined:{combined_rank:binRank,group},native:[]},lot_value:{total:'40',subtotal:'40',bid_difference:'999',buy_now_difference:'-10',references:[]}});
const dualRank=ranked('dual-rank',2,1),betterBin=ranked('better-bin',1,2),partialRank=ranked('partial-rank',3,3,'partial');
assert.deepEqual(Array.from(display.select([dualRank,partialRank,betterBin],{now,mode:'buy_now'}),r=>r.id),['better-bin','dual-rank','partial-rank']);
assert.deepEqual(Array.from(display.select([dualRank,partialRank,betterBin],{now,mode:'auction'}),r=>r.id),['dual-rank','better-bin','partial-rank']);
assert.deepEqual(Array.from(display.select([dualRank,partialRank,betterBin],{now}),r=>r.id),['better-bin','dual-rank','partial-rank']);
// A late response carrying a withdrawn contribution is pruned without restoring scores.
dualRank.lot_value.references=[{source_contract:'withdrawn'},{source_contract:'valid'}];
dualRank.lot_value.identified_quantity=3;
dualRank.lot_value.cards=[{quantity:2,reference_subtotal:'20',reference:{source_contract:'withdrawn'}},{quantity:1,reference_subtotal:'5',reference:{source_contract:'valid'}}];
dualRank.lot_value.benchmark_costs={auction:{difference:'999',subtotal_difference:'1'},buy_it_now:{difference:'-10',subtotal_difference:null}};
display.invalidate(dualRank,ref=>ref.source_contract==='withdrawn');
assert.equal(dualRank.lot_value.total,null);
assert.equal(dualRank.value_order.lanes.auction.rank,null);
assert.equal(dualRank.value_order.lanes.buy_it_now.score,null);
assert.equal(dualRank.lot_value.benchmark_costs.auction.subtotal_difference,null);
assert.equal(dualRank.lot_value.cards[1].reference_subtotal,'5');
assert.equal(dualRank.lot_value.priced_quantity,1);
assert.equal(dualRank.lot_value.identified_unpriced_quantity,2);
assert.equal(dualRank.lot_value.references.length,1);
console.log('LV-05 server lane order, negative/partial groups and dependent score invalidation passed.');
// A dense, factored list restores both server ranks without repeating source metadata.
const packed = {id:'packed',evidence_version:'local',lot_value:{native_guides:[],cohort_rows:[
  ['cohort',0,'2026-11-06','publisher_build',2,'7.50',false,[0],2,1]
]},value_order:{native:[],lanes:{auction:{},buy_it_now:{}}}};
display.unpack({results:[packed],cohort_labels:['Authored'],cohort_sources:[{source_contract:'gone'}]});
assert.equal(packed.lot_value.native_guides[0].subtotal,'7.50');
assert.equal(packed.lot_value.native_guides[0].total,null);
assert.deepEqual(Array.from(packed.value_order.native,o=>o.rank),[2,1]);
Object.assign(packed.lot_value,{references:[{source_contract:'gone'},{source_contract:'valid'}],
  priced_coverage:[[3,[0]],[2,[1]]],identified_quantity:5,subtotal:'20'});
display.invalidate(packed,ref=>ref.source_contract==='gone');
assert.equal(packed.lot_value.priced_quantity,2);
assert.equal(packed.lot_value.identified_unpriced_quantity,3);
assert.equal(packed.lot_value.native_priced_quantity,0);
assert.equal(packed.lot_value.subtotal,null);
// The default recommendation view is one ordered list, not assessment groups.
const bestA=ranked('best-a',2,1),bestB=ranked('best-b',1,2);
bestA.buying_order={combined:{rank:1},auction:{rank:2}};
bestB.buying_order={combined:{rank:2},auction:{rank:1}};
assert.deepEqual(Array.from(display.select([bestB,bestA],{now,sort:'best'}),r=>r.id),['best-a','best-b']);
assert.deepEqual(Array.from(display.select([bestA,bestB],{now,sort:'best',mode:'auction'}),r=>r.id),['best-b','best-a']);
assert.equal(display.groups([bestA,bestB],{sort:'best'}),null);
display.invalidate(bestA,()=>true);
assert.equal(bestA.buying_order,null);
console.log('Recommendation order, single list and expired-rank removal passed.');
// Simple local filters never turn a partial/unknown estimate into a discount.
const quick = (id, amount, complete, ratio, pre2000=false) => ({id,buy_now_price:'87',buying_order:{combined:{estimate_amount:amount,estimate_complete:complete,price_to_estimate:ratio,all_pre_2000:pre2000}}});
const options = [quick('good','100',true,'.87',true),quick('high','100',true,'1.44'),quick('partial','20',false,null),quick('unknown',null,false,null)];
assert.equal(display.glance(options[0]).tone,'good');
assert.equal(display.glance(options[0]).label,'87% of value');
assert.equal(display.glance(options[1]).tone,'high');
assert.equal(display.glance(options[1]).label,'144% of value');
assert.equal(display.glance(options[2]).label,'Partial estimate');
assert.deepEqual(Array.from(display.select(options,{estimate:'estimated'}),r=>r.id),['good','high','partial']);
assert.deepEqual(Array.from(display.select(options,{estimate:'below'}),r=>r.id),['good']);
assert.deepEqual(Array.from(display.select(options,{era:'pre2000'}),r=>r.id),['good']);
assert.deepEqual(Array.from(display.select(options,{estimate:'below',era:'pre2000'}),r=>r.id),['good']);
options[0].buying_order=null;
assert.deepEqual(Array.from(display.select(options,{estimate:'below'}),r=>r.id),[]);
assert.equal(display.glance(quick('zero','0',true,null)).tone,'unknown');
