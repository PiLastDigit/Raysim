# RaySim benchmark corpus

Per `MVP_PLAN.md` §6 Phase 0 and `MVP_STEPS.md` §0.4. Goal: a small, redistributable set of geometries with analytic or published targets, used for Phase A acceptance and B5 nightly regression.

## Layout

```
benchmarks/
├── geometries/           # canonical analytic geometries (procedurally generated)
│   ├── aluminum_box/     # one solid Al box; closed-form ∑ρL via face/diagonal lookup
│   ├── solid_sphere/     # one solid Al sphere; closed-form ∑ρL = 2 ρ √(R²−d²) at impact d
│   └── concentric_shell/ # Al outer + Cu inner; closed-form per-shell chord lengths
├── assemblies/           # multi-material engineering assemblies
│   └── custom_test_article/  # box + PCB + battery + panel, procedurally generated STL
├── scenarios/            # OMERE .dos scenarios used as test fixtures
│   └── (the user's dose700km.dos lives in tests/fixtures/ — not duplicated here)
└── analytic_targets.yaml # per-geometry analytic ∑ρL test fixtures (Phase A acceptance)
```

## Generating the geometries

```bash
uv run python scripts/build_benchmarks.py
```

Outputs land in `benchmarks/geometries/<name>/` and `benchmarks/assemblies/<name>/`. The script is deterministic: same `trimesh` version → same vertex hash. A `manifest.json` per geometry records the SHA-256 hashes for CI guardrails.

## Status of the open-source CAD assemblies

`MVP_STEPS.md` §0.4 calls for two third-party STEP assemblies (an open-source CubeSat and a larger open mission) on top of the custom test article authored here. They are **deferred to a follow-up commit pending licensing review** — candidate sources include:

  * **LibreCube** ([librecube.org](https://librecube.org/)) — CubeSat structural CAD under permissive licenses.
  * **NASA 3D Resources** ([nasa3d.arc.nasa.gov](https://nasa3d.arc.nasa.gov/)) — selected mission models, public domain.
  * **ESA OSIP / open-source mission archives** — case-by-case licensing.

They are nice-to-have for B5.2 cross-tool comparison; they are not blockers for Phase A or for the §0.4 done-when (which the procedural geometries already satisfy).
