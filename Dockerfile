# ADR-005: one Railway service serves both the API and the built frontend.
# Stage 1 builds the static frontend; stage 2 is the FastAPI runtime that
# serves it. ANTHROPIC_API_KEY is never referenced here — it's a runtime
# env var read by extraction.py, not a build-time input.

FROM node:22-slim AS frontend-build
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
# Build-time only, no secret: relative-path default already works for the
# same-origin deploy this Dockerfile produces. Override to point the built
# frontend at a different backend origin instead.
ARG VITE_API_BASE_URL=""
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
RUN npm run build

FROM python:3.14-slim AS backend
WORKDIR /app
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ ./
COPY --from=frontend-build /app/frontend/dist ./static

# Railway injects PORT at runtime; uvicorn needs it as a CLI arg.
CMD ["sh", "-c", "uvicorn app:app --host 0.0.0.0 --port ${PORT:-8000}"]
