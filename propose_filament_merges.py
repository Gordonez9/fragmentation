"""
Propose candidate merges between crYOLO filament chains based on
endpoint distance + tangent-direction agreement, instead of distance
(jump_threshold) alone.

Input: a STAR_FILAMENT_SEGMENTED file for one micrograph.
Output: ranked list of candidate merges for manual review in boxmanager.

This does NOT modify any files or auto-merge anything. It only proposes.

Usage:
    python propose_filament_merges.py path/to/mgname.star \
        --max_dist 60 --angle_weight 40 --n_tangent 4 --top 20
"""

import argparse
import math
from collections import defaultdict
from itertools import combinations

import numpy as np
from scipy.optimize import linear_sum_assignment


def read_star_filament_segmented(path):
    """
    Parses a STAR_FILAMENT_SEGMENTED file into {filament_id: [(x, y), ...]}
    ordered as they appear in the file (assumed trace order).

    Assumes columns include rlnCoordinateX, rlnCoordinateY, rlnHelicalTubeID.
    Adjust column names below if your header differs -- check with:
        grep "^_rln" yourfile.star
    """
    with open(path) as f:
        lines = f.readlines()

    header_cols = {}
    data_start = None
    col_idx = 0
    for i, line in enumerate(lines):
        s = line.strip()
        if s.startswith("_rln"):
            name = s.split()[0][1:]  # strip leading underscore
            header_cols[name] = col_idx
            col_idx += 1
        elif header_cols and not s.startswith(("_", "loop_", "data_", "#")) and s:
            data_start = i
            break

    if data_start is None:
        return {}

    x_col = header_cols.get("rlnCoordinateX")
    y_col = header_cols.get("rlnCoordinateY")
    id_col = header_cols.get("rlnHelicalTubeID")
    if x_col is None or y_col is None or id_col is None:
        raise ValueError(
            f"Expected columns not found. Got: {list(header_cols.keys())}. "
            "Update column names in read_star_filament_segmented()."
        )

    chains = defaultdict(list)
    for line in lines[data_start:]:
        parts = line.split()
        if len(parts) <= max(x_col, y_col, id_col):
            continue
        x, y, tube_id = float(parts[x_col]), float(parts[y_col]), parts[id_col]
        chains[tube_id].append((x, y))

    return dict(chains)


def chain_endpoints_with_tangent(points, n_tangent=4):
    """
    Returns (start_point, start_tangent, end_point, end_tangent).
    Tangent points AWAY from the chain body at each end, estimated from
    up to n_tangent points, so it's a fair "which way was this chain
    heading" estimate rather than just the last two (noisy) points.
    """
    pts = np.array(points, dtype=float)
    n = min(n_tangent, len(pts) - 1)
    if n < 1:
        # degenerate single-point chain, no direction info
        return pts[0], None, pts[-1], None

    start_tangent = pts[0] - pts[n]      # points away from the chain, at the start
    end_tangent = pts[-1] - pts[-1 - n]  # points away from the chain, at the end

    def normalize(v):
        norm = np.linalg.norm(v)
        return v / norm if norm > 1e-9 else None

    return pts[0], normalize(start_tangent), pts[-1], normalize(end_tangent)


def angle_between(v1, v2):
    """Angle in degrees between two direction vectors, 0-180."""
    if v1 is None or v2 is None:
        return 180.0  # no info -> treat as worst case, don't reward it
    cos_angle = np.clip(np.dot(v1, v2), -1.0, 1.0)
    return math.degrees(math.acos(cos_angle))


def build_cost_matrix(loose_ends, max_dist, angle_weight):
    """
    loose_ends: list of dicts with keys chain_id, end ('start'/'end'), point, tangent
    Returns an NxN cost matrix (same list used for both axes) with a large
    cost (BIG) for same-chain pairs and pairs beyond max_dist.
    """
    n = len(loose_ends)
    BIG = 1e6
    cost = np.full((n, n), BIG)

    for i, j in combinations(range(n), 2):
        a, b = loose_ends[i], loose_ends[j]
        if a["chain_id"] == b["chain_id"]:
            continue  # can't merge a chain with itself

        dist = np.linalg.norm(a["point"] - b["point"])
        if dist > max_dist:
            continue

        # Two chain ends continuing each other should have roughly
        # ANTIPARALLEL outward tangents (both point away from their own
        # chain, toward each other's chain if it's really one filament).
        angle = angle_between(a["tangent"], b["tangent"])
        angle_disagreement = 180.0 - angle  # 0 = perfectly antiparallel (good)

        c = dist + angle_weight * (angle_disagreement / 180.0)
        cost[i, j] = c
        cost[j, i] = c

    return cost


def propose_merges(star_path, max_dist=60, angle_weight=40, n_tangent=4, top=20):
    chains = read_star_filament_segmented(star_path)
    if len(chains) < 2:
        print("Fewer than 2 chains found, nothing to compare.")
        return []

    loose_ends = []
    for chain_id, points in chains.items():
        if len(points) < 2:
            continue
        start_pt, start_tan, end_pt, end_tan = chain_endpoints_with_tangent(
            points, n_tangent=n_tangent
        )
        loose_ends.append(
            {"chain_id": chain_id, "end": "start", "point": start_pt, "tangent": start_tan}
        )
        loose_ends.append(
            {"chain_id": chain_id, "end": "end", "point": end_pt, "tangent": end_tan}
        )

    cost = build_cost_matrix(loose_ends, max_dist, angle_weight)
    row_ind, col_ind = linear_sum_assignment(cost)

    proposals = []
    seen_pairs = set()
    for i, j in zip(row_ind, col_ind):
        if i >= j:
            continue
        c = cost[i, j]
        if c >= 1e6:
            continue  # infeasible pair, Hungarian was forced into it, discard
        a, b = loose_ends[i], loose_ends[j]
        pair_key = frozenset([a["chain_id"], b["chain_id"]])
        if pair_key in seen_pairs:
            continue
        seen_pairs.add(pair_key)
        dist = np.linalg.norm(a["point"] - b["point"])
        proposals.append(
            {
                "chain_a": a["chain_id"],
                "end_a": a["end"],
                "chain_b": b["chain_id"],
                "end_b": b["end"],
                "distance_px": round(dist, 1),
                "cost": round(c, 1),
            }
        )

    proposals.sort(key=lambda p: p["cost"])
    return proposals[:top]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("star_file", help="Path to a STAR_FILAMENT_SEGMENTED file")
    parser.add_argument("--max_dist", type=float, default=60,
                         help="Max pixel distance to even consider a merge (start here, tune against your 4 changed micrographs)")
    parser.add_argument("--angle_weight", type=float, default=40,
                         help="How much angular disagreement counts vs. distance, in pixel-equivalent units")
    parser.add_argument("--n_tangent", type=int, default=4,
                         help="Number of points used to estimate direction at each chain end")
    parser.add_argument("--top", type=int, default=20)
    args = parser.parse_args()

    results = propose_merges(
        args.star_file, args.max_dist, args.angle_weight, args.n_tangent, args.top
    )

    if not results:
        print("No candidate merges found within max_dist.")
    else:
        print(f"{'chain_a':>10} {'end_a':>6} {'chain_b':>10} {'end_b':>6} "
              f"{'dist_px':>8} {'cost':>8}")
        for p in results:
            print(f"{p['chain_a']:>10} {p['end_a']:>6} {p['chain_b']:>10} {p['end_b']:>6} "
                  f"{p['distance_px']:>8} {p['cost']:>8}")
