"""
schema.py — Pydantic schema for structured lab observations.

LabObservation is the core data contract of the pipeline.
Every field is Optional except deviation_flag and hedged — a missing field
is more honest than a hallucinated one.
"""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class AppearanceDescriptor(str, Enum):
    """Controlled vocabulary for visual appearance assessments."""

    CLEAR = "clear"
    SLIGHTLY_HAZY = "slightly_hazy"
    HAZY = "hazy"
    TURBID = "turbid"
    OPAQUE = "opaque"
    OTHER = "other"


class LabObservation(BaseModel):
    """
    Structured record of a single lab observation extracted from a voice transcript.

    All measurement fields are Optional — the LLM sets them to None rather than
    hallucinating a value when information is absent from the transcript.
    """

    sample_id: Optional[str] = Field(
        None,
        description="Sample identifier as stated by the operator (e.g. 'F-204')",
    )
    batch_id: Optional[str] = Field(
        None,
        description="Batch identifier if distinct from sample_id",
    )
    operator_id: Optional[str] = Field(
        None,
        description="Operator name or ID as stated in the recording",
    )
    stated_timestamp: Optional[str] = Field(
        None,
        description="Time stated by the operator (e.g. '14:32'), as a string",
    )
    measurement_type: Optional[str] = Field(
        None,
        description="Type of measurement (e.g. 'viscosity', 'pH', 'temperature')",
    )
    value: Optional[float] = Field(
        None,
        description="Numeric value of the measurement",
    )
    unit: Optional[str] = Field(
        None,
        description="Unit of the measurement (e.g. 'mPa·s', 'pH', '°C', 'g')",
    )
    appearance: Optional[AppearanceDescriptor] = Field(
        None,
        description="Appearance descriptor mapped to controlled vocabulary",
    )
    ingredient_added: Optional[str] = Field(
        None,
        description="Name of any ingredient or excipient added during this observation",
    )
    ingredient_quantity: Optional[float] = Field(
        None,
        description="Quantity of ingredient added",
    )
    ingredient_unit: Optional[str] = Field(
        None,
        description="Unit for ingredient quantity (e.g. 'g', 'mL', '%w/w')",
    )
    deviation_flag: bool = Field(
        False,
        description="True if the operator reported a deviation from expected range",
    )
    hedged: bool = Field(
        False,
        description="True if the value was qualified ('approximately', 'about', 'maybe')",
    )
    notes: Optional[str] = Field(
        None,
        description="Additional free-text observations not captured in structured fields",
    )
