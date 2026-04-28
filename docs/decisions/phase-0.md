# Phase 0 decisions

Closes the open items from `MVP_PLAN.md` §10 and the spike gates from
`MVP_STEPS.md` §0.1–§0.4. Linear dev environment is **WSL Ubuntu (Linux)**;
Windows is verified via the GH Actions matrix once a remote is configured.

## Tooling

| Decision | Outcome | Notes |
|---|---|---|
| Package manager | **`uv`** | Per `MVP_PLAN.md` §10 proposal. Significantly faster than `poetry` for the cold-start case we hit on every CI matrix entry. |
| Python | **3.11+, 3.12 used locally** | Pinned via `pyproject.toml`. CI matrix runs 3.11 and 3.12. |
| Lint / type / test | `ruff` + `mypy --strict` + `pytest` + `pytest-benchmark` | All wired in `pyproject.toml`; pre-commit config in repo. |
| Project layout | Single package `raysim/` under `src/`, modules per `MVP_PLAN.md` §5 | `geom`, `mat`, `env`, `ray`, `dose`, `proj`, `ui`, `report`, `cli`. |
| CI | GH Actions matrix, Ubuntu + Windows, py3.11 + py3.12 | `.github/workflows/ci.yml`. **Will not run until a GitHub remote exists** — currently a local-only repo. |
| Packaging tool (briefcase vs PyInstaller) | **Deferred to B4** per `MVP_PLAN.md` §10 | Decided based on how OCCT shared libs bundle on Windows. |

## Per-dependency install paths and smoke results

| Dependency | Install path | Status (Linux) | Status (Windows) | Notes |
|---|---|---|---|---|
| `numpy`, `scipy`, `pydantic`, `click`, `structlog`, `trimesh` | `uv pip` (pyproject) | ✅ | expected ✅ via CI | Standard PyPI. |
| `embreex` | `uv pip` (pyproject `[project.optional-dependencies].ray`) | ✅ — version **4.4.0**, BVH+closest-hit verified | needs CI verification | Single-source: `embreex` 4.4.0 PyPI wheel. |
| `healpy` | `uv pip`, gated `platform_system != 'Windows'` in pyproject | ✅ — verified `healpy.pix2vec` agrees with our vendored fallback to ≤1e-13 | **fall back to vendored `pix2vec`** | See HEALPix section below. |
| `pythonocc-core` | **conda-forge only** — `micromamba create -n raysim-occt -c conda-forge python=3.12 pythonocc-core` | ✅ — version **7.9.0**, STEP read + tessellation + healing verified | needs CI verification (use `setup-micromamba` action) | Not on PyPI. Phase B2.2 has an open issue with `XCAFDoc_DocumentTool` bootstrap, see below. |

## Phase-0 spike gates — outcomes

### `pix2vec` on Windows (HEALPix) — §0.2

**Decision:** RaySim ships with a **vendored NumPy `pix2vec` fallback** (`src/raysim/ray/healpix.py`).

* The fallback is ~120 lines, derived from Górski et al. 2005 Eq. 5–8.
* Verified bit-equal to `healpy.pix2vec` (RING ordering) to ≤1e-13 across Nside ∈ {1, 2, 4, 8, 16, 32, 64, 128} for every pixel index — see `tests/unit/test_healpix_smoke.py::test_vendored_matches_healpy`.
* On Linux/macOS the top-level `pix2vec` dispatches to `healpy` for free perf; on Windows or any environment without `healpy` it transparently uses the fallback.
* RaySim only needs unit-direction generation, not the full HEALPix surface (no FITS, no spherical harmonics, no rotator).

This is the lowest-risk path: no Windows wheel-availability dependency, identical numerics regardless of which library backs the call.

### `BRepMesh_ModelHealer` binding — §0.2

**Decision:** Use the OCCT-native `BRepMesh_ModelHealer` directly. The fallback hand-written healing pass is **not needed**.

`OCC.Core.BRepMesh.BRepMesh_ModelHealer` is exposed in conda-forge `pythonocc-core` 7.9.0 and importable. `BRepMesh_IncrementalMesh` is also exposed and runs cleanly on a `BRepPrimAPI_MakeBox` test shape (`mesh.IsDone() == True`). Verified by `tests/unit/test_occt_smoke.py::test_makebox_brepmesh_modelhealer`.

### Embree filter callback / `IntersectContext` — §0.2 (HARD FINDING)

**Decision:** The A.4 fallback "window query with exclusion" path **is not implementable on this `embreex` version**. Pre-built coincident-face groups (B1.5) are the **mandatory** tie-handling mechanism. This upgrades the `MVP_STEPS.md` §A.4 status from "preferred" to "the only supported path."

`embreex` 4.4.0 exposes:
* `EmbreeScene.run(origins, dirs, dists=None, query='INTERSECT'|'OCCLUDED'|'DISTANCE', output=None)`
* `EmbreeDevice`
* `TriangleMesh`

It does **not** expose `IntersectContext`, `RTCIntersectContext`, or any per-ray filter-callback path — the entire surface is the single batched `run()` call. RaySim's Phase A.4 traversal must therefore:

* Build coincident-face groups at scene-build time (B1.5).
* On a closest-hit query, use the pre-built map to identify all primitives sharing the hit's tied group.
* No second filtered query is ever issued.

A failing test (`tests/unit/test_embreex_smoke.py::test_filter_callback_unavailable`) guards against silently relying on these symbols — if they appear in a future `embreex` version we revisit the decision.

### `XCAFDoc_DocumentTool` bootstrap — observed regression

**Finding (carried forward to B1.1 / B2.2, not a Phase 0 gate):** in conda-forge `pythonocc-core` 7.9.0, constructing `TDocStd_Document(TCollection_ExtendedString('BinXCAF'))` throws `Standard_NullObject`, even after `binxcafdrivers.DefineFormat(app)` registers the format on the `XCAFApp_Application` singleton. Multiple variants (`XmlXCAF`, `MDTV-XCAF`, empty-string) reproduce.

This blocks the STEP material-tag ingestion path (`MVP_STEPS.md` §B2.2), but **does not block Phase 0 or Phase A** — Stage A consumes STL via `trimesh`, which is unaffected. STEP geometry import via `STEPControl_Reader` (the non-CAF path) works fine and is what Phase B1.1 will start with.

Plan when this becomes load-bearing (B2.2):
1. Try a different `pythonocc-core` build (7.8.x conda-forge, or an earlier 7.9 patch).
2. If still broken, switch to `cadquery-ocp` (PyPI-distributed OCCT binding) for the XCAF flow only — keeps `pythonocc-core` for the rest.
3. As last resort, fall back to a hand-rolled STEP material-tag parser (the AP214 IS material assignment is plain STEP entity-id text).

A tracking xfail lives in `tests/unit/test_occt_smoke.py::test_xcafdoc_material_tool_bootstrap` so an upstream fix surfaces immediately.

## Benchmark corpus — §0.4

**Decision:** Phase 0 ships the procedural canonical-analytic geometries and the custom test article in repo. The two third-party STEP assemblies are deferred to a follow-up commit pending licensing review.

Generated by `scripts/build_benchmarks.py` (deterministic; CI guard via per-STL SHA-256 in `manifest.json`):

| Geometry | Files | Triangles | Purpose |
|---|---|---|---|
| `aluminum_box` | `aluminum.stl` | 12 | Phase A acceptance: principal-axis ∑ρL = ρ_Al × 100 mm. |
| `solid_sphere` | `aluminum.stl` (icosphere s=4) | 5120 | Phase A acceptance: ∑ρL(d) = 2 ρ √(R²−d²). |
| `concentric_shell` | `aluminum.stl` + `copper.stl` | 5120 + 1280 | Phase A acceptance: per-shell chord-pair fixture. |
| `custom_test_article` | `aluminum.stl`, `fr4.stl`, `copper.stl`, `gaas.stl` | 12 each | Multi-material end-to-end test article. Box + PCB + battery + panel. |

Analytic ∑ρL fixtures live in `benchmarks/analytic_targets.yaml` and are recomputed from densities × chord lengths in the test (so the YAML stays the geometric truth and densities can drift independently).

### Open-source CubeSat + larger open mission

Deferred. Candidate sources (need licensing review before checkin or submodule):
* **LibreCube** — CubeSat structural CAD, permissive licenses.
* **NASA 3D Resources** — selected mission models, public domain.
* **ESA OSIP archives** — case-by-case.

Not blocking Phase A or B1; needed by B5.2 (cross-tool comparison).

## Project file schema policy — preview for §10

Tentative (confirm at B2.5): every breaking change to the `.raysim` schema bumps `schema_version`; the loader supports `N-1` for one release, then drops. `run.json` follows the same rule.

## What's still open

* Windows CI verification — gated on the user creating a GitHub remote and pushing. The workflow is in place; it has not run yet.
* Material anomaly thresholds (block-run vs warning) — physicist sign-off needed before B2.6.
* `XCAFDoc_DocumentTool` bootstrap fix — investigated again at B1.1.
* Third-party STEP corpus — licensing review.

## Sign-off

Phase 0 gate is met for the items the gate explicitly requires:
* ✅ `embreex` smoke (with a clearly-documented constraint on filter callbacks).
* ✅ `healpy`/vendored fallback decided.
* ✅ `pythonocc-core` STEP+tessellation+`ModelHealer` smoke on Linux; Windows pending CI activation.
* ✅ OMERE `.dos` importer + spline round-trip ≤1%.
* ✅ Benchmark corpus generated; analytic targets internally consistent.
* ✅ CI scaffold in place (Linux green; Windows ready to run on remote push).

Phase A may proceed.
