"""
Independent pixel-size calibration for the new 20260710_TMV_TALOS TIFFs, read
directly off the burned-in scale bar rather than trusted from any header field.

This is a DIFFERENT dataset from the one CLAUDE.md's "Resolved" section settled
(9300X, 19.14 Aa/px, header tag 65027, TalosF200C not confirmed for that run).
These files are 22000X (confirmed per-file below from FEI tag 34682) and were
shot on a Talos F200C (per the same tag) -- a new magnification, quite possibly
a new microscope session. Do NOT reuse 19.14 Aa/px for this folder. This script
establishes this folder's own number instead of assuming continuity.

Method: FEI/Thermo TIA-style TIFFs embed a caption strip burned into the image
itself (not just header text) showing a caliper-style scale bar ("|---| 500 nm").
This script locates that bar by pixel intensity, measures its length in pixels,
and divides the known real-world length by it. It does NOT use the camera's
physical pixel size or any calibrated-magnification header field -- those
aren't present in this software's metadata block (checked: FEI tag 34682 has
Magnification=22000 but no pixel-size or camera-model field). The scale bar is
the calibration source of truth for this folder, the same role the MRC header
played for the 9300X dataset.

Two conventions for reading caliper-style tick marks are reported side by side
(see printed output) because they can differ by a few percent and this script
does not assume which one the acquisition software intended:
  - outer edge to outer edge of the two end ticks
  - center to center of the two end ticks
Neither is asserted as correct; both are printed so a human judges plausibility
against the physical-detector cross-check also printed below.

Standalone, PIL + numpy only.

Usage:
    python measure_scale_bar.py <tif_dir> --bar-nm 500

Redirect stdout into its own dated run folder rather than overwriting a prior
result, e.g.:
    python measure_scale_bar.py 20260710_TMV_TALOS --bar-nm 500 \
        > runs/<YYYYMMDD>_<label>/output.txt
"""

import argparse
import os
import re
import sys

import numpy as np
from PIL import Image

# --- Named constants, each with where-it-came-from -------------------------

BRIGHTNESS_THRESHOLD = 200
# 8-bit grayscale cutoff for "this pixel is part of the white scale bar/text
# on the black caption strip." Checked on KMCB2_B3_RLTMV_22kx_001.tif: bar and
# text pixels are flat 255, background is flat 0, no antialiasing observed
# (threshold 100 and 200 gave identical column masks) -- so this is not a
# sensitive choice for this dataset, but it is named because a different
# export setting could reintroduce antialiased edges.

MICROGRAPH_ROW_MEAN_THRESHOLD = 80.0
# A micrograph row (grainy negative-stain background) has mean pixel value
# ~167-171 (measured, file 001). Every row of the black caption strip stays
# below ~60, INCLUDING rows that pass through the bar or text -- those are
# sparse bright pixels on a black field (e.g. a tick-mark row: 32 of 2048
# columns bright ~= mean 4). Row std is NOT used for this because bar/text
# rows have high variance too (bright-on-black) and get misidentified as
# micrograph noise -- mean is the signal that actually separates the two.

MIN_TICK_HEIGHT_PX = 15
# A caliper end-tick is tall (~32px measured); the horizontal connecting line
# between the two ticks is shorter (~8px measured, file 001). Used to split
# tick columns from line columns WITHIN the single bar run (see
# BAR_RUN_MIN_WIDTH_PX) -- NOT to distinguish the bar from text, since text
# digit glyphs ("5", "0") are just as tall as a tick and this cannot tell them
# apart by height alone.

BAR_RUN_MIN_WIDTH_PX = 150
# The bar -- both end ticks plus the connecting line between them -- forms ONE
# contiguous bright run (the line's height is only 8px but still > 0, so
# col_heights never drops to 0 between the ticks; there is no run gap there).
# Measured width on file 001: 381px. A single text glyph run is much narrower
# (24-40px, measured). 150 sits well between the two, so "the one run wider
# than this" identifies the bar run robustly, independent of tick height,
# which text digits also reach.

CAPTION_SEARCH_MAX_ROWS = 250
# How far up from the bottom of the image to search for the caption-strip
# boundary. Measured caption strip on file 001 is ~70px tall; 250 gives large
# margin without risking picking up a false low-std row inside the micrograph
# itself (unlikely but not asserted impossible).


def find_caption_strip_top(gray_arr):
    """Row index where the black caption strip begins, found by scanning
    upward from the bottom for the first row with micrograph-like brightness."""
    h = gray_arr.shape[0]
    search_start = max(0, h - CAPTION_SEARCH_MAX_ROWS)
    row_mean = gray_arr[search_start:h, :].mean(axis=1)
    for i in range(len(row_mean) - 1, -1, -1):
        if row_mean[i] > MICROGRAPH_ROW_MEAN_THRESHOLD:
            return search_start + i + 1
    return None


def find_bar_ticks(gray_arr, caption_top):
    """Within the caption strip, return (left_tick, right_tick) column ranges
    for the two end ticks of the scale bar, or None if not found."""
    strip = gray_arr[caption_top:, :]
    bright = strip > BRIGHTNESS_THRESHOLD
    col_heights = bright.sum(axis=0)
    nonzero_cols = np.where(col_heights > 0)[0]
    if len(nonzero_cols) == 0:
        return None

    # Group into contiguous runs (small gaps tolerated within one glyph/tick).
    runs = []
    start = nonzero_cols[0]
    prev = nonzero_cols[0]
    for c in nonzero_cols[1:]:
        if c - prev > 3:
            runs.append((start, prev))
            start = c
        prev = c
    runs.append((start, prev))

    # The bar (both ticks + connecting line) is ONE run, wider than any single
    # text glyph -- see BAR_RUN_MIN_WIDTH_PX. Text runs are excluded by width,
    # not by height (a digit glyph can be as tall as a tick).
    bar_runs = [r for r in runs if (r[1] - r[0] + 1) >= BAR_RUN_MIN_WIDTH_PX]
    if len(bar_runs) != 1:
        return None
    bar_left, bar_right = bar_runs[0]

    # Within the bar run, split tick columns (tall) from connecting-line
    # columns (short) to find the two tick clusters.
    is_tick = col_heights[bar_left:bar_right + 1] >= MIN_TICK_HEIGHT_PX
    tick_cols = np.where(is_tick)[0] + bar_left
    if len(tick_cols) == 0:
        return None
    clusters = []
    c_start = tick_cols[0]
    c_prev = tick_cols[0]
    for c in tick_cols[1:]:
        if c - c_prev > 3:
            clusters.append((c_start, c_prev))
            c_start = c
        c_prev = c
    clusters.append((c_start, c_prev))
    if len(clusters) < 2:
        return None
    return clusters[0], clusters[-1]


def get_magnification(tif_path):
    img = Image.open(tif_path)
    xml = img.tag_v2.get(34682, "")
    m = re.search(r"<Label>Magnification</Label><Value>([\d.]+)</Value>", xml)
    return float(m.group(1)) if m else None


def measure_one(tif_path, bar_nm):
    img = Image.open(tif_path).convert("L")
    arr = np.array(img)

    caption_top = find_caption_strip_top(arr)
    if caption_top is None:
        return {"file": os.path.basename(tif_path), "error": "caption strip not found"}

    ticks = find_bar_ticks(arr, caption_top)
    if ticks is None:
        return {"file": os.path.basename(tif_path), "error": "scale bar ticks not found"}

    left, right = ticks
    outer_px = right[1] - left[0]
    center_px = ((right[0] + right[1]) / 2.0) - ((left[0] + left[1]) / 2.0)

    bar_A = bar_nm * 10.0
    return {
        "file": os.path.basename(tif_path),
        "magnification": get_magnification(tif_path),
        "outer_px": outer_px,
        "center_px": center_px,
        "aa_per_px_outer": bar_A / outer_px,
        "aa_per_px_center": bar_A / center_px,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Measure the burned-in scale bar across a folder of TIFFs "
                    "to get an independent, per-folder Aa/px calibration.")
    parser.add_argument("tif_dir", help="Directory of .tif files with a burned-in scale bar.")
    parser.add_argument("--bar-nm", type=float, required=True,
                         help="Real-world length the scale bar represents, in nm "
                              "(read visually off the image -- this script does not OCR it).")
    args = parser.parse_args()

    files = sorted(f for f in os.listdir(args.tif_dir)
                    if f.endswith(".tif") and not f.startswith("._"))
    print("=== measure_scale_bar.py -- per-folder scale-bar calibration ===")
    print("Input directory: %s" % args.tif_dir)
    print("Scale bar length assumed: %.1f nm (user-confirmed, not OCR'd)" % args.bar_nm)
    print(".tif files found: %d" % len(files))
    print()

    results = []
    for f in files:
        r = measure_one(os.path.join(args.tif_dir, f), args.bar_nm)
        results.append(r)
        if "error" in r:
            print("  %-40s ERROR: %s" % (r["file"], r["error"]))
        else:
            print("  %-40s mag=%dx  outer=%.1fpx (%.3f Aa/px)  center=%.1fpx (%.3f Aa/px)"
                  % (r["file"], r["magnification"], r["outer_px"], r["aa_per_px_outer"],
                     r["center_px"], r["aa_per_px_center"]))

    ok = [r for r in results if "error" not in r]
    errors = [r for r in results if "error" in r]
    print()
    print("Measured OK: %d / %d" % (len(ok), len(results)))
    if errors:
        print("Failed: %s" % ", ".join(r["file"] for r in errors))

    if not ok:
        sys.exit(1)

    mags = set(r["magnification"] for r in ok)
    if len(mags) > 1:
        print("WARNING: multiple magnifications found in this folder: %s -- "
              "a single pooled Aa/px is not valid across them." % mags)

    outer_vals = np.array([r["aa_per_px_outer"] for r in ok])
    center_vals = np.array([r["aa_per_px_center"] for r in ok])
    print()
    print("--- Pooled result (n=%d) ---" % len(ok))
    print("outer-edge convention:  median=%.4f Aa/px  IQR=[%.4f, %.4f]  std=%.4f"
          % (np.median(outer_vals), np.percentile(outer_vals, 25),
             np.percentile(outer_vals, 75), outer_vals.std()))
    print("center-to-center conv:  median=%.4f Aa/px  IQR=[%.4f, %.4f]  std=%.4f"
          % (np.median(center_vals), np.percentile(center_vals, 25),
             np.percentile(center_vals, 75), center_vals.std()))
    print()
    print("Low std across files (if seen above) means the bar is drawn identically")
    print("every frame, as expected for a fixed-magnification session -- that's a")
    print("consistency check on this script, not a precision claim about the true")
    print("Aa/px. The outer-edge vs. center-to-center gap is the real uncertainty;")
    print("report a range, not a single number, until cross-checked another way")
    print("(e.g. against a known camera physical pixel size + binning, or against")
    print("a directly measured TMV virion in one of these images).")


if __name__ == "__main__":
    main()
