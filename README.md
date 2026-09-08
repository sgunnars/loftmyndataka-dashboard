# Loftmyndataka Íslands 2025–2028 — framvindumælaborð (progress dashboard)

Live dashboard: https://claude.ai/code/artifact/f0d0b15a-ee81-4277-bbc0-a4dec33cd0b4

This folder is everything needed to keep updating the dashboard in a future
Claude conversation, without re-doing the original geospatial extraction from
scratch. Attach this whole folder (as a zip) to a new chat and say what
changed (e.g. "mark block X as done" or "block Y is now 45% flown, from
image counts") — Claude can pick up from here directly.

## What's in here

**Pipeline scripts** (run in this order, only `export3.py` needs edits for
routine updates):
- `extract.py` — one-time loader. Reads the master tender-grid GeoPackage,
  the `hex_done.gpkg` 2025 baseline, the flight-track GeoPackage, and a
  hand-parsed FlightRadar24 KML, and writes `blocks.pkl` / `tracks.pkl` /
  `hd_labels.json`. **You should not need to re-run this** unless the
  underlying source files change (new flight-track export, corrected master
  grid, etc.) — those source GeoPackage/KML files aren't included here since
  they're large; re-upload them if a full re-extraction is ever needed.
- `analyze.py` — spatial join: for every block, computes flown length and
  estimated coverage fraction at a range of swath-buffer widths. Reads
  `blocks.pkl` + `tracks.pkl`, writes `block_results.json`. Also shouldn't
  need re-running unless the flight-track data changes.
- `calib.py` — one-off calibration that established the default swath widths
  by GSD (650 m for 10 cm imagery, 2600 m for 25 cm). Reference only.
- `export3.py` — **the file to edit for routine updates.** Reads
  `blocks.pkl` + `block_results.json`, applies the human-confirmed
  classification lists (see below), and writes `dashboard_data.json`.

**Data files** (outputs of the pipeline, already generated):
- `blocks.pkl`, `tracks.pkl`, `block_results.json`, `hd_labels.json` —
  intermediate pipeline outputs (expensive to regenerate; keep these).
- `dashboard_data.json` — the current generated dataset, already baked into
  `dashboard_final.html`.

**Dashboard files:**
- `dashboard_template.html` — the dashboard source, with a `__DATA_JSON__`
  placeholder where the data gets injected.
- `dashboard_final.html` — the current fully-built, currently-published
  dashboard (template + data merged). This is what gets published as the
  Artifact.

## How to make a routine update (e.g. "block SW12_34 is now 60% done")

1. Open `export3.py`. Near the top are the classification sets/dicts:
   - `HD_RAW` / `HD_EXCLUDE` — Hexagon's 2025 baseline ("done2025") blocks.
   - `DONE_2026` — blocks fully flown in the 2026 season.
   - `PARTIAL_2026` — blocks partially flown in 2026 (label must be in this
     set to show ANY nonzero coverage — anything not in one of these lists,
     including blocks with flight-track "bleed-over" from a neighbouring
     block, is credited 0%).
   - `IMAGE_COUNT_FRACTIONS` — exact, human-supplied percentages (from
     collected-image counts, not flight-track geometry) that override the
     geometric swath-model estimate for specific `PARTIAL_2026` blocks. This
     is the most accurate source when available — prefer it over the model.
   - `CLOUDS` — blocks with a note about cloud-affected imagery quality.
2. Add/edit/remove the block label in the relevant set/dict.
3. Re-run: `python3 export3.py` (regenerates `dashboard_data.json` and
   prints an aggregate sanity check per contractor).
4. Re-inject into the template:
   ```python
   tpl = open("dashboard_template.html", encoding="utf-8").read()
   data = open("dashboard_data.json", encoding="utf-8").read()
   open("dashboard_final.html", "w", encoding="utf-8").write(tpl.replace("__DATA_JSON__", data))
   ```
5. Screenshot-check `dashboard_final.html` in both light and dark mode
   (Playwright, `/opt/pw-browsers/chromium`) before publishing.
6. Publish with the Artifact tool using `url:
   https://claude.ai/code/artifact/f0d0b15a-ee81-4277-bbc0-a4dec33cd0b4` so it
   updates the same page instead of creating a new one.

## Key modeling decisions to preserve

- **Only human-confirmed blocks get nonzero credit.** Flight-track geometry
  that clips into a neighbouring block ("bleed-over" from transit/turn
  segments) is real track data but is never counted as mapped area unless a
  human has explicitly confirmed that block.
- **Swath-model estimates use the most conservative (pessimistic) width
  multiplier** (0.5×) — this is fixed, not a user-adjustable slider, per the
  contract overseer's explicit preference to be pleasantly surprised rather
  than disappointed.
- **Exact (image-count) fractions bypass the model entirely** — no
  multiplier, and no "potential upside" shading on the progress bar, since
  there's no modeling uncertainty left for a ground-truth number.
- **Lot 1 = Meixner, Lot 2 = Hexagon.**
- Contractor colors: Meixner = green, Hexagon = purple (deep purple/solid
  for Hexagon's confirmed-done 2025 baseline; diagonal hatch = partially
  flown, for either contractor).
