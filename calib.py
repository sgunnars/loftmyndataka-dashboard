import json
blocks = json.load(open("/tmp/dash/block_results.json"))

# reload gsd per label since block_results already carries gsd
widths = [100,250,500,800,1200,1800,2500,3500]

def crossing(cov, target=0.95):
    ws = sorted(cov.keys(), key=lambda x:int(x))
    vals = [cov[w] for w in ws]
    ws = [int(w) for w in ws]
    for i in range(len(ws)-1):
        if vals[i] < target <= vals[i+1]:
            # linear interp
            w0,w1=ws[i],ws[i+1]; v0,v1=vals[i],vals[i+1]
            return w0 + (target-v0)/(v1-v0)*(w1-w0)
    if vals[-1] >= target:
        return ws[-1]
    return None

by_gsd = {}
for b in blocks:
    cov = {str(k):v for k,v in b["coverage_by_width"].items()}
    c = crossing(cov, 0.95)
    if c is not None and b["flown_len_km_2026"] > 5:
        by_gsd.setdefault(b["gsd"], []).append((b["label"], round(c,1)))

for gsd, items in by_gsd.items():
    vals = sorted(v for _,v in items)
    print("GSD", gsd, "n=",len(items), items)
    import statistics
    print("  median crossing width:", statistics.median(vals))
