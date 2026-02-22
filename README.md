# voice-to-data

A production-oriented pipeline that turns voice recordings from laboratory bench sessions into structured, validated records — ready for ELN/LIMS handoff with a GxP-compliant audit trail.

Built for pharmaceutical and biotech R&D environments where scientists have both hands occupied during experiments and need a hands-free way to capture structured observations.

---

## Architecture

```
INPUT: Voice (audio file or real-time mic)
         │
         ▼
┌─────────────────────────────────┐
│  Stage 1 — ASR                  │
│  faster-whisper (local, CPU/GPU)│
│  Output: raw transcript         │
└──────────────┬──────────────────┘
               │
               ▼
┌─────────────────────────────────┐
│  Stage 2 — Structured Extraction│
│  Instructor + Pydantic + Ollama │
│  Output: typed schema record    │
└──────────────┬──────────────────┘
               │
               ▼
┌─────────────────────────────────┐
│  Stage 3 — Validation           │
│  Pydantic + DomainValidator     │
│  Output: validated record or    │
│          flagged review item    │
└──────────────┬──────────────────┘
               │
               ▼
┌─────────────────────────────────┐
│  Stage 4 — Serialization        │
│  JSON output + AuditRecord      │
└─────────────────────────────────┘
```

All processing runs **locally** — no audio or transcript data leaves your network. This is the only defensible configuration for pharma R&D environments where recordings may contain compound names under NDA, formulation parameters, or batch identifiers tied to regulatory submissions.

---

## Stack

| Component | Tool | Why |
|---|---|---|
| ASR | `faster-whisper` (CTranslate2) | Open-weights Whisper, 2–4× faster than PyTorch impl, CPU-capable |
| Structured extraction | `instructor` + `ollama` | Guaranteed schema-conformant LLM output via tool-calling |
| Schema & validation | `pydantic` v2 | Type enforcement + domain plausibility checks |
| Dependency management | `uv` | Fast, reproducible Python environment |

---

## Installation

Requires [Ollama](https://ollama.com) running locally with a model pulled:

```bash
ollama pull llama3.1:8b
```

Then:

```bash
git clone https://github.com/antoinelucasfra/voice-to-data-pipeline
cd voice-to-data-pipeline
uv sync
```

---

## Usage

```bash
uv run pipeline.py path/to/bench_note.mp3 output/observation.json
```

Output is a JSON file with two top-level keys:

- `observation` — the structured `LabObservation` record (all fields typed, enums resolved)
- `audit` — the immutable `AuditRecord` (model versions, transcript hash, validation flags, commit status)

### Example output

```json
{
  "observation": {
    "batch_id": "F-204",
    "operator_id": "Antoine",
    "stated_timestamp": "14:32",
    "measurement_type": "viscosity",
    "value": 4200.0,
    "unit": "mPa·s",
    "appearance": "slightly_hazy",
    "ingredient_added": "carbomer",
    "ingredient_quantity": 1.2,
    "ingredient_unit": "g",
    "deviation_flag": false,
    "hedged": true,
    "notes": "mixing at 500 RPM"
  },
  "audit": {
    "pipeline_run_id": "run_20260222_143512_a3f9",
    "asr_model": "faster-whisper:medium",
    "llm_model": "ollama:llama3.1:8b",
    "raw_transcript_sha256": "e3b0c44298fc1c...",
    "extraction_timestamp": "2026-02-22T14:35:12Z",
    "validation_flags": ["HEDGED_VALUE:confirm_with_operator"],
    "review_required": true,
    "commit_status": "pending_review"
  }
}
```

### Commit statuses

| Status | Meaning |
|---|---|
| `committed` | Record passed all validation checks, written to output |
| `pending_review` | Soft flags present (hedged value, missing optional field) — requires human review |
| `rejected` | Hard validation failure (implausible value, missing mandatory field) — not written to primary output |

---

## Project structure

```
voice-to-data-pipeline/
├── pyproject.toml          # dependencies + ruff config
├── pipeline.py             # main entrypoint — run_pipeline()
├── schema.py               # LabObservation Pydantic model
├── validator.py            # DomainValidator class
├── audit.py                # AuditRecord dataclass
├── examples/
│   └── sample_run.py       # synthetic demo without Ollama/Whisper
└── .github/
    └── workflows/ci.yml    # ruff lint on push/PR
```

---

## Compliance notes

This pipeline is designed with GxP environments in mind:

- **Audit trail**: every record carries an immutable `AuditRecord` — model versions, transcript SHA-256, validation flags, reviewer ID, commit timestamp
- **Model version-locking**: treat model updates as change control events; pin versions in `pyproject.toml`
- **Temperature = 0**: all extraction calls use `temperature=0` for maximum determinism
- **Review gate**: records with soft flags go to `pending_review` — never auto-committed
- **Local-only**: no audio or transcript data is sent to external APIs

This is a reference implementation, not a validated system. Deployment in a regulated environment requires IQ/OQ/PQ documentation per your organization's CSV framework.

---

## Detailed write-up

Full architecture walkthrough, design decisions, failure modes, and compliance considerations:
[Voice to Data: An LLM Pipeline for Lab Notebooks](https://antoinelucasfra.github.io/posts/voice-to-data-lab-pipeline/)

---

## License

MIT
