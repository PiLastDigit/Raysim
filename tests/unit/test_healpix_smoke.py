"""Phase 0 smoke (§0.2): HEALPix pix2vec direction generation.

Verifies the vendored NumPy fallback against healpy where available, and that
both produce equal-area unit vectors for typical Nside values.
"""

from __future__ import annotations

import numpy as np
import pytest

from raysim.ray.healpix import (
    HEALPY_AVAILABLE,
    _pix2vec_vendored,
    all_pixel_directions,
    npix_for_nside,
    pix2vec,
)

NSIDES = [1, 2, 4, 8, 16, 32, 64]


@pytest.mark.parametrize("nside", NSIDES)
def test_npix(nside: int) -> None:
    assert npix_for_nside(nside) == 12 * nside * nside


@pytest.mark.parametrize("nside", NSIDES)
def test_vendored_unit_vectors(nside: int) -> None:
    vecs = _pix2vec_vendored(nside, np.arange(12 * nside * nside, dtype=np.int64))
    norms = np.linalg.norm(vecs, axis=1)
    np.testing.assert_allclose(norms, 1.0, atol=1e-12)


@pytest.mark.parametrize("nside", NSIDES)
def test_vendored_z_in_range(nside: int) -> None:
    vecs = _pix2vec_vendored(nside, np.arange(12 * nside * nside, dtype=np.int64))
    assert np.all(vecs[:, 2] >= -1.0 - 1e-12)
    assert np.all(vecs[:, 2] <= 1.0 + 1e-12)


@pytest.mark.parametrize("nside", [1, 2, 4, 8, 16])
def test_vendored_pixels_distinct(nside: int) -> None:
    """Sanity: no two pixel centers coincide. Limited to small Nside (O(N²) check)."""
    vecs = _pix2vec_vendored(nside, np.arange(12 * nside * nside, dtype=np.int64))
    diffs = np.linalg.norm(vecs[:, None, :] - vecs[None, :, :], axis=-1)
    np.fill_diagonal(diffs, np.inf)
    assert diffs.min() > 1e-6, "two HEALPix pixel centers coincide"


@pytest.mark.needs_healpy
@pytest.mark.skipif(not HEALPY_AVAILABLE, reason="healpy not installed")
@pytest.mark.parametrize("nside", NSIDES)
def test_vendored_matches_healpy(nside: int) -> None:
    """Vendored fallback must agree with healpy.pix2vec to float64 precision."""
    import healpy as hp

    n = 12 * nside * nside
    ipix = np.arange(n, dtype=np.int64)
    ours = _pix2vec_vendored(nside, ipix)
    x, y, z = hp.pix2vec(nside, ipix, nest=False)
    theirs = np.stack([x, y, z], axis=-1)
    np.testing.assert_allclose(ours, theirs, atol=1e-13)


@pytest.mark.parametrize("nside", [4, 16])
def test_uniform_integration(nside: int) -> None:
    """∫ z dΩ over the sphere ≈ 0 (mean z over equal-area pixels = 0)."""
    vecs = all_pixel_directions(nside)
    np.testing.assert_allclose(vecs.mean(axis=0), [0.0, 0.0, 0.0], atol=1e-14)


def test_pix2vec_dispatch() -> None:
    """Top-level pix2vec returns correct shape for scalar and array input."""
    v = pix2vec(8, np.arange(10, dtype=np.int64))
    assert v.shape == (10, 3)


def test_invalid_nside() -> None:
    with pytest.raises(ValueError):
        npix_for_nside(3)  # not a power of 2
    with pytest.raises(ValueError):
        npix_for_nside(0)
