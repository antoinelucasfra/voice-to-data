"""
examples/sample_run.py — Synthetic demo of the pipeline without Ollama or Whisper.

Runs Stages 2–4 with a hand-crafted transcript, demonstrating schema extraction
(mocked), domain validation, and audit record generation — no external services needed.

Usage:
    uv run examples/sample_run.py
"""

import json
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

# Allow running from the repo root
sys.path.insert(0, str(Path(__file__).parent.parent))

from audit import AuditRecord
from schema import AppearanceDescriptor, LabObservation
from validator import DomainValidator


def demo_extraction_mock() -> list[tuple[str, LabObservation]]:
    """
    Return a list of (transcript, observation) pairs without calling an LLM.

    In real usage, the LLM produces these LabObservation instances via Instructor.
    Here we construct them directly to demonstrate the validation and audit stages.
    """
    return [
        (
            "Antoine here, batch F-204, pH is 5.9, no deviations.",
            LabObservation(
                batch_id="F-204",
                operator_id="Antoine",
                measurement_type="pH",
                value=5.9,
                unit="pH",
                deviation_flag=False,
                hedged=False,
            ),
        ),
        (
            "Viscosity is about 4,200 millipascal seconds, appearance slightly hazy.",
            LabObservation(
                batch_id="F-204",
                operator_id="Antoine",
                measurement_type="viscosity",
                value=4200.0,
                unit="mPa·s",
                appearance=AppearanceDescriptor.SLIGHTLY_HAZY,
                deviation_flag=False,
                hedged=True,  # "about" → hedged=True
            ),
        ),
        (
            "pH reading is 15.2 — something went wrong with the probe.",
            LabObservation(
                batch_id="F-204",
                operator_id="Antoine",
                measurement_type="pH",
                value=15.2,  # Implausible → hard reject
                unit="pH",
                deviation_flag=True,
                hedged=False,
            ),
        ),
        (
            "Batch F-205, added 2.5 grams of carbomer to the water phase.",
            LabObservation(
                # operator_id missing → soft flag
                batch_id="F-205",
                measurement_type="mass",
                ingredient_added="carbomer",
                ingredient_quantity=2.5,
                ingredient_unit="g",
                deviation_flag=False,
                hedged=False,
            ),
        ),
    ]


def run_demo() -> None:
    validator = DomainValidator()
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)

    print("=" * 60)
    print("voice-to-data-pipeline — synthetic demo")
    print("=" * 60)

    for i, (transcript, observation) in enumerate(demo_extraction_mock(), start=1):
        run_id = f"demo_{uuid.uuid4().hex[:8]}"
        extraction_ts = datetime.now(UTC).isoformat()

        # Stage 3: Validation
        result = validator.validate(observation)
        if not result.passed:
            commit_status = "rejected"
        elif result.requires_review:
            commit_status = "pending_review"
        else:
            commit_status = "committed"

        # Stage 4: Audit record
        audit = AuditRecord(
            pipeline_run_id=run_id,
            audio_file_path=f"demo_audio_{i}.mp3",
            asr_model_version="faster-whisper:medium:ct2",
            llm_model_version="ollama:llama3.1:8b",
            instructor_version="1.3.4",
            raw_transcript=transcript,
            extraction_timestamp=extraction_ts,
            validation_flags=result.flags,
            review_required=result.requires_review,
            commit_status=commit_status,
        )

        output = {
            "observation": observation.model_dump(),
            "audit": audit.to_dict(),
        }

        out_path = output_dir / f"demo_obs_{i}.json"
        out_path.write_text(json.dumps(output, indent=2, ensure_ascii=False))

        # Print summary
        status_symbol = {"committed": "✓", "pending_review": "~", "rejected": "✗"}[commit_status]
        print(f"\n[{status_symbol}] Example {i} — {commit_status.upper()}")
        print(f"  Transcript : {transcript}")
        print(f"  Batch      : {observation.batch_id}")
        measurement = (
            f"{observation.measurement_type} = {observation.value} {observation.unit or ''}"
        )
        print(f"  Measurement: {measurement}")
        if result.flags:
            for flag in result.flags:
                print(f"  ! {flag}")
        print(f"  Output     : {out_path}")

    print("\n" + "=" * 60)
    print(f"Demo complete. {len(demo_extraction_mock())} records processed.")
    print("Check output/ for JSON files.")


if __name__ == "__main__":
    run_demo()
