"""Material governance layer — Phase B2.

Seeded material library, naming-rule auto-assignment, STEP tag ingestion
(OCCT-optional), auto-assignment review, and run gating.
"""

from raysim.mat.gating import (
    DensityAnomaly,
    GatingResult,
    check_density_anomalies,
    check_run_readiness,
)
from raysim.mat.library import MaterialLibrary, load_library
from raysim.mat.review import (
    AssignmentReview,
    AssignmentStatus,
    build_review,
    format_review_summary,
    review_to_assignments,
)
from raysim.mat.rules import NamingRule, RuleMatch, SolidRef, apply_rules, load_rules

__all__ = [
    "AssignmentReview",
    "AssignmentStatus",
    "DensityAnomaly",
    "GatingResult",
    "MaterialLibrary",
    "NamingRule",
    "RuleMatch",
    "SolidRef",
    "apply_rules",
    "build_review",
    "check_density_anomalies",
    "check_run_readiness",
    "format_review_summary",
    "load_library",
    "load_rules",
    "review_to_assignments",
]
