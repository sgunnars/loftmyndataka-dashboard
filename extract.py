import fiona, json, re, math
from shapely.geometry import shape, mapping, LineString, MultiLineString
from shapely.ops import transform, unary_union, linemerge
import pyproj

UP = "/root/.claude/uploads/b7b93e2e-8d62-58c3-9d32-47d6b7c12909"
GRID = f"{UP}/5035a45e-A4iceland_ortho_tender_blocks_v20230308.gpkg"
HEXDONE = f"{UP}/36175fbe-hex_done.gpkg"
TRACKS = f"{UP}/7f339d5b-flight_tracks_merged_2026.gpkg"
KML = f"{UP}/0c898f5b-meixner_reykjanes_20260901.kml"

TARGET_CRS = "EPSG:3057"

# --- grid ---
with fiona.open(GRID) as src:
    src_crs = src.crs
    grid_feats = list(src)
print("grid crs", src_crs, "count", len(grid_feats))

to3057 = pyproj.Transformer.from_crs(src_crs, TARGET_CRS, always_xy=True).transform

blocks = []
for f in grid_feats:
    geom = shape(f['geometry'])
    geom3057 = transform(to3057, geom)
    p = f['properties']
    blocks.append({
        "label": p['label'],
        "lot": p['Lot'],
        "region": p['region'],
        "area_km2_attr": p['area'],
        "area_km2_geom": geom3057.area / 1e6,
        "accessable": bool(p['Accessable']),
        "season": p['season'],
        "gsd": p['GSD'],
        "sidelap": p['min. sidelap'],
        "sun_angle": p['min. sun angle'],
        "geom": geom3057,
    })

# --- hex_done (2025 completed, all Lot=2/Hexagon) ---
with fiona.open(HEXDONE) as src:
    hd_crs = src.crs
    hd_feats = list(src)
hd_labels = set(f['properties']['label'] for f in hd_feats)
print("hex_done labels", hd_labels)

# --- flight tracks 2026 ---
with fiona.open(TRACKS) as src:
    tr_crs = src.crs
    print("tracks crs", tr_crs, "count", len(src))
    track_geoms = []
    for f in src:
        g = f['geometry']
        if g is None: continue
        geom = shape(g)
        track_geoms.append(geom)
print("loaded track geoms", len(track_geoms))

# tracks already EPSG:3057 per earlier inspection; verify and reproject if needed
if str(tr_crs) not in (TARGET_CRS, "EPSG:3057"):
    to_t = pyproj.Transformer.from_crs(tr_crs, TARGET_CRS, always_xy=True).transform
    track_geoms = [transform(to_t, g) for g in track_geoms]

json.dump({"n": len(track_geoms)}, open("/tmp/dash/_status1.json","w"))
print("done stage1")

# --- parse Reykjanes KML by hand (no libkml driver available) ---
kml_text = open(KML, encoding="utf-8", errors="replace").read()
coord_blocks = re.findall(r"<coordinates>(.*?)</coordinates>", kml_text, re.S)
kml_lines_wgs84 = []
for cb in coord_blocks:
    pts = []
    for tok in cb.split():
        parts = tok.split(",")
        if len(parts) >= 2:
            try:
                lon, lat = float(parts[0]), float(parts[1])
                pts.append((lon, lat))
            except ValueError:
                pass
    if len(pts) >= 2:
        kml_lines_wgs84.append(LineString(pts))
print("kml line segments parsed", len(kml_lines_wgs84))

to3057_wgs = pyproj.Transformer.from_crs("EPSG:4326", TARGET_CRS, always_xy=True).transform
kml_lines_3057 = [transform(to3057_wgs, l) for l in kml_lines_wgs84]

all_tracks = track_geoms + kml_lines_3057
print("total flight geoms (2026 tracks + reykjanes kml)", len(all_tracks))

import pickle
with open("/tmp/dash/blocks.pkl","wb") as f:
    pickle.dump(blocks, f)
with open("/tmp/dash/tracks.pkl","wb") as f:
    pickle.dump({"tracks2026": track_geoms, "kml": kml_lines_3057, "all": all_tracks}, f)
with open("/tmp/dash/hd_labels.json","w") as f:
    json.dump(sorted(hd_labels), f)
print("stage2 done")
