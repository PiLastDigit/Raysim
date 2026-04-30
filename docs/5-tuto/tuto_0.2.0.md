# Tutorial: Material Governance and the Priority Resolution Chain

## The Problem

A spacecraft STEP file might contain 200 solids. Manually assigning each
one to a material library entry would take 200 mouse clicks and human
knowledge of what "AL_PANEL_TOP" means. Worse, typos and missed parts
produce silent dose errors — the sector-analysis code happily computes
∑ρL through unassigned geometry at zero density.

Phase B2's material governance layer solves this by automating assignment
through three layered sources with strict priority ordering, then gating
the run until every solid resolves.

## The Priority Chain: manual > step_tag > naming_rule

When `build_review()` evaluates a solid, it checks three sources in
decreasing priority:

1. **Manual assignment** — the user explicitly picked a library material.
   This always wins, even if the `group_id` is wrong (unknown IDs become
   "unresolved" rather than silently falling through to auto-sources).

2. **STEP tag** — the CAD file carried an AP214 material attribute. The
   XCAF reader extracts it and fuzzy-matches against the library.

3. **Naming rule** — a regex pattern matched the solid's `solid_id`,
   `path_key`, or `display_name`.

If none of the three sources produce a match, the solid is "unassigned"
and the run is gated.

## Why Invalid Manual Assignments Don't Fall Through

An earlier version of the code treated an invalid manual assignment
(group_id not in the library) as "no manual assignment" and tried the
next source. This is wrong: if a user explicitly said "this solid is
titanium" but the library doesn't have "titanium", the correct behavior
is to flag the mismatch, not to silently pick whatever the naming rule
says.

The fix is simple: the manual branch always consumes the solid. Valid
manual → resolved. Invalid manual → unresolved (needs attention).

```python
if sid in manual_map:
    gid = manual_map[sid]
    if gid in library:
        # Resolved via manual assignment
        ...
    else:
        # Unresolved — invalid manual stays as "needs attention"
        ...
    continue  # Never fall through to step_tag or naming_rule
```

## The Two-Reader Correlation Problem

STEP tag extraction requires the XCAF reader (`STEPCAFControl_Reader`),
but B1's geometry pipeline uses the plain `STEPControl_Reader`. These
are two independent reads of the same file, and the Python objects they
produce are not identity-comparable.

The join key is **DFS walk-order index**: both readers traverse the STEP
compound in the same depth-first order dictated by OCCT's
`TopoDS_Iterator`. But "same order" is an assumption, not a guarantee.

The verification gate adds two checks before zipping:
1. **Leaf count** — the XCAF walk must produce the same number of leaf
   solids as B1's `load_step`.
2. **Bbox fingerprint** — each XCAF leaf's bounding box must match the
   corresponding B1 `LeafSolid`'s bbox within 1e-3 mm.

If either check fails, the tag extraction returns an empty list and
logs a warning. The naming-rule engine and manual assignment remain
available as fallbacks.

## SolidRef: The Stable Input Token

Rules need to match against multiple identifiers (synthetic `solid_id`,
assembly tree `path_key`, human-readable `display_name`). Rather than
passing three separate lists, Phase B2 introduces `SolidRef` — a frozen
dataclass that bundles all three. This gives the rules engine and review
API a single, well-typed input they can pattern-match against.

```python
@dataclass(frozen=True)
class SolidRef:
    solid_id: str      # "solid_0003"
    path_key: str       # "0/2/1"
    display_name: str   # "AL_PANEL_TOP" (defaults to solid_id)
```

B1's `LeafSolid` maps 1:1 to a `SolidRef`. Stage A's STL-only callers
build `SolidRef(solid_id=stem, path_key=stem)` where both fields are the
filename stem.
