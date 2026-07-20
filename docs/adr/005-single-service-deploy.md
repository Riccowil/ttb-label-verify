# ADR-005: Single Railway service — FastAPI serves the built frontend

## Context
SPEC section 13's deploy step needs a target for both the FastAPI backend
and the Vite frontend. Railway supports either one service per component
(two builds, two URLs, cross-service env wiring) or one service that
serves both.

## Decision
Ship one Railway service. A multi-stage Dockerfile builds the frontend
with Vite, then copies the static output into the FastAPI container;
`app.py` mounts it after all `/api/*` routes so the API always wins the
match. `VITE_API_BASE_URL` is left empty at build time, so the frontend
calls relative paths (`/api/verify`) — same origin, no cross-service URL
to wire up.

## Consequences
One service to create, one env var to set (`ANTHROPIC_API_KEY`), one
URL, no production CORS surface to get wrong. `/api/health` doubles as
the container healthcheck.

Trade-off: frontend and backend redeploy together — a frontend-only copy
change still rebuilds the Python image. Acceptable for a prototype;
splitting into two services is a Dockerfile/app.py change away if
release cadences ever diverge, not a rewrite.
