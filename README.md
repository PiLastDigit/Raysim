# RaySim

3D **Total Ionizing Dose (TID)** sector-shielding simulator for spacecraft.

RaySim casts HEALPix equal-area rays from user-placed detectors through CAD geometry, accumulates mass-thickness along each ray, converts to mm-Al-equivalent shielding, and looks up dose from an imported dose-depth curve. The result is a per-detector TID estimate with full angular shielding maps and per-species breakdown.

```
STEP file  ──► tessellate + heal ──► Embree BVH ──► HEALPix rays ──► dose
materials  ─┘                                                         │
detectors  ──────────────────────────────────────► aggregate ──► run.json
dose curve (.dos) ──► log-cubic spline ──────────┘
```

## Features

- **Deterministic sector analysis** -- no Monte Carlo, no in-process orbit propagation. Bit-identical `run.json` on identical inputs.
- **STEP ingest** -- reads AP203/AP214/AP242 via pythonocc-core with XCAF metadata (part names, colors, material hints).
- **Material governance** -- seeded 14-material library, regex naming-rule auto-assignment, STEP tag ingestion, manual overrides. Every solid must resolve before a run.
- **Desktop application** -- PySide6 GUI with OCCT 3D viewer, assembly tree, material/detector/scenario panels, run dispatch with progress, and result overlays (3D ray-view, Mollweide projection, 6-face box projection).
- **Headless CLI** -- `raysim run` for scripted/CI use with canonical JSON output and full provenance hashing.
- **Per-species dose breakdown** -- trapped electrons, trapped protons, solar protons, gamma, plus dialect-specific extras from the imported `.dos` file.

## Project status

**v0.3.0** -- Phases A through B3 complete.

| Phase | Status | What it delivers |
|-------|--------|-----------------|
| Phase A | Complete | Headless ray engine, DDC spline, HEALPix sampling, CLI |
| Phase B1 | Complete | STEP loader, tessellation, healing, watertightness, overlap diagnostic |
| Phase B2 | Complete | Material library, naming rules, STEP tags, project file (.raysim) |
| Phase B3 | Complete | PySide6 desktop app, OCCT viewer, panels, overlays, run dispatch |
| Phase B4 | Planned | PDF/CSV reports, installer packaging |
| Phase B5 | Planned | Cross-tool validation, nightly regression, performance hardening |

## Quickstart

### Engine + CLI (headless)

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```bash
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone and sync
git clone <repo-url> raysim && cd raysim
uv sync --extra dev --extra ray

# Verify
uv run raysim --version
uv run pytest
```

Run a scenario:

```bash
uv run raysim run \
    --scene benchmarks/geometries/aluminum_box/ \
    --materials benchmarks/geometries/aluminum_box/materials.csv \
    --detectors benchmarks/geometries/aluminum_box/detectors.json \
    --dose-curve tests/fixtures/dose700km.dos \
    --nside 64 \
    --out run.json
```

### Desktop application (GUI)

The GUI requires `pythonocc-core` (conda-only) and `PySide6`. Install scripts handle everything automatically -- micromamba download, environment creation, and launcher setup.

**Windows** (PowerShell):

```powershell
powershell -ExecutionPolicy Bypass -File scripts\install-windows.ps1
```

This creates a desktop shortcut and `raysim.cmd` / `raysim-gui.vbs` launchers. Double-click the desktop icon to start the GUI.

**Linux / macOS**:

```bash
bash scripts/install-linux.sh
```

This creates a `raysim.sh` launcher:

```bash
./raysim.sh gui          # launch the GUI
./raysim.sh run ...      # headless CLI
```

**Manual setup** (if you prefer to control the steps):

```bash
# Download micromamba, create env, install
curl -Ls https://micro.mamba.pm/api/micromamba/linux-64/latest | tar -xvj bin/micromamba
export MAMBA_ROOT_PREFIX=.micromamba
./bin/micromamba create -n raysim-ui python=3.12 \
    pythonocc-core=7.9.0 pyside6 matplotlib pyqtgraph -c conda-forge -y
./bin/micromamba run -n raysim-ui pip install -e ".[ray,ui]"
./bin/micromamba run -n raysim-ui raysim gui
```

### Lint and type check

```bash
uv run ruff check .
uv run mypy
```

## Architecture at a glance

```
src/raysim/
    cli/        -- click CLI (raysim run, raysim gui)
    env/        -- dose-depth curve schema + importers (OMERE .dos)
    dose/       -- log-cubic spline + per-detector aggregation
    ray/        -- HEALPix sampling, Embree BVH scene, iterative tracer
    proj/       -- Pydantic schemas, canonical JSON, provenance hashing
    geom/       -- STEP loader (XCAF), tessellation, healing, overlap
    mat/        -- material library, naming rules, STEP tags, review, gating
    ui/         -- PySide6 app, OCCT viewer, panels, overlays, workers
    report/     -- (Phase B4) PDF/CSV report generation
```

The engine (env + dose + ray + proj) is physics-only and has no GUI or CAD dependencies. The geometry pipeline (geom) requires pythonocc-core. The UI (ui) requires PySide6 + pythonocc-core.

See [`docs/ARCHI.md`](docs/ARCHI.md) for the full architecture documentation.

## Technology stack

| Concern | Choice |
|---------|--------|
| Language | Python 3.11+ |
| Package manager | uv |
| Ray engine | embreex (Embree BVH) |
| HEALPix | healpy (Linux/macOS) or vendored NumPy fallback (Windows) |
| CAD kernel | pythonocc-core 7.9.0 (conda-forge) |
| UI framework | PySide6 |
| Numeric core | numpy, scipy |
| Schema | pydantic |
| Plotting | matplotlib, pyqtgraph |

## Documentation

| Document | Purpose |
|----------|---------|
| [`MVP_PLAN.md`](MVP_PLAN.md) | Scope, decisions, deferred items |
| [`MVP_STEPS.md`](MVP_STEPS.md) | Phase-by-phase delivery steps |
| [`docs/ARCHI.md`](docs/ARCHI.md) | Architecture (the daily-driver reference) |
| [`docs/ARCHI-rules.md`](docs/ARCHI-rules.md) | When and how to update ARCHI.md |
| [`docs/decisions/phase-0.md`](docs/decisions/phase-0.md) | Install paths and spike outcomes |
| [`docs/2-changelog/`](docs/2-changelog/) | Per-version changelogs |
| [`docs/5-tuto/`](docs/5-tuto/) | Tutorials (XCAF, spline math, etc.) |

## License

Proprietary. See `pyproject.toml` for details.
