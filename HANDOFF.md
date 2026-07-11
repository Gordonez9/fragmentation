# HANDOFF: crYOLO Filament Fragmentation (TMV)

## Read these first, in order

1. **`CLAUDE.md`** — project context, scope (TMV only), the pixel-size resolution writeup,
   ghez environment details, and working agreements. This is the authoritative source for
   project rules; this handoff summarizes but does not replace it.
2. **`TMV_TASK_PROMPT.md`** — the actual task list (Task 0 → 0.5 → 1 → 2 → 3), in order, with
   acceptance gates per task. Work through it in order; do not skip ahead.
3. **`kayleigh_script_reference.md`** — reference for `inspect_stars.m` (the labmate script
   whose output is one leg of the Task 2 three-way comparison) and `jump_threshold=50px`.

## Critical operating constraint — read before doing anything

**Claude Code runs locally in VS Code, on the user's laptop, with no access to ghez** (the
compute cluster holding the real data: micrographs, the full 82-micrograph
`output_1/STAR_FILAMENT_SEGMENTED/`, `.mrc`/`.tif` headers). The user transfers scripts to
ghez and runs them by hand; **never say "let me run this and check"** for anything that needs
ghez. Write the script, give the exact command to run (ghez shell is **csh/tcsh** — `|&` for
stderr, never `2>&1`), state what output would confirm vs. falsify the hypothesis, then
**stop and wait for pasted-back real output.**

Exception: `cbox_raw/TMV/` (4 real `.cbox` files, a small dev subset pulled from ghez) and
`TMV/` (4 matching `.star` files) live in this local repo, gitignored. Claude Code **can**
and should run/test scripts against these locally — the user has explicitly authorized this
for local-subset work. Anything touching the full 82-micrograph set or ghez-only files
(`.mrc`, `.tif`, `output_1/*`) cannot be run locally; ask the user to run it and paste output.

ghez conda env is `fragviz`: **Python 3.8, numpy + matplotlib + pillow only. No pandas, no
scipy.** Target 3.8 syntax (no `match`, no `X | Y` unions). Write new scripts standalone
(no imports from this repo's other `.py` files) so a single `scp` transfers everything needed.

## Goal

Diagnosing and fixing filament fragmentation from crYOLO's automated tracing on TMV cryo-EM
data. crYOLO splits one continuous physical filament into multiple disconnected detections
(tube IDs), corrupting downstream length statistics even though RELION 3D reconstruction from
the same picks looks fine (helical averaging only needs locally consistent segments, so a good
map is *not* evidence the picks are unfragmented). Building a from-scratch chain-tracer that
works from crYOLO's **raw CBOX box detections** (pre-linking) rather than its already-linked
STAR output, so the linking step itself can be diagnosed rather than just patched after the
fact.

**Scope: TMV only** (asyn is archived — see below). TMV is the only dataset with real ground
truth: a virion is a textbook **300 nm long, 18 nm wide**, and TMV is used as an EM
magnification standard precisely because those numbers are reliable. Every length this
pipeline produces gets checked against them, as a hard gate.

## Task status (per `TMV_TASK_PROMPT.md`)

- **Task 0 — pixel size — ✅ CLOSED, 2026-07-11.** Header-confirmed **19.14 Å/px**. The
  long-standing `1.05 Å/px` (hardcoded literal in `inspect_stars.m`, silently inherited by
  everything downstream including `compute_lengths_by_tubeid.py`) was wrong by ~18×, and is
  the confirmed explanation for previously "impossible" 7.38 nm mean tube-ID lengths (shorter
  than a virion's own width). Confirmed via `get_pixel_size_from_tiff.py` (user's script, not
  local to this repo) reading a TIFF's vendor metadata block: camera pixel size 24 µm ÷ actual
  magnification 12,541.7× = 19.14 Å/px. Indicated magnification came back exactly 9300.0,
  matching the filenames — the sanity check that confirms the byte-offset parsing landed on
  real fields, not garbage. Lands within ~1.5% of Kayleigh's independent Napari Boxmanager
  calibration (19.42 Å/px) — two independent methods agreeing. **Use 19.14 Å/px going
  forward; never 1.05, including retroactively on old numbers.**

  Built `establish_scale.py` (this repo, standalone, numpy-only) as a third, CBOX-only
  cross-check, independent of both circulating numbers: derives pixel size from `_EstWidth`
  vs. TMV's known 180 Å width. Run locally against the 4-file `cbox_raw/TMV/` dev subset
  (642 boxes): pooled median `_EstWidth` = 17.0 px → implied **10.59 Å/px**. This is well
  short of the header's 19.14 Å/px (real, unexplained discrepancy — flagged, not resolved) but
  it did the job asked of it: it ruled out 1.05 Å/px hard, on two independent physical
  grounds — implied filament width (171 px) doesn't fit a 16 px training box, and implied FOV
  (105×94 nm) is smaller than one virion. **Not yet run against the full 82-file
  `output_1/CBOX/` on ghez** — worth doing to see whether the 10.59-vs-19.14 gap shrinks with
  the full dataset or is a real per-subset artifact. Command: `python establish_scale.py
  output_1/CBOX`.

- **Task 0.5 — recompute existing lengths at 19.14 Å/px — 🔶 IN PROGRESS, blocked on user.**
  Three sub-items, per `TMV_TASK_PROMPT.md`:
  1. **Re-run `compute_lengths_by_tubeid.py`** against `output_1/STAR_FILAMENT_SEGMENTED/`
     with `pixel_size=19.14`, report new mean/std/min/max vs. the old (wrong) ones. **Blocked:
     this script is not in this local repo** (checked; only `cbox_utils.py`,
     `filament_tracer.py`, `propose_filament_merges.py`, `establish_scale.py` exist here) and
     needs the full ghez dataset. Asked the user to either run it themselves and paste back
     results, or paste the script if they want it reviewed/modified first (e.g. confirm
     `pixel_size` is truly a required CLI arg, not hardcoded, per the working agreement in
     `CLAUDE.md`). **Not yet answered.**
  2. **Visually re-check the `..._0033` case.** Previously reported 72.60 nm, called "clean,
     single, continuous" in a 2026-07-09 visual check. Under 19.14 Å/px this becomes ~1320 nm
     — longer than one 300 nm virion. Two honest possibilities to distinguish (real end-to-end
     aggregate, known to happen in negative stain, vs. something that looks different once the
     scale correction makes it stand out) — **this is an explicit visual judgment call on the
     overlay TIFF, which Claude cannot see** (no ghez access, and `0033` isn't one of the 4
     local dev CBOX files — those are `0007`, `0021`, `0060`, `0071`). Entirely on the user.
     Gave a suggestion for what to look for (a visible seam/angle-discontinuity near the
     midpoint, and whether crYOLO's own tube-ID linking also split at that point) but this is
     not a substitute for actually looking. **Not yet answered.**
  3. **ELN note** that `inspect_stars.m` still hardcodes `pixel_size = 1.05` and will produce
     wrong numbers until hand-fixed (out of scope to fix ourselves — it's the user's script).
     **Drafted, given to user for review/edit** (see chat history around 2026-07-11 for the
     draft text) — not yet confirmed accepted into the real ELN.
  4. Explicit non-goal: do **not** re-run `inspect_stars.m` or regenerate
     `master_fiberapp_session.mat` — out of scope, that's the user's script to fix by hand.

- **Task 1 — `trace_chains_from_cbox.py` — not started, blocked on Task 0.5 closing.** Full
  spec is in `TMV_TASK_PROMPT.md`: parse → candidate links (k-NN within a physically-justified
  radius) → link cost (distance + `_Angle` agreement + collinearity, each term named/weighted/
  explained) → matching (greedy first, structured so Hungarian and a graph/MST variant can be
  swapped in behind the same interface) → chains → lengths (px and nm). Crossover boxes (3+
  good candidate links) must be flagged in the output, not silently resolved — angle
  continuity is the proposed lever (the PI's suggestion). Acceptance gates include: box counts
  match CBOX row counts, pixel size and derived nm thresholds print at the top of every run,
  and — explicitly — **if the new tracer's length-distribution mode isn't meaningfully closer
  to a virion than crYOLO's, say so plainly; a null result is a real result.**

  `filament_tracer.py` (this repo, from the earlier raw-box-tracing exploration — see below)
  is a prior greedy bidirectional path-cover prototype over raw boxes and is a natural
  starting point/building block for Task 1's greedy matcher, **but it doesn't yet have**: the
  named/weighted link-cost decomposition Task 1 asks for (it uses one blended cost, not
  separate distance/angle/collinearity terms), the pluggable Hungarian/MST interface, physical
  (nm) unit thresholds, crossover flagging, or CSV output. Treat it as a reference/starting
  point, not a finished Task 1 deliverable.

- **Task 2 — three-way comparison + overlay — not started, blocked on Task 1.** `visualize_
  tubeid.py` (referenced as something to adapt) is not in this local repo — build the overlay
  tool fresh, informed by the box-scatter + STAR-chain-overlay plotting logic already in
  `raw_box_tracing.ipynb`. Kayleigh's `jump_threshold=50px` logic is fully documented in
  `kayleigh_script_reference.md` (simple sequential distance-threshold walk, no angle/tangent/
  crossover awareness) — implement it directly from that spec, no separate script needed.
  Comparison must report **per-filament disagreement, not just aggregate means** — the whole
  point is that aggregates already agree while individual filaments don't.

- **Task 3 — unbiased fragmentation rate — not started, blocked on Task 2.** Random sample of
  N micrographs (fixed seed, recorded) — explicitly *not* drawn from distribution extremes,
  per the selection-bias trap already hit once with the merge-proposal approach's TMV test
  cases (see below). Propose N and state what it buys vs. doesn't.

## What Worked

- **Verifying pixel size empirically before building anything on it, rather than trusting
  either circulating number.** Two plausible-looking values (1.05 and 19.42 Å/px) existed;
  neither was adopted until a third method (MRC/TIFF header read) confirmed one of them. This
  caught an ~18× error that would have propagated into every length in the pipeline.
- **`establish_scale.py`'s physical-plausibility framing** (implied filament width vs. known
  box size; implied FOV vs. known virion length) turned out to be a genuinely strong
  discriminator even before the header result came back — it ruled out 1.05 Å/px on two
  independent grounds, using only local dev-subset data.
- **Refusing to hand-scale old results** (`× 19.14/1.05`) instead of recomputing — flagged
  explicitly in `CLAUDE.md`/`TMV_TASK_PROMPT.md` as a trap, because a >72 nm case becomes
  >1 virion length under the real scale, which changes what the trace should be interpreted
  as, not just its reported number.
- Verifying the CBOX corner-vs-center convention empirically (nearest-neighbor distance
  against the STAR trace) rather than trusting CBOX format assumptions — the first hardcoded
  guess (as-is = center) was wrong by ~10-100px depending on box size. (`cbox_utils.
  box_centers()`.)
- Drawing raw-box orientation as a **double-ended** line segment (±angle), not a directed
  arrow — `_Angle` has a 180° ambiguity for a line's local orientation.
- Writing scripts standalone (no cross-imports) so a single `scp` is enough to run them on
  ghez — avoids a round-trip discovering a missing dependency.

## What Didn't Work / Open Blockers

- **`establish_scale.py`'s point estimate (10.59 Å/px) undershoots the header-confirmed value
  (19.14 Å/px) by a real margin on the local 4-file subset** — unexplained. Median `_EstWidth`
  (17 px) came out close to the training box size itself (16-20 px) rather than roughly half
  of it, which is what an earlier box-size argument in `CLAUDE.md` assumed. Worth re-running
  against the full 82-file set; not yet done.
- Task 0.5 items 1 and 2 are both stalled on the user (script paste-back / visual check) — see
  Task status above. Do not proceed to Task 1 until Task 0.5 fully closes per
  `TMV_TASK_PROMPT.md`'s explicit ordering.
- (From the earlier raw-box-tracing exploration, still open) Whether the "raw boxes bridge a
  STAR-level gap smoothly" pattern (a genuine linker artifact, found in TMV 0071's chain 3/4,
  26px gap) generalizes across the other TMV micrographs, vs. the "no boxes in between, angle
  discontinuous" real-gap pattern (chain 1/2, 270px gap) — only 0071 was examined at this
  level of detail. This is effectively subsumed by Task 1's acceptance gates now (comparing
  the new tracer's output against crYOLO's directly), so likely doesn't need separate
  follow-up.
- Never got a validated positive/negative control test from the *merge-proposal* approach
  (TMV tube_id 15 in micrograph 0038 known-fragmented; tube_id 1 in micrograph 0033
  known-clean) — the downloaded TMV files were random, not these known cases. Superseded in
  practice: Task 0.5 is now independently flagging `..._0033` for a fresh look under the
  corrected scale anyway.

## Next Steps

1. **Waiting on user** for Task 0.5 items 1 (tube-ID lengths at 19.14 Å/px — either pasted
   output or the script itself) and 2 (visual call on `..._0033`). Do not start Task 1 until
   both close, per the task file's explicit blocking order.
2. Optional, non-blocking: run `establish_scale.py` against the full `output_1/CBOX/` on ghez
   to see if the 10.59-vs-19.14 Å/px gap on the local subset shrinks with more data.
3. Once Task 0.5 closes: start Task 1 (`trace_chains_from_cbox.py`), staged exactly as
   `TMV_TASK_PROMPT.md` specifies (parse → candidate links → link cost → matching → lengths),
   stopping after each stage for the user to inspect real output before continuing — same
   protocol as Task 0's `establish_scale.py`. Reuse `filament_tracer.py`'s bidirectional-growth
   logic as a starting point for the greedy matcher, but build out the named-term link cost,
   swappable-matcher interface, crossover flagging, and CSV output it doesn't yet have.
4. Confirm the ELN note draft (Task 0.5 item 3) was usable or get corrected wording.

---

## Prior exploratory work: raw-box tracing (informs Task 1, not a separate task)

Before the formal `TMV_TASK_PROMPT.md` task list existed, this session validated the core
premise that a from-scratch CBOX tracer is worth building, using `raw_box_tracing.ipynb`:

- **Box count / matching problem scale:** 52-337 boxes per micrograph, mean ~170 — trivial for
  an all-pairs cost matrix. The *shape* of the problem is path-tracing over mostly-interior
  points (up to 2 neighbors each), not endpoint-only bipartite matching.
- **TMV 0071 sanity check:** compared raw boxes against the two closest STAR-linked-chain gaps.
  - Chain 1↔2 (~270px gap): raw boxes exist only in two tight clusters at each endpoint,
    nothing in between, angle discontinuous (~112-119° vs ~0-2.5°). **Not a linking artifact**
    — nothing to link, a from-scratch tracer wouldn't bridge this either.
  - Chain 3↔4 (~26px gap, both chains only 25 points): raw boxes run continuously and evenly
    spaced through the gap, smooth consistent angle (~20-25°, no jump). **Looks like a genuine
    linking-step artifact** — crYOLO's linker cut one continuous strand into two short chains.
  - This contrast (not all STAR-level "gaps" have the same root cause) is the core
    justification for building a from-scratch tracer instead of patching `rlnHelicalTubeID`
    chains after the fact, and is exactly what Task 1's acceptance gates are designed to
    quantify systematically.
- `_Angle` reliability was validated against STAR-trace tangents: pooled median error ~3.6° on
  TMV, 97-99% of on-chain boxes within 15°. This is why Task 1's spec explicitly says to use
  `_Angle` directly before building any neighbor-based tangent estimator, and is what
  `filament_tracer.py`'s `angle_tol_deg=20` default is based on.
- Under-linking (orphan boxes far from any STAR point) is real on TMV but modest (0-9% of
  files), and orphans cluster into coherent strands rather than scattering as isolated noise —
  motivates `filament_tracer.py`'s `min_len=3` noise guard.
- A persistence-length estimate attempted on STAR-linked chains came out **confounded/censored**
  by crYOLO's own chain boundaries (chains never show measurable tangent decorrelation because
  they were built to be locally straight) — not usable as an independent rigidity measurement.
  Same root issue as the whole pivot: anything downstream of crYOLO's linking has its
  assumptions already baked in.

## Prior Approach (Paused): Merge Proposals on Already-Linked Chains

`propose_filament_merges.py` still exists and works (parses `STAR_FILAMENT_SEGMENTED`, groups
by `rlnHelicalTubeID`, tangent + distance cost matrix, Hungarian assignment, non-destructive
proposals). Paused in favor of the from-scratch CBOX approach, since it can only patch
mistakes crYOLO already made rather than diagnosing the linking step itself. Prior findings,
kept for reference:

- Confirmed fragmentation happens inside crYOLO's own tracing (not downstream STAR
  processing).
- Calibrated `max_dist` against real loose-end distances across the local STAR files — no
  single global threshold looked right, reinforcing that per-root-cause handling (the
  linker-artifact vs. real-gap distinction above) matters more than per-dataset threshold
  tuning.
- `propose_merges`'s candidate count is **not monotonic** in `max_dist` (solves a global
  min-cost perfect matching, not independent per-pair thresholding) — worth remembering if
  this approach is ever revisited.
- `fragmentation_visualization.ipynb` (colors = chains, arrows = tangent, dashed lines =
  closest gaps) still reflects this approach and is useful for eyeballing STAR-linked chains,
  but doesn't show raw boxes — see `raw_box_tracing.ipynb` for that.

---

## Focus & Archive

**TMV only, asyn archived.** As of 2026-07-11, alpha-synuclein ("asyn") material was moved
out of the active working set (not deleted):

- `asyn/` → `archive/asyn/`, `cbox_raw/asyn/` → `archive/cbox_raw/asyn/`.
- `raw_box_tracing.ipynb` and `fragmentation_visualization.ipynb` code paths were repointed to
  the `archive/` locations, so both notebooks still run end-to-end; asyn stays in them as a
  TMV comparison baseline, analysis and outputs intact.
- Per `CLAUDE.md`: **do not write asyn code paths, `--dataset` switches, or "generalize for
  later" abstractions** in any new script. TMV only until told otherwise.

### Archived (asyn) findings, kept for reference

- **Coordinate scale not comparable to TMV, unresolved for asyn specifically** (TMV's own
  scale is now resolved — see Task 0 above; this was never re-examined for asyn). asyn
  micrographs span ~3700-3850 raw units with 240×240 px boxes vs. TMV's much smaller scale —
  order-of-magnitude differences, no pixel size/binning metadata available locally for asyn.
- **crYOLO's asyn linking is close to right** — traced-vs-STAR filament counts stay roughly
  matched on asyn (16→16, 22→23), unlike TMV which over-segments and collapses under a
  from-scratch tracer (28→19, 6→4, 15→13). The fragmentation problem is more a TMV story.
- **19863050 (one asyn file) is a persistent outlier** across four independent metrics:
  bimodal gap distribution, all-artifact closest gaps, 26% orphaned boxes (mostly isolated
  spurious detections), messy field overall. Don't pool it blindly with the other three asyn
  files if this work is ever picked back up.
- asyn semi-flexibility vs. TMV rigidity motivated a persistence-length comparison that came
  out confounded for both datasets (see "Prior exploratory work" above) — not asyn-specific.
