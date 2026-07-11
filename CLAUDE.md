# CLAUDE.md — crYOLO filament fragmentation (TMV)

## The project

crYOLO's filament mode appears to be chopping continuous physical filaments into multiple
disconnected detections. We're diagnosing that, and building a from-scratch chain-tracing
algorithm that works from crYOLO's **raw CBOX box detections** rather than from its
already-linked STAR output.

What this corrupts is downstream length statistics. RELION reconstructions still look fine
— helical averaging only needs locally consistent segments — so a good map is *not* evidence
that the picks are unfragmented.

---

## Scope: TMV only

Asyn is parked. Do not write asyn code paths, `--dataset` switches, or "let's generalize this
for later" abstractions. TMV only until I say otherwise.

**Why TMV:** it is the only dataset here with real ground truth. A TMV virion is **300 nm long
and 18 nm wide** — textbook, and TMV is used as an EM magnification standard precisely because
those numbers are reliable. Every length this pipeline produces can be checked against them.
Asyn has no such anchor. Use TMV's dimensions constantly, as a hard gate, not a footnote.

---

## ✅ Resolved — TMV pixel size is 19.14 Å/px, not 1.05 Å/px

**Confirmed 2026-07-11**, header-verified. `1.05 Å/px` (hardcoded in `inspect_stars.m`, and
inherited by everything downstream, including `compute_lengths_by_tubeid.py`) was wrong.

**How it was confirmed:** pulled the vendor metadata block embedded in a real TMV `.tif`
(`get_pixel_size_from_tiff.py`, TIFF tag 65027). Camera pixel size = 24 µm (a standard CCD pixel
size). Actual (calibrated) magnification = 12,541.7×. Indicated magnification = 9300.0 — an exact
match to the `9300X` in the filenames, which is the sanity check that confirms the byte-offset
parsing landed on the right fields rather than garbage.

```
pixel_size (Å/px) = (24 µm × 10,000) / 12,541.7  =  19.14 Å/px
```

This lands within ~1.5% of Kayleigh's independent Napari Boxmanager calibration (19.42 Å/px) —
two different methods converging on the same answer. **Use 19.14 Å/px going forward** (the
header-derived value; more directly traceable than a manual scale-bar read). Do not use 1.05 Å/px
anywhere, including in old comparisons — flag any number computed under it as stale.

**What this changes, roughly** (÷1.05 × 19.14 ≈ ×18.2, exact factor: recompute, don't hand-scale):
tube-ID mean length goes from an impossible 7.38 nm to something in the neighborhood of ~135 nm —
physically plausible for a partial-virion trace. **But the previous max (72.60 nm, the case the
2026-07-09 visual check called "clean and continuous") would become roughly ~1320 nm — longer than
one full 300 nm virion.** That's not automatically wrong (TMV rods do aggregate end-to-end in
negative stain), but that specific overlay needs a second look under the corrected framing before
being cited as a single clean filament — don't assume the earlier visual read still holds once the
scale changes this much.

**Still needed before treating any TMV length as final:**
- Re-run `compute_lengths_by_tubeid.py` with `pixel_size=19.14`, don't hand-scale the old numbers.
- Re-check the `..._0033` "clean, continuous" case under the corrected scale — length changes this
  large can change what a trace should be interpreted as.
- Fix `inspect_stars.m`'s hardcoded `1.05` if it's ever re-run, so it doesn't silently regenerate
  wrong numbers again. Not blocking for the CBOX/from-scratch tracer, but worth doing before anyone
  trusts a fresh `master_fiberapp_session.mat`.
- `establish_scale.py`'s CBOX-based `_EstWidth` estimate is still worth running as an independent
  third cross-check, even though the header result is already trustworthy on its own — free
  confirmation, no reason to skip it.

---

## What you (Claude Code) can and cannot do

**You are running locally in VS Code on my laptop. You have no access to ghez.**

- You cannot run these scripts. You cannot see the micrographs, the STAR files, or the cluster
  filesystem. I scp scripts over and run them by hand.
- So: **never say "let me run this and check."** Write the script, give me the **exact command to
  run on ghez**, and tell me **what output would confirm vs. falsify** what you expect.
- If you need to know something about data you can't see: **stop and write a 5-line inspection
  script** for me to run. Do not guess and build on the guess. A round-trip is cheap. A wrong
  assumption baked into 200 lines is not.
- Wait for me to paste real output back before moving to the next step.

### ghez environment (the target machine, not yours)

- Shell is **csh/tcsh**. Redirect stderr with `|&`, never `2>&1`.
- Conda env is **`fragviz`** — Python **3.8**, with **numpy, matplotlib, pillow only**.
  - **No pandas. No scipy.** Use the stdlib `csv` module. If you need
    `scipy.optimize.linear_sum_assignment`, **say so explicitly** so I can install it — do not
    silently `import scipy`.
  - Target 3.8 syntax: no `match`, no `X | Y` type unions, no `dict | dict` merge.
- The shared **base** conda env is broken (mangled, root-owned PIL install). Never suggest it.
- `cryolo-cu11` is for crYOLO runs only.
- File transfer requires a jump host:
  `scp -J gordonez9@sayre.mbi.ucla.edu gordonez9@ghez:<remote> <local>`
  Direct `scp gordonez9@ghez:...` fails from PowerShell (DNS).

---

## Data

**Local (this repo):**
- `cbox_raw/` — TMV `.cbox` files pulled from ghez for development. Asyn work has been archived
  out of this repo, so this directory is TMV-only. Gitignored.

**Remote (ghez) — Kayleigh's TMV run. `output_1/` = Fine Tune 1, 82 micrographs:**

```
/auto_nfs/rodriguez1/kmc012/__crYOLO/TMV/
├── input/                          raw micrographs
└── output_1/
    ├── CBOX/                       ← raw box detections. THIS is our input.
    ├── STAR_FILAMENT_SEGMENTED/    already linked (_rlnHelicalTubeID). Baseline only.
    ├── STAR_FILAMENT_START_END/    ⚠ TWO rows per filament (start + end). Divide by 2.
    ├── VISUAL_OVERLAYS_TIFF/
    └── logs/cmdlogs/               ⚠ predict flags for output_1 NOT yet confirmed
```

**Parameters:**
- **Pixel size: 19.14 Å/px, header-confirmed** (see resolved section above). Still always pass it as
  a required CLI argument and echo it in script output — don't hardcode it as a silent default,
  even though it's now confirmed. Scripts should make the assumption visible every run, not just
  once.
- 82 micrographs. `output_1` used `min_boxes=20`. `box_distance` appears to be **1 px** (inferred
  from a 691-px-long point-to-point path) but is **not confirmed from the log**.
- crYOLO reported **1021 filaments** for Fine Tune 1; my tube-ID script got 1022. That agreement
  is the reproduction target any new grouping code should hit — or deliberately, explicably beat.

---

## CBOX format

STAR-style text. Per-box columns: `_CoordinateX`, `_CoordinateY`, `_Width`, `_Height`,
`_EstWidth`, `_EstHeight`, `_Confidence`, `_Angle` (radians).

**No `_rlnHelicalTubeID`. No grouping at all.** That is the whole point — CBOX is pre-linking, so
it is the correct place to intervene. We build the chains ourselves.

- `_Angle` is a per-box local orientation estimate. **Try using it directly before writing any
  neighbour-based tangent estimator.** It may make the tangent-cost term free.
- `_EstWidth` is crYOLO's estimate of the filament width **in pixels** — and for TMV that width is
  a known 180 Å. See Task 0.

---

## Settled — do not re-litigate

1. **crYOLO's own internal tracing is the fragmentation source**, not Kayleigh's downstream
   `jump_threshold` heuristic. Established by comparing tube-ID lengths against her
   jump_threshold lengths (7.38 vs 7.98–10.15 nm — the "cleaner" grouping was *not* longer),
   plus direct visual inspection.
2. **Two distinct failure modes:**
   - *collinear splitting* — one continuous filament broken into 4–5 tube IDs along its length
   - *crossover clustering* — spurious short fragments accumulating where filaments intersect
3. `STAR_FILAMENT_SEGMENTED` already has crYOLO's linking baked in. It is a **comparison baseline**,
   never a "raw" input.
4. `STAR_FILAMENT_START_END` is **two rows per filament.** Every naive count off it is 2× too high.
5. Kayleigh's `jump_threshold=50px` heuristic and crYOLO's tube IDs **disagree on individual
   filaments** even when their aggregate means look similar. They answer different questions;
   results from the two must not be mixed.

---

## Working agreements

- **Non-destructive, always.** Scripts propose, report, visualize. Nothing overwrites source data.
  No exceptions.
- **Small, runnable increments.** One script, one job. Do not hand me a 400-line pipeline. I have to
  read, understand and defend every line — this goes in an ELN and eventually a paper.
- **Validate before you trust.** New grouping/tracing code must first reproduce a known number
  (crYOLO's own reported filament count) before its novel output means anything. This is what
  caught the 2× bug and it will catch the next one.
- **Physical plausibility is a hard gate.** TMV = 300 nm × 18 nm. A "filament" shorter than ~18 nm
  is not a filament. Any length distribution whose mode isn't near a virion (or a clean shear
  fragment of one) needs an explanation before it becomes a result.
- **No magic numbers.** Every threshold is a named constant at the top of the file, with a comment
  saying where it came from and what it's sensitive to.
- **Print your assumptions.** Every script's first lines of output: input path, pixel size used,
  N files read, N boxes read. A wrong assumption should announce itself immediately, not surface in
  a plot two hours later.
- **Explain the why.** For any algorithmic choice — cost function, threshold, matching strategy —
  say what the alternatives were and why this one. "It's standard" is not a reason.
- **Beware selection bias.** Cases pulled from the extremes of a distribution cannot support a rate
  estimate. Rates come from random samples.
- **git:** `.gitignore` excludes `.mrc`, `.star`, `.cbox`. Never commit data.

---

## Style

I write the ELN myself: first person, casual, reasoning inline, gaps flagged explicitly, no
overclaiming. If you draft ELN text, match that — not a formal report. And when something is
uncertain, say it's uncertain.
