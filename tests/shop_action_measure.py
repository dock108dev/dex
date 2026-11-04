"""Sample the shared Shopping probe after usable content paints."""


def take(page, report, errors, kind, parse_path="/api/shopping/listing/compare/"):
    page.locator("html[data-shop-ready=true]").wait_for(timeout=10000)
    value = page.evaluate(
        """parsePath => {
        const p=window.shopProbe, origin=performance.timeOrigin;
        const resources=performance.getEntriesByType('resource').filter(r=>origin+r.responseEnd>=p.action && r.responseEnd<=p.ready);
        const nav=performance.getEntriesByType('navigation')[0];
        const entries=[nav,...resources].filter(r=>origin+r.responseEnd>=p.action && r.responseEnd<=p.ready);
        const end=Math.max(p.action-origin,...entries.map(r=>r.responseEnd));
        const intervals=entries.flatMap(r=>r.serverTiming.filter(t=>t.name==='application').map(t=>[Math.max(p.action-origin,r.responseStart-t.duration),r.responseStart])).concat(p.previous_server_intervals.filter(r=>r[1]>=p.action).map(r=>[Math.max(p.action,r[0])-origin,r[1]-origin])).sort((a,b)=>a[0]-b[0]);
        let server=0,right=p.action-origin;for(const [left,stop] of intervals){server+=Math.max(0,stop-Math.max(left,right));right=Math.max(right,stop);}
        const parses=p.parses.filter(r=>new URL(r.url).pathname===parsePath && origin+r.start>=p.action && r.end<=p.ready);
        const last=parses.at(-1);
        return {...p,parses,parse_dom_paint_ms:p.ready-(last?last.start:end),
        scheduling_transfer_ms:Math.max(0,origin+end-p.action-server),
        resources:entries.map(r=>({path:new URL(r.name).pathname,start:r.startTime,end:r.responseEnd,server:r.serverTiming.map(s=>({name:s.name,duration:s.duration}))}))};
        }""",
        parse_path,
    )
    report["samples"].setdefault(kind, []).append(value)
    assert not errors, errors
