"""HEALPix direction-vector generator.

RaySim only needs `pix2vec` in RING ordering for batched ray emission. This module
prefers `healpy.pix2vec` when available, otherwise falls back to a vendored NumPy
implementation derived from Górski et al. 2005 (HEALPix paper).

The fallback is feature-minimal by design (no FITS, no spherical harmonics,
no rotator) — see `MVP_PLAN.md` §4.3. Both implementations agree to ≤1e-12 in
the unit-vector components for all valid pixel indices, verified in tests.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

try:
    import healpy

    _hp: object | None = healpy
    HEALPY_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised on Windows or stripped envs
    _hp = None
    HEALPY_AVAILABLE = False


def npix_for_nside(nside: int) -> int:
    """Total pixel count: 12 * Nside²."""
    if nside < 1 or (nside & (nside - 1)) != 0:
        raise ValueError(f"Nside must be a positive power of 2, got {nside}")
    return 12 * nside * nside


def pix2vec(nside: int, ipix: NDArray[np.int64] | int) -> NDArray[np.float64]:
    """Return unit direction vectors for HEALPix RING-ordered pixel indices.

    Uses healpy when available; otherwise the vendored NumPy fallback. Returns
    array of shape (..., 3) with (x, y, z) on the unit sphere.
    """
    if _hp is not None:
        x, y, z = _hp.pix2vec(nside, ipix, nest=False)  # type: ignore[attr-defined]
        return np.stack(np.broadcast_arrays(x, y, z), axis=-1).astype(np.float64)
    return _pix2vec_vendored(nside, ipix)


def _pix2vec_vendored(
    nside: int, ipix: NDArray[np.int64] | int
) -> NDArray[np.float64]:
    """Vendored RING-ordering pix2vec.

    Algorithm follows Górski et al. 2005, Appendix:
      - North polar cap: rings i = 1..Nside-1, each with 4i pixels.
      - Equatorial belt: rings i = Nside..2Nside, each with 4*Nside pixels.
      - South polar cap: rings i = 2Nside+1..4Nside-1, mirroring the north.

    Returns z = cos(theta) and phi, then converts to (x, y, z).
    """
    if nside < 1 or (nside & (nside - 1)) != 0:
        raise ValueError(f"Nside must be a positive power of 2, got {nside}")

    npix = 12 * nside * nside
    p = np.atleast_1d(np.asarray(ipix, dtype=np.int64))
    if p.min() < 0 or p.max() >= npix:
        raise ValueError(f"pixel index out of range [0, {npix})")

    ncap = 2 * nside * (nside - 1)  # pixels in the north polar cap
    z = np.empty(p.shape, dtype=np.float64)
    phi = np.empty(p.shape, dtype=np.float64)
    nside_f = float(nside)

    # --- North polar cap: p < ncap ---
    mask_n = p < ncap
    if mask_n.any():
        ip = p[mask_n] + 1  # 1-indexed within cap
        # ring index i in [1..Nside-1]
        i = np.floor(0.5 * (1.0 + np.sqrt(2.0 * ip - 1.0))).astype(np.int64)
        j = ip - 2 * i * (i - 1)  # pixel-in-ring, 1..4i
        z[mask_n] = 1.0 - (i * i) / (3.0 * nside_f * nside_f)
        phi[mask_n] = (j - 0.5) * (np.pi / 2.0) / i

    # --- Equatorial belt: ncap <= p < npix - ncap ---
    nbelt_start = ncap
    nbelt_end = npix - ncap
    mask_b = (p >= nbelt_start) & (p < nbelt_end)
    if mask_b.any():
        ip = p[mask_b] - ncap
        # ring index measured from north-cap boundary (0-indexed)
        i_belt = ip // (4 * nside)  # 0..2Nside (incl)
        j = ip % (4 * nside) + 1  # 1..4Nside
        i_total = i_belt + nside  # 1-indexed ring overall
        z[mask_b] = (2 * nside - i_total) * 2.0 / (3.0 * nside_f)
        # Górski 2005 Eq. 8: phi = (π/(2 Nside)) (j - (s+1)/2)
        # with s = (i_total + Nside) mod 2 — half-pixel offset on alternate rings.
        s = (i_total + nside) % 2  # 0 or 1
        phi[mask_b] = (j - 0.5 * (s + 1)) * np.pi / (2.0 * nside_f)

    # --- South polar cap: p >= npix - ncap ---
    mask_s = p >= nbelt_end
    if mask_s.any():
        ip = npix - p[mask_s]  # 1..ncap from the south pole
        i = np.floor(0.5 * (1.0 + np.sqrt(2.0 * ip - 1.0))).astype(np.int64)
        j = 4 * i + 1 - (ip - 2 * i * (i - 1))
        z[mask_s] = -1.0 + (i * i) / (3.0 * nside_f * nside_f)
        phi[mask_s] = (j - 0.5) * (np.pi / 2.0) / i

    sin_theta = np.sqrt(np.maximum(0.0, 1.0 - z * z))
    x = sin_theta * np.cos(phi)
    y = sin_theta * np.sin(phi)
    out = np.stack([x, y, z], axis=-1)
    return out if np.ndim(ipix) > 0 else out[0]


def all_pixel_directions(nside: int) -> NDArray[np.float64]:
    """Convenience: unit direction for every RING-ordered pixel at this Nside."""
    return pix2vec(nside, np.arange(npix_for_nside(nside), dtype=np.int64))
