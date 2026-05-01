# RaySim — Delivery Steps

Companion to `MVP_PLAN.md` (v3.1). The plan defines scope and decisions; this file decomposes each phase into the steps that actually get implemented. Each step is the smallest body of work that produces a coherent reviewable artifact: a scaffold, an importer, a module with unit tests, a UI panel.

Step IDs are stable references (`A.3`, `B2.4`, etc.) so they can be cited in commits, PRs, and issues.

---

## Progress checklist

Use this section as the working tracker. Keep the detailed step definitions below as the source of truth for scope and "done when" criteria.

### Phase 0
- [x] 0.1 — Repository scaffold and tooling
- [x] 0.2 — Dependency bring-up and smoke tests
- [x] 0.3 — OMERE `.dos` format characterization and `omere_dos` importer
- [x] 0.4 — Benchmark corpus and canonical test geometries
- [x] 0.5 — Phase-0 decision write-up

### Phase A
- [x] A.1 — Project schemas
- [x] A.2 — DDC import and log-cubic spline
- [x] A.3 — Scene loader and Embree BVH
- [x] A.4 — HEALPix ray generator and iterative closest-hit traversal
- [x] A.5 — Per-detector aggregation and per-species breakdown
- [x] A.6 — CLI and run output
- [x] A.7 — Acceptance test suite and performance baseline

### Phase B1
- [ ] B1.1 — STEP loader with assembly tree
- [ ] B1.2 — Tessellation pipeline
- [ ] B1.3 — Healing and orientation normalization
- [ ] B1.4 — Per-solid-shell watertightness validator
- [ ] B1.5 — Overlap and interference diagnostic
- [ ] B1.6 — Stage A adapter and STL export

### Phase B2
- [x] B2.1 — Material library
- [x] B2.2 — STEP AP214_IS material-tag ingestion
- [x] B2.3 — Naming-rules auto-assignment
- [x] B2.4 — Auto-assignment review
- [x] B2.5 — Project file format
- [x] B2.6 — Run gating and density anomaly warnings

### Phase B3
- [x] B3.0 — XCAF migration: unify STEP loader on STEPCAFControl_Reader
- [x] B3.1 — Main window shell
- [x] B3.2 — OCCT AIS viewer integration with picking
- [x] B3.3 — Material assignment UI
- [x] B3.4 — Detector placement
- [x] B3.5 — Scenario panel
- [x] B3.6 — Run dispatcher
- [x] B3.7 — Result overlays

### Phase B4
- [ ] B4.1 — Report data model and PDF generator
- [ ] B4.2 — CSV exports
- [ ] B4.3 — JSON scenario bundle and reopen-reproduces
- [ ] B4.4 — Installer build
- [ ] B4.5 — Clean-machine install verification

### Phase B5
- [ ] B5.1 — Canonical analytic validation
- [ ] B5.2 — Cross-tool reference comparison
- [ ] B5.3 — Nightly regression infrastructure
- [ ] B5.4 — Performance benchmarking and tuning
- [ ] B5.5 — UX hardening
- [ ] B5.6 — Validation dossier

---

## Phase 0 — Spikes and gates

Goal: de-risk and decide before any Phase A code lands on `main`.

### 0.1 — Repository scaffold and tooling
Set up the Python package layout (`raysim/`, `tests/`, `benchmarks/`, `docs/`). Pin Python 3.11+. Configure `pyproject.toml`, `uv` (or `poetry`), `ruff`, `mypy`, `pytest`, `pytest-benchmark`, `structlog`, `pre-commit`. Add a GitHub Actions CI workflow that runs lint + typecheck + tests on Linux and Windows. Define the canonical CLI entrypoint `raysim` as a `--version` stub.

**Done when:** green CI on a hello-world commit; `raysim --version` prints on both target OSes.

### 0.2 — Dependency bring-up and smoke tests
Install and verify the load-bearing third-party libs on Linux and Windows: `embreex`, `healpy` (or a NumPy `pix2vec` fallback), `trimesh`, `pythonocc-core`, `numpy`, `scipy`, `pydantic`, `click`. For each: a one-file smoke test that exercises the minimum API surface RaySim needs:
- **HEALPix `pix2vec`** — direction-vector generation for a small Nside.
- **Embree BVH build + closest-hit ray cast** — single ray against a triangulated cube.
- **Embree `IntersectContext` filter callback** — a ray query with a Python-side filter that accepts/rejects primitives based on `t` and `primitive_id`. **Required for A.4's fallback tie-batch path.** If `embreex` does not expose this API surface (or exposes it too slowly for batched use), the A.4 pre-built coincident-face group path becomes the *only* supported path and is upgraded from "preferred" to **mandatory** in B1.5.
- **`pythonocc-core` STEP read** of a single-cube file.

**Special attention:**
- **healpy on Windows:** PyPI wheel availability for healpy on Windows for the chosen Python version is unreliable. Verify on a clean Windows CI runner. If install fails, vendor a NumPy-only `pix2vec` substitute (~50 lines from the HEALPix paper) — RaySim only needs direction generation, not the full healpy surface (no FITS, no spherical harmonics, no rotator).
- **`BRepMesh_ModelHealer` binding:** OCCT healing APIs vary across OCCT versions and binding generators. Verify the exact class is exposed by the chosen `pythonocc-core` build. If not, the fallback is a hand-written healing pass on the tessellated mesh (fill micro-cracks via vertex welding within tolerance, snap edges, drop degenerate triangles).
- **Embree filter callback:** if absent or unreliable, A.4's fallback tie-batch query has no implementation path. Document the conclusion: pre-built coincident groups (B1.5) become the only tie-handling mechanism.

**Done when:** every smoke test passes in CI on both OSes; install paths (conda vs pip wheel) documented per dependency; healpy, ModelHealer, and Embree filter-callback fallback paths are decided in writing.

### 0.3 — OMERE `.dos` format characterization and `omere_dos` importer
Parse the user's actual `.dos` file (e.g. `dose700km.dos`). Document its grammar: header block (mission/orbit/model metadata), the per-species column layout (Trapped e⁻ / Trapped p⁺ / Solar p⁺ / Gamma / Total), units (mm Al → cm conversion, rad → krad). Implement `raysim.env.importers.omere_dos` returning the canonical `DoseDepthCurve` Pydantic model. Round-trip plot the imported curve against the source rows.

**Done when:** importer parses the user's `.dos` losslessly; spline fit reproduces every source row to ≤1% relative error; per-species columns preserved end-to-end.

### 0.4 — Benchmark corpus and canonical test geometries
Source three STEP assemblies with redistributable licensing: an open-source CubeSat, a custom-authored test article (box + PCB + battery + panel), one larger open mission. Generate canonical analytic test geometries as STL: solid aluminum box, solid sphere, concentric Al/Cu shell. Place them in `/benchmarks` with provenance notes.

**Done when:** all benchmark assets in-repo or referenced by submodule; canonical analytic ∑ρL values for the simple geometries documented as test fixtures.

### 0.5 — Phase-0 decision write-up
One short markdown note in `/docs/decisions/` capturing: install paths chosen per dependency, packaging tool tentative choice (briefcase vs PyInstaller), benchmark corpus identifiers, and any blockers found during spikes.

**Done when:** decision doc reviewed and merged; Phase A can proceed without ambiguity.

---

## Phase A — Core ray loop

Goal: a deterministic, headless engine that turns (STL + materials CSV + detectors JSON + DDC) into per-detector TID. Internal milestone, not user-facing.

### A.1 — Project schemas
Define Pydantic models for `Material`, `MaterialAssignment`, `Detector`, `DoseDepthCurve`, `RunResult`, `Provenance`. JSON schema export for external consumers. Versioned with `schema_version`.

**Done when:** every model has a fixture JSON, schemas round-trip lossless, schema version pinned in code.

### A.2 — DDC import and log-cubic spline
Wire the `omere_dos` importer from 0.3 into a `DoseDepthCurve` consumer. Build the SciPy `CubicSpline` on `(log t, log D_total)` plus per-species variants. Add endpoint guards (clamp on extrapolation, warn). Unit tests against analytic exponentials and against the imported DDC's own source rows.

**Edge cases that must be handled explicitly (log(0) breaks naively):**
- **Thickness `t = 0`.** OMERE `.dos` files start at a small but nonzero thickness (e.g. `1e-2 mm`). For `t < t_min` (which can happen for direct-line-of-sight rays on the edge of the spacecraft), clamp to the dose at `t_min` and emit a warning rather than extrapolating into log-space. Document the clamp in the report provenance.
- **Zero or near-zero species columns.** `.dos` files commonly have `0.0` for species that don't contribute (e.g. trapped electrons at deep thicknesses). For a per-species spline where the entire column is zero, return a constant-zero callable and skip the log transform. For columns with mixed zero and nonzero values, replace zeros with a floor (e.g. `1e-30 krad`) before the log, document the floor.
- **Monotonicity.** OMERE DDCs are monotonically decreasing within a species but not strictly so when summed (rare numerical jitter). Validate input; log if any row's `D` exceeds the previous row.

**Done when:** dose lookup at any thickness ≤ 1% relative against source rows; per-species lookups available; the three edge cases above are covered by unit tests with clear failure messages.

### A.3 — Scene loader and Embree BVH
STL loader via `trimesh`. Scene format: a flat directory of `*.stl` files, one per solid; file stem becomes the `solid_id`. Material mapping via an optional `MaterialAssignment[]` JSON; when omitted, `solid_id` is treated as the `material_group_id` directly. Build an Embree scene with per-triangle material indices that map back to the materials CSV. Compute scene bounding box for downstream epsilon scaling.

**Done when:** loading the canonical aluminum-box STL produces a watertight Embree BVH whose ray-cast against an external ray returns expected hit positions to `float32` precision.

### A.4 — HEALPix ray generator and iterative closest-hit traversal
Wrap `pix2vec(Nside, range(npix))` (healpy or fallback per step 0.2) to emit unit direction vectors. Implement the iterative closest-hit loop: batched `embreex` calls with `tnear` advanced by `eps = 1e-6 × bbox_diagonal` past each ray's latest hit, repeated until all rays miss or hit the safety cap (4096 hits).

**Material-state stack accumulator** (not scalar accumulation). Real STEP assemblies have coincident faces, touching parts, and occasional overlaps; a scalar ρ-sum mis-handles these. Each ray maintains an *open material stack* — the set of solid IDs the ray is currently inside. **Precondition:** all shell normals are outward (validated/normalized in B1.3); without this, entry/exit classification inverts silently.

**Tie batches, not single hits.** Each loop iteration processes a *tie batch* of one or more primitives that share the same hit distance within float-noise. The batch is built before the stack is mutated:

For each iteration:
1. **Closest-hit query** at the current `tnear`. Returns one primitive `P0` at `t_hit`.
2. **Build the tie batch.** Collect every primitive whose hit distance falls in `[t_hit − tie_window, t_hit + tie_window]` (`tie_window = 4 × eps`). Two implementation strategies, decided in B1.5 / 0.2:
   - **(preferred) Pre-built coincident-face groups.** B1.5 detects coincident triangles at scene build and stores a `triangle_id → tied_group_id` map. At runtime, look up `P0`'s tied group; the batch is the group's primitives. Zero extra Embree queries; deterministic by construction.
   - **(fallback) Window query with exclusion.** If pre-grouping is incomplete, do a second `embreex` query with an `IntersectContext` filter callback that accepts hits in `[t_hit − tie_window, t_hit + tie_window]` and excludes `P0`. Append matches to the batch. Requires `embreex` to expose the filter-callback path; verified in 0.2.

   **Sort the batch by `(geometry_id, primitive_id)` ascending** for deterministic processing order.

3. **Segment contribution — once per batch.** ∑ρL accumulates `(t_batch − t_last) × Σ_{s in stack} ρ_s` into the per-ray total (in `float64` on the Python side), where `t_batch` is the median `t` of the batch. This is a single segment regardless of batch size.

4. **Stack updates — zero-length surface events, in batch order.** For each primitive in the sorted batch:
   - Compute `dot(ray_dir, triangle_normal)`. Entry if `< 0`; exit if `> 0`.
   - Push solid_id on entry, pop on exit.
   - Mismatches (entry where stack already contains the solid, exit on a solid not in the stack) logged and counted; do not abort.
   These are zero-length events — they update the stack but contribute no segment ∑ρL.

5. Advance `tnear ← t_batch + eps` and repeat.

**Why this is correct.** Two solids sharing a face produce a tie batch of size 2: one exit (leaving solid A) + one entry (entering solid B), or vice versa. The segment up to the shared face contributes once at the pre-batch stack. The stack then transitions A→B in deterministic order, contributing zero length itself. The next segment uses the post-batch stack. Coincident faces don't double-count and don't zero-count.

**Termination invariants:**
- At ray-miss the stack must be empty. Non-empty stack ⇒ geometry leak ⇒ ray flagged, logged with the offending solid.
- A ray accumulating "inside" depth > bbox_diagonal is overlap-suspicious; surface in the result.
- Hits exceeding the safety cap (4096) raise a run-fatal error with the offending ray ID.

**Done when:** ray-through-concentric-shell test matches analytic ∑ρL to relative error ≤ 1e-5; tangent-grazing edge cases produce consistent ∑ρL values; coincident-face stress test (two solids sharing a face) accumulates exactly once (not zero, not twice); deliberately-overlapped-solids test produces an overlap warning rather than a silent doubled ρ.

### A.5 — Per-detector aggregation and per-species breakdown
For each detector: convert ∑ρL to mm-Al-equivalent, look up dose on the spline (total + per species), aggregate across HEALPix rays. Statistics: mean, per-species mean, **angular spread** (per-pixel variance — a diagnostic of how much shielding varies by direction, *not* a Monte Carlo statistical uncertainty; deterministic computation has no σ), shielding histogram (Min, P05, Median, P95, Max). Output field names use `angular_spread` and `shielding_pctile`, never `sigma` or `±σ`.

**Done when:** uniform-shield test (uniform Al sphere, thickness t) reproduces the imported DDC's interpolated value at t to ±0.1%; per-species sums match the total to floating-point precision.

### A.6 — CLI and run output
Click-based CLI: `raysim run --scene <path> --materials <csv> --detectors <json> --dose-curve <dos> --nside 64 --out run.json`. Emits the `RunResult` JSON with provenance (input hashes, build SHA, seed, Nside, epsilon, library versions). Deterministic ordering of detectors and HEALPix pixels in the output.

**Done when:** two runs with identical inputs produce byte-identical `run.json`; output validates against the schema from A.1. JSON is canonicalized (sorted keys, fixed float format `repr` or `%.17g`); reductions are ordered (HEALPix pixels summed in index order, detectors processed in input order); no timestamps or wall-clock fields in the deterministic output stream — those go in a separate `human_metadata` block excluded from the deterministic hash.

### A.7 — Acceptance test suite and performance baseline
Codify the five Phase-A acceptance tests from `MVP_PLAN.md` §6 as pytest cases. Add `pytest-benchmark` markers for performance.

**Hard gate — float32 precision impact on ∑ρL.** The concentric-shell test must demonstrate relative error ≤ 1e-5 with the chosen accumulation strategy (default: float64 chord-length accumulation in Python, outside Embree). If this is not attainable on the largest benchmark mesh:
- Document the achieved bound (e.g. 1e-4) and the measurement.
- Decide explicitly: relax the documented bound, or implement parametric-distance re-query in float64.
- Either way, the decision is logged in `/docs/decisions/` before Phase A is considered complete.

**Performance:**
- **Dev benchmark** (Phase A acceptance): aluminum-box, Nside=64, single-threaded, ≤ 10 s on a dev laptop.
- **Smoke target** (per Phase 0): batched ray cast on 1 M triangles ≤ ~1 s.
- The **product benchmark** (full real assembly, 100 detectors, Nside=64, ≤ 90 s on 16 cores) belongs to Phase B5 — not gated here.

Stash baseline timings in CI for regression detection.

**Done when:** all five acceptance tests green; the float32 precision gate is met or its relaxation is documented; CI publishes a performance trend.

---

## Phase B1 — Geometry pipeline

Goal: turn a single STEP file into the same in-memory scene Phase A consumes from STL.

### B1.1 — STEP loader with assembly tree
`STEPCAFControl_Reader` from `pythonocc-core`: parse AP203/AP214/AP242, walk the assembly hierarchy, extract per-part names, layers, colors, and the `TopoDS_Shape` for each leaf solid. Build an internal `AssemblyNode` tree mirroring the STEP structure.

**Implementation note (B1 as-shipped):** The initial implementation uses the plain `STEPControl_Reader` (not the XCAF reader) and assigns synthetic `solid_NNNN` IDs via depth-first walk order. Per-part names, colors, and layers from XCAF are not yet extracted. This deferral was pragmatic — the plain reader was sufficient for tessellation and the downstream engine — but creates a two-reader problem for B2.2's STEP material-tag ingestion, which requires the XCAF reader. The XCAF migration is planned for B3.0 (see below), where the UI needs names and colors for the assembly tree panel and material assignment UI.

**Done when:** opening each benchmark STEP produces an `AssemblyNode` tree whose part count and naming match the source CAD's BoM; round-trip metadata (name, color, layer) preserved.

### B1.2 — Tessellation pipeline
`BRepMesh_IncrementalMesh` per leaf solid with user-controlled linear and angular deflection (sensible defaults: linear = 0.1 mm, angular = 0.5 rad). Emit per-solid triangle arrays with stable indexing. Track per-triangle source-shell IDs for the watertightness validator.

**Done when:** every benchmark assembly tessellates without throwing; triangle counts within an order of magnitude of expected for the given deflection settings.

### B1.3 — Healing and orientation normalization
Integrate `BRepMesh_ModelHealer` (or the Phase-0 fallback if the binding wasn't exposed) to close micro-cracks, resolve self-intersecting wires, snap edges. Re-tessellate any healed shapes. Log the diff (parts touched, fixes applied). The exact API to call is fixed in step 0.2; this step depends on that decision.

**Shell orientation normalization.** OCCT tessellation honors the topological face orientation, which can be inward for shells flagged `TopAbs_REVERSED` in the source STEP or for shells whose orientation was inverted during prior processing. A perfectly watertight but inward-oriented shell will silently invert the A.4 entry/exit classification and produce wrong ∑ρL. **The convention RaySim enforces: every triangle's normal points out of solid material into vacuum (or into a cavity / other material).**

**Hollow solids (shell-with-cavity) — explicit expected pattern.** A solid with an internal void has *two or more* closed sub-shells: one outer enclosing shell, and one or more inner cavity shells. Under RaySim's "out of solid material" convention:
- The **outer shell's normals point outward** (away from the solid, into vacuum).
- The **inner cavity shells' normals also point out of the solid material — which means they point inward into the cavity void.** Relative to a standalone closed volume, this looks "reversed," but it is geometrically correct and **must not be flipped**. A subsequent step that "fixes" them by flipping is a bug.

The orientation-validator algorithm therefore classifies sub-shells before deciding what's correct:
1. For each closed shell of a solid, determine if it is the outer shell or a cavity shell — by point-in-polyhedron containment relative to other shells of the same solid (one outer; cavities lie strictly inside it).
2. Cast a probe ray from a point provably outside the *whole* solid (outside the outer shell's bbox) toward the solid's centroid. Count signed crossings using `dot(ray_dir, triangle_normal)`.
3. **Expected crossing patterns:**
   - **Solid with no cavities:** `entry, exit` (one of each, outer shell). Outer shell normals outward.
   - **Solid with cavities:** `entry, exit, entry, exit, …` where each entry/exit pair traverses solid material. Cavity shells, when crossed, contribute one entry-into-solid (cavity boundary, from cavity-void back into material) followed by one exit-from-solid (the other side of the cavity). Both events have the cavity-shell normal pointing into the void.
4. **Failure signal:** the first crossing from an outside point must be `entry` (`dot < 0`). If it is `exit`, the outer shell is reversed → flip every outer-shell triangle. Cavity shells are left alone unless they fail their own consistency check (e.g., a probe ray from inside the cavity should encounter `exit, entry` patterns into solid material).
5. For inverted shells, flip every triangle's vertex order (and therefore its normal).

**Done when:** running the healer twice in a row produces no further changes (idempotent); healed assemblies tessellate cleanly downstream; deliberately-reversed-outer-shell fixture is detected and flipped; deliberately-cavity-bearing fixture (hollow box with internal void) passes without anyone "fixing" the cavity shell; the post-pass ray-cast pattern matches the expected entry/exit sequence for both fixtures.

### B1.4 — Per-solid-shell watertightness validator
Group triangles by their source `TopoDS_Shell`. For each closed shell: every non-degenerate edge must appear in exactly two triangles with opposite orientation. Fail-list for shells that don't pass, with the offending edges identified.

**Done when:** all three benchmark assemblies pass per-solid-shell watertightness after the healer; deliberately broken test geometry (e.g., a cube with one face removed) is correctly flagged.

### B1.5 — Overlap and interference diagnostic
Watertight shells are necessary but not sufficient. Real STEP assemblies frequently contain coincident faces, nested solids, and small interferences that produce wrong ∑ρL even with perfect watertightness. This step adds a separate diagnostic pass and **classifies each detected pair into one of four physical categories** so that the run gate's accept/reject logic is informed, not just a boolean.

**Detection passes:**
- **Coincident-face detection.** Triangle pairs from different solids whose centroids and normals coincide within tolerance.
- **Solid-solid interference.** AABB overlap test followed by an OCCT `BOPAlgo_CheckerSI`-style intersection check on candidate pairs. Computes intersection volume.
- **Nested-solid detection.** A solid wholly inside another (e.g., a connector pin inside a socket cavity).

**Pair classification** (mutually exclusive):
| Status | Physical meaning | Stack accumulator behavior | Default gate action |
|---|---|---|---|
| `contact_only` | Touching faces, zero intersection volume; coincident triangles share a face but neither solid is inside the other | A.4 tie batch transitions A→B cleanly | Accept silently |
| `accepted_nested` | Solid B fully inside solid A (intersection volume = volume of B). Physically real (connector pins in housings, components in cavities) | Stack contains both A and B inside B's region; densities sum correctly because the geometry really is "B's material occupying part of A's notional volume" | Accept; surface in report so the topology is visible to reviewers |
| `interference_warning` | Partial volume overlap below a tunable threshold (default: < 1 mm³ or < 0.1% of smaller solid's volume) | Stack will sum ρ_A + ρ_B in the overlap region — physically incorrect (only one material is actually there), but the bias is small | Accept on explicit user override only; record the override and the bias estimate in the project + report |
| `interference_fail` | Partial volume overlap above the threshold | Same density-doubling bias, but large enough to materially affect dose | Block runs; require CAD fix |

`accepted_nested` is the case the reviewer correctly distinguished from interference: nested topology is physically real and the accumulator handles it correctly. Partial interference (`_warning` / `_fail`) is the bug case where ρ-sum gives wrong physics.

Diagnostic output: a per-pair report (`solid_a, solid_b, status, intersection_volume, bias_estimate_g_per_cm2`). User overrides for `interference_warning` are persisted in the project with a free-text justification.

**Done when:** the diagnostic catches a deliberate overlapping-solids fixture and classifies it `interference_fail`; nested-pin-in-socket fixture classifies as `accepted_nested`; the benchmark CubeSat's contact-only pairs classify as `contact_only` without false positives.

### B1.6 — Stage A adapter and STL export
Adapter that converts the post-healed assembly + materials assignment into the same in-memory scene Phase A's Embree builder consumes. STL export per material group for round-trip regression: load STEP → tessellate → heal → export STL → re-run Phase A on the STL → compare results to a STEP-direct path.

**Done when:** STL volume matches STEP solid volume within 0.5% per assembly; per-detector TID computed via the STL path matches the STEP path to within numerical tolerance.

---

## Phase B2 — Materials and project file

Goal: every solid resolves to a material before a run, with minimum manual effort.

### B2.1 — Material library
Pydantic `Material` model: `group_id`, `density_g_cm3`, `z_eff`, `display_name`, optional `composition`, `provenance`. Ship a seeded library: Al 6061, Cu, Si, SiO₂, Kapton, FR4, Ti-6Al-4V, W, GaAs, Au, Sn-Pb solder, plus composite defaults (battery, populated PCB, harness). Library is YAML, user-extendable.

**Done when:** seeded library loads, every entry has a sourced density (NIST or vendor datasheet), library validation rejects malformed entries.

### B2.2 — STEP AP214_IS material-tag ingestion
Wire `XCAFDoc_MaterialTool` to extract STEP-carried material names per part. Map STEP material strings to library entries via a fuzzy matcher with configurable thresholds. Tag each part with its STEP-derived material as a *suggestion* (overridable).

**Implementation note (B2 as-shipped):** Because B1.1 uses the plain `STEPControl_Reader` while tag extraction requires the XCAF reader, `step_tags.extract_step_tags()` performs a second independent STEP read. Shape object identity does not survive across the two readers. Correlation uses DFS walk-order index with a **two-gate verification**: (a) leaf count must match, (b) per-leaf bounding boxes must agree within 1e-3 mm. If either gate fails, tag extraction returns an empty list and logs a warning — the naming-rule engine and manual assignment remain available as fallbacks. This workaround is eliminated by B3.0's XCAF migration, after which `LeafSolid` carries name/color/material_hint directly from the single XCAF load pass.

**Done when:** a benchmark STEP that carries material tags (custom test article) auto-resolves ≥ 80% of parts on first import; mismatches are surfaced for review.

### B2.3 — Naming-rules auto-assignment
YAML ruleset (regex pattern → `group_id`) shipped with the app, covering common conventions (`AL_*`, `*_AL`, `*_PCB`, `FR4_*`, `CU_*`, `KAPTON_*`, `BATT*`, `TI_*`, `W_*`, `AU_*`). User-editable rules persisted at the project level so team conventions accumulate. Run rules over part-name paths after STEP-tag ingestion fills in the gaps.

**Done when:** the rule engine reduces unmatched-part count by ≥ 60% on the benchmark CubeSat (a standard naming convention); rule edits reload without restart.

### B2.4 — Auto-assignment review
Combined view of the assignment status post-tags-and-rules: counters for *auto-matched / ambiguous / unmatched*; per-part list with current state and source (`STEP-tag`, `naming-rule`, `manual`); accept-all / review / skip actions. Ambiguous parts (multiple rules fire) listed with the candidate materials.

**Done when:** typical workflow on the benchmark is "open STEP → click *accept all suggestions* → manually resolve ~20–30 residual parts" and the run gate is unblocked.

### B2.5 — Project file format
`.raysim` JSON via Pydantic. Contains: STEP path or hash, tessellation params, material assignments, detectors, scenario `.dos` reference, naming-rule overrides, schema version. SHA-256 hash of the canonical-ordered geometry computed and stored. Canonical JSON serialization (sorted keys, fixed float formatting) is bit-stable across save → reopen → save cycles.

**Reproducibility scope (explicit):**
- **`.raysim` canonical JSON is bit-identical** after save → reopen → save on the same build.
- **In-memory state may differ at the object-identity level** — OCCT object IDs, dict iteration order, Embree handle pointers — but is functionally equivalent: it serializes to the same canonical JSON and produces the same `run.json` if a run is dispatched.

**Done when:** save → reopen → save produces a byte-identical `.raysim` JSON; project hash changes only when geometry-or-assignment changes; running the engine on the original vs the reopened project produces a bit-identical `run.json`.

### B2.6 — Run gating and density anomaly warnings
Block-run-until-complete state: a run is permitted only when every solid resolves to a library material. Density anomaly warnings (`< 0.5 g/cm³` or `> 25 g/cm³`) shown as soft yellow flags but do not block. Display these states inline in the assembly tree.

**Done when:** run button disabled with a clear message when assignments are incomplete; warnings displayed without blocking on outlier densities.

---

## Phase B3 — UI and authoring

Goal: a clickable desktop app where the user opens a STEP, places detectors, picks a scenario, runs, and sees results.

### B3.0 — XCAF migration: unify STEP loader on `STEPCAFControl_Reader`
Migrate `raysim.geom.step_loader` from the plain `STEPControl_Reader` to `STEPCAFControl_Reader`. This is a prerequisite for B3.1–B3.3 (the UI needs part names, colors, and layers for the assembly tree panel) and eliminates the two-reader correlation workaround in `raysim.mat.step_tags`.

**Changes:**
- `step_loader.load_step()` uses `STEPCAFControl_Reader` as its primary reader. The XCAF label tree provides both the `TopoDS_Shape` per leaf and the per-label metadata (name, color, material hint).
- `LeafSolid` gains optional fields: `name: str | None`, `color_rgb: tuple[float,float,float] | None`, `material_hint: str | None`.
- `AssemblyNode` gains `name: str | None` from the XCAF label.
- `step_tags.extract_step_tags()` is simplified: instead of a second STEP read + two-gate verification, it reads `name`/`color_rgb`/`material_hint` directly from the already-loaded `LeafSolid` records. The verification gate becomes dead code and is removed.
- All existing B1 tests must still pass (same `LeafSolid` count, same bbox, same tessellation). New tests verify that name/color/material_hint are populated from XCAF-carrying STEP fixtures.

**Done when:** `load_step()` on the benchmark STEPs produces the same leaf count and bboxes as before; `LeafSolid.name` is populated from XCAF labels where available; `step_tags.extract_step_tags()` no longer performs an independent STEP read; B1 + B2 test suites green.

### B3.1 — Main window shell
PySide6 `QMainWindow` with a dockable panel layout: left = assembly tree + material panel + detector panel, center = 3D viewer, right = scenario panel + result panel + run panel. Menu bar (File / Edit / View / Run / Help). Settings persisted via `QSettings`.

**Done when:** the empty shell launches on Linux and Windows, panels dock and undock, state persists across sessions.

### B3.2 — OCCT AIS viewer integration with picking
Embed `pythonocc-core`'s `qtDisplay.qtViewer3d` widget. Hook face / edge / vertex picking. Implement camera controls (orbit, pan, zoom-to-fit, axis-aligned views). Selection state synced with the assembly tree on the left.

**Done when:** opening a benchmark STEP renders the assembly; clicking a face highlights it and selects the corresponding tree node, and vice versa.

### B3.3 — Material assignment UI
Material panel showing the seeded library + project-local additions. Assembly tree dropdown per node (with "inherit from parent" as a state). Bulk operations: "propagate to subtree", "override leaf only". Missing-materials counter visible in the run panel.

**Done when:** a user can fully assign materials to the benchmark CubeSat using only mouse interactions (review of auto-assignments + dropdown picks for the residual).

### B3.4 — Detector placement
Click-pick on a face places a point detector at the face centroid by default. Snap modes (face centroid, vertex, edge midpoint, free) selectable from a small toolbar near the cursor or via modifier keys. Normal-offset slider to push the detector along the face normal. "Switch to box template" with editable size in mm. Detector list panel with rename / delete / inspect.

**Done when:** placing 5 detectors on a benchmark PCB takes ≤ 2 minutes for a first-time user; detectors round-trip into the project file via B2.5.

### B3.5 — Scenario panel
Browse-and-load `.dos` file. Preview the dose-depth curve (log-log) and per-species columns inline (matplotlib via `matplotlib_qt`). Show the scenario provenance (orbit, percentile, models) extracted from the `.dos` header.

**Done when:** loading the user's `dose700km.dos` shows the curve and metadata correctly; switching scenarios in an open project updates the preview without restart.

### B3.6 — Run dispatcher
"Run" button kicks off the engine in a `QThread` worker that owns the Embree pool. Progress bar driven by per-detector completion. Cancel mid-run cleanly. After completion, populate the result panel with per-detector TID, per-species breakdown, and shielding histogram values.

**Done when:** a full run on the benchmark assembly completes inside the perf budget; cancel during a run leaves the app in a usable state.

### B3.7 — Result overlays
Three overlays toggleable per detector: (1) 3D ray-view colored by accumulated mm-Al-equivalent thickness, (2) 6-face equivalent-thickness projection rendered as a 2D unfolded box, (3) angular shielding histogram in Mollweide projection (`healpy.mollview` where `healpy` is the build's HEALPix path, or a matplotlib-only Mollweide projection over the HEALPix pixel array where the vendored `pix2vec` fallback is in use). Overlays pickable: clicking a ray or pixel shows that direction's hit list.

**Done when:** overlays render at interactive frame rates on the benchmark; toggling between detectors updates within 1 s.

---

## Phase B4 — Reports and packaging

Goal: ship a self-contained installer that produces reproducible reports.

### B4.1 — Report data model and PDF generator
Per-detector summary structure (mirroring Nucleon-style: Min / P05 / Median / P95 / Max + Expected Dose + per-species breakdown + provenance block). ReportLab PDF generator: cover page (mission, scenario, geometry hash, run timestamp), table of contents, per-detector pages, appendix with full provenance (build SHA, library versions, Nside, epsilon, seed, input hashes). Finite-box approximation disclaimer rendered on the relevant pages.

**Done when:** generated PDF on the benchmark scenario is review-ready (no layout artifacts, all metadata fields populated, correct units everywhere).

### B4.2 — CSV exports
Two CSVs per run: per-detector summary (one row per detector with the full statistical breakdown) and per-ray-bin export (HEALPix pixel index → direction → ∑ρL → mm Al-equivalent → dose). Both with header rows naming columns and units.

**Done when:** CSVs open cleanly in Excel and pandas; column units match `MVP_PLAN.md` §3.

### B4.3 — JSON scenario bundle and reopen-reproduces
The `.raysim` project + the produced `run.json` packaged as a single bundle (zip). Reopening on the same build SHA + pinned library versions reproduces an identical `run.json`. Reports (PDF, CSV exports with timestamps) are not bit-identical by design and are excluded from the reproducibility check.

**Two-tier reproducibility:**
- **Engine output (`run.json`):** bit-identical on same build + pinned deps. Hashed and verified.
- **Human artifacts (PDF report, dashboard JSON with timestamps):** numerically identical but layout/timestamp may differ. Not hashed.

**Done when:** bundle handed to a colleague off-machine reproduces bit-identical `run.json` on the same build SHA; PDF reports render the same numbers but may differ in timestamp/layout.

### B4.4 — Installer build
`briefcase` (default) or PyInstaller (fallback): single-installer per OS bundling Python runtime, pinned dependencies, OCCT shared libraries, embreex native libs, and **either `healpy` data files (where `healpy` is installed) or RaySim's vendored NumPy `pix2vec` module (where the fallback is in use)** per the Phase 0 §0.2 decision. Windows MSI, Linux AppImage, macOS optional. App icon, version metadata, code signing if certs available.

**Done when:** installer builds in CI for both Linux and Windows; resulting artifact is < 500 MB; the bundled HEALPix path (healpy or fallback) matches the build's `pyproject.toml` resolution and is verified by a smoke import in the post-install hook.

### B4.5 — Clean-machine install verification
On a fresh VM (no Python, no OCCT, no Visual C++ runtimes pre-installed), the installer runs and the app launches end-to-end on the benchmark workflow. Document any prerequisites the installer cannot bundle (e.g., GPU drivers).

**Done when:** clean-VM smoke test passes on Windows 10/11 and Ubuntu 22.04/24.04; documented in `/docs/install`.

---

## Phase B5 — Validation and hardening

Goal: ship with evidence the numbers can be trusted.

### B5.1 — Canonical analytic validation
Re-run the Phase A acceptance suite against the full Stage B pipeline: aluminum-box, solid-sphere, concentric-shell — but starting from STEP, not STL. Confirm STL and STEP paths agree. Add a `.raysim` project for each canonical case checked into `/benchmarks`.

**Done when:** STEP-direct results match STL-direct results to relative error ≤ 1e-4; analytic targets met as in A.7.

### B5.2 — Cross-tool reference comparison
Pick at least one benchmark scenario where an external reference exists (SSAT-published shielding distribution, a SHIELDOSE-2 reference output, or a Nucleon report you can rerun against). Document the comparison: agreement bounds, regimes of disagreement, uncertainty envelope. Treat ≤ 20% agreement for electron-dominated LEO as acceptance.

**Done when:** comparison documented in `/docs/validation/cross-tool.md`; bias envelope explicitly stated.

### B5.3 — Nightly regression infrastructure
Nightly CI job runs the full benchmark suite (canonical cases + three real assemblies + the user's `dose700km.dos` scenario), checks per-detector TID against frozen tolerance bands, fails the build on regression. Trend dashboard or simple text report of last-N-nights for human review.

**Done when:** nightly job has been green for a sustained period; introducing a deliberate ∑ρL bug in a feature branch turns the job red.

### B5.4 — Performance benchmarking and tuning
Measure per-detector wall-clock on the largest benchmark (target: full assembly, 100 detectors, Nside=64, < 90 s on 16 cores). Identify the top-three hotspots via `cProfile` / `py-spy`. If a hotspot exceeds the 30%-overhead threshold (per `MVP_PLAN.md` §8), prototype a `nanobind` extension and measure delta.

**Done when:** performance budget met; if exceeded, decision documented (accept slower budget, optimize, or drop to native).

### B5.5 — UX hardening
Stress paths: 50 M+ triangle assemblies, partial watertightness with override, deliberately broken material assignments, malformed `.dos` files, cancelled runs mid-flight, project files from older `schema_version`s. Each failure mode should produce a clear user message and a recoverable state.

**Done when:** every stress case in the test plan produces a user-visible error or warning rather than a crash, exception trace, or silent bad result.

### B5.6 — Validation dossier
Compile `/docs/validation/` into a single dossier: methodology, scope of applicability, regimes of known approximation error (sector-analysis limits per `MVP_PLAN.md` §8), comparison against external references (B5.2), reproducibility guarantees (B4.3), known limitations. This becomes the document a customer or reviewer reads before trusting RaySim's output.

**Done when:** dossier is complete, internally reviewed, and referenced from the report PDF's provenance block so every output points back to its validation basis.
