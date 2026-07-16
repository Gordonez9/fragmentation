"""
Convert the hand-traced filament polylines in ground_truth_annotations/merged.json
into real-world lengths (nm), using the scale-bar calibration from
measure_scale_bar.py (this folder's own Aa/px -- NOT the 19.14 Aa/px resolved
for the separate 9300X dataset, see CLAUDE.md).

Length is arc length: the sum of straight-line segment distances between
consecutive traced points, in px, converted to nm. This is NOT end-to-end
(start-to-finish) distance, so a curved/kinked trace is measured correctly
along its path rather than shortcut across it.

This ground truth was traced deliberately including small broken pieces,
overlapping/crossing filaments, and fragments cut off at the image edge (per
the user, 2026-07-15) -- so the resulting length distribution is NOT expected
to cluster near one virion length. Short lengths here are real, not noise:
they are exactly the fragmentation this whole project exists to characterize.
Do not silently filter them.

Usage:
    python measure_ground_truth_lengths.py ground_truth_annotations/merged.json
"""

import argparse
import json
import math

# --- Named constants --------------------------------------------------------

# From measure_scale_bar.py, run on this same 20260710_TMV_TALOS folder
# (64/64 images, std=0 -- see runs/20260715_talos_scale_bar_calibration/).
# Two tick-reading conventions, neither picked as correct -- both reported.
AA_PER_PX_OUTER_EDGE = 13.158
AA_PER_PX_CENTER_TO_CENTER = 13.405

TMV_LENGTH_NM = 300.0
TMV_WIDTH_NM = 18.0
# Textbook TMV dimensions (CLAUDE.md) -- comparison targets only.

MIN_PHYSICALLY_PLAUSIBLE_NM = 18.0
# CLAUDE.md's hard gate: "A 'filament' shorter than ~18 nm is not a filament."
# Flags traces this script can't itself explain (e.g. an accidental 2-click
# trace), not a filter -- nothing is dropped from the output.


def arc_length_px(points):
    total = 0.0
    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        total += math.hypot(x1 - x0, y1 - y0)
    return total


def main():
    parser = argparse.ArgumentParser(description="Compute real-world lengths for hand-traced ground-truth filaments.")
    parser.add_argument("merged_json")
    args = parser.parse_args()

    data = json.load(open(args.merged_json))
    print("=== measure_ground_truth_lengths.py ===")
    print("Input: %s" % args.merged_json)
    print("Aa/px candidates: outer-edge=%.3f, center-to-center=%.3f (from measure_scale_bar.py, this folder)"
          % (AA_PER_PX_OUTER_EDGE, AA_PER_PX_CENTER_TO_CENTER))
    print()

    rows = []
    for name, rec in sorted(data["images"].items()):
        for fi, filament in enumerate(rec["filaments"]):
            if len(filament) < 2:
                print("  SKIP %s filament %d: only %d point(s), no length defined"
                      % (name, fi, len(filament)))
                continue
            length_px = arc_length_px(filament)
            length_nm_outer = length_px * AA_PER_PX_OUTER_EDGE / 10.0
            length_nm_center = length_px * AA_PER_PX_CENTER_TO_CENTER / 10.0
            rows.append((name, fi, len(filament), length_px, length_nm_outer, length_nm_center))

    print("--- Per-filament lengths ---")
    print("%-32s %4s %6s %10s %14s %16s" % ("image", "fil#", "npts", "px", "nm (outer)", "nm (center)"))
    n_below_gate = 0
    for name, fi, npts, px, nm_o, nm_c in rows:
        flag = ""
        if nm_o < MIN_PHYSICALLY_PLAUSIBLE_NM or nm_c < MIN_PHYSICALLY_PLAUSIBLE_NM:
            flag = "  <-- below %.0f nm plausibility gate" % MIN_PHYSICALLY_PLAUSIBLE_NM
            n_below_gate += 1
        print("%-32s %4d %6d %10.1f %14.1f %16.1f%s" % (name, fi, npts, px, nm_o, nm_c, flag))

    lengths_nm_outer = [r[4] for r in rows]
    lengths_nm_center = [r[5] for r in rows]
    n = len(rows)
    print()
    print("--- Summary (n=%d traced filaments, %d images) ---" % (n, len(data["images"])))
    for label, vals in [("outer-edge Aa/px", lengths_nm_outer), ("center-to-center Aa/px", lengths_nm_center)]:
        vals_sorted = sorted(vals)
        median = vals_sorted[n//2] if n % 2 else (vals_sorted[n//2-1] + vals_sorted[n//2]) / 2
        print("  %-24s min=%.1f  median=%.1f  max=%.1f  mean=%.1f nm"
              % (label, min(vals), median, max(vals), sum(vals)/n))
    print()
    print("Filaments below the %.0f nm plausibility gate: %d / %d" % (MIN_PHYSICALLY_PLAUSIBLE_NM, n_below_gate, n))
    print("(Not an error by itself -- this ground truth deliberately includes small")
    print("broken pieces and edge fragments. Judge against what's visible in the")
    print("runs/20260715_ground_truth_qc/ overlays, not against this number alone.)")
    print()
    print("Textbook virion: %.0f nm long. Median above should be judged against that" % TMV_LENGTH_NM)
    print("with the fragmentation/aggregation caveat in mind -- this set was NOT")
    print("selected to be 'clean' filaments, so agreement or disagreement with 300 nm")
    print("here is not itself a validation of anything yet.")


if __name__ == "__main__":
    main()
