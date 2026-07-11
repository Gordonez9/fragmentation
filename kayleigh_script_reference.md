# Reference — Kayleigh's `inspect_stars.m` (real source)

Context for Task 2 (three-way comparison). **Update:** the actual source turned up in her ELN
export (`Computational_Fibril_Analysis.pdf`, in this project). The earlier version of this doc was
built from a recreated batch script and is superseded — real source below.

## What it actually does

Reads `STAR_FILAMENT_SEGMENTED` (the default `file_type='particles'` path — despite the name, this
is per-box coordinates along crYOLO's traced chain, not individual particle picks). It does **not**
read `_rlnHelicalTubeID` at all — walks the raw coordinate list in file order and applies:

```matlab
pixel_size = 1.05;          % Å/px — hardcoded literal, see CLAUDE.md pixel-size issue
jump_threshold = 50;        % px — gap cutoff for splitting into separate fibers
...
for i = 2:num_points
    dist = sqrt((star_X(i) - star_X(i-1))^2 + (star_Y(i) - star_Y(i-1))^2);
    if dist > jump_threshold
        current_fiber_id = current_fiber_id + 1;
    end
    fiber_ids(i) = current_fiber_id;
end
```

Consecutive points more than 50 px apart start a new fiber ID. That's the entire grouping logic —
no angle, no tangent, no crossover handling. Length per fiber is a running sum of consecutive
point-to-point distances, converted to nm via `pixel_size / 10.0`.

**Confirmed wrong, 2026-07-11:** the pixel size is a hardcoded `1.05` literal, not read from the
MRC header despite her notebook's stated plan to pull it from there. Header-verification (see
CLAUDE.md) puts the real value at **19.14 Å/px** — 1.05 was off by a factor of ~18×. This is the
confirmed source of the impossible length numbers, not just a suspicion anymore.

## Batch version (what actually produces `output_1`'s overlays)

Full signature: `inspect_stars(box_size_angstrom, image_dir, segmented_dir, start_end_dir)`.
Per-micrograph, it:
1. Reads `STAR_FILAMENT_SEGMENTED/<name>.star` — all traced points, no grouping yet.
2. Runs the same 50 px jump_threshold walk to assign `fiber_ids`.
3. Computes `total_lengths_nm` per fiber (same running-sum method).
4. Writes one `.mat` per micrograph to `FIBERAPP_MATS/`, and a color overlay TIFF (one color per
   reconstructed fiber ID, via `jet(numFibers)`) to `VISUAL_OVERLAYS_TIFF/`.
5. Concatenates all per-micrograph `.mat` files into `master_fiberapp_session.mat`.

This is the source of the `⟨L⟩ = 10.15 nm, σ = 10.45 nm` full-batch histogram and the
`⟨L⟩ = 7.98 nm, σ = 7.32 nm` single-micrograph histogram already on record.

## What it is NOT

- Not aware of crYOLO's own tube-ID linking — completely ignores `_rlnHelicalTubeID`, rebuilds
  grouping from raw coordinate proximity as if crYOLO's own chains didn't exist.
- Not aware of local direction/tangent — pure Euclidean distance cutoff.
- Not aware of crossovers specifically — a crossover point with two chains within 50 px gets
  bridged the same as a genuine single filament with a small real gap. No distinction is possible
  from this logic alone.

## Known empirical behavior (2026-07-09 comparison, still valid)

On the same 82-micrograph `output_1` data as the tube-ID script:
- **Long, unambiguous filament (`..._0033`):** full agreement with tube-ID grouping — both call it
  one continuous filament. Not informative; both methods agree on the easy case.
- **Short, fragmented case (`..._0038`):** real disagreement. crYOLO's own tube IDs split a diagonal
  cluster into 4–5 pieces; jump_threshold only splits it into 2 — it bridges some but not all of the
  gaps crYOLO's own tracer left.
- **Crossover fragmentation** shows up in both methods' output independently — not an artifact of
  either particular script.

Net effect: jump_threshold quietly merges some of what crYOLO's own tracer left split, inconsistently,
with no way to tell from the output which merges are correct.

## Why this matters for Task 2

Expect all three methods (crYOLO tube IDs / jump_threshold / a new CBOX-based tracer) to **agree on
clean, isolated filaments** — not informative, both existing methods already agree there. The
comparison is only useful on **ambiguous cases**: near-collinear splits and crossovers, where the
50 px blind cutoff, crYOLO's own tracer, and an angle-aware tracer should be expected to diverge —
and where that divergence is the actual signal.

## Open question this raises for FiberApp downstream work

Her notebook (page 18) also lists planned FiberApp improvements — incorporating `inspect_stars`
directly and adding CSV/Excel export. **Not in scope for this project's tasks**, but worth flagging:
once the pixel-size fix lands, every `.mat`/histogram already produced by this pipeline (including
`master_fiberapp_session.mat`) is off by the same factor and should be regenerated, not patched.
