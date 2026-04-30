"""STEP material-tag ingestion — Phase B2.2 + B3.0 simplification.

After the B3.0 XCAF migration, ``LeafSolid`` carries ``name``,
``color_rgb``, and ``material_hint`` directly from the XCAF reader.
``extract_step_tags`` maps these fields to ``StepMaterialTag`` instances
without any OCC imports or second file read.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING

import structlog

from raysim.mat.library import MaterialLibrary

if TYPE_CHECKING:
    from raysim.geom.step_loader import LeafSolid

_LOG = structlog.get_logger(__name__)


@dataclass(frozen=True)
class StepMaterialTag:
    """Material tag extracted from STEP XCAF attributes."""

    solid_id: str
    material_name: str | None
    color_rgb: tuple[float, float, float] | None


@dataclass(frozen=True)
class TagMatch:
    """Result of matching a STEP tag to a library entry."""

    solid_id: str
    matched_group_id: str | None
    confidence: float
    raw_tag: str


def extract_step_tags(
    leaves: Sequence[LeafSolid],
) -> list[StepMaterialTag]:
    """Build material tags from ``LeafSolid`` XCAF attributes.

    After the B3.0 XCAF migration, the ``LeafSolid`` dataclass carries
    ``material_hint`` and ``color_rgb`` populated by the XCAF reader at
    load time. This function is a pure mapping — no OCC imports needed.
    """
    tags: list[StepMaterialTag] = []
    for leaf in leaves:
        tags.append(StepMaterialTag(
            solid_id=leaf.solid_id,
            material_name=leaf.material_hint,
            color_rgb=leaf.color_rgb,
        ))

    _LOG.info("step_tags.extracted", n_tags=len(tags))
    return tags


def match_tags_to_library(
    tags: Sequence[StepMaterialTag],
    library: MaterialLibrary,
    *,
    threshold: float = 0.7,
) -> list[TagMatch]:
    """Fuzzy-match STEP material name strings to library entries."""
    results: list[TagMatch] = []
    for tag in tags:
        if tag.material_name is None or not tag.material_name.strip():
            results.append(TagMatch(
                solid_id=tag.solid_id,
                matched_group_id=None,
                confidence=0.0,
                raw_tag=tag.material_name or "",
            ))
            continue

        raw = tag.material_name
        best_id: str | None = None
        best_score = 0.0

        normalized = raw.lower().strip()
        for mat in library.materials:
            score = _similarity(normalized, mat.group_id.lower(), mat.display_name.lower())
            if score > best_score:
                best_score = score
                best_id = mat.group_id

        results.append(TagMatch(
            solid_id=tag.solid_id,
            matched_group_id=best_id if best_score >= threshold else None,
            confidence=best_score,
            raw_tag=raw,
        ))

    return results


def _similarity(query: str, group_id: str, display_name: str) -> float:
    """Simple substring/containment similarity score in [0, 1]."""
    if query in (group_id, display_name):
        return 1.0
    if query in group_id or group_id in query:
        return 0.8
    if query in display_name or display_name in query:
        return 0.8
    tokens_q = set(query.replace("-", " ").replace("_", " ").split())
    tokens_g = set(group_id.replace("-", " ").replace("_", " ").split())
    tokens_d = set(display_name.replace("-", " ").replace("_", " ").split())
    overlap_g = len(tokens_q & tokens_g) / max(len(tokens_q | tokens_g), 1)
    overlap_d = len(tokens_q & tokens_d) / max(len(tokens_q | tokens_d), 1)
    return max(overlap_g, overlap_d)
