# Tutorial 0.4.0 — Mandatory vs Advisory Pipeline Gates

## The Problem

A 250-solid PCBA takes minutes to open in the GUI because the pipeline runs an O(N²) volume-intersection diagnostic on every pair of solids. Most of those pairs are irrelevant — only touching or overlapping solids matter. And the meca team already validates the CAD before import, so interference is rare.

## Two Kinds of Gate

RaySim's geometry pipeline has two categories of validation:

**Mandatory gates** block the run if they fail. They catch problems that would produce wrong physics:
- Watertightness — a non-watertight shell leaks rays.
- Mismatched contacts — coplanar faces with different tessellations can't form tied pairs, causing double-counting.

**Advisory checks** inform the user but don't block. They catch problems that are either rare or not physics-critical:
- Volume-based interference classification — expensive, rare in validated CAD.
- Boolean failures — OCCT couldn't compute the intersection (inconclusive, not conclusive).

## The Design Pattern

Split the work into a **fast path** (always runs) and a **full path** (on demand):

```python
# Fast path: ContactReport — tied pairs + mismatched contacts
# Always runs in the pipeline. O(N) per AABB-overlapping pair.
contacts = extract_contacts(healed_solids)

# Full path: OverlapReport — adds volume classification
# On demand via "Validate Geometry" or CLI.
report = diagnose_overlaps(healed_solids, shapes=shape_map)
```

The fast path produces everything the ray engine needs (tied pairs for coincident-face handling) and everything the mandatory gate needs (mismatched contacts). The full path adds the expensive OCCT volume classification that produces the four-way status.

## Why Not Just Make It Faster?

Phase 2 of the plan does add spatial-hash pair filtering to reduce the O(N²) to O(N × neighbors). But even with filtering, the OCCT `BRepAlgoAPI_Common` call per pair is inherently slow — it's a full boolean intersection on B-Rep geometry. Moving it off the mandatory path is the architecturally correct choice regardless of optimization, because it's advisory, not physics-critical.

## The Async Problem

When validation moves off the mandatory path and into a QThread worker, a new problem appears: the user can change geometry while validation is running. If the old result completes and gets applied to the new geometry, the run could incorrectly report "validated" when it wasn't.

The fix is a **monotonic revision counter**:

```python
class AppState:
    _geometry_revision: int = 0

    def open_step(self, path):
        ...
        self._geometry_revision += 1  # invalidates any in-flight validation

# In RunPanel:
def _start_validation(self):
    self._validate_geom_rev = self._state.geometry_revision
    # start worker...

def _on_validation_complete(self, report):
    if self._state.geometry_revision != self._validate_geom_rev:
        return  # stale — geometry changed while we were validating
    self._state.set_overlap_report(report)
```

This pattern generalizes to any async operation whose result is keyed to mutable state: capture a version token at dispatch, discard on completion if the token doesn't match.

## Takeaway

When a pipeline has both mandatory and advisory checks, separate them structurally — not just by flag. The mandatory path should be fast enough to never block the user. The advisory path should be explicit, on-demand, and async-safe.
