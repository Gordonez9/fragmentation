"""
Task 0 -- establish TMV's pixel size before anything else gets built on it.

Two numbers are in circulation and were never reconciled (see CLAUDE.md):
  - 1.05 Aa/px  -- hardcoded literal in Kayleigh's inspect_stars.m, despite
                   her own notebook's stated plan to read it from the MRC
                   header. Never actually read from anywhere.
  - 19.42 Aa/px -- a measured calibration from her notebook (Napari
                   Boxmanager, "ASPECT RATIO IS 0.5150 PIXELS/NM"), i.e. a
                   scale-bar-derived number, not a header read either.

This script does NOT decide between them. It computes a third, independent
estimate from the CBOX boxes themselves (_EstWidth vs. TMV's known 180 Aa
width), prints both candidates side by side against that estimate, and
prints a coordinate-range sanity check. It picks no winner in code.

The real answer is the MRC header, which this script cannot read (no ghez
access from here) -- see the printed instructions at the end for the two
commands that actually settle it.

Standalone on purpose (no project imports) so it is a single file to scp to
ghez. Python 3.8, numpy only -- no scipy, no pandas (fragviz conda env).

Usage:
    python establish_scale.py <cbox_dir>

Examples:
    python establish_scale.py cbox_raw/TMV                     # local dev subset (4 files)
    python establish_scale.py output_1/CBOX                    # ghez, real 82-micrograph run
"""

import argparse
import sys
from pathlib import Path

import numpy as np

# --- Named constants, each with where-it-came-from -------------------------

TMV_WIDTH_ANGSTROM = 180.0
# TMV virion width, textbook value (CLAUDE.md: "A TMV virion is 300 nm long
# and 18 nm wide"). Independent of both candidates below -- used to derive a
# third pixel-size estimate straight from the CBOX boxes.

CANDIDATE_HARDCODED_AA_PER_PX = 1.05
# Kayleigh's inspect_stars.m: `pixel_size = 1.05;` -- a literal constant,
# NOT read from the MRC header despite her notebook's stated intent to do so
# (see kayleigh_script_reference.md). Leading suspect for being wrong.

CANDIDATE_NAPARI_CALIBRATION_AA_PER_PX = 19.42
# Kayleigh's notebook, Napari Boxmanager training setup: "ASPECT RATIO IS
# 0.5150 PIXELS/NM = 19.42 Å/PIXEL". A measured calibration, but not
# confirmed to be a header read or how the scale bar itself was calibrated.

MAGNIFICATION = 9300
# From the CBOX filenames themselves (..._9300X_...). Used only to label the
# coordinate-range sanity check below -- not used in any calculation.


def read_cbox(path):
    """Parse a .cbox file's data_cryolo loop_ block into a list of dicts,
    one per raw box detection. Numeric fields converted, <NA> -> None.
    Self-contained copy of cbox_utils.read_cbox's parsing logic (kept
    standalone here so this script has zero project dependencies)."""
    with open(path) as f:
        lines = f.readlines()

    header_cols = {}
    data_start = None
    col_idx = 0
    in_cryolo_block = False
    for i, line in enumerate(lines):
        s = line.strip()
        if s == "data_cryolo":
            in_cryolo_block = True
            continue
        if not in_cryolo_block:
            continue
        if s.startswith("_"):
            name = s.split()[0][1:]
            header_cols[name] = col_idx
            col_idx += 1
        elif header_cols and not s.startswith(("_", "loop_", "data_", "#")) and s:
            data_start = i
            break

    if data_start is None:
        return []

    def parse_val(v):
        return None if v == "<NA>" else float(v)

    boxes = []
    for line in lines[data_start:]:
        parts = line.split()
        if len(parts) < len(header_cols):
            continue
        row = dict((name, parse_val(parts[idx])) for name, idx in header_cols.items())
        boxes.append(row)
    return boxes


def summarize(values):
    """(median, q1, q3, n) via numpy only -- no scipy."""
    arr = np.asarray(values, dtype=float)
    q1, med, q3 = np.percentile(arr, [25, 50, 75])
    return float(med), float(q1), float(q3), len(arr)


def main():
    parser = argparse.ArgumentParser(
        description="Task 0: triangulate TMV's pixel size from CBOX _EstWidth, "
                     "without adopting either candidate on faith.")
    parser.add_argument("cbox_dir", help="Directory containing .cbox files "
                         "(e.g. cbox_raw/TMV locally, or output_1/CBOX on ghez).")
    args = parser.parse_args()

    cbox_dir = Path(args.cbox_dir)
    if not cbox_dir.is_dir():
        print("ERROR: not a directory: %s" % cbox_dir, file=sys.stderr)
        sys.exit(1)

    files = sorted(cbox_dir.glob("*.cbox"))
    if not files:
        print("ERROR: no .cbox files found in %s" % cbox_dir, file=sys.stderr)
        sys.exit(1)

    print("=== establish_scale.py -- Task 0 pixel-size triangulation ===")
    print("Input directory: %s" % cbox_dir)
    print(".cbox files found: %d" % len(files))
    print()

    all_estwidths = []
    all_coord_x = []
    all_coord_y = []
    total_boxes = 0

    print("--- Per-file box counts and _EstWidth (px) ---")
    for f in files:
        boxes = read_cbox(f)
        total_boxes += len(boxes)
        ew = [b["EstWidth"] for b in boxes if b.get("EstWidth") is not None]
        n_missing = len(boxes) - len(ew)
        all_estwidths.extend(ew)
        all_coord_x.extend(b["CoordinateX"] for b in boxes if b.get("CoordinateX") is not None)
        all_coord_y.extend(b["CoordinateY"] for b in boxes if b.get("CoordinateY") is not None)

        if ew:
            med, q1, q3, n = summarize(ew)
            missing_note = "  (%d missing EstWidth)" % n_missing if n_missing else ""
            print("  %-55s n_boxes=%4d  EstWidth median=%.2f  IQR=[%.2f, %.2f]%s"
                  % (f.name, len(boxes), med, q1, q3, missing_note))
        else:
            print("  %-55s n_boxes=%4d  EstWidth: NO VALID VALUES" % (f.name, len(boxes)))
    print()
    print("Total boxes read (all files): %d" % total_boxes)
    print("Total boxes with a valid _EstWidth: %d" % len(all_estwidths))
    print()

    if not all_estwidths:
        print("ERROR: no valid _EstWidth values anywhere in this directory -- "
              "cannot compute the CBOX-derived estimate.", file=sys.stderr)
        sys.exit(1)

    med_ew, q1_ew, q3_ew, n_ew = summarize(all_estwidths)
    print("--- Pooled _EstWidth summary (px), all files combined ---")
    print("n=%d  median=%.3f px  IQR=[%.3f, %.3f]" % (n_ew, med_ew, q1_ew, q3_ew))
    print()

    # [1] Estimate independent of both Kayleigh numbers -------------------
    implied_px_size_from_estwidth = TMV_WIDTH_ANGSTROM / med_ew
    print("[1] Estimate from _EstWidth alone (independent of both Kayleigh numbers)")
    print("    TMV known width = %.1f Aa (textbook, CLAUDE.md)" % TMV_WIDTH_ANGSTROM)
    print("    median _EstWidth (pooled, above) = %.3f px" % med_ew)
    print("    implied pixel size = %.1f / %.3f = %.4f Aa/px"
          % (TMV_WIDTH_ANGSTROM, med_ew, implied_px_size_from_estwidth))
    print()

    # [2] The two named candidates, stated plainly -------------------------
    implied_width_a = TMV_WIDTH_ANGSTROM / CANDIDATE_HARDCODED_AA_PER_PX
    implied_width_b = TMV_WIDTH_ANGSTROM / CANDIDATE_NAPARI_CALIBRATION_AA_PER_PX
    print("[2] The two candidates in circulation, stated plainly (no winner picked here)")
    print("    Candidate A -- inspect_stars.m hardcoded literal: %.2f Aa/px"
          % CANDIDATE_HARDCODED_AA_PER_PX)
    print("        implied filament width = %.1f / %.2f = %.2f px"
          % (TMV_WIDTH_ANGSTROM, CANDIDATE_HARDCODED_AA_PER_PX, implied_width_a))
    print("        vs. measured median _EstWidth = %.3f px" % med_ew)
    print("    Candidate B -- Kayleigh's Napari Boxmanager calibration: %.2f Aa/px"
          % CANDIDATE_NAPARI_CALIBRATION_AA_PER_PX)
    print("        implied filament width = %.1f / %.2f = %.2f px"
          % (TMV_WIDTH_ANGSTROM, CANDIDATE_NAPARI_CALIBRATION_AA_PER_PX, implied_width_b))
    print("        vs. measured median _EstWidth = %.3f px" % med_ew)
    print()

    # [3] Coordinate range sanity check ------------------------------------
    x_arr = np.asarray(all_coord_x, dtype=float)
    y_arr = np.asarray(all_coord_y, dtype=float)
    x_min, x_max = float(x_arr.min()), float(x_arr.max())
    y_min, y_max = float(y_arr.min()), float(y_arr.max())
    span_x_px = x_max - x_min
    span_y_px = y_max - y_min

    def fov_nm(span_px, aa_per_px):
        return span_px * aa_per_px / 10.0

    print("[3] Coordinate range sanity check (pooled across all files -- boxes span")
    print("    multiple micrographs, so this is the union of box positions, not one")
    print("    micrograph's frame; still useful as an order-of-magnitude check)")
    print("    _CoordinateX range: [%.1f, %.1f] px  (span %.1f px)" % (x_min, x_max, span_x_px))
    print("    _CoordinateY range: [%.1f, %.1f] px  (span %.1f px)" % (y_min, y_max, span_y_px))
    print("    Magnification on record (from filenames): %dx" % MAGNIFICATION)
    print("    Implied box-position span in real space, per candidate:")
    print("        at %.2f Aa/px (A): %.1f x %.1f nm"
          % (CANDIDATE_HARDCODED_AA_PER_PX, fov_nm(span_x_px, CANDIDATE_HARDCODED_AA_PER_PX),
             fov_nm(span_y_px, CANDIDATE_HARDCODED_AA_PER_PX)))
    print("        at %.2f Aa/px (B): %.1f x %.1f nm"
          % (CANDIDATE_NAPARI_CALIBRATION_AA_PER_PX,
             fov_nm(span_x_px, CANDIDATE_NAPARI_CALIBRATION_AA_PER_PX),
             fov_nm(span_y_px, CANDIDATE_NAPARI_CALIBRATION_AA_PER_PX)))
    print("    (No independent detector physical-pixel-size figure is available")
    print("     locally, so this prints the implied span for each candidate without")
    print("     asserting which is plausible -- judge against what you know of the")
    print("     detector and this micrograph's actual frame size.)")
    print()

    print("=== This script does not settle it. Two things do: ===")
    print("  1. header <a real TMV .mrc file> |& grep -i pixel")
    print("     (csh syntax, ghez. Real answer -- everything above is triangulation")
    print("     while we wait for this.)")
    print("  2. Whatever confirms how the 0.5150 px/nm / 19.42 Aa/px number in")
    print("     Kayleigh's notebook was actually derived (scale-bar measurement?")
    print("     known standard? a specific micrograph?) -- good corroborating")
    print("     evidence, but not as authoritative as the header.")


if __name__ == "__main__":
    main()
