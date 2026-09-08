import pickle, json, time
import numpy as np
from shapely.ops import unary_union
from shapely.strtree import STRtree

blocks = pickle.load(open("/tmp/dash/blocks.pkl","rb"))
tr = pickle.load(open("/tmp/dash/tracks.pkl","rb"))
all_tracks = tr["all"]
hd_labels = set(json.load(open("/tmp/dash/hd_labels.json")))

t0=time.time()
tree = STRtree(all_tracks)
print("tree built", time.time()-t0)

BUFFER_WIDTHS = [50, 100, 200, 325, 500, 650, 800, 1200, 1300, 1800, 2600, 3500, 5200, 7000]

results = []
for b in blocks:
    geom = b["geom"]
    idxs = tree.query(geom)
    cand = [all_tracks[i] for i in idxs]
    clipped = []
    total_len_m = 0.0
    for c in cand:
        if not geom.intersects(c):
            continue
        inter = geom.intersection(c)
        if inter.is_empty:
            continue
        total_len_m += inter.length
        clipped.append(inter)

    cov_by_width = {}
    if clipped:
        for w in BUFFER_WIDTHS:
            buffered = [ln.buffer(w, cap_style=2, join_style=2) for ln in clipped]
            u = unary_union(buffered)
            inter_area = u.intersection(geom).area
            frac = min(1.0, inter_area / geom.area)
            cov_by_width[w] = round(frac, 4)
    else:
        cov_by_width = {w: 0.0 for w in BUFFER_WIDTHS}

    results.append({
        "label": b["label"],
        "lot": b["lot"],
        "region": b["region"],
        "area_km2": round(b["area_km2_geom"], 2),
        "accessable": b["accessable"],
        "season": b["season"],
        "gsd": b["gsd"],
        "done_2025": b["label"] in hd_labels,
        "flown_len_km_2026": round(total_len_m/1000.0, 2),
        "coverage_by_width": cov_by_width,
    })

json.dump(results, open("/tmp/dash/block_results.json","w"), ensure_ascii=False, indent=1)
print("analysis done", time.time()-t0, "blocks", len(results))
for r in results:
    print(r["label"], r["lot"], r["done_2025"], r["flown_len_km_2026"], r["coverage_by_width"])
