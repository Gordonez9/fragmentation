"""
Parser + helpers for crYOLO's raw pre-linking CBOX output (data_cryolo
block), as opposed to the already-linked STAR_FILAMENT_SEGMENTED files
(rlnHelicalTubeID) that propose_filament_merges.py works on.

No chain/tube grouping exists in this format -- every row is one
independent box detection.
"""

import numpy as np


def read_cbox(path):
    """
    Parses a .cbox file's data_cryolo loop_ block into a list of dicts,
    one per raw box detection, with numeric fields converted (², <NA> -> None).
    """
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
        row = {name: parse_val(parts[idx]) for name, idx in header_cols.items()}
        boxes.append(row)
    return boxes


def box_centers(boxes):
    """
    (N, 2) array of box centers.

    CoordinateX/Y in CBOX are the box's top-left corner, not its center --
    confirmed empirically by nearest-neighbor distance against the
    corresponding STAR_FILAMENT_SEGMENTED trace: the +width/2, +height/2
    offset gives median NN distance of 3.4px (TMV) / 6.5px (asyn) vs.
    9.7px / 99.8px taking CoordinateX/Y as-is. Every other corner
    hypothesis (+/-w/2, +/-h/2 combinations) was much worse in both
    datasets.
    """
    return np.array([
        [b["CoordinateX"] + b["Width"] / 2, b["CoordinateY"] + b["Height"] / 2]
        for b in boxes
    ])


def box_angles(boxes):
    """_Angle field in radians, as-is (meaning not yet fully confirmed)."""
    return np.array([b["Angle"] for b in boxes])


def box_confidences(boxes):
    return np.array([b["Confidence"] for b in boxes])
