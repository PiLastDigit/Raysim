# Tutorial: Shell Orientation and the Cavity Convention

**Version**: 0.1.0 — Phase B1 Geometry Pipeline

## The Problem

When a ray traverses a spacecraft model, RaySim's stack accumulator decides whether it's *entering* or *exiting* solid material by checking the dot product between the ray direction and the triangle's outward normal. If a triangle's normal points the wrong way, the entry/exit classification inverts — and the accumulated mass-thickness (∑ρL) is wrong.

For a simple box, getting normals right is trivial: every triangle faces outward. But real spacecraft geometry includes *hollow solids* — a structural panel with an internal cavity, a payload fairing with walls. These have multiple shells:

- An **outer shell** whose normals face outward into vacuum.
- One or more **cavity shells** whose normals face inward — into the void of the cavity, *away from solid material*.

If we naively orient every shell's normals "outward" in the geometric sense, a cavity shell's normals would point *into the solid wall*, which is exactly backwards for the accumulator.

## The Convention

RaySim's convention, enforced by `raysim.geom.healing`:

> Every triangle's normal points **out of solid material**.

For an outer shell, that means pointing into vacuum. For a cavity shell, that means pointing into the cavity void. The effect is that a ray crossing into solid material always sees `dot(direction, normal) < 0` (entry), and a ray leaving solid material always sees `dot(direction, normal) > 0` (exit), regardless of which shell it's crossing.

## How It's Determined

The healer can't use the normals themselves to decide if they're correct — that's circular. Instead, it uses a **probe-ray approach** that's normal-independent:

1. **Classify shells by containment.** Compute each shell's vertex centroid (just the average of all vertex positions — no normal involvement). Test whether each centroid is inside any other shell using a simple odd-crossing ray cast through the triangle positions. The shell that contains all others is OUTER; the rest are CAVITY.

2. **Per-shell probe ray.** For each shell, cast a ray from a known-outside point (beyond the solid's bounding box) toward that shell's vertex centroid. This guarantees intersection even when cavities are off-axis.

3. **Check the first-hit dot product.** For the outer shell, the first hit should have `dot < 0` (the probe enters solid material). For a cavity shell, the first hit on that shell should have `dot > 0` (the probe exits solid material into the cavity). If the sign is wrong, flip that shell's triangle winding.

4. **Re-verify.** After any flip, re-cast and verify the full entry/exit sequence across all shells. The stack count must return to zero — the probe enters and exits every layer cleanly.

## Why This Matters

A single misoriented cavity shell on a 2 mm aluminum wall would make the accumulator *skip* that wall on every ray, silently removing ~0.5 g/cm² of shielding from the TID estimate. On a LEO mission, that's the difference between "component is safe" and "component needs redesign." The healer catches this automatically, before the ray engine ever sees the geometry.

## In Code

```python
from raysim.geom.healing import ShellRole, heal_assembly

healed = heal_assembly(tessellated_solids)
for solid in healed:
    for shell in solid.shells:
        print(f"{solid.solid_id} shell {shell.shell_index}: "
              f"{shell.role}, flipped={shell.was_flipped}")
```

Each `HealedShell` carries its `role` (OUTER or CAVITY) and whether it was flipped during healing — useful for debugging geometry issues when the healer intervenes.
