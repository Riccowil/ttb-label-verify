# Claude Code Instructions — ttb-label-verify

Read SPEC.md before writing any code. It is the single source of truth for:
comparison rules, the statutory warning constant, the extraction prompt,
the response envelope, thresholds, API contract, batch semantics, UI copy,
and the test matrix (T1-T8).

Rules:
- The LLM extracts, code decides. No compliance logic in prompts.
- comparators.py must be fully testable with zero API calls.
- Write the failing tests from SPEC.md section 12 FIRST, then implement
  (red-green on the comparator module).
- All tunable values live in thresholds.py only. No magic numbers.
- Every field result: {field, verdict, reason, evidence}. reason is always
  a plain-language sentence.
- Diff ops map to difflib.SequenceMatcher opcodes: equal|replace|delete|insert.
- Commit per phase from SPEC.md section 13, meaningful messages
  ("comparators + test suite", "extraction client", etc.).
- Stack: FastAPI backend, Vite + React frontend, single repo.
- Do not add features beyond SPEC.md. Working core > ambitious incomplete.
