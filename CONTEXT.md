# Context

## What this repo is

This is a public showcase. The production system it is derived from is confidential
and cannot be shared. The tech stack published here — faster-whisper, Instructor,
Pydantic, Ollama, the four-stage pipeline design, the validation logic, the GxP
audit trail — is the same stack used in the real project. What has been removed is
the proprietary schema, real formulation data, and the LIMS integration layer.

## Why I built it

Lab scientists across pharma, biotech, food science, and materials R&D spend a
significant part of their bench time recording observations — batch IDs, measurements,
deviations, ingredient additions — while both hands are occupied with equipment. The
standard solution is paper, voice memos, or interrupting the experiment to type. None
of these produce structured data. The notes have to be transcribed, interpreted, and
re-entered downstream before they reach an ELN or LIMS. That gap is where data quality
problems and compliance risk accumulate.

This pipeline closes that gap: voice in, structured validated record out, with a
complete audit trail suitable for a regulated environment. The engineering challenge
that makes this non-trivial is the reliability constraint — an LLM that occasionally
hallucinates a value is not acceptable in a GxP context. The combination of
Instructor-enforced schema extraction, domain-level plausibility validation, and a
human review gate for soft-flagged records is what makes it usable rather than just
demonstrable.

## Why this matters to me

This work sits at an intersection I find genuinely stimulating: local LLM inference,
structured data extraction, and regulated-industry reliability requirements. It is not
a research prototype — it was built to solve a real problem that real lab teams hit
every day, and the design reflects that. The constraint of making an LLM pipeline
trustworthy enough for a compliance context forced every architectural decision to be
deliberate: why temperature 0, why a two-tier validation model, why SHA-256 the
transcript rather than store it, why a human review gate rather than a confidence
threshold.

If you are working on something in this space — lab automation, voice interfaces for
scientific workflows, LLM pipelines with compliance requirements — I would be glad to
talk: [antoinelucasfra.github.io](https://antoinelucasfra.github.io/)
