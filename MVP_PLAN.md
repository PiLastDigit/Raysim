# RaySim — MVP Plan (v3.1)

A 3D Total Ionizing Dose (TID) sector-shielding simulator for spacecraft. The MVP is a detector-centric ray engine that casts HEALPix rays through CAD geometry, convolves accumulated ∑ρL with an imported SHIELDOSE-2-style dose-depth curve, and produces engineering-reviewable TID reports.

## Recent changes

**v3 → v3.1 (scope cut):**
- **MVP consumes only pre-computed dose-depth curves (Path B).** Reference dialect: OMERE `.dos`. RaySim does **not** run SHIELDOSE-2 itself, does **not** import fluence spectra, does **not** propagate orbits.
- The spectrum schema, spectrum importers, and SpacePy dependency are removed from MVP. The SHIELDOSE-2 phase-0 spike is removed. Path A (spectrum-in + SHIELDOSE-2-in-RaySim) is moved to the post-MVP roadmap.
- Justification: in-process SHIELDOSE-2 and orbit propagation are real engineering risks that don't add MVP value when OMERE/SPENVIS/IRENE already produce the inputs. RaySim's MVP value is the geometry + ∑ρL + spline-lookup loop on real CAD.

**v2 → v3 (language pivot):**
- Python 3.11+ as the primary language. C++ reserved for a post-MVP optimization drop. Rust out (OCCT binding gap).
- HEALPix math is simple; `healpy` availability is checked in Phase 0 with a vendored NumPy `pix2vec` fallback for platforms (notably Windows) where the wheel is unreliable. New risk: Python packaging on Windows.

---

## 1. Guiding principles

1. **Sector analysis, not full transport.** Deterministic raytracing + 1D dose-depth convolution. No Monte Carlo in-process. Geant4 is post-MVP.
2. **Python first; drop to native only on evidence.** The hot path is Embree's ray-triangle intersection, which runs at C speed regardless of caller. Python overhead on the glue is ~10–30% — acceptable for MVP.
3. **Detector-centric everything.** Rays, caches, and reports are keyed to user-placed detectors, not a whole-scene grid.
4. **Ship the ray loop first, the product second.** Stage A is a headless CLI that proves the physics. Stage B wraps it in CAD, UI, reports.
5. **Material truth is governed.** STEP metadata is unreliable; a sidecar material table is the source of record. STEP-carried material tags are ingested as defaults, overridden by the sidecar.
6. **Mission-averaged by default.** MVP computes a single mission-averaged TID per detector from one imported dose-depth curve. Per-waypoint integration is post-MVP.
7. **Reproducibility is non-negotiable, with explicit scope.** Every result embeds geometry hash, tessellation tolerances, material assignments, HEALPix Nside, epsilon, seed, build SHA, and dose-curve hash. **Bit-identical reproducibility applies to the engine's machine-readable output (`run.json`)**, not to human-facing artifacts. Reports (PDF, dashboards) include timestamps and rendering-dependent layout and are explicitly *not* bit-identical. The deterministic-engine guarantee requires: canonical JSON ordering (sorted keys, fixed float formatting), ordered reductions in the ∑ρL accumulator (no nondeterministic parallel sums — fold detector by detector, sort HEALPix pixels by index before summing), and pinned library versions in the build SHA.

---

## 2. Scope

### Stage A — Core ray loop (internal physics milestone)

Headless Python CLI. No CAD kernel, no GUI, no report engine. Proves the physics loop is correct and fast enough. **This is a developer/test deliverable, not a user-facing product** — end users will never run Stage A directly. Its purpose is to land the ray engine, dose math, and integration tests in isolation, so Stage B can build on a verified physics core.

| Area | Capability |
|---|---|
| Geometry input | Pre-tessellated STL or OBJ per solid; one file per material group |
| Material input | CSV: `group_id, density_g_cm3, z_eff, display_name` |
| Detector input | JSON: list of `{position_xyz, frame_axes, name}` |
| Environment input | Pre-computed solid-sphere dose-depth curve (mm Al thickness vs dose per species). MVP dialect: OMERE `.dos`. RaySim does not run SHIELDOSE-2 itself in MVP |
| Dose kernel | Imported DDC fitted with a log-cubic spline; per-species columns preserved through to results |
| Interpolation | Log-cubic spline on (log t, log D) via SciPy |
| Ray engine | HEALPix equal-area sampling (`pix2vec` from `healpy` where available, or RaySim's vendored NumPy fallback per §4.3); Embree BVH (`embreex`); iterative closest-hit with bbox-scaled epsilon; max-hit guard |
| Output | JSON per-detector: TID, shielding distribution stats (Min/P05/Median/P95/Max + variance across HEALPix pixels — *angular spread*, not Monte Carlo σ), per-species breakdown, HEALPix map array, provenance block |

**Why this exists.** It verifies the geometry-and-convolution path — DDC spline fit, HEALPix uniformity, multi-hit traversal, ∑ρL accumulation — against analytic cases and reference outputs, without CAD or UI distractions. The full MVP release adds Stages B1–B5 (STEP ingest, materials UI, detector placement, reports + packaging, validation) on top of this engine. Stage A's STL+CSV+JSON interface exists for internal regression testing and CI, not for end users.

### Stage B — Product MVP (adds to Stage A)

| Area | Capability |
|---|---|
| Geometry | STEP AP203/AP214/AP242 via `pythonocc-core`; assembly tree; `BRepMesh_IncrementalMesh` tessellation with governed deflection; `BRepMesh_ModelHealer`; per-solid-shell watertightness validator |
| Materials | In-app library + assembly-tree assignment UI; STEP material-tag ingestion as defaults; block-run-until-complete gating |
| Detectors | Click-pick on CAD faces; point detectors; finite-box template sampled as a cloud of point subdetectors (*approximation, disclosed in reports*) |
| UI | PySide6 desktop shell: model tree, material panel, detector panel, scenario panel, run panel, result panel; OCCT AIS 3D viewer (via `pythonocc-core` PySide6 integration) |
| Overlays | 3D ray-view colored by accumulated thickness; 6-face equivalent-thickness projection; angular shielding histogram (Mollweide via `healpy.mollview` where `healpy` is in use, or a matplotlib-only Mollweide projection over the HEALPix pixel array where the vendored `pix2vec` fallback is in use) |
| Reports | PDF (ReportLab) + CSV + JSON bundle with full provenance; per-species TID breakdown when the input source provides it; reopen-reproduces-result round-trip |
| Scenario | Single mission-averaged dose-depth curve imported from OMERE `.dos`. No in-process orbit propagation, no in-process SHIELDOSE-2. Per-species TID breakdown shown by default (always present in `.dos`) |
| Packaging | `briefcase` or PyInstaller single-installer per OS |

### Explicitly deferred (post-MVP)

- In-process environment: IRENE (AE9/AP9/SPM), AE8/AP8, SGP4, SAPPHIRE/ESP, GCR models
- Per-waypoint / time-resolved dose (mission-averaged only in MVP)
- OptiX / RT-core GPU path
- Geant4 reference backend, reverse/adjoint MC
- Adaptive HEALPix refinement on shielding gradient
- Automatic spot-shield synthesis
- WebAssembly / web UI
- ECSS V&V package and benchmark farm
- TNID, SEE, LET, MicroElec
- **Stage C: native-language port** — if profiling or distribution demands justify it, port Stage A's hot path to C++ via `pybind11`/`nanobind`. Never speculatively.

---

## 3. Units, frames, conventions

**Units** (fixed at the boundary; internal math in SI where sensible, conventional units at I/O):

| Quantity | MVP unit (I/O) | Internal |
|---|---|---|
| Length (CAD) | mm | m |
| Shielding thickness (Al-equivalent) | mm Al | g/cm² internally, mm Al for UI |
| Density | g/cm³ | kg/m³ |
| Dose | krad(Si) | Gy(Si) internally, krad(Si) for UI |

*Energy and fluence units are not part of the MVP I/O surface (RaySim does not ingest spectra in MVP). They are preserved as provenance-only fields when present in the imported `.dos` header, and become first-class units when the post-MVP spectrum-in path lands.*

**Frames:**
- Scene frame: CAD world coordinates from the STEP or STL file.
- Detector frame: per-detector local frame with explicit `x,y,z` axes stored in the project file. MVP sources are isotropic, so the frame is cosmetic — but it's persisted from day 1 for future directional sources.
- HEALPix sampling is always in the scene frame.

**Mission model:** single mission-averaged dose-depth curve in → single TID number out, per detector. No time slicing in MVP.

**Material physics in MVP — explicit scope:**
- The only material-derived input to dose math is **mass density** (`density_g_cm3`).
- ∑ρL is converted to mm-Al-equivalent by mass-equivalence: `t_Al = ∑ρᵢLᵢ / ρ_Al`. This is the standard sector-analysis approximation, accurate to ~10–20% across most low-Z spacecraft materials.
- **`z_eff` is metadata only** in MVP. It is preserved in the project file and reports for traceability and so future Z-dependent corrections (high-Z bremsstrahlung, low-energy proton scattering) can land without a schema change. **MVP does not perform material-specific transport.** Reports state this so users do not infer otherwise.
- `composition`, `display_name`, and other material fields are similarly metadata only.

**Numerical conventions:**
- Ray math in `float64` (NumPy default).
- Geometry stored `float64`; Embree consumes `float32` (native). Chord-length accumulation stays `float64` on the Python side.
- Epsilon for iterative closest-hit `tnear` = `1e-6 × scene_bbox_diagonal`, not material-scaled.
- Max hits per ray = 4096 (configurable). Exceeding is a run-fatal error with the offending ray reported.
- Path-length accuracy target: relative error ≤ `1e-5` vs analytic for concentric-shell tests.

**Dose-depth curve schema (canonical internal form):**

RaySim's only environment input. Produced by an external tool (OMERE in MVP) and imported as-is:
- `thickness_mm_al`: monotonically increasing 1D array, mm Al-equivalent.
- `dose_per_species`: dict `{species → 1D array}`, krad(Si) per thickness sample. Species: `trapped_electron`, `trapped_proton`, `solar_proton`, `gamma`.
- `dose_total`: 1D array, krad(Si) per thickness sample (sum of species).
- `source_tool`: free-text provenance (`OMERE-5.9`, etc.).
- `mission_metadata`: optional dict (orbit, duration, confidence, models used) carried through to the report unchanged.

Per-species columns enable the report's TID breakdown (Trapped e⁻ / Trapped p⁺ / Solar p⁺ / Gamma) without re-running physics. Importers live in `raysim.env.importers.<dialect>` (MVP ships `omere_dos`); adding a new dialect is one file plus a fixture.

---

## 4. Key decisions

### 4.1 Python 3.11+ as the primary language
- **Hot path:** Embree via `embreex` — batched `rtcIntersect1M` queries at millions of rays per second; Python overhead is outside the inner loop.
- **Glue:** NumPy-vectorized where it matters (∑ρL accumulation, spline eval, HEALPix integration).
- **Escape hatch:** if Stage A profiling shows a specific function is the bottleneck, drop it to `pybind11`/`nanobind` as an extension module. Don't pre-optimize.
- **Why not Rust:** OCCT bindings (`opencascade-rs`) are incomplete. For a CAD-heavy app, you'd spend the Stage A timeline writing FFI. Revisit when the ecosystem matures.
- **Why not C++ now:** slower iteration on MVP-shaped work, and the perf gap on this problem is small. Reserve C++ for a post-MVP Stage C port if distribution or perf demands it.

### 4.2 CPU Embree via `embreex`
Embree covers MVP performance needs. **Three labelled performance targets** are used consistently across the doc to avoid contradictions:
- **Smoke target** — single-shot dependency check: ~1 s for a batched ray cast on a 1 M triangle mesh (Phase 0 spike).
- **Dev benchmark** — Phase A acceptance on a developer laptop: aluminum-box scenario, Nside=64, ≤ 10 s single-threaded.
- **Product benchmark** — Phase B5 release gate on a workstation: full real assembly, 100 detectors, Nside=64, ≤ 90 s on 16 cores.

Batched ray queries from Python keep overhead under 30%. OptiX/RT-core is a later optimization behind the same Python interface.

### 4.3 HEALPix sampling
Equal-area pixels → TID reduces to unweighted mean of per-ray dose. Hierarchical for future adaptive refinement. **Implementation:** `healpy` where it installs cleanly (Linux, macOS, and Windows when wheels are available); a vendored NumPy-only `pix2vec` fallback (~50 lines from the HEALPix paper) on platforms where `healpy` does not install. RaySim only needs direction-vector generation, not the full `healpy` surface — no FITS, no spherical harmonics, no rotator. The Phase 0 spike (§6) decides which is used per OS.

### 4.4 Iterative closest-hit, not AnyHit
AnyHit returns hits out of BVH order, forcing unbounded per-ray sort buffers. Iterative closest-hit with a scene-bbox-scaled `tnear` bump guarantees ordered entry/exit pairs in fixed memory. Implemented as a Python loop over batched Embree calls: cast all rays, advance `tnear` by epsilon past each ray's latest hit, re-batch, repeat until all rays miss or hit the safety cap.

### 4.5 `pythonocc-core` + BRepMesh + Healer + per-solid-shell watertightness check
`pythonocc-core` is production-used in FreeCAD and related tools and exposes a wide OCCT surface, including `STEPCAFControl_Reader` (assembly tree + material/color attributes) and `BRepMesh_IncrementalMesh`. Watertightness is validated per closed shell of each solid: group triangles by source shell; every non-degenerate edge appears in exactly two triangles with opposite orientation. Solids that fail the check surface in the UI and block runs until fixed or overridden.

### 4.6 Dose-curve import only; no in-process environment, no in-process SHIELDOSE-2
MVP requires the user to bring a pre-computed solid-sphere dose-depth curve. Reference dialect: OMERE `.dos`, which already bundles per-species dose vs mm Al for one mission scenario.

**Why this scope.** In-process orbit propagation (IRENE / AE9-AP9 / SGP4 / IGRF) is a substantial subsystem in its own right. In-process SHIELDOSE-2 (via SpacePy or a hand-port) is a real engineering risk on top of it. Both are deferred. RaySim's MVP value is the geometry + ∑ρL + spline-lookup loop on real CAD, not the environment models that already exist in OMERE/SPENVIS/IRENE.

**What this opens up post-MVP.** A spectrum-in path (SPENVIS / OMERE `.fle` / IRENE API → SHIELDOSE-2 in RaySim → DDC) lands behind the same downstream code, producing the same internal `DoseDepthCurve` consumed by the dose module. The MVP architecture is set up so this is an additive change, not a refactor.

### 4.7 Desktop-first PySide6 + OCCT AIS viewer (Stage B only)
Stage A is headless CLI. Stage B uses PySide6 with the OCCT AIS viewer widget exposed by `pythonocc-core`. Precise picking and sectioning on heavy STEP is the hard UX problem; doing it in a browser adds years. PySide6 is the Qt for Python binding under the LGPL Qt license.

### 4.8 Material governance
- Sidecar table is source of record.
- STEP AP214_IS material tags and color attributes ingested as **defaults** on import (via `STEPCAFControl_Reader`).
- Every solid must resolve to a library material before a run.
- Density anomalies (`< 0.5 g/cm³` or `> 25 g/cm³`) surface as warnings but do not block.

### 4.9 Finite-box detector is an approximation
A finite-box detector is sampled as a cloud of point subdetectors averaging ∑ρL. This is **not** equivalent to volume-averaged dose (which would require Monte Carlo sampling of interaction points, not just ∑ρL evaluation). Reports state this explicitly. Proper volume-averaged dose lands with the Geant4 backend.

### 4.10 Packaging via `briefcase` or PyInstaller
Single-installer per OS (Windows MSI, macOS `.app`, Linux AppImage). Bundle Python runtime, pinned dependencies, and the OCCT shared libraries. Decide between `briefcase` and PyInstaller at Stage B4 based on OCCT binary handling.

---

## 5. Architecture

```
┌─────────────────────────────────────────────────────────────┐
│ Stage B: PySide6 Desktop Shell                              │
│  [Tree] [Materials] [Detectors] [Scenario] [Run] [Results]  │
│  + OCCT AIS Viewer + Overlays + Report Engine               │
└──────────────────────┬──────────────────────────────────────┘
                       │
     ┌─────────────────┼───────────────────┐
     │                 │                   │
┌────▼─────┐     ┌─────▼──────┐     ┌──────▼──────┐
│ geom     │     │ mat        │     │ proj        │
│ pythonocc│     │ library +  │     │ .raysim JSON│
│ + tess + │     │ assignment │     │ + hashes    │
│ healer + │     │ + STEP tag │     │ (Pydantic)  │
│ wt check │     │ interop    │     │             │
└────┬─────┘     └─────┬──────┘     └──────┬──────┘
     │                 │                   │
     └──────┬──────────┴───────────────────┘
            │
┌───────────▼────────────────────────────────────────┐
│ Stage A: Core ray loop (headless, reusable)        │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────┐  │
│  │ env      │  │ ray      │  │ dose             │  │
│  │ DDC      │  │ embreex +│  │ log-cubic spline │  │
│  │ import   │→ │ HEALPix +│→ │ + per-species    │  │
│  │ (.dos)   │  │ multi-hit│  │ stats            │  │
│  └──────────┘  └──────────┘  └──────────────────┘  │
└────────────────────────────────────────────────────┘
```

**Module boundaries** (Python 3.11+, one package `raysim/`):

- `raysim.geom` — `pythonocc-core` ingest, tessellation, healing, per-solid-shell watertightness. Stage B only. Stage A consumes STL via `trimesh`.
- `raysim.mat` — material library + assignment table + STEP-tag ingestion. Pydantic models.
- `raysim.env` — DDC importers. MVP dialect: OMERE `.dos` (`raysim.env.importers.omere_dos`). Each importer produces the same internal `DoseDepthCurve` consumed by the dose module.
- `raysim.ray` — `embreex` wrapper, HEALPix `pix2vec` ray generator (from `healpy` or RaySim's vendored fallback per §4.3), iterative closest-hit loop. Physics-agnostic.
- `raysim.dose` — SciPy log-cubic spline, per-ray dose lookup, detector aggregation.
- `raysim.proj` — project file I/O (Pydantic JSON), geometry hash, provenance block.
- `raysim.ui` — PySide6 + OCCT AIS. Stage B only.
- `raysim.report` — ReportLab PDF + CSV + JSON emitters. Stage B only.
- `raysim.cli` — Click CLI for Stage A headless runs.

**Threading / concurrency:**
- Embree runs its own TBB pool under `embreex`.
- PySide6 UI stays on the main thread; runs dispatch to a `QThread` or `concurrent.futures` worker that drives the ray engine.
- Per-detector parallelism via `concurrent.futures.ProcessPoolExecutor` if GIL becomes a bottleneck (Embree releases the GIL during batched intersection calls, so threading is usually fine).
- Per-ray parallelism is Embree's internal.

**External dependencies** (pinned in `pyproject.toml`):
- `numpy`, `scipy`, `embreex` (or `trimesh[all]` which vendors it), `trimesh`, plus `healpy` *or* the vendored NumPy `pix2vec` fallback (decided per OS in §4.3 / §0.2) — Stage A.
- `pythonocc-core`, `PySide6`, `pyqtgraph`, `matplotlib`, `reportlab` — Stage B.
- `pydantic`, `click`, `structlog`, `pytest`, `pytest-benchmark` — common.

---

## 6. Delivery plan

### Phase 0 — Spikes and gates

No code lands on `main` except infra and decided spikes.

| Spike | Gate | Outcome |
|---|---|---|
| OMERE `.dos` importer | `dose700km.dos` parses into the canonical `DoseDepthCurve` schema (§3); spline fit round-trips to ≤1% relative error against the source rows; per-species columns (Trapped e⁻ / Trapped p⁺ / Solar p⁺ / Gamma) preserved through to the report | Ship `omere_dos` importer; the user's actual `.dos` file becomes the integration fixture |
| Benchmark corpus | Three STEP assemblies with redistributable licensing: one open-source CubeSat, one custom-authored test article (box + PCB + battery + panel), one larger open mission | Assets in `/benchmarks` or referenced as submodule |
| `embreex` on target OS | Builds, installs via pip, batched ray cast at smoke target (~1 s on a 1 M triangle mesh) | Confirm or pick alternative (e.g. `trimesh.ray.ray_pyembree`) |
| `healpy` on Windows | `pip install healpy` succeeds on Windows CI **or** a vetted pure-Python/NumPy `pix2vec` substitute is in place | If healpy lacks Windows wheels for our Python version, vendor a minimal NumPy-only `pix2vec` (~50 lines) — RaySim only needs direction-vector generation, not the full healpy surface |
| `pythonocc-core` on target OS | STEP import + `BRepMesh_IncrementalMesh` + `BRepMesh_ModelHealer` minimal example runs on Windows and Linux; AIS viewer renders a cube | Confirm install path (conda vs pip wheel); verify the exact `BRepMesh_ModelHealer` binding is exposed (OCCT healing APIs are version-sensitive — fall back to a hand-written healing pass if not exposed) |
| Tooling | `uv` or `poetry`, ruff, mypy, pytest, GH Actions CI on Linux + Windows | Green CI on scaffold repo |

**Exit:** every spike decided in writing; canonical aluminum-box test vector available for downstream phases.

### Phase A — Core ray loop

- `env`: OMERE `.dos` importer producing the canonical `DoseDepthCurve` (rad → krad units, per-species columns preserved).
- `dose`: SciPy `CubicSpline` on (log t, log D_total) plus per-species variants with endpoint guards; unit tests against analytic exponentials and round-trip on the imported DDC.
- `ray`: `pix2vec` generator (from `healpy` or RaySim's NumPy fallback per the §4.3 decision), `embreex` scene from `trimesh`-loaded STL, iterative closest-hit with bbox-scaled epsilon + max-hit guard. Vectorized batched loop.
- `dose`: per-detector aggregation (unweighted mean, per-pixel variance, per-species breakdown).
- `raysim.cli`: `raysim run --scene scene.stl --materials mat.csv --detectors det.json --dose-curve env.dos --nside 64 --out run.json`.

**Acceptance tests:**
1. Ray through a concentric-shell test article matches analytic ∑ρL to relative error ≤ 1e-5.
2. HEALPix uniform-shield test: uniform spherical Al shell of thickness t → computed dose within ±0.1% of the imported DDC's interpolated value at t.
3. Mass-conservation sanity: sum of per-ray ∑ρL over the full HEALPix sphere equals 4π × mean mass-per-unit-solid-angle within numerical tolerance.
4. **Dev benchmark:** `raysim run` on the custom aluminum-box benchmark, Nside=64, completes in ≤ 10 s on a dev laptop (single-threaded).
5. Determinism: two runs with identical inputs produce byte-identical `run.json`.

**Exit: physics-correct ray engine.** Internal milestone — Stage B builds the user-facing product on top.

### Phase B1 — Geometry pipeline

- `pythonocc-core` STEP importer (`STEPCAFControl_Reader`); assembly tree with names, colors, layers.
- `BRepMesh_IncrementalMesh` with exposed linear + angular deflection.
- `BRepMesh_ModelHealer` integration (or hand-written healing pass per the Phase 0 fallback) **+ shell-normal orientation normalization** so every closed shell has consistent outward-pointing triangles (precondition for the A.4 stack accumulator).
- Per-solid-shell watertightness validator; failure list surfaced via the logger and API.
- **Overlap and interference diagnostic** (coincident-face detection, solid-solid AABB+intersection check, nested-solid detection). Per-pair report; user-acceptable pairs persisted in the project file.
- STL export path so Stage B geometry drops into Stage A for regression.

**Exit:** all three benchmark assemblies import, tessellate, heal, pass watertightness; overlap diagnostic clean (or with all flagged pairs explicitly accepted); STL round-trip matches volume within 0.5%.

### Phase B2 — Materials + project file

- Material library (seeded: Al, Cu, Si, SiO₂, Kapton, FR4, Ti, W, GaAs, Au, Sn-Pb solder) as a Pydantic model.
- STEP AP214_IS material-tag ingestion as defaults (`STEPCAFControl_Reader` with `XCAFDoc_MaterialTool`).
- **Pattern-based material auto-assignment on STEP import.** Ship a default naming-rules YAML covering common conventions (Al, Cu, Si, FR4, Kapton, Ti, W, Au, etc.); rules are user-editable and persisted at the project level so team conventions accumulate. After import, a review panel surfaces auto-matched / ambiguous / unmatched part counts and lets the user accept-all, review individually, or skip.
- Assembly-tree assignment with propagate / override / unassigned states.
- `.raysim` project JSON round-trip with SHA-256 geometry hash.
- Block-run-until-complete gating + density-anomaly warnings.

**Exit:** open STEP, fully assign materials (partly auto from STEP tags + naming rules — typically 20–30 dropdown picks for the residual instead of 100+); save → reopen → save produces a byte-identical canonical `.raysim`; rerunning the engine on either copy produces an identical `run.json`.

### Phase B3 — UI + authoring

- PySide6 main window.
- OCCT AIS viewer with face/edge/vertex picking (via `pythonocc-core`'s `qtDisplay`).
- Detector placement: click-pick + face-centroid snap + normal-offset + finite-box template.
- Scenario panel: `.dos` file picker + DDC preview plot (matplotlib).
- Run panel: QThread worker + progress + cancel.
- Overlays: 3D ray-view by thickness; 6-face projection; angular shielding histogram (Mollweide).

**Exit:** first-session engineer can open a CubeSat STEP, assign materials, place 5 detectors, run, and see colored rays + TID numbers within 10 minutes.

### Phase B4 — Reports + packaging

- PDF per run (cover + per-detector pages + provenance block + finite-box approximation disclaimer).
- CSV per detector and per-ray-bin.
- JSON scenario bundle; reopen on the same build SHA + pinned library versions reproduces a bit-identical `run.json`. Reports (PDF, dashboards) render identical numerics but may differ in timestamps and layout.
- `briefcase` or PyInstaller packaging for Windows + Linux (macOS optional).

**Exit:** bundle handed to a reviewer off-machine reproduces a bit-identical `run.json` on the same build; reports render identical numerics; installer produces a working app on a clean machine.

### Phase B5 — Validation + hardening

- Canonical validation: aluminum-box, solid-sphere, concentric-shell vs analytic + SHIELDOSE-2.
- Cross-check at least one benchmark against SSAT or a published SHIELDOSE-2 reference within literature-stated bounds (≤20% for electron-dominated LEO).
- Nightly regression corpus with tolerance bands.
- **Product benchmark:** full real assembly, 100 detectors, Nside=64, ≤ 90 s on 16 cores.
- UX hardening (large STEPs, unassigned materials, partial watertightness overrides).

**Exit:** RC build, regression-green, performance budget met, validation dossier in `/docs/validation`.

### Release shape

- **Stage A** is a developer/test-only deliverable: the physics-correct ray engine with a CLI for regression and CI use. Not user-facing.
- **Internal interactive checkpoint** = Stage A + B1 + B2 + B3. The smallest build where opening the app, importing a STEP, assigning materials, placing detectors, and getting TID numbers + 3D overlays all work end-to-end. Used internally to validate the UX flow on real geometry. **Not the MVP** — produces no PDF, no installer, no validation evidence; not shippable to a reviewer.
- **MVP release** = Stage A + B1 + B2 + B3 + B4 + B5. The full reviewable build: STEP-driven authoring + reports + installer + validation dossier. This is what "MVP" means throughout the doc and the §7 acceptance criteria.

---

## 7. Acceptance criteria

### Stage A internal milestone gate
*Not a release — internal checkpoint that Phase A is complete and the engine is trustworthy for downstream phases to build on.*
1. All Stage A acceptance tests (§6 Phase A) green, including the float32-precision hard gate.
2. Determinism: identical inputs → byte-identical `run.json` (engine output only; human reports include timestamps and are not bit-identical).
3. Documented, versioned JSON output schema (Pydantic model + `schema_version`).
4. Installable via `pip install raysim` from a local wheel for downstream regression use.

### Internal interactive checkpoint
*Not a release — the smallest end-to-end build (A + B1 + B2 + B3) used internally to validate UX flow on real geometry before B4/B5 land.*
1. Open a benchmark STEP, fully assign materials (auto + dropdown), place ≥ 5 detectors, run, see colored ray overlays + per-detector TID.
2. Save → reopen → save produces a byte-identical canonical `.raysim`; rerunning the engine on either copy produces an identical `run.json`.
3. No PDF, no installer, no validation dossier required at this checkpoint.

### MVP release (Stages A + B1 + B2 + B3 + B4 + B5)
*The full reviewable release — what "MVP" means in this doc.*
1. Imports the three benchmark assemblies; every solid watertight and material-assigned, with mismatched-contact gate clean. Full overlap/interference diagnostic (on-demand via `raysim validate` or UI "Validate Geometry") clean or accepted in the project file.
2. Produces per-detector TID for a standard imported `.dos` scenario inside the product-benchmark performance target (≤ 90 s on 16 cores for the full real assembly with 100 detectors at Nside=64).
3. Matches analytic path-length tests to relative error ≤ 1e-5 (or documented relaxation); spline reproduces the imported DDC to ≤1% relative against source rows.
4. Bundle handed off-machine reproduces a bit-identical `run.json` on the same build SHA and pinned library versions (PDF and dashboard artifacts may differ by timestamp/layout but render identical numerics).
5. Reports carry the full provenance block and the finite-box approximation disclaimer where applicable; per-species TID breakdown rendered.
6. Installer runs on a clean Windows and Linux machine with no Python or OCCT pre-installed.
7. Nightly regression suite stable and green before release.
8. Validation dossier (B5.6) complete and referenced from the report's provenance block.

---

## 8. Top risks and mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| STEP metadata incomplete / wrong materials | Dose off by orders of magnitude | Sidecar source-of-record; block runs until all solids assigned; density-anomaly warnings |
| Non-watertight tessellation | Infinite path lengths, silent bad results | Per-solid-shell validator; refuse to run on unhealable solids; max-hit guard catches escapes at runtime |
| Overlapping or coincident solids in the assembly | Silent ρ double-counting (overlaps) or zero-counting (cancellation) | B1.5 overlap/interference diagnostic at scene build; A.4 material-state stack accumulator handles legitimate coincident faces deterministically; runtime overlap-suspicious detection (in-stack depth > bbox diagonal) flags the rest |
| Imported DDC misinterpreted (units, columns, percentile) | Systematic dose error | Strict `omere_dos` parser with explicit unit conversion (rad → krad); fixture tests on a reference `.dos`; mission-metadata block carried into reports so the percentile/model is visible |
| Iterative closest-hit epsilon at tangent edges | Missed exits / double counts | Bbox-scaled epsilon; tangent-grazing unit tests; max-hit guard |
| Python overhead outside Embree loop | Slow iteration on very large scenes | Vectorize aggregation in NumPy; profile in Stage A; drop hottest function to `nanobind` C++ extension if measured > 30% overhead |
| Python packaging on Windows with OCCT binaries | Broken installer on user machines | Evaluate `briefcase` vs PyInstaller in phase 0; test on a clean VM in phase B4 |
| `pythonocc-core` binding gaps for a needed OCCT API | Blocker on an OCCT feature | Call the missing class via `pythonocc-core`'s SWIG fallback or write a small `pybind11` extension for that class; escalate if systemic |
| Scope creep toward Geant4 / OptiX / IRENE | Slip | Deferred list is contractual until MVP+1 planning |
| Schedule slips on Stage B | MVP release delayed | The internal interactive checkpoint (A+B1+B2+B3) provides a usable end-to-end build for in-house validation while B4/B5 close out, so internal review can begin before reports/installer/validation dossier are ready — but the *MVP release* gate is not crossed until B5 is done |
| Material assignment is still tedious despite STEP tags + naming rules | User friction on first project per spacecraft | Combined with STEP AP214_IS tag ingestion, name-pattern rules typically reduce the per-project assignment task from 100+ dropdown picks to ~25; rules accumulate in the project file so successive missions converge on near-zero manual assignment |
| Finite-box detector misread as volume-averaged dose | User misinterprets | Explicit disclaimer on every finite-box result in UI + report |
| Sector analysis overestimates dose in heavy / low-E-p / secondary-rich cases | User misinterprets | Document limits in report boilerplate; surface caution flag when per-ray ∑ρL exceeds literature-calibrated threshold |
| Benchmark corpus unavailable | Phase 0 blocked | Custom-author a third test article in phase 0; two open-source assemblies are nice-to-have, not critical |

---

## 9. Post-MVP roadmap (signal, not commitment)

Ordered by approximate value-to-effort:

1. **Spectrum-in path (Path A)** — accept SPENVIS / OMERE `.fle` / generic CSV spectra and run SHIELDOSE-2 (SpacePy or hand-port) in-process to produce the same internal `DoseDepthCurve`. Removes the dependency on the user pre-computing the dose curve.
2. **IRENE (AE9/AP9/SPM) + SGP4 in-process** via IRENE's Python API — orbit propagation + environment models in-app, feeding the spectrum-in pipeline.
3. **Per-waypoint / time-resolved dose** — mission segmentation and worst-case modes.
4. **Adaptive HEALPix refinement** on shielding gradient.
5. **OptiX / RT-core GPU path** behind the same `raysim.ray` interface, via `optix` Python bindings or a `nanobind` extension.
6. **Geant4 reference backend** for `reference`-mode runs on the same scenario bundle, via Geant4's Python bindings.
7. **Spot-shield synthesis** from the HEALPix shielding map.
8. **Web report viewer** over the JSON bundle.
9. **TNID, LET, MicroElec** physics extensions.
10. **SSAT / GRAS / MCNP validation farm** per ECSS-E-ST-10-12C expectations.
11. **Stage C: native-language port** — only if profiling proves a systemic Python penalty or distribution demands a sealed single binary. Port Stage A's hot path to C++ via `nanobind`; keep the Python API surface.

---

## 10. Open decisions — close in phase 0

- [ ] OS priority for dev loop. *Proposed: Linux first; Windows target from Stage B1 onward.*
- [ ] Package manager: `uv` vs `poetry`. *Proposed: `uv` for speed, `poetry` if a team member prefers.*
- [ ] `pythonocc-core` install path (conda vs pip wheel). *Decide by end of phase 0; affects packaging strategy.*
- [ ] Installer tool (`briefcase` vs PyInstaller). *Decide by phase B4 based on how OCCT shared libs bundle.*
- [ ] Benchmark corpus sources (two open assemblies + one custom test article). *Named by end of phase 0.*
- [ ] Project file schema version policy (every change bumps `schema_version`; loader supports N-1). *Confirm before Stage B2.*
- [ ] What counts as block-run vs warning for material anomalies. *Physicist sign-off before Stage B2.*
- [x] **Embree `float32` precision impact on ∑ρL accuracy is a hard Phase A gate, not an open decision.** Acceptance test A.7 must demonstrate relative error ≤ 1e-5 on the concentric-shell test using `float64` accumulation in Python outside Embree. If float32 hit distances make this unattainable on large scenes, the decision is to (a) accept a relaxed bound (e.g. 1e-4) and document, or (b) compute hit positions in float64 by re-querying parametric distances post-hit. The choice is forced by measurement, not deferred.
