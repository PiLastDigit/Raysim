"""OMERE ``.dos`` importer (MVP reference dialect).

Parses a SHIELDOSE-derived solid-sphere dose-depth curve emitted by OMERE 5.9
(verified against ``dose700km.dos``). Returns the canonical
:class:`raysim.env.schema.DoseDepthCurve`.

Format notes (from observed files; OMERE has no formal spec):
  * Header lines start with ``#`` and contain free-form mission/orbit/model
    metadata. Captured verbatim into ``mission_metadata`` (best-effort key/value
    extraction) and a literal ``raw_header`` blob for full traceability.
  * The data block is space-separated. Column header rows (also ``#``-prefixed)
    name 9 columns: Thickness, Trapped electrons, Trapped protons, Solar proton,
    Other electrons, Other protons, Gamma photons, Other_Gamma photons, Total.
  * Units: ``mm_Al`` for thickness, ``rad`` for every dose column.

RaySim convention is ``krad`` for dose; this importer converts on read
(``rad / 1000 → krad``). Thickness stays in mm_Al (RaySim's UI/I/O unit per
MVP_PLAN §3).

Edge cases handled (MVP_STEPS §A.2):
  * Strictly-increasing thickness validated (DDCs always start at a small but
    nonzero ``t``; we don't synthesize ``t=0``).
  * Zero entries preserved verbatim — the dose module decides whether to floor
    them when fitting a log spline.
  * ``Other electrons`` / ``Other protons`` / ``Other_Gamma photons`` columns
    are stashed in ``extra_species`` (non-canonical), preserving traceability.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from pathlib import Path
from re import Match

from raysim.env.schema import DoseDepthCurve

# OMERE column → (canonical_species_name | None, target_extra_key)
# A None canonical name means "park in extra_species under target_extra_key".
_COLUMN_MAP: dict[str, tuple[str | None, str | None]] = {
    "trapped electrons": ("trapped_electron", None),
    "trapped protons": ("trapped_proton", None),
    "solar proton": ("solar_proton", None),
    "gamma photons": ("gamma", None),
    "other electrons": (None, "other_electrons"),
    "other protons": (None, "other_protons"),
    "other_gamma photons": (None, "other_gamma_photons"),
}

_RAD_TO_KRAD = 1.0 / 1000.0


def import_omere_dos(path: str | Path) -> DoseDepthCurve:
    """Parse an OMERE 5.x ``.dos`` file into a :class:`DoseDepthCurve`."""
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    return _parse(text, source_path=str(path))


def _parse(text: str, source_path: str = "") -> DoseDepthCurve:
    lines = text.splitlines()
    raw_header: list[str] = []
    data_rows: list[list[float]] = []
    # Capture the last few comment lines before the data block: that's the
    # multi-line column header (primary / qualifier / units in OMERE).
    pre_data_buffer: list[str] = []

    for line in lines:
        s = line.strip()
        if not s:
            pre_data_buffer.clear()
            continue
        if s.startswith("#"):
            raw_header.append(line)
            pre_data_buffer.append(s)
            continue
        # Data row: pure floats, whitespace-separated.
        parts = s.split()
        try:
            row = [float(p) for p in parts]
        except ValueError:
            # Any stray free-form text in the data block is fatal.
            raise ValueError(
                f"OMERE .dos: cannot parse data row {line!r}"
            ) from None
        data_rows.append(row)
        # Once data starts, freeze the column header buffer.
    column_header_lines = pre_data_buffer

    if not data_rows:
        raise ValueError("OMERE .dos: no data rows found")

    columns = _resolve_columns(column_header_lines, ncols=len(data_rows[0]))
    if any(len(r) != len(columns) for r in data_rows):
        raise ValueError(
            f"OMERE .dos: ragged data block — expected {len(columns)} columns, "
            f"saw rows of width {sorted({len(r) for r in data_rows})}"
        )

    thickness = tuple(r[0] for r in data_rows)
    dose_per_species: dict[str, list[float]] = {}
    extra_species: dict[str, list[float]] = {}
    dose_total: tuple[float, ...] | None = None

    for col_idx, col_name in enumerate(columns):
        if col_idx == 0:
            continue  # thickness
        col_values = [row[col_idx] * _RAD_TO_KRAD for row in data_rows]
        if col_name == "total":
            dose_total = tuple(col_values)
            continue
        canonical, extra_key = _COLUMN_MAP.get(col_name, (None, None))
        if canonical is not None:
            dose_per_species[canonical] = col_values
        elif extra_key is not None:
            extra_species[extra_key] = col_values
        else:
            extra_species[col_name.replace(" ", "_")] = col_values

    if dose_total is None:
        raise ValueError("OMERE .dos: no 'Total' column found")

    metadata = _extract_metadata(raw_header)
    metadata["source_path"] = source_path
    metadata["raw_header"] = "\n".join(raw_header)
    metadata["columns_observed"] = list(columns)

    source_tool_raw = metadata.get("source_tool", "OMERE")
    source_tool = str(source_tool_raw) if source_tool_raw is not None else "OMERE"

    return DoseDepthCurve(
        thickness_mm_al=thickness,
        dose_per_species={k: tuple(v) for k, v in dose_per_species.items()},
        dose_total=dose_total,
        extra_species={k: tuple(v) for k, v in extra_species.items()},
        source_tool=source_tool,
        mission_metadata=metadata,
    )


def _resolve_columns(header_lines: Sequence[str], ncols: int) -> list[str]:
    """Combine the multi-line OMERE column header into ``ncols`` lower-case names.

    OMERE writes the column header across three lines, e.g.::

        # Thickness    Trapped     Trapped     Solar       Other       ...   Total
        #   Al        electrons    protons     proton    electrons     ...   Dose
        #  mm_Al          rad         rad         rad         rad      ...   rad

    We tokenize each line and zip column-wise, then merge the first two rows
    into the canonical name (``"trapped electrons"``, ``"solar proton"``,
    ``"other_gamma photons"``, ``"total"``), ignoring the units row.
    """
    if not header_lines:
        raise ValueError("OMERE .dos: missing column header rows")

    name_rows: list[list[str]] = []
    for line in header_lines:
        tokens = re.split(r"\s+", line.lstrip("#").strip())
        # Drop a trailing units annotation if it shows up alone, but generally
        # we expect 3 lines × ncols tokens each.
        if len(tokens) == ncols:
            name_rows.append(tokens)

    if len(name_rows) < 2:
        raise ValueError(
            f"OMERE .dos: expected ≥2 column-header rows of width {ncols}, "
            f"found {len(name_rows)}"
        )

    # First row = primary name (Thickness, Trapped, Solar, Other, Gamma, Total)
    # Second row = qualifier (electrons, protons, proton, electrons, photons, Dose)
    # Third row = units (we don't use it for naming).
    primary = name_rows[0]
    qualifier = name_rows[1]
    out: list[str] = []
    for i in range(ncols):
        p = primary[i].lower()
        q = qualifier[i].lower()
        if i == 0:
            out.append("thickness")
            continue
        if p == "total" or q == "dose":
            out.append("total")
            continue
        # Some dialects write "Other_Gamma" as one token in the primary row.
        out.append(f"{p} {q}")
    return out


_KEY_PATTERNS: list[tuple[str, str, Callable[[Match[str]], object]]] = [
    (r"\bOMERE\s+([0-9.]+)", "source_tool", lambda m: f"OMERE-{m.group(1)}"),
    (r"Start\s+mission\s*:\s*(\d+)", "start_year", lambda m: int(m.group(1))),
    (r"Lifetime\s*:\s*([0-9.]+)\s*month", "lifetime_months", lambda m: float(m.group(1))),
    (r"Perigee\s*:\s*([0-9.]+)\s*km", "perigee_km", lambda m: float(m.group(1))),
    (r"Apogee\s*:\s*([0-9.]+)\s*km", "apogee_km", lambda m: float(m.group(1))),
    (r"Inclination\s*:\s*([0-9.]+)", "inclination_deg", lambda m: float(m.group(1))),
    (r"Target\s+material\s*:\s*(.+)", "target_material", lambda m: m.group(1).strip()),
]


def _extract_metadata(header_lines: Sequence[str]) -> dict[str, object]:
    """Best-effort key/value extraction from OMERE's free-form header comments.

    Untrusted; surfaced in the report as-is. The ``raw_header`` field carries the
    full original text for any field this routine doesn't parse.
    """
    out: dict[str, object] = {}
    blob = "\n".join(line.lstrip("#").strip() for line in header_lines)
    for pattern, key, conv in _KEY_PATTERNS:
        m = re.search(pattern, blob)
        if m is not None:
            out[key] = conv(m)
    # Trapped-particle model + percentile (Trapped electrons : Model : ...).
    if m := re.search(r"Trapped electrons\s*:\s*\n\s*Model\s*:\s*(.+)", blob):
        out["trapped_electron_model"] = m.group(1).strip()
    if m := re.search(r"Trapped protons\s*:\s*\n\s*Model\s*:\s*(.+)", blob):
        out["trapped_proton_model"] = m.group(1).strip()
    if m := re.search(r"Solar protons\s*:\s*([A-Za-z0-9 ]+)", blob):
        out["solar_proton_model"] = m.group(1).strip()
    if m := re.search(r"Confidence level\s*=\s*([0-9.]+)", blob):
        out["solar_proton_confidence_pct"] = float(m.group(1))
    return out
