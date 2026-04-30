"""Naming-rule auto-assignment engine — Phase B2.3.

Matches solid identifiers (``solid_id``, ``path_key``, ``display_name``)
against regex patterns and resolves to library ``group_id`` values.
"""

from __future__ import annotations

import importlib.resources
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass(frozen=True)
class SolidRef:
    """Stable reference to a solid for rules and review APIs."""

    solid_id: str
    path_key: str
    display_name: str = ""

    def __post_init__(self) -> None:
        if not self.display_name:
            object.__setattr__(self, "display_name", self.solid_id)


@dataclass(frozen=True)
class NamingRule:
    """One regex→group_id mapping."""

    pattern: str
    group_id: str
    priority: int = 10
    source: str = "default"
    _compiled: re.Pattern[str] = field(
        init=False, repr=False, compare=False, hash=False,
    )

    def __post_init__(self) -> None:
        object.__setattr__(self, "_compiled", re.compile(self.pattern))


@dataclass(frozen=True)
class RuleMatch:
    """Result of applying rules to one solid."""

    solid_id: str
    matched_group_id: str | None
    is_ambiguous: bool
    candidates: tuple[NamingRule, ...]


def _default_rules_path() -> Path:
    ref = importlib.resources.files("raysim.mat").joinpath("default_rules.yaml")
    with importlib.resources.as_file(ref) as p:
        return Path(p)


def load_rules(path: Path | None = None) -> tuple[NamingRule, ...]:
    """Load naming rules from *path* (YAML), or the bundled default."""
    if path is None:
        path = _default_rules_path()
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    entries = data["rules"] if isinstance(data, dict) and "rules" in data else data
    return tuple(
        NamingRule(
            pattern=e["pattern"],
            group_id=e["group_id"],
            priority=e.get("priority", 10),
            source=e.get("source", "default"),
        )
        for e in entries
    )


def apply_rules(
    rules: Sequence[NamingRule],
    solids: Sequence[SolidRef],
) -> list[RuleMatch]:
    """Evaluate *rules* against each solid's identifiers.

    For each solid, the pattern is tested against ``solid_id``, ``path_key``,
    and ``display_name``. Highest-priority match wins. If 2+ rules at the
    same priority both match, the solid is marked ambiguous.
    """
    results: list[RuleMatch] = []
    for solid in solids:
        targets = (solid.solid_id, solid.path_key, solid.display_name)
        hits: list[NamingRule] = []
        for rule in rules:
            if any(rule._compiled.search(t) for t in targets):
                hits.append(rule)

        if not hits:
            results.append(RuleMatch(
                solid_id=solid.solid_id,
                matched_group_id=None,
                is_ambiguous=False,
                candidates=(),
            ))
            continue

        best_priority = max(h.priority for h in hits)
        top = [h for h in hits if h.priority == best_priority]

        if len(top) == 1:
            results.append(RuleMatch(
                solid_id=solid.solid_id,
                matched_group_id=top[0].group_id,
                is_ambiguous=False,
                candidates=tuple(top),
            ))
        else:
            unique_ids = {h.group_id for h in top}
            if len(unique_ids) == 1:
                results.append(RuleMatch(
                    solid_id=solid.solid_id,
                    matched_group_id=top[0].group_id,
                    is_ambiguous=False,
                    candidates=tuple(top),
                ))
            else:
                results.append(RuleMatch(
                    solid_id=solid.solid_id,
                    matched_group_id=None,
                    is_ambiguous=True,
                    candidates=tuple(top),
                ))

    return results
