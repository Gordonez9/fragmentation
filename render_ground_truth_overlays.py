"""
Visual QC: draw each traced filament from merged.json back onto its source
PNG, so tracing mistakes (a point landing on the wrong filament during an
overlap, a stray click, a filament that didn't get closed) are visible before
this ground truth gets used for anything -- CLAUDE.md: "validate before you
trust." This does not compute anything; it is purely a look-at-it check.

Usage:
    python render_ground_truth_overlays.py ground_truth_annotations/merged.json \
        20260710_TMV_TALOS/png <output_dir>
"""

import argparse
import json
import os

from PIL import Image, ImageDraw

# --- Named constants --------------------------------------------------------

POINT_RADIUS_PX = 6
# Marker size for each traced point, in full-resolution image px. Large
# enough to see clearly at the zoomed-out preview scale this script also
# writes (see PREVIEW_MAX_DIM), without swamping a single filament's own
# points at full res.

LINE_WIDTH_PX = 3

PREVIEW_MAX_DIM = 1400
# Long-edge size (px) for a second, downscaled copy of each overlay. Full-res
#2048x2115 overlays are fine to inspect one at a time but slow to flip
# through; the preview is for a quick scan across all six.

COLORS = ["#ff4d4d", "#4dff4d", "#4d9fff", "#ffd24d", "#ff4dff", "#4dffff",
          "#ff9d4d", "#c04dff", "#9dff4d", "#ff4d9d"]
# Same palette as annotate_filaments.html, so a filament's color matches
# between the tracing UI and this QC render.


def main():
    parser = argparse.ArgumentParser(description="Render traced filaments back onto their source PNGs for visual QC.")
    parser.add_argument("merged_json")
    parser.add_argument("png_dir")
    parser.add_argument("out_dir")
    args = parser.parse_args()

    data = json.load(open(args.merged_json))
    os.makedirs(args.out_dir, exist_ok=True)

    print("=== render_ground_truth_overlays.py ===")
    print("Ground truth: %s" % args.merged_json)
    print("PNG source dir: %s" % args.png_dir)
    print("Output dir: %s" % args.out_dir)
    print()

    for name, rec in sorted(data["images"].items()):
        png_path = os.path.join(args.png_dir, name)
        if not os.path.exists(png_path):
            print("  %-32s SKIPPED (png not found at %s)" % (name, png_path))
            continue

        img = Image.open(png_path).convert("RGB")
        draw = ImageDraw.Draw(img)
        for fi, filament in enumerate(rec["filaments"]):
            color = COLORS[fi % len(COLORS)]
            pts = [(p[0], p[1]) for p in filament]
            if len(pts) >= 2:
                draw.line(pts, fill=color, width=LINE_WIDTH_PX)
            for (x, y) in pts:
                draw.ellipse([x - POINT_RADIUS_PX, y - POINT_RADIUS_PX,
                              x + POINT_RADIUS_PX, y + POINT_RADIUS_PX], fill=color)

        full_out = os.path.join(args.out_dir, name.replace(".png", "_overlay.png"))
        img.save(full_out)

        scale = min(1.0, PREVIEW_MAX_DIM / max(img.size))
        preview = img.resize((int(img.width * scale), int(img.height * scale)))
        preview_out = os.path.join(args.out_dir, name.replace(".png", "_overlay_preview.png"))
        preview.save(preview_out)

        print("  %-32s %d filaments, %d points -> %s" %
              (name, len(rec["filaments"]), sum(len(f) for f in rec["filaments"]), full_out))

    print()
    print("Look at the *_overlay_preview.png files first -- full-res versions")
    print("are there too if a preview looks suspicious anywhere.")


if __name__ == "__main__":
    main()
