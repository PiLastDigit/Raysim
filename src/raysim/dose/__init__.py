"""Dose math — DDC log-cubic spline + per-detector aggregation."""

from raysim.dose.aggregator import RHO_AL_REF_G_CM3, aggregate_detector
from raysim.dose.spline import DoseSpline, build_dose_spline

__all__ = ["RHO_AL_REF_G_CM3", "DoseSpline", "aggregate_detector", "build_dose_spline"]
