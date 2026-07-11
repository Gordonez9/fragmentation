# Session task — TMV chain tracing from CBOX

Read `CLAUDE.md` first.

Work through these **in order**. **Stop after each task and wait for me to paste back real
output.** You cannot run any of this yourself — do not run ahead, do not assume a result.

---

## Task 0 — Confirm the pixel size ✅ CLOSED, 2026-07-11

**Header-confirmed: 19.14 Å/px.** Pulled directly from the TIFF's own vendor metadata (camera
pixel size 24 µm ÷ actual magnification 12,541.7×). Indicated magnification came back exactly
9300.0, matching the filenames — confirms the byte-offset parsing landed on the right fields, not
garbage. Lands within ~1.5% of Kayleigh's independent Napari calibration (19.42 Å/px). `1.05 Å/px`
was wrong. Don't use it anywhere going forward, including retroactively on old numbers already
written down — see CLAUDE.md for the full writeup.

**Don't hand-scale old results by the ratio (÷1.05 × 19.14).** Recompute properly — see Task 0.5.

---

## Task 0.5 — Recompute existing lengths under the corrected pixel size (BLOCKING for Task 1)

Get the existing tube-ID numbers onto solid ground before starting the from-scratch tracer, so
Task 1 has something trustworthy to compare against.

1. Re-run `compute_lengths_by_tubeid.py` against `output_1/STAR_FILAMENT_SEGMENTED/`, passing
   `pixel_size=19.14` explicitly. Report the new mean/std/min/max next to the old (wrong) ones.
2. **Specifically re-examine the `..._0033` case** — previously reported as 72.60 nm and called
   "clean, single, continuous" in the 2026-07-09 visual check. Under the corrected scale this
   becomes roughly ~1320 nm — longer than one full 300 nm TMV virion. Pull up its overlay again.
   Two honest possibilities, don't assume either one:
   - it's a real end-to-end aggregate of multiple virions (known to happen in negative stain), in
     which case the earlier "clean and continuous" read still holds, just at a different scale
   - or something about that trace looks different in a way that wasn't obvious before the scale
     correction made it stand out
   Report which one it looks like, and why — this is a visual judgment call, not a script output.
3. Do **not** re-run `inspect_stars.m` or regenerate `master_fiberapp_session.mat` — that's
   Kayleigh's script and out of scope for you to modify. Just note in the ELN draft that it still
   hardcodes `pixel_size = 1.05` and will produce wrong numbers until she fixes it by hand.

**Acceptance:** corrected mean/std/min/max reported, the `..._0033` visual re-check done with a
clear stated judgment (not just "the number changed"), and nothing downstream treats the old
7.38 nm-scale numbers as current.

---

## Task 1 — From-scratch chain tracing from CBOX

Only after Task 0.5 is closed. Build `trace_chains_from_cbox.py`.

**Input:** a directory of `.cbox` files + pixel size (required arg, no default).
**Output:** a CSV of `micrograph, chain_id, n_boxes, length_px, length_nm`, plus the box→chain
assignment. Non-destructive — writes nothing back into the source directory.

Structure it in stages so I can inspect each one independently:

1. **Parse.** CBOX → boxes with x, y, angle, confidence, est_width. Print counts.
2. **Candidate links.** For each box, its k nearest neighbours within a max radius. **Justify that
   radius in physical units (nm), derived from box spacing and pixel size — not picked.**
3. **Link cost.** Combine:
   - euclidean distance
   - agreement between the two boxes' `_Angle` values
   - collinearity — how well the displacement vector between them aligns with their shared orientation

   Each term named, weighted, and explained. **Use `_Angle` directly before building any
   neighbour-based tangent estimator.**
4. **Matching.** Start with **greedy** — simplest, easiest to debug, no scipy dependency. Structure
   the code so **Hungarian** and a **graph/MST-based** variant can be swapped in behind the same
   interface. I want to compare all three, not commit to one upfront.
5. **Chains → lengths.** Sum consecutive distances, convert px → nm.

**Crossovers:** a box with 3+ good candidate links is ambiguous. Propose how to resolve it — angle
continuity is the obvious lever, and it's what my PI suggested — and **flag those boxes in the output
rather than silently picking one.**

**Acceptance gates, in order:**
- Box counts per micrograph match the CBOX file's own row count.
- Assumed pixel size and all derived thresholds (in nm) print at the top of every run.
- The resulting length distribution is compared against (a) crYOLO's tube-ID lengths and (b) TMV's
  known 300 nm.
- **If the new tracer's mode isn't meaningfully closer to a virion than crYOLO's is, say so plainly.**
  A null result here is a real result and I would rather know than be told what I want to hear.

---

## Task 2 — Three-way comparison + overlay

Only after Task 1 produces plausible chains.

- Overlay tool (matplotlib, `fragviz`-compatible — numpy/matplotlib/pillow only): raw micrograph +
  boxes coloured by chain, with an option to bold one chain. Adapt the existing `visualize_tubeid.py`.
- Run the same micrographs three ways: **my CBOX chains** vs **crYOLO tube IDs** vs **Kayleigh's
  jump_threshold = 50 px**.
- Report **where they disagree**, per filament — not just aggregate means. The entire point of the
  earlier comparison was that the aggregates agree while the individual filaments don't.

---

## Task 3 — Unbiased fragmentation rate

Only after Task 2.

Random sample of N micrographs — **random**, not drawn from the extremes of the length distribution.
That's the selection-bias trap I already fell into once. Fixed seed, recorded.

Systematic tally CSV: per micrograph, real filaments by eye vs. chains produced. Ratio = fragmentation
rate, with an honest uncertainty.

Propose N. Tell me what N buys me and what it doesn't.
