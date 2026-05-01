# CLAUDE.md — RaySim

## Project overview

RaySim is a 3D Total Ionizing Dose (TID) sector-shielding simulator for spacecraft. It casts HEALPix rays through CAD geometry, accumulates mass-thickness, and produces per-detector dose estimates from an imported dose-depth curve.

**Current version**: 0.3.0 (Phase A + B1 + B2 + B3 complete).

## Repository layout

```
src/raysim/
    cli/        click CLI (raysim run, raysim gui)
    env/        dose-depth curve schema + OMERE .dos importer
    dose/       log-cubic spline + per-detector aggregation
    ray/        HEALPix sampling, Embree BVH, iterative tracer
    proj/       Pydantic schemas, canonical JSON, provenance hashing, .raysim project file
    geom/       STEP loader (XCAF), tessellation, healing, watertightness, overlap
    mat/        material library, naming rules, STEP tags, review, gating
    ui/         PySide6 desktop app, OCCT viewer, panels, overlays, workers
    report/     (placeholder — Phase B4)
tests/
    unit/       per-module tests
    integration/ Phase A acceptance gates
    fixtures/   dose700km.dos, step_leaf_golden.yaml (generated on first OCCT run)
benchmarks/     analytic STL geometries + STEP fixtures
scripts/        install scripts, fixture generators
docs/           ARCHI.md, plans, changelogs, code reviews, tutorials
```

## Development workflow

**Primary dev environment**: WSL (Ubuntu) with `uv`. Code lives on the Windows filesystem at `/mnt/c/Users/Samir/Documents/raysim`.

```bash
# Sync dependencies
uv sync --extra dev --extra ray

# Run tests
uv run pytest

# Lint + typecheck
uv run ruff check .
uv run mypy

# CLI smoke test
uv run raysim --version
```

**GUI testing**: The PySide6 desktop app requires pythonocc-core (conda-only). A separate conda environment on Windows native is used for GUI testing. Install once with the Windows install script, then launch from PowerShell whenever needed.

```powershell
# One-time setup (from PowerShell, not WSL)
powershell -ExecutionPolicy Bypass -File scripts\install-windows.ps1

# Launch GUI (picks up code changes immediately — editable install)
.\raysim.cmd gui
```

## Important reminders

### Re-run install script when dependencies change

The Windows conda environment (`raysim-ui`) is installed in editable mode, so Python code changes are picked up immediately. However, **if you add, remove, or change a dependency in `pyproject.toml`**, the conda env will not see it automatically. Remind the user to re-run the install script:

```
The pyproject.toml dependencies changed. Re-run the install script on Windows:
    powershell -ExecutionPolicy Bypass -File scripts\install-windows.ps1
```

Same applies for the Linux install: `bash scripts/install-linux.sh`.

### pythonocc-core is conda-only

`pythonocc-core` is not on PyPI. It can only be installed via conda/micromamba from conda-forge. The `uv` dev environment does NOT have it — OCCT-dependent tests are skipped in the `uv` environment. This is by design (documented in `docs/decisions/phase-0.md`).

Modules that need OCCT guard imports at call time:
- `raysim.geom.*` — all modules guard `OCC.Core` imports
- `raysim.ui.viewer` — guards `OCC.Display` imports
- `raysim.ui.state` — imports geom modules lazily in methods

Tests use `pytest.importorskip("OCC.Core")` or `pytest.importorskip("PySide6")`.

### PySide6 UI modules use `type: ignore[misc]` for Qt subclasses

PySide6 does not ship complete type stubs. All `class Foo(QWidget)` / `class Foo(QDockWidget)` declarations carry `# type: ignore[misc]` to suppress mypy's "cannot subclass Any" error. This is standard practice with PySide6 + mypy strict mode.

## Key architectural rules

Read `docs/ARCHI.md` before touching code that spans modules. The short version:

1. **Determinism is a contract.** `run.json` must be byte-identical on identical inputs. Canonical JSON, ordered reductions, provenance hashing. No timestamps in the deterministic stream.
2. **Stack accumulator, not scalar sum.** The ray tracer uses a material-state stack for nested/touching solids. Don't simplify it to a scalar.
3. **Density is the only physics input.** `z_eff`, `composition`, etc. are metadata only — preserved for traceability, not consumed by the dose math.
4. **Material truth is governed.** STEP tags are suggestions; the sidecar library + assignment table is the source of record.
5. **Pre-built tied groups are mandatory.** embreex 4.4 has no filter callback, so coincident-face handling uses pre-built groups at scene build time.
6. **Float64 accumulation outside Embree.** Embree returns float32 hit distances; the chord-length accumulator runs in float64 on the Python side.

## Coding conventions

- `ruff` for linting, `mypy --strict` for type checking. Both must be clean before committing.
- Pydantic models use `frozen=True` + `extra="forbid"`.
- `structlog` is the only logger: `_LOG = structlog.get_logger(__name__)`.
- No comments unless the WHY is non-obvious. No docstring essays.
- Tests use `pytest.approx` for floats (relative tolerance by default, `abs=` only near zero).
- OCCT-dependent tests: `pytest.importorskip("OCC.Core")` + `@pytest.mark.needs_occt`.
- PySide6-dependent tests: `pytest.importorskip("PySide6")`.

## Test commands

```bash
uv run pytest                    # all tests (OCCT/PySide6 tests auto-skip)
uv run pytest -q                 # quiet mode
uv run pytest -k test_spline     # run specific tests
uv run pytest -m needs_occt      # only OCCT tests (skip if not installed)
uv run ruff check .              # lint
uv run mypy                      # typecheck
```

## Version management

Version is stored in two places (keep in sync):
- `pyproject.toml` → `version = "x.y.z"`
- `src/raysim/__init__.py` → `__version__ = "x.y.z"`

## Documentation update rules

After code changes, check if `docs/ARCHI.md` needs updating per `docs/ARCHI-rules.md`. ARCHI.md must stay under ~20,000 tokens (check with `bash .claude/skills/TRIP-compact/count-tokens.sh docs/ARCHI.md`).

## Commit conventions

- One-line imperative commit messages focused on the "why".
- Tag releases: `git tag vx.y.z`.
- Don't amend published commits. Create new commits for fixes.
- Stage specific files, not `git add -A`.
