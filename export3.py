import pickle, json
from shapely.ops import unary_union

blocks = pickle.load(open("/tmp/dash/blocks.pkl","rb"))
results = json.load(open("/tmp/dash/block_results.json"))
res_by_label = {r["label"]: r for r in results}

HD_RAW = {'NE81_39','HI80_31','NE86_39','SE79_16','SE92_31','SE92_35','SE92_25','NE80_35','NE86_35','NE86_31'}
HD_EXCLUDE = set()  # previously excluded HI80_31/NE80_35/NE81_39 as "not yet flown"; user corrected — they were flown in 2025 after all
HD = HD_RAW - HD_EXCLUDE
DONE_2026 = {'RVK','KEF','SW56_15','SW52_23','HI74_27','HI74_23','SE79_20','NE75_35','NE80_43','HI68_19','SW62_19','SW57_23','NW47_40','NW51_44','NW51_40','SW45_27'}
PARTIAL_2026 = {'SW51_27','SW57_27','SW51_17','SE74_15','NW67_31','NW67_37','NW63_37','HI74_19','NE74_39','SW62_15','NW44_35'}
CLOUDS = {'SW51_17','HI74_19'}
# Ground-truth fractions from actual collected-image counts (more accurate than
# the flight-line swath-buffer model) — these override the geometric estimate
# entirely and are not subject to the pessimistic-multiplier adjustment.
IMAGE_COUNT_FRACTIONS = {
    'SW51_17': 0.50,
    'SW57_27': 0.60,
    'NE74_39': 0.197,
    'SE74_15': 0.40,
    'SW62_15': 0.30,
    'NW67_37': 0.75,
    'HI74_19': 0.90,
    'SW51_27': 0.15,
    'NW44_35': 0.50,
}

def default_w(gsd): return 650 if gsd == 10 else 2600

def interp(cov, w):
    cov = sorted(cov.items(), key=lambda kv: int(kv[0]))
    cov = [(int(k), v) for k, v in cov]
    if w <= cov[0][0]: return cov[0][1]
    if w >= cov[-1][0]: return cov[-1][1]
    for i in range(len(cov) - 1):
        w0, v0 = cov[i]; w1, v1 = cov[i + 1]
        if w0 <= w <= w1:
            t = (w - w0) / (w1 - w0)
            return v0 + t * (v1 - v0)

def classify(label, lot, gsd, cov):
    # Only manually-confirmed blocks may carry a nonzero fraction. Flight-track
    # geometry that clips into a neighbouring block ("bleed-over" from transit/
    # turn segments of an adjacent contractor's sortie) is real track data but
    # is NOT credited as mapped area unless a human has confirmed the block.
    est_frac = interp(cov, default_w(gsd))
    if lot == 2 and label in HD:
        return {"status": "done2025", "confirmed": True, "exact": True, "fraction": 1.0, "note": None}
    if label in DONE_2026:
        return {"status": "done2026", "confirmed": True, "exact": True, "fraction": 1.0, "note": None}
    if label in PARTIAL_2026:
        note = "Ljósmyndagæði óviss – ský á hluta þekju" if label in CLOUDS else None
        if label in IMAGE_COUNT_FRACTIONS:
            return {"status": "partial2026", "confirmed": True, "exact": True,
                    "fraction": IMAGE_COUNT_FRACTIONS[label], "note": note}
        return {"status": "partial2026", "confirmed": True, "exact": False,
                "fraction": round(est_frac, 3), "note": note}
    # Everything else: not credited, regardless of any detected track bleed-over.
    return {"status": "not_started", "confirmed": False, "exact": False, "fraction": 0.0, "note": None}

def project_lot(lot_blocks, shared_bbox, vb_w=760.0, pad_frac=0.035):
    geoms = [b["geom"] for b in lot_blocks]
    # Use a bounding box shared across both lots so both maps render at the
    # identical scale and the same physical card size (directly comparable).
    minx, miny, maxx, maxy = shared_bbox
    W = maxx - minx; H = maxy - miny
    pad = max(W, H) * pad_frac
    minx -= pad; miny -= pad; maxx += pad; maxy += pad
    W = maxx - minx; H = maxy - miny
    scale = vb_w / W
    vb_h = H * scale
    def to_svg(x, y):
        return ((x - minx) * scale, vb_h - (y - miny) * scale)
    def poly_to_path(geom, tol=90):
        geom = geom.simplify(tol, preserve_topology=True)
        parts = []
        polys = geom.geoms if geom.geom_type == "MultiPolygon" else [geom]
        for poly in polys:
            for ring in [poly.exterior] + list(poly.interiors):
                pts = [to_svg(x, y) for x, y in ring.coords]
                parts.append("M " + " L ".join(f"{x:.1f},{y:.1f}" for x, y in pts) + " Z")
        return " ".join(parts)
    out = []
    for b in lot_blocks:
        r = res_by_label[b["label"]]
        cx, cy = to_svg(b["geom"].centroid.x, b["geom"].centroid.y)
        cls = classify(b["label"], b["lot"], b["gsd"], r["coverage_by_width"])
        out.append({
            "label": b["label"], "lot": b["lot"], "region": b["region"],
            "area_km2": round(b["area_km2_geom"], 1), "gsd": b["gsd"],
            "sidelap": b["sidelap"], "season": b["season"], "accessable": b["accessable"],
            "flownKm2026": r["flown_len_km_2026"],
            "cov": [[int(w), v] for w, v in sorted(r["coverage_by_width"].items(), key=lambda kv: int(kv[0]))],
            "path": poly_to_path(b["geom"]),
            "cx": round(cx, 1), "cy": round(cy, 1),
            **cls,
        })
    outline = unary_union(geoms).simplify(60, preserve_topology=True)
    outline_path = poly_to_path(outline, tol=0)
    return {"viewBox": [0, 0, round(vb_w, 1), round(vb_h, 1)], "outline": outline_path, "blocks": out}

lot1 = [b for b in blocks if b["lot"] == 1]
lot2 = [b for b in blocks if b["lot"] == 2]
all_geoms = [b["geom"] for b in blocks]
shared_bbox = (
    min(g.bounds[0] for g in all_geoms), min(g.bounds[1] for g in all_geoms),
    max(g.bounds[2] for g in all_geoms), max(g.bounds[3] for g in all_geoms),
)
data = {
    "generated": "2026-09-07",
    "defaultWidths": {"10": 650, "25": 2600},
    "combined": project_lot(blocks, shared_bbox, vb_w=1000.0),
}
json.dump(data, open("/tmp/dash/dashboard_data.json", "w"), ensure_ascii=False)

# quick aggregate report
def agg(lot_num):
    lb = [b for b in data["combined"]["blocks"] if b["lot"] == lot_num]
    tot = sum(b["area_km2"] for b in lb)
    confirmed_done = sum(b["area_km2"] for b in lb if b["status"] in ("done2025","done2026"))
    confirmed_partial = sum(b["area_km2"]*b["fraction"] for b in lb if b["status"]=="partial2026")
    estimated = sum(b["area_km2"]*b["fraction"] for b in lb if b["status"]=="estimated_partial")
    return tot, confirmed_done, confirmed_partial, estimated

for name, lot_num in [("Meixner(lot1)", 1), ("Hexagon(lot2)", 2)]:
    tot,cd,cp,es = agg(lot_num)
    print(name, "total", round(tot,1), "confirmed_done", round(cd,1), "confirmed_partial_credit", round(cp,1), "estimated_credit", round(es,1),
          "sum%", round(100*(cd+cp+es)/tot,1))
