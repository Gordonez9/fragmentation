"""
compute_lengths_by_tubeid.py

Reads STAR_FILAMENT_SEGMENTED files and computes contour length per filament,
using crYOLO's own _rlnHelicalTubeID column to group points instead of a
distance heuristic (jump_threshold).
"""

import sys
import glob
import math
import csv
from collections import defaultdict


def parse_star_file(path):
    with open(path) as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith(("_", "#", "data_", "loop_")):
                continue
            cols = line.split()
            x = float(cols[0])
            y = float(cols[1])
            tube_id = cols[3]
            yield tube_id, x, y


def lengths_for_file(path, pixel_size_angstrom):
    points_by_tube = defaultdict(list)
    for tube_id, x, y in parse_star_file(path):
        points_by_tube[tube_id].append((x, y))

    lengths_nm = {}
    for tube_id, pts in points_by_tube.items():
        length_px = 0.0
        for (x1, y1), (x2, y2) in zip(pts[:-1], pts[1:]):
            length_px += math.hypot(x2 - x1, y2 - y1)
        length_angstrom = length_px * pixel_size_angstrom
        lengths_nm[tube_id] = length_angstrom / 10.0

    return lengths_nm


def main():
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(1)

    star_dir = sys.argv[1]
    pixel_size_angstrom = float(sys.argv[2])

    all_lengths = []
    per_file_counts = {}

    star_files = sorted(glob.glob(f"{star_dir}/*.star"))
    if not star_files:
        print(f"No .star files found in {star_dir}")
        sys.exit(1)

    for f in star_files:
        lengths = lengths_for_file(f, pixel_size_angstrom)
        per_file_counts[f] = len(lengths)
        all_lengths.extend(lengths.values())

    n = len(all_lengths)
    mean_len = sum(all_lengths) / n
    variance = sum((l - mean_len) ** 2 for l in all_lengths) / n
    std_len = math.sqrt(variance)

    print(f"Micrographs processed: {len(star_files)}")
    print(f"Total filaments (tube-ID grouped): {n}")
    print(f"Mean length: {mean_len:.2f} nm")
    print(f"Std dev: {std_len:.2f} nm")
    print(f"Min / Max: {min(all_lengths):.2f} / {max(all_lengths):.2f} nm")

    out_csv = "filament_lengths_tubeid.csv"
    with open(out_csv, "w", newline="") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["micrograph", "tube_id", "length_nm"])
        for f in star_files:
            lengths = lengths_for_file(f, pixel_size_angstrom)
            for tube_id, length_nm in lengths.items():
                writer.writerow([f, tube_id, f"{length_nm:.3f}"])

    print(f"\nPer-filament lengths written to: {out_csv}")


if __name__ == "__main__":
    main()
