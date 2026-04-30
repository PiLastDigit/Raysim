"""Auto-assignment review API — Phase B2.4.

Combines STEP tags, naming rules, and manual assignments into a single
per-solid assignment status with priority resolution.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from raysim.mat.library import MaterialLibrary
from raysim.mat.rules import RuleMatch, SolidRef
from raysim.mat.step_tags import TagMatch
from raysim.proj.schema import MaterialAssignment


@dataclass(frozen=True)
class AssignmentStatus:
    """Per-solid assignment result."""

    solid_id: str
    source: Literal["step_tag", "naming_rule", "manual", "unassigned"]
    material_group_id: str | None
    is_ambiguous: bool
    candidates: tuple[str, ...]


@dataclass(frozen=True)
class AssignmentReview:
    """Combined review of all assignment sources."""

    statuses: tuple[AssignmentStatus, ...]
    n_auto_matched: int
    n_ambiguous: int
    n_unassigned: int


def build_review(
    solids: Sequence[SolidRef],
    *,
    tag_matches: Sequence[TagMatch] | None = None,
    rule_matches: Sequence[RuleMatch] | None = None,
    manual_assignments: Sequence[MaterialAssignment] | None = None,
    library: MaterialLibrary,
) -> AssignmentReview:
    """Build a review with priority: manual > step_tag > naming_rule."""
    manual_map: dict[str, str] = {}
    if manual_assignments:
        for a in manual_assignments:
            manual_map[a.solid_id] = a.material_group_id

    tag_map: dict[str, TagMatch] = {}
    if tag_matches:
        for t in tag_matches:
            tag_map[t.solid_id] = t

    rule_map: dict[str, RuleMatch] = {}
    if rule_matches:
        for r in rule_matches:
            rule_map[r.solid_id] = r

    statuses: list[AssignmentStatus] = []
    n_auto = 0
    n_ambiguous = 0
    n_unassigned = 0

    for solid in solids:
        sid = solid.solid_id

        # Priority 1: manual assignment — always wins when present.
        if sid in manual_map:
            gid = manual_map[sid]
            if gid in library:
                statuses.append(AssignmentStatus(
                    solid_id=sid, source="manual",
                    material_group_id=gid, is_ambiguous=False,
                    candidates=(gid,),
                ))
                n_auto += 1
            else:
                statuses.append(AssignmentStatus(
                    solid_id=sid, source="manual",
                    material_group_id=None, is_ambiguous=False,
                    candidates=(gid,),
                ))
                n_unassigned += 1
            continue

        # Priority 2: STEP tag.
        tag_gid = tag_map.get(sid)
        if tag_gid is not None and tag_gid.matched_group_id is not None:
            gid = tag_gid.matched_group_id
            if gid in library:
                statuses.append(AssignmentStatus(
                    solid_id=sid, source="step_tag",
                    material_group_id=gid, is_ambiguous=False,
                    candidates=(gid,),
                ))
                n_auto += 1
                continue

        # Priority 3: naming rule.
        if sid in rule_map:
            rm = rule_map[sid]
            if rm.is_ambiguous:
                cands = tuple(c.group_id for c in rm.candidates)
                statuses.append(AssignmentStatus(
                    solid_id=sid, source="naming_rule",
                    material_group_id=None, is_ambiguous=True,
                    candidates=cands,
                ))
                n_ambiguous += 1
                continue
            if rm.matched_group_id is not None and rm.matched_group_id in library:
                statuses.append(AssignmentStatus(
                    solid_id=sid, source="naming_rule",
                    material_group_id=rm.matched_group_id, is_ambiguous=False,
                    candidates=(rm.matched_group_id,),
                ))
                n_auto += 1
                continue

        # No match.
        statuses.append(AssignmentStatus(
            solid_id=sid, source="unassigned",
            material_group_id=None, is_ambiguous=False,
            candidates=(),
        ))
        n_unassigned += 1

    return AssignmentReview(
        statuses=tuple(statuses),
        n_auto_matched=n_auto,
        n_ambiguous=n_ambiguous,
        n_unassigned=n_unassigned,
    )


def review_to_assignments(review: AssignmentReview) -> list[MaterialAssignment]:
    """Convert resolved statuses to ``MaterialAssignment[]``.

    Raises ``ValueError`` if any solid is unassigned or ambiguous.
    """
    unresolved = [
        s.solid_id for s in review.statuses
        if s.material_group_id is None
    ]
    if unresolved:
        raise ValueError(
            f"Cannot convert review to assignments: "
            f"{len(unresolved)} solid(s) unresolved: {unresolved[:5]}"
        )
    return [
        MaterialAssignment(solid_id=s.solid_id, material_group_id=s.material_group_id)
        for s in review.statuses
        if s.material_group_id is not None
    ]


def format_review_summary(review: AssignmentReview) -> str:
    """Human-readable summary for CLI output."""
    lines = [
        f"Assignment review: {len(review.statuses)} solids",
        f"  auto-matched: {review.n_auto_matched}",
        f"  ambiguous:    {review.n_ambiguous}",
        f"  unassigned:   {review.n_unassigned}",
    ]
    problems = [
        s for s in review.statuses
        if s.is_ambiguous or s.material_group_id is None
    ]
    if problems:
        lines.append("")
        lines.append("  Solids needing attention:")
        for s in problems:
            if s.is_ambiguous:
                lines.append(f"    {s.solid_id}: AMBIGUOUS — candidates: {', '.join(s.candidates)}")
            elif s.source == "manual" and s.material_group_id is None:
                cands = ', '.join(s.candidates) if s.candidates else 'none'
                lines.append(f"    {s.solid_id}: UNRESOLVED manual — group_id not in library: {cands}")
            else:
                lines.append(f"    {s.solid_id}: UNASSIGNED")
    return "\n".join(lines)
