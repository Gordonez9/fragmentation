"""
Second, independent cross-check on the scale-bar-derived Aa/px for
20260710_TMV_TALOS (see measure_scale_bar.py): measure one isolated,
unambiguous TMV rod directly in KMCB2_B3_RLTMV_22kx_001.tif and see whether
its length/width land near the textbook 300 nm x 18 nm virion once converted
with the scale-bar pixel size. This uses neither the scale bar nor any header
field -- it is a measurement of the specimen itself, so if it agrees with the
scale-bar number that's a genuinely independent confirmation, not a repeat of
the same method.

This is a demo/plausibility check on ONE hand-picked filament, not a filament
detector -- CLAUDE.md scopes automated CBOX-based tracing as a separate,
bigger piece of work. Local-only script (uses scipy, which is NOT available in
the ghez fragviz conda env -- do not scp this to ghez).

Usage:
    python measure_one_virion_talos.py 20260710_TMV_TALOS/KMCB2_B3_RLTMV_22kx_001.tif
"""

import argparse

import numpy as np
from PIL import Image
from scipy import ndimage

# --- Named constants, each with where-it-came-from -------------------------

CROP_BOX = (1450, 1150, 1800, 1750)
# (left, top, right, bottom) in full-image px. Hand-picked region around one
# isolated, straight, unambiguous rod in image 001 -- chosen by eye from a
# downsampled preview specifically because it does not cross or touch any
# other filament, so connected-component picking can't merge two rods into
# one measurement. Specific to this one file; not a general rod finder.

ROD_DARK_THRESHOLD = 110.0
# 8-bit grayscale cutoff for "this pixel is rod, not background." Measured on
# this crop: background is a roughly Gaussian noise field centered ~156,
# std~30 (checked directly); the rod's dark stain forms a clearly separated
# tail below ~110 in the crop's intensity histogram. Sensitive to stain
# contrast -- would need re-tuning per image, which is exactly why this is a
# one-rod demo, not a pipeline.

MORPHOLOGY_ITERATIONS = 1
# Binary opening iterations to strip single-pixel noise specks from the dark
# mask before connected-component labeling, so isolated noise pixels don't
# get picked as a separate (spurious) component. One pass was enough to clean
# the mask on visual inspection; not tuned further.

WIDTH_PERCENTILE = (1, 99)
# Cross-rod width is read as the 1st-99th percentile spread of pixel
# positions along the rod's minor (short) axis, not the full min/max range --
# a handful of stray dark pixels at the mask's edge would otherwise inflate
# the width. 1/99 trims those without meaningfully trimming the rod itself.

TMV_LENGTH_NM = 300.0
TMV_WIDTH_NM = 18.0
# Textbook TMV dimensions (CLAUDE.md). The comparison target, not a fitted
# value.

# The two scale-bar-derived candidates from measure_scale_bar.py on this same
# folder (64/64 files, std=0 -- see that script's output). Both printed here,
# neither picked as more correct, same policy as establish_scale.py.
AA_PER_PX_OUTER_EDGE = 13.158
AA_PER_PX_CENTER_TO_CENTER = 13.405


def main():
    parser = argparse.ArgumentParser(
        description="Measure one isolated TMV rod directly and compare "
                    "against textbook dimensions, as a check independent of "
                    "the scale-bar reading.")
    parser.add_argument("tif_path")
    args = parser.parse_args()

    img = Image.open(args.tif_path).convert("L")
    crop = img.crop(CROP_BOX)
    arr = np.array(crop).astype(float)
    print("=== measure_one_virion_talos.py -- single-rod plausibility check ===")
    print("Input file: %s" % args.tif_path)
    print("Crop box (full-image px): %s" % (CROP_BOX,))
    print("Crop size: %dx%d px" % (arr.shape[1], arr.shape[0]))
    print()

    mask = arr < ROD_DARK_THRESHOLD
    mask = ndimage.binary_opening(mask, iterations=MORPHOLOGY_ITERATIONS)

    labeled, n_components = ndimage.label(mask)
    if n_components == 0:
        print("ERROR: no dark component found below threshold %.1f" % ROD_DARK_THRESHOLD)
        return
    sizes = ndimage.sum(mask, labeled, range(1, n_components + 1))
    rod_label = 1 + int(np.argmax(sizes))
    print("Connected components found: %d (after opening). Using the largest "
          "(%.0f px) as the rod." % (n_components, sizes.max()))

    ys, xs = np.where(labeled == rod_label)
    points = np.stack([xs, ys], axis=1).astype(float)
    centroid = points.mean(axis=0)
    centered = points - centroid

    # PCA via covariance eigen-decomposition: principal axis = rod's long axis.
    cov = np.cov(centered.T)
    eigvals, eigvecs = np.linalg.eigh(cov)
    long_axis = eigvecs[:, np.argmax(eigvals)]
    short_axis = eigvecs[:, np.argmin(eigvals)]

    proj_long = centered @ long_axis
    proj_short = centered @ short_axis

    length_px = proj_long.max() - proj_long.min()
    lo, hi = np.percentile(proj_short, WIDTH_PERCENTILE)
    width_px = hi - lo

    print("Rod pixel count: %d" % len(xs))
    print("Length (long-axis full extent): %.1f px" % length_px)
    print("Width (%d-%dth percentile of short-axis spread): %.1f px"
          % (WIDTH_PERCENTILE[0], WIDTH_PERCENTILE[1], width_px))
    print()

    print("--- Converted to real units, both scale-bar candidates ---")
    for label, aa_per_px in [("outer-edge", AA_PER_PX_OUTER_EDGE),
                              ("center-to-center", AA_PER_PX_CENTER_TO_CENTER)]:
        length_nm = length_px * aa_per_px / 10.0
        width_nm = width_px * aa_per_px / 10.0
        print("  %-17s (%.3f Aa/px): length=%.1f nm (textbook %.0f nm)  "
              "width=%.1f nm (textbook %.0f nm)"
              % (label, aa_per_px, length_nm, TMV_LENGTH_NM, width_nm, TMV_WIDTH_NM))
    print()
    print("Judge plausibility yourself: is length within reason of a whole or")
    print("clean partial virion, and is width close to 18 nm? Do not treat this")
    print("as proof by itself -- one hand-picked rod is not a sample, it's a")
    print("plausibility gate (CLAUDE.md: physical plausibility is a hard gate,")
    print("not a rate estimate).")


if __name__ == "__main__":
    main()
