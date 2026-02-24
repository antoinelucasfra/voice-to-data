"""
pipeline.py — Voice-to-data pipeline: audio file → structured lab observation.

Entrypoint for the full 4-stage pipeline:
  Stage 1: ASR          — faster-whisper (local, CPU/GPU)
  Stage 2: Extraction   — Instructor + Pydantic + Ollama (local LLM)
  Stage 3: Validation   — DomainValidator (plausibility + mandatory fields)
  Stage 4: Serialize    — JSON output + immutable AuditRecord

Usage:
    uv run pipeline.py <audio_file> <output_json>

Example:
    uv run pipeline.py bench_note_F204.mp3 output/observation_F204.json

Requirements:
    - Ollama running locally: ollama serve
    - Model pulled: ollama pull llama3.1:8b
    - faster-whisper installed via: uv sync

IMPORTANT: This is a reference implementation. Production deployment in a
regulated (GxP) environment requires IQ/OQ/PQ validation per your
organization's CSV framework. See README.md for compliance notes.
"""

import importlib.metadata
import json
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

import instructor
from faster_whisper import WhisperModel
from ollama import Client

from audit import AuditRecord
from schema import LabObservation
from validator import DomainValidator

# ── Constants ─────────────────────────────────────────────────────────────────

ASR_MODEL_SIZE = "medium"
LLM_MODEL = "llama3.1:8b"
OLLAMA_HOST = "http://localhost:11434"

SYSTEM_PROMPT = """
You are a laboratory data extraction assistant for a pharmaceutical formulation lab.
Your task is to extract structured observations from a voice transcript of a scientist
recording bench notes.

Rules:
- Extract only what is explicitly stated. Do not infer or assume field values.
- If a value is hedged ("approximately", "about", "maybe", "around"), set hedged=true.
- If a field is not stated, set it to null. Never invent a value.
- Map appearance descriptions to the closest AppearanceDescriptor enum value.
- If multiple measurements are stated in one transcript, extract the primary one
  and put the rest in the notes field.

Examples:

Input: "Antoine here, batch F-204, pH is 5.9, no issues."
Output: {operator_id: "Antoine", batch_id: "F-204", measurement_type: "pH",
         value: 5.9, unit: "pH", deviation_flag: false, hedged: false}

Input: "Viscosity is about 4,200 millipascal seconds, appearance is slightly hazy."
Output: {measurement_type: "viscosity", value: 4200.0, unit: "mPa·s",
         appearance: "slightly_hazy", hedged: true}

Input: "Added 1.2 grams of carbomer, mixing at 500 RPM."
Output: {ingredient_added: "carbomer", ingredient_quantity: 1.2,
         ingredient_unit: "g", notes: "mixing at 500 RPM"}

Input: "Batch F-205, everything looks fine."
Output: {batch_id: "F-205", notes: "operator stated everything looks fine",
         deviation_flag: false}
"""


# ── Stage 1: ASR ──────────────────────────────────────────────────────────────


def transcribe(audio_path: Path, model_size: str = ASR_MODEL_SIZE) -> str:
    """
    Transcribe an audio file using faster-whisper.

    Runs entirely on CPU (int8 quantization). On a standard workstation,
    the medium model processes ~3 min audio in 15–20 seconds.

    The initial_prompt nudges Whisper toward domain vocabulary (compound names,
    units, abbreviations) that it would otherwise misrecognize.
    """
    model = WhisperModel(model_size, device="cpu", compute_type="int8")
    segments, _ = model.transcribe(
        str(audio_path),
        initial_prompt=(
            "Formulation lab note. Batch ID, pH, viscosity mPa·s, "
            "carbomer, excipient, API concentration, temperature degrees Celsius."
        ),
    )
    return " ".join(segment.text.strip() for segment in segments)


# ── Stage 2: Structured extraction ────────────────────────────────────────────


def extract(transcript: str) -> LabObservation:
    """
    Extract a structured LabObservation from a raw ASR transcript.

    Uses Instructor to enforce schema-conformant output from the local LLM.
    Temperature is set to 0 for maximum determinism — required in regulated contexts.
    """
    ollama_client = Client(host=OLLAMA_HOST)
    client = instructor.from_ollama(ollama_client, mode=instructor.Mode.JSON)

    return client.chat.completions.create(
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"Extract the observation from this transcript:\n\n{transcript}",
            },
        ],
        response_model=LabObservation,
        options={"temperature": 0},
    )


# ── Stage 3: Validation ────────────────────────────────────────────────────────


def validate(obs: LabObservation) -> tuple[bool, list[str], bool]:
    """
    Run domain validation. Returns (passed, flags, requires_review).

    passed=False → hard block (IMPLAUSIBLE_* or MISSING_MANDATORY_FIELD)
    requires_review=True → soft flag, human review before commit
    """
    validator = DomainValidator()
    result = validator.validate(obs)
    return result.passed, result.flags, result.requires_review


# ── Stage 4: Serialize ────────────────────────────────────────────────────────


def serialize(
    observation: LabObservation,
    audit: AuditRecord,
    output_path: Path,
) -> None:
    """Write observation + audit record as a single JSON file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    result = {
        "observation": observation.model_dump(),
        "audit": audit.to_dict(),
    }
    output_path.write_text(json.dumps(result, indent=2, ensure_ascii=False))


# ── Pipeline orchestration ────────────────────────────────────────────────────


def run_pipeline(audio_path: Path, output_path: Path) -> None:
    """
    Run the full 4-stage pipeline for a single audio file.

    Prints commit status and any validation flags to stdout.
    Exits with code 1 if the record is hard-rejected.
    """
    run_id = (
        f"run_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}"
        f"_{uuid.uuid4().hex[:6]}"
    )
    extraction_ts = datetime.now(UTC).isoformat()

    try:
        instructor_version = importlib.metadata.version("instructor")
    except importlib.metadata.PackageNotFoundError:
        instructor_version = "unknown"

    # Stage 1
    print(f"[{run_id}] Stage 1/4 — ASR ({ASR_MODEL_SIZE} model)...")
    transcript = transcribe(audio_path)
    print(f"[{run_id}] Transcript: {transcript[:120]}{'...' if len(transcript) > 120 else ''}")

    # Stage 2
    print(f"[{run_id}] Stage 2/4 — Extraction ({LLM_MODEL})...")
    observation = extract(transcript)

    # Stage 3
    print(f"[{run_id}] Stage 3/4 — Validation...")
    passed, flags, requires_review = validate(observation)

    commit_status: str
    if not passed:
        commit_status = "rejected"
    elif requires_review:
        commit_status = "pending_review"
    else:
        commit_status = "committed"

    # Stage 4
    audit = AuditRecord(
        pipeline_run_id=run_id,
        audio_file_path=str(audio_path),
        asr_model_version=f"faster-whisper:{ASR_MODEL_SIZE}:ct2",
        llm_model_version=f"ollama:{LLM_MODEL}",
        instructor_version=instructor_version,
        raw_transcript=transcript,
        extraction_timestamp=extraction_ts,
        validation_flags=flags,
        review_required=requires_review,
        commit_status=commit_status,
    )

    print(f"[{run_id}] Stage 4/4 — Serializing...")
    serialize(observation, audit, output_path)

    # Report
    status_label = {
        "committed": "COMMITTED",
        "pending_review": "PENDING REVIEW",
        "rejected": "REJECTED",
    }[commit_status]

    print(f"\n[{status_label}] {run_id}")
    print(f"  Output: {output_path}")
    if flags:
        for flag in flags:
            print(f"  ! {flag}")

    if commit_status == "rejected":
        sys.exit(1)


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: uv run pipeline.py <audio_file> <output_json>")
        print("Example: uv run pipeline.py bench_note_F204.mp3 output/obs_F204.json")
        sys.exit(1)

    run_pipeline(Path(sys.argv[1]), Path(sys.argv[2]))
