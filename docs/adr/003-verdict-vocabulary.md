# ADR-003: Three-tier verdict vocabulary (PASS / FLAG / FAIL) + NEEDS BETTER IMAGE

## Context
One field (government warning) demands strict matching while others (brand
name) demand tolerance; agents distrust tools that false-fail.

## Decision
Per-field three-tier verdicts with FLAG routing to human judgment;
unreadable images get a distinct non-compliance verdict.

## Consequences
The tool assists rather than replaces agents; strictness is per-field
policy in config, not global.

Trade-off: FLAG volume depends on thresholds — tunable in one file.
