# TTB Label Verification Prototype

AI-assisted verification of alcohol beverage label applications. An agent
uploads a label image plus the application data; the tool extracts the label
text with a vision model and deterministically compares five required fields —
brand name, class/type, alcohol content, net contents, and the government
health warning — returning per-field verdicts with evidence.

**Design principle: the LLM extracts, code decides.** All compliance logic is
deterministic, unit-tested, and explainable. The model never renders a verdict.

Deployed prototype: `<URL>`

## Quick Start

```bash
# Backend
cd backend
pip install -r requirements.txt
export ANTHROPIC_API_KEY=your-key
uvicorn app:app --reload

# Frontend
cd frontend
npm install && npm run dev

# Tests (no API key required)
cd backend && pytest
```

## How It Works

1. **Extraction** — one vision API call returns verbatim label text as
   structured JSON with per-field confidence scores and image-quality
   assessment. Temperature 0, nulls over guesses.
2. **Comparison** — five field-specific comparators produce PASS / FLAG /
   FAIL with a plain-language reason and evidence. The government warning
   uses a two-part rule: case-sensitive prefix ("GOVERNMENT WARNING:") +
   case-insensitive word-level body match against 27 CFR Part 16 statutory
   text, with a word-diff in the output. Brand and class/type use normalized
   fuzzy matching; ABV and net contents compare as parsed numbers
   (formatting variance is legal, value variance isn't).
3. **Aggregation** — overall verdict is the worst field verdict;
   low-confidence extractions cap at FLAG; unreadable images return
   NEEDS BETTER IMAGE instead of a compliance verdict.

The response envelope includes `processing_time_ms` — typical round trip is
2–4 seconds against the stated 5-second usability requirement.

## Batch Mode

Upload a CSV (schema in `test_labels/batch.csv`) plus matching images, up to
300 rows. Pre-flight validation, sequential processing with live progress,
exportable results.

## Verdicts

| Verdict | Meaning | UI |
|---|---|---|
| PASS | Matches application | Green |
| FLAG | Needs agent review | Amber |
| FAIL | Does not match | Red |
| NEEDS BETTER IMAGE | Label unreadable — request resubmission | Neutral |

## Test Labels

`test_labels/` contains eight generated labels mapped to expected outcomes
(clean pass, casing variance, title-case warning prefix, warning word-swap,
missing warning, ABV mismatch, glare, wine without stated ABV). These double
as the acceptance suite and the demo script.

## Assumptions & Interpretation Notes

The written instructions leave several decisions open; each was resolved with
a documented assumption rather than a clarifying question:

- Application data is entered manually or via CSV; no COLA integration —
  the IT interview explicitly frames this as a standalone proof-of-concept.
  The instructions don't specify how application data enters the system;
  manual entry + CSV batch was implemented based on the interview notes'
  batch-upload request.
- The government warning is validated against the statutory text in
  27 CFR Part 16 as a two-part rule: the "GOVERNMENT WARNING:" prefix is
  compared case-sensitively; the body is compared word-for-word,
  case-insensitively, with whitespace collapsed to accommodate legal
  line-wrapping on labels.
- Bold-prefix detection is advisory (FLAG, not FAIL): typography judgment
  from a photo is inherently visual, so the tool surfaces it for agent
  confirmation rather than auto-rejecting.
- ABV and net contents are compared as parsed numeric values, not strings —
  formatting variance ("45% Alc./Vol." vs "45% ABV") is legal; value
  variance is not. Tolerance is zero.
- Brand and class/type use normalized fuzzy matching with a three-tier
  verdict (PASS/FLAG/FAIL). Thresholds live in a single config file and are
  tunable without code changes.
- Images below a legibility threshold return NEEDS BETTER IMAGE rather than
  a compliance verdict — mirroring current agent practice of requesting
  resubmission, per the junior agent interview.
- The tool is decision support, not a decision-maker: every verdict includes
  per-field evidence and a plain-language reason, and FLAG explicitly routes
  to human judgment. No auto-approval or auto-rejection is implied.

## Trade-offs & Limitations

- **Hosted vision API vs. the TTB firewall.** The prototype uses a cloud LLM
  vision endpoint for extraction. IT noted TTB's network blocks many
  outbound ML endpoints; a production deployment would require a
  FedRAMP-authorized service or self-hosted inference. The extraction layer
  is isolated behind a single interface so the model provider is swappable.
- **Extraction is probabilistic; comparison is deterministic.** All
  compliance logic is plain code with unit tests — the LLM never renders a
  verdict. This bounds the blast radius of model error to extraction, where
  per-field confidence scores cap uncertain fields at FLAG.
- **Speed vs. accuracy.** The default model is chosen for sub-5-second round
  trips (the prior vendor pilot failed at 30–40s). A higher-accuracy model
  is a one-line config change at a latency cost.
- **Batch runs sequentially** with visible progress, capped at 300 rows.
  Parallelism would be the first production optimization but adds rate-limit
  and ordering complexity beyond prototype scope.
- **No image enhancement.** Bad photos are detected and routed, not
  corrected. Deskewing/glare-removal preprocessing is a documented future
  item.
- **Beverage-type rule variance** (e.g., ABV optional on some wine/beer) is
  handled minimally; a production version would encode the full CFR rule
  matrix per class.

## Deployment

Single Railway service (ADR-005): a multi-stage `Dockerfile` builds the
Vite frontend, then copies the static output into the FastAPI container.
`app.py` mounts it after every `/api/*` route, so the API always wins the
match; the frontend calls relative paths (`/api/verify`), same origin, no
CORS surface in production. `/api/health` doubles as the Railway
healthcheck (`railway.json`).

```bash
docker build -t ttb-label-verify .
docker run -p 8000:8000 -e PORT=8000 -e ANTHROPIC_API_KEY=sk-... ttb-label-verify
```

`ANTHROPIC_API_KEY` is a runtime-only env var — never baked into the
image, never committed to a file. Set it in the Railway dashboard.

## Architecture Decisions

See `docs/adr/` for records on extract-then-decide, provider swappability,
the verdict vocabulary, batch design, and the deploy topology. Full
specification in `SPEC.md`.

## What I'd Do Next

Image preprocessing (deskew/glare), per-beverage-type CFR rule engine, COLA
workflow integration study, agent feedback loop on FLAG resolutions, audit
logging with retention policy.
