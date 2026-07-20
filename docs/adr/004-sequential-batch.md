# ADR-004: Sequential batch processing, capped at 300

## Context
Peak-season importers submit 200-300 applications at once; prior tooling
failure was latency-driven abandonment.

## Decision
Pre-flight CSV validation, then sequential processing with live per-row
progress; hard cap at 300.

## Consequences
Predictable rate-limit behavior, simple ordering, visible progress.

Trade-off: throughput vs. parallel workers — parallelism deferred as first
production optimization.
