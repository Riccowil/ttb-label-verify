# ADR-001: Extract-then-decide architecture

## Context
LLM vision is needed to read labels, but compliance verdicts must be
explainable, testable, and auditable.

## Decision
The LLM performs extraction only, returning verbatim text with confidence
scores; all pass/fail logic is deterministic code with unit tests.

## Consequences
Model errors are bounded to extraction (capped at FLAG via confidence);
compliance rules are reviewable by non-ML staff; the comparator suite runs
without API keys.

Trade-off: two-stage design vs. asking the model to judge directly —
accepted for auditability.
