"""
validator.py — Domain-level validation for LabObservation records.

Operates at two distinct levels:
  - Structural validation: handled automatically by Pydantic during extraction
  - Domain validation (this module): scientific plausibility checks

Domain validation produces ValidationResult with:
  - passed: False → hard block, record not serialized to primary output
  - requires_review: True → soft flag, record routed to review queue before commit
"""

from dataclasses import dataclass, field
from typing import NamedTuple

from schema import LabObservation


class ValidationResult(NamedTuple):
    passed: bool
    flags: list[str]
    requires_review: bool


@dataclass
class DomainValidator:
    """
    Applies domain-specific plausibility checks to a LabObservation.

    Thresholds and unit whitelists are configurable. The defaults shown
    here are illustrative for a pharmaceutical formulation context.
    Override them for your specific domain.
    """

    ph_range: tuple[float, float] = (0.0, 14.0)
    viscosity_range_mpas: tuple[float, float] = (1.0, 200_000.0)
    temperature_range_celsius: tuple[float, float] = (-80.0, 200.0)
    allowed_units: dict[str, list[str]] = field(
        default_factory=lambda: {
            "pH": ["pH", ""],
            "viscosity": ["mPa·s", "cP", "mPas", "mPa.s"],
            "temperature": ["°C", "°F", "K", "C", "F"],
            "mass": ["g", "mg", "kg"],
            "volume": ["mL", "L", "µL", "uL"],
            "concentration": ["%w/w", "%v/v", "%w/v", "mg/mL", "g/L", "ppm"],
        }
    )
    mandatory_fields: list[str] = field(
        default_factory=lambda: ["batch_id", "operator_id", "measurement_type"]
    )

    def validate(self, obs: LabObservation) -> ValidationResult:
        flags: list[str] = []

        # ── Mandatory field checks ──────────────────────────────────────────
        for f in self.mandatory_fields:
            if getattr(obs, f) is None:
                flags.append(f"MISSING_MANDATORY_FIELD:{f}")

        # ── pH plausibility ─────────────────────────────────────────────────
        if obs.measurement_type == "pH" and obs.value is not None:
            lo, hi = self.ph_range
            if not (lo <= obs.value <= hi):
                flags.append(f"IMPLAUSIBLE_PH:{obs.value}")

        # ── Viscosity plausibility ──────────────────────────────────────────
        if obs.measurement_type == "viscosity" and obs.value is not None:
            lo, hi = self.viscosity_range_mpas
            if not (lo <= obs.value <= hi):
                flags.append(f"IMPLAUSIBLE_VISCOSITY:{obs.value}")

        # ── Temperature plausibility ────────────────────────────────────────
        if obs.measurement_type == "temperature" and obs.value is not None:
            lo, hi = self.temperature_range_celsius
            if obs.unit in ("°C", "C") and not (lo <= obs.value <= hi):
                flags.append(f"IMPLAUSIBLE_TEMPERATURE:{obs.value}")

        # ── Unit whitelist ──────────────────────────────────────────────────
        if obs.measurement_type and obs.unit:
            allowed = self.allowed_units.get(obs.measurement_type, [])
            if allowed and obs.unit not in allowed:
                flags.append(f"UNEXPECTED_UNIT:{obs.unit}_for_{obs.measurement_type}")

        # ── Hedged values always require review ─────────────────────────────
        if obs.hedged:
            flags.append("HEDGED_VALUE:confirm_with_operator")

        # ── Deviation flag requires review ──────────────────────────────────
        if obs.deviation_flag:
            flags.append("DEVIATION_REPORTED:review_required")

        # A record fails (hard block) only on IMPLAUSIBLE or MISSING_MANDATORY flags.
        # All other flags are soft — record proceeds to review queue.
        passed = not any(
            f.startswith(("IMPLAUSIBLE", "MISSING_MANDATORY")) for f in flags
        )
        requires_review = len(flags) > 0

        return ValidationResult(passed=passed, flags=flags, requires_review=requires_review)
