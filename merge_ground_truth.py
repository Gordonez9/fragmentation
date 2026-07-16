"""
Consolidate the repeated exports in ground_truth_annotations/ into one
canonical file.

annotate_filaments.html's Export button dumps the tool's ENTIRE in-memory
state every time, not just what changed since the last export -- so as images
get traced in a session, each successive export is a superset of the one
before it (confirmed by inspection: 6 files, 6 unique images, zero conflicting
filament data for any image that appears in more than one file). This script
re-verifies that assumption in code (it does NOT just trust the prior manual
check) and fails loudly if two files ever disagree on the same image, rather
than silently picking one.

Usage:
    python merge_ground_truth.py ground_truth_annotations
"""

import argparse
import json
import os
import sys


def main():
    parser = argparse.ArgumentParser(
        description="Merge repeated annotate_filaments.html exports into one "
                    "canonical ground-truth file, failing loudly on conflicts.")
    parser.add_argument("gt_dir")
    parser.add_argument("--out", default=None,
                         help="Output path (default: <gt_dir>/merged.json)")
    args = parser.parse_args()

    files = sorted(f for f in os.listdir(args.gt_dir) if f.endswith(".json") and f != "merged.json")
    print("=== merge_ground_truth.py ===")
    print("Input directory: %s" % args.gt_dir)
    print("Export files found: %d -> %s" % (len(files), files))
    print()

    merged = {}
    source_file = {}
    for f in files:
        data = json.load(open(os.path.join(args.gt_dir, f)))
        for name, rec in data["images"].items():
            if name in merged:
                if merged[name]["filaments"] != rec["filaments"]:
                    print("ERROR: conflicting filament data for %s between "
                          "%s and %s -- refusing to guess which is right."
                          % (name, source_file[name], f), file=sys.stderr)
                    sys.exit(1)
                continue
            merged[name] = rec
            source_file[name] = f

    total_filaments = sum(len(r["filaments"]) for r in merged.values())
    total_points = sum(sum(len(fl) for fl in r["filaments"]) for r in merged.values())
    print("--- Merged result ---")
    for name, rec in sorted(merged.items()):
        n_fil = len(rec["filaments"])
        n_pts = sum(len(fl) for fl in rec["filaments"])
        print("  %-32s filaments=%3d  points=%4d  (from %s)"
              % (name, n_fil, n_pts, source_file[name]))
    print()
    print("Images: %d   Total filaments: %d   Total points: %d"
          % (len(merged), total_filaments, total_points))

    out_path = args.out or os.path.join(args.gt_dir, "merged.json")
    out = {"version": 1, "source_files": files, "images": merged}
    with open(out_path, "w") as f:
        json.dump(out, f, indent=2)
    print()
    print("Wrote %s" % out_path)


if __name__ == "__main__":
    main()
