"""PFF vocabularies — the charted words this project reads, and how they fold into role families.

Two different PFF objects say "position", and the distinction is the whole project:
  * `pffdefense.pff_POSITION` / `coverage_defense.position` — the ALIGNMENT SLOT on that snap
    (RCB, SCBL, FSL, LILB, REO ...). Left/right are the DEFENSE's left and right.
  * `pffdefense.pff_GAMEPOSITION` / `coverage_defense.season_position` — one label for how he was
    "most commonly used" that game/season. This is the single position the user wants to get past.
`coverage_defense.assignment` is the charted RESPONSIBILITY (19 classes). PRE = pressure (rusher).
"""
from __future__ import annotations

import re

# ── alignment slots → alignment family (pre-snap geometry class) ─────────────────────────────────
ALIGN_FAMILY: dict[str, str] = {
    # defensive line
    "DLT": "INTERIOR_DL", "DRT": "INTERIOR_DL", "DT": "INTERIOR_DL", "NT": "INTERIOR_DL",
    "NLT": "INTERIOR_DL", "NRT": "INTERIOR_DL", "DL": "INTERIOR_DL",
    # edge (ends and outside backers on the line)
    "LE": "EDGE", "RE": "EDGE", "DLE": "EDGE", "DRE": "EDGE", "LEO": "EDGE", "REO": "EDGE",
    "DE": "EDGE", "EDGE": "EDGE", "LOLB": "EDGE", "ROLB": "EDGE", "OLB": "EDGE",
    # off-ball linebackers
    "MLB": "OFF_BALL_LB", "LILB": "OFF_BALL_LB", "RILB": "OFF_BALL_LB", "ILB": "OFF_BALL_LB",
    "LLB": "OFF_BALL_LB", "RLB": "OFF_BALL_LB", "LB": "OFF_BALL_LB",
    # corners
    "LCB": "BOUNDARY_CB", "RCB": "BOUNDARY_CB", "CB": "BOUNDARY_CB",
    "SCBL": "SLOT_CB", "SCBR": "SLOT_CB", "SCBiL": "SLOT_CB", "SCBiR": "SLOT_CB",
    "SCBoL": "SLOT_CB", "SCBoR": "SLOT_CB", "NB": "SLOT_CB",
    # safeties — PFF's FS/SS is already a role guess; tracking decides the depth class
    "FS": "DEEP_SAFETY", "FSL": "DEEP_SAFETY", "FSR": "DEEP_SAFETY",
    "SS": "BOX_SAFETY", "SSL": "BOX_SAFETY", "SSR": "BOX_SAFETY", "S": "DEEP_SAFETY",
}

ALIGN_LABEL: dict[str, str] = {  # coach words; left/right are the defense's
    "LEO": "Left edge", "REO": "Right edge", "LE": "Left end", "RE": "Right end", "DLE": "Left end", "DRE": "Right end",
    "LOLB": "Left outside backer", "ROLB": "Right outside backer",
    "DLT": "Left tackle (interior)", "DRT": "Right tackle (interior)", "NT": "Nose",
    "NLT": "Nose, left shade", "NRT": "Nose, right shade",
    "LILB": "Left inside backer", "RILB": "Right inside backer", "MLB": "Middle backer",
    "LLB": "Left backer", "RLB": "Right backer",
    "LCB": "Left corner", "RCB": "Right corner", "SCBL": "Left slot", "SCBR": "Right slot",
    "SCBoL": "Left slot, outside", "SCBoR": "Right slot, outside", "SCBiL": "Left slot, inside", "SCBiR": "Right slot, inside",
    "FS": "Free safety", "FSL": "Free safety, left", "FSR": "Free safety, right",
    "SS": "Strong safety", "SSL": "Strong safety, left", "SSR": "Strong safety, right",
}


def align_family(code: str | None) -> str | None:
    if not code:
        return None
    return ALIGN_FAMILY.get(code.strip())


# ── coverage_defense.assignment (19 classes) → responsibility class ─────────────────────────────
ASSIGNMENT_CLASS: dict[str, str] = {
    "MAN": "MAN",
    "PRE": "RUSH",
    # deep zones
    "3L": "DEEP_ZONE", "3M": "DEEP_ZONE", "3R": "DEEP_ZONE", "DF": "DEEP_ZONE",
    "4IL": "DEEP_ZONE", "4IR": "DEEP_ZONE", "4OL": "DEEP_ZONE", "4OR": "DEEP_ZONE",
    "2L": "DEEP_ZONE", "2R": "DEEP_ZONE",
    # underneath zones
    "HOL": "UNDER_ZONE", "CFL": "UNDER_ZONE", "CFR": "UNDER_ZONE", "HCL": "UNDER_ZONE", "HCR": "UNDER_ZONE",
    "FL": "UNDER_ZONE", "FR": "UNDER_ZONE",
}
ASSIGNMENT_LABEL: dict[str, str] = {
    "MAN": "man", "PRE": "rush", "3L": "deep third, left", "3M": "deep middle third", "3R": "deep third, right",
    "DF": "deep free (post)", "4IL": "inside quarter, left", "4IR": "inside quarter, right",
    "4OL": "outside quarter, left", "4OR": "outside quarter, right", "2L": "deep half, left", "2R": "deep half, right",
    "HOL": "hook", "CFL": "curl-flat, left", "CFR": "curl-flat, right", "HCL": "hook-curl, left", "HCR": "hook-curl, right",
    "FL": "flat, left", "FR": "flat, right",
}
# zone assignments a pattern-match modifier converts to man-in-effect (measured: +33% man reps)
MATCH_MODIFIERS = {"MAT", "SEA", "CAR", "TAM"}


def assignment_class(assignment: str | None, mod1: str | None = None, mod2: str | None = None) -> str | None:
    """Responsibility class. A zone with a match modifier is reported as MAN_MATCH, not MAN — the
    call was zone, the rep played man; the role mix keeps them apart."""
    if not assignment:
        return None
    a = assignment.strip()
    cls = ASSIGNMENT_CLASS.get(a)
    if cls is None:
        return None
    if cls in ("DEEP_ZONE", "UNDER_ZONE") and ({mod1, mod2} & MATCH_MODIFIERS):
        return "MAN_MATCH"
    return cls


# ── pffplays depth/width strings: "LCB (5); SCBL (3); FSL (11)" ─────────────────────────────────
_DEPTH_RE = re.compile(r"([A-Za-z]+)\s*\(\s*(-?\d+(?:\.\d+)?)\s*\)")


def parse_depth_string(s: str | None) -> dict[str, float]:
    """`pff_DBDEPTH` / `pff_LBDEPTH` / `pff_DEFENDERWIDTH` → {slot: yards}. Empty string → {}."""
    if not s:
        return {}
    return {m.group(1): float(m.group(2)) for m in _DEPTH_RE.finditer(s)}
