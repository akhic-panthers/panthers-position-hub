"""The role vocabulary — two axes, both registered. Changing either is a new registration.

AXIS 1 · ALIGNMENT ROLE (where he lined up, from tracking geometry at the snap). Finer than PFF's
slot where the geometry supports it (safety depth classes), coarser where it does not (left/right
are dropped; the mirror image is the same job).

AXIS 2 · RESPONSIBILITY (what he did): charted by PFF in coverage_defense.assignment for pass
plays (19 classes → 5), learned from tracking where charting is absent, and geometric on runs.

A player-season "position field" is the mean probability vector over his snaps on each axis, e.g.
  alignment:      DEEP_MIDDLE 0.61 · DEEP_HALF 0.12 · BOX_SAFETY 0.19 · SLOT_CB 0.05 · OVERHANG 0.03
  responsibility: DEEP_ZONE 0.55 · UNDER_ZONE 0.20 · MAN 0.15 · RUN_FIT 0.08 · RUSH 0.02
That is the answer to "70% free safety, 20% strong safety, 10% something else".
"""
from __future__ import annotations

ALIGN_ROLES: list[str] = [
    "EDGE",          # on the line, outside the offensive tackle
    "INTERIOR_DL",   # on the line, inside the tackles
    "OFF_BALL_LB",   # second level, inside the tackles' width (box, off the line)
    "OVERHANG",      # second level, outside the tackle, not over a slot receiver (apex / force player)
    "SLOT_CB",       # over #2/#3 receiver, inside the numbers, < 8 yd
    "BOUNDARY_CB",   # over #1 receiver, outside
    "BOX_SAFETY",    # 5–10 yd, inside or near the box ("strong safety" job)
    "DEEP_HALF",     # ≥ 10 yd, one of two deep defenders off the middle
    "DEEP_MIDDLE",   # ≥ 10 yd, the lone (or middle) deep defender ("free safety" job)
]

RESPONSIBILITIES: list[str] = ["RUSH", "RUN_FIT", "MAN", "MAN_MATCH", "UNDER_ZONE", "DEEP_ZONE"]

ROLE_LABEL: dict[str, str] = {
    "EDGE": "Edge", "INTERIOR_DL": "Interior D-line", "OFF_BALL_LB": "Off-ball linebacker",
    "OVERHANG": "Overhang / apex", "SLOT_CB": "Slot corner", "BOUNDARY_CB": "Boundary corner",
    "BOX_SAFETY": "Box safety", "DEEP_HALF": "Deep half safety", "DEEP_MIDDLE": "Deep middle safety",
    "RUSH": "Pass rush", "RUN_FIT": "Run fit", "MAN": "Man coverage", "MAN_MATCH": "Zone-match (man in effect)",
    "UNDER_ZONE": "Underneath zone", "DEEP_ZONE": "Deep zone",
}

# roster / NGS position → peer group for percentiles (a safety is compared with safeties)
ROSTER_GROUP_OF: dict[str, str] = {
    "DE": "EDGE", "OLB": "EDGE", "EDGE": "EDGE", "DT": "IDL", "NT": "IDL", "DL": "IDL",
    "LB": "LB", "ILB": "LB", "MLB": "LB", "CB": "CB", "DB": "DB", "S": "S", "SS": "S", "FS": "S", "SAF": "S",
}

# which alignment roles are "expected" for each peer group — used only for the viewer's ordering
PRIMARY_ROLES_OF_GROUP: dict[str, list[str]] = {
    "EDGE": ["EDGE", "INTERIOR_DL", "OVERHANG", "OFF_BALL_LB"],
    "IDL": ["INTERIOR_DL", "EDGE"],
    "LB": ["OFF_BALL_LB", "OVERHANG", "EDGE", "BOX_SAFETY", "SLOT_CB"],
    "CB": ["BOUNDARY_CB", "SLOT_CB", "DEEP_HALF", "BOX_SAFETY", "OVERHANG"],
    "S": ["DEEP_MIDDLE", "DEEP_HALF", "BOX_SAFETY", "SLOT_CB", "OVERHANG", "OFF_BALL_LB"],
    "DB": ["BOUNDARY_CB", "SLOT_CB", "DEEP_HALF", "DEEP_MIDDLE", "BOX_SAFETY"],
}
