# RaySim

3D Total Ionizing Dose (TID) sector-shielding simulator for spacecraft. Detector-centric ray engine that casts HEALPix rays through CAD geometry, convolves accumulated ∑ρL with an imported SHIELDOSE-2-style dose-depth curve, and produces engineering-reviewable TID reports.

See [`MVP_PLAN.md`](MVP_PLAN.md) for scope and decisions, [`MVP_STEPS.md`](MVP_STEPS.md) for the delivery breakdown.

## Project status

**v0.2.0** — Phase A complete (headless `raysim run` CLI). Phase B1 geometry pipeline landed (STEP loader, tessellation, healing, watertightness, overlap diagnostic, Stage A adapter). Phase B2 material governance landed: seeded 14-entry material library, naming-rule auto-assignment engine, STEP tag ingestion (OCCT-optional), auto-assignment review API, run gating with density anomaly warnings, `.raysim` project file format.

## Quickstart (development)

```bash
# Install uv (https://docs.astral.sh/uv/)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Sync dev environment
uv sync --extra dev --extra ray --extra ui --extra report

# Run tests
uv run pytest

# Lint
uv run ruff check .
uv run mypy
```

`pythonocc-core` is required for STEP ingest (Stage B). It is not on PyPI — install via conda:

```bash
conda install -c conda-forge pythonocc-core=7.8
```

See [`docs/decisions/phase-0.md`](docs/decisions/phase-0.md) for install-path decisions per dependency.
