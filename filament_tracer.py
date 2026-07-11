"""
From-scratch filament tracer over crYOLO's raw pre-linking box detections
(cbox_raw / CBOX format), bypassing crYOLO's own chain-linking entirely.

Motivation (see raw_box_tracing.ipynb): crYOLO's STAR_FILAMENT_SEGMENTED
output has the linker's decisions already baked in, so anything measured
from it is circular. This traces filaments directly from the raw boxes so
that the DIFF between these traces and crYOLO's STAR chains is an
independent fragmentation report (splits, truncations, and orphan strands
all fall out of it), not a patch applied on top of the linker.

Design, and how each parameter was justified from the data:

- Greedy bidirectional path cover: seed from the highest-confidence
  unclaimed box, grow both directions, claim each box to at most one
  filament. Box counts are small (52-337/micrograph) so this is cheap; the
  problem shape is path-tracing over interior points, not endpoint matching.

- Angle gate uses the raw `_Angle` field directly. Verified in the notebook
  (Goal 5): `_Angle` matches the STAR-trace tangent to a median 2-4deg
  (97-99% within 15deg), so it is a reliable local orientation. `_Angle`
  is a line orientation with a genuine 180deg ambiguity, so all angle
  comparisons are mod-pi.

- `angle_tol_deg` default 20: true continuations sit at 2-4deg, so 20deg
  keeps essentially all real links while rejecting junk. (crYOLO's own
  chains, for contrast, tolerate none of this reasoning -- they were the
  problem.)

- `min_len` default 3: the orphan census (Goal 5) showed isolated
  single/double raw boxes are mostly spurious detections (esp. asyn
  19863050), while genuine missed strands come in coherent groups of >=3.
  Filaments shorter than min_len boxes are dropped as noise.

- `max_step_mult` default 3.0 (x this micrograph's median box spacing):
  large enough to bridge a one-box detection dropout, small enough not to
  jump between distinct parallel rods.
"""

import numpy as np
from scipy.spatial import cKDTree


def _median_stride(centers):
    """Median nearest-neighbour spacing -- the natural length unit for one
    micrograph, since absolute scale differs ~10x between datasets and
    isn't calibrated (pixel size still unresolved; see notebook Goal 3)."""
    if len(centers) < 2:
        return 1.0
    d, _ = cKDTree(centers).query(centers, k=2)
    return float(np.median(d[:, 1]))


def _ang_diff_mod_pi(a, b):
    d = np.abs(a - b) % np.pi
    return np.minimum(d, np.pi - d)


def _grow(start, init_heading, centers, angles, tree, claimed,
          max_step, angle_tol, forward_cos_min):
    """Grow one strand from `start` box in the direction of `init_heading`.
    Returns the ordered list of box indices added (excluding `start`)."""
    added = []
    current = start
    heading = init_heading / (np.linalg.norm(init_heading) + 1e-12)

    while True:
        cur_pos = centers[current]
        cand = [i for i in tree.query_ball_point(cur_pos, r=max_step)
                if i != current and not claimed[i]]
        best, best_cost = None, None
        best_dir = None
        for i in cand:
            vec = centers[i] - cur_pos
            dist = np.linalg.norm(vec)
            if dist < 1e-9:
                continue
            vdir = vec / dist
            # must continue roughly forward, not fold back on the strand
            fwd = float(np.dot(vdir, heading))
            if fwd < forward_cos_min:
                continue
            # candidate's local orientation must agree with current box's
            adiff = _ang_diff_mod_pi(angles[current], angles[i])
            if adiff > angle_tol:
                continue
            # cost: nearer + straighter is better; forward alignment breaks ties
            cost = dist * (1.0 + (adiff / angle_tol)) - fwd
            if best_cost is None or cost < best_cost:
                best_cost, best, best_dir = cost, i, vdir
        if best is None:
            break
        claimed[best] = True
        added.append(best)
        # blend heading so gentle curvature is followed but noise is damped
        heading = 0.5 * heading + 0.5 * best_dir
        heading = heading / (np.linalg.norm(heading) + 1e-12)
        current = best
    return added


def trace_filaments(centers, angles, confidences=None,
                    max_step_mult=3.0, angle_tol_deg=20.0,
                    forward_cos_min=0.3, min_len=3):
    """
    Trace filaments from raw box detections for a single micrograph.

    centers: (N,2) box centres (use cbox_utils.box_centers).
    angles:  (N,) raw `_Angle` in radians (use cbox_utils.box_angles).
    confidences: (N,) optional; seeds are grown most-confident-first so
        strong detections anchor strands before ambiguous ones.

    Returns a list of filaments, each an ordered list of box indices.
    Every box belongs to at most one filament; filaments shorter than
    min_len boxes are dropped (noise guard, see module docstring).
    """
    centers = np.asarray(centers, dtype=float)
    angles = np.asarray(angles, dtype=float)
    n = len(centers)
    if n == 0:
        return []

    stride = _median_stride(centers)
    max_step = max_step_mult * stride
    angle_tol = np.radians(angle_tol_deg)
    tree = cKDTree(centers)

    if confidences is None:
        seed_order = np.arange(n)
    else:
        seed_order = np.argsort(-np.asarray(confidences, dtype=float))

    claimed = np.zeros(n, dtype=bool)
    filaments = []

    for seed in seed_order:
        if claimed[seed]:
            continue
        claimed[seed] = True
        # seed heading = the box's own line orientation; grow both ways
        a = angles[seed]
        h = np.array([np.cos(a), np.sin(a)])
        fwd = _grow(seed, h, centers, angles, tree, claimed,
                    max_step, angle_tol, forward_cos_min)
        bwd = _grow(seed, -h, centers, angles, tree, claimed,
                    max_step, angle_tol, forward_cos_min)
        strand = list(reversed(bwd)) + [seed] + fwd
        if len(strand) >= min_len:
            filaments.append(strand)
        else:
            # release short strands so their boxes can't block real ones...
            # but keep the seed claimed to avoid re-seeding the same noise.
            for i in strand:
                if i != seed:
                    claimed[i] = False
    return filaments


def filament_length(centers, strand):
    """Arc length of a traced strand in raw coordinate units."""
    pts = np.asarray(centers)[strand]
    if len(pts) < 2:
        return 0.0
    return float(np.sum(np.linalg.norm(np.diff(pts, axis=0), axis=1)))
