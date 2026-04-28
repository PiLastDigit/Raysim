# Testing Guidelines

## Test Framework

`pytest` 8.0+ with `pytest-benchmark` 4.0+. Both pinned in
`pyproject.toml`'s `[dev]` extra.

## Running Tests

```bash
# Default loop (everything except slow/benchmark when those markers are excluded explicitly)
uv run pytest

# Verbose with stdout (shows the dev-benchmark timing line)
uv run pytest -v -s

# A single file
uv run pytest tests/unit/test_tracer.py

# A single test
uv run pytest tests/integration/test_phase_a_acceptance.py::test_a7_1_concentric_shell_float32_hard_gate

# Phase A acceptance only
uv run pytest tests/integration/test_phase_a_acceptance.py

# Skip slow / benchmark
uv run pytest -m "not benchmark and not slow"
```

Coverage is not wired by default. Add `pytest-cov` to dev deps if needed.

## Test Organization

```
tests/
├── unit/                                   # one file per source module
│   ├── test_proj_schema.py                 # raysim.proj.schema, canonical_json
│   ├── test_dose_spline.py                 # raysim.dose.spline
│   ├── test_aggregator.py                  # raysim.dose.aggregator
│   ├── test_omere_dos.py                   # raysim.env.importers.omere_dos
│   ├── test_healpix_smoke.py               # raysim.ray.healpix
│   ├── test_scene_loader.py                # raysim.ray.scene
│   ├── test_tracer.py                      # raysim.ray.tracer
│   ├── test_cli_loaders.py                 # raysim.cli.run loader helpers
│   ├── test_cli_smoke.py                   # raysim.cli.main
│   ├── test_embreex_smoke.py               # phase-0 dependency contract
│   └── test_occt_smoke.py                  # phase-0 + xfail tracker
├── integration/
│   └── test_phase_a_acceptance.py          # the 5 MVP_PLAN §6 gates
└── fixtures/
    └── dose700km.dos                       # canonical OMERE fixture
```

Naming convention: `tests/unit/test_<source_module>.py`. One unit test
file per source module; the pairing is enforced by code review.

## Writing Tests

Conventions observed across the codebase:

- Use **`pytest.approx`** for float comparisons. Default to relative
  tolerance (`rel=1e-5` or tighter for analytic gates); use `abs=` only
  when comparing to zero.
- Optional backends are imported via **`pytest.importorskip("embreex")`**
  at the top of the file so CI legs without the extra still pass.
- Parametrize when a function has discrete edge cases. Use module-scoped
  fixtures (`@pytest.fixture(scope="module")`) for expensive setups (the
  spline build on the real OMERE fixture is one).
- For determinism tests, run the **CLI as a subprocess** — not
  `CliRunner` — so what's tested is what users hit:
  ```python
  raysim_bin = shutil.which("raysim")
  cmd_prefix = [raysim_bin] if raysim_bin else [sys.executable, "-m", "raysim.cli.main"]
  ```
- Tests for the float-precision hard gate (A.7-1) and HEALPix identity
  (A.7-3) **cannot have their tolerance relaxed casually** — see the
  ARCHI §15 documented escape hatch.

## Markers

Registered in `pyproject.toml`:

| Marker | Purpose |
|---|---|
| `slow` | Long-running tests excluded from the default loop. |
| `benchmark` | `pytest-benchmark` perf regressions; the dev benchmark uses this. |
| `needs_embree` | Requires `embreex`. |
| `needs_healpy` | Requires `healpy` (else use the vendored fallback). |
| `needs_occt` | Requires `pythonocc-core` (conda-only). |

## Coverage Requirements

No formal coverage threshold is set. The implicit floor is "every
public function in `src/raysim/` is exercised by at least one test."
The five Phase A acceptance gates are non-negotiable; everything else
is at the discretion of the change author + reviewer.

## What to Test

When adding a feature, the test plan should cover:

- **Happy path** on a realistic input (the OMERE fixture, the canonical
  analytic STLs).
- **Edge cases** — empty stack, missing canonical species, t = 0 LOS
  rays, pure-zero columns, max-hit cap, deeply nested solids.
- **Determinism** — when adding a new output field, add a determinism
  test that runs the path twice and diffs bytes.
- **Reconciliation** — when adding a new species path, assert
  `sum(per-species) ≈ dose_total` to OMERE's print precision (~5e-3).
- **Backend optionality** — guard imports with `pytest.importorskip`
  so CI legs without the extra still pass.

See `docs/ARCHI.md §19 Testing Strategy` for the project-level testing
philosophy.
