"""
audit.py — Immutable audit trail record for GxP compliance.

AuditRecord is created once per pipeline run and never modified after creation.
It captures everything needed to reconstruct what happened:
  - which models were used (versions pinned)
  - what the raw transcript contained (SHA-256 hash — not the text itself)
  - what validation flags were raised
  - whether human review occurred and by whom

In a validated GxP system, this record is the electronic signature substrate
under 21 CFR Part 11 / EMA Annex 11.
"""

import hashlib
from dataclasses import dataclass
from typing import Optional


@dataclass
class AuditRecord:
    """
    Immutable audit trail for a single pipeline run.

    Store this alongside (but separately from) the observation record.
    Never edit after creation.
    """

    pipeline_run_id: str
    audio_file_path: str
    asr_model_version: str  # e.g. "faster-whisper:medium:ct2"
    llm_model_version: str  # e.g. "ollama:llama3.1:8b"
    instructor_version: str  # e.g. "1.3.4"
    raw_transcript: str  # verbatim ASR output — hashed in serialization
    extraction_timestamp: str  # ISO 8601, UTC
    validation_flags: list[str]
    review_required: bool
    commit_status: str  # "committed" | "pending_review" | "rejected"
    reviewer_id: Optional[str] = None  # None if auto-committed
    reviewer_timestamp: Optional[str] = None

    def to_dict(self) -> dict:
        """
        Serialize to dict for JSON output.

        The raw transcript is stored as a SHA-256 hash — the full text lives
        in a separate immutable store. This satisfies traceability requirements
        without duplicating potentially sensitive text across every record.
        """
        return {
            "pipeline_run_id": self.pipeline_run_id,
            "audio_file_path": self.audio_file_path,
            "asr_model_version": self.asr_model_version,
            "llm_model_version": self.llm_model_version,
            "instructor_version": self.instructor_version,
            "raw_transcript_sha256": hashlib.sha256(
                self.raw_transcript.encode("utf-8")
            ).hexdigest(),
            "extraction_timestamp": self.extraction_timestamp,
            "validation_flags": self.validation_flags,
            "review_required": self.review_required,
            "reviewer_id": self.reviewer_id,
            "reviewer_timestamp": self.reviewer_timestamp,
            "commit_status": self.commit_status,
        }
