# TrueCivic

TrueCivic surfaces Canadian parliamentary data, conversational insights, and retrieval-augmented bill summaries. The stack combines Django, PostgreSQL, Qdrant, and a modern Next.js frontend.

## Overview

- **Backend:** Django 5.2 project (`parliament/`) with REST endpoints and ingestion pipelines.
- **Knowledge base:** Qdrant vector store populated by `RagIngestor` (`parliament/rag/ingest.py`).
- **Embeddings:** OpenAI `text-embedding-3-large` via `src/services/ai/embedding_service.py`.
- **Frontend:** Next.js 14 app in `frontend/` with chat and bill-summary pages.
- **Deployment:** Docker image driven by `uv`, Railway Postgres, and optional Kafka orchestration utilities.

## Prerequisites

- Python 3.13 with [uv](https://github.com/astral-sh/uv) (automatic in Docker).
- Node.js 20+ and pnpm/npm for the frontend.
- Access to Railway service credentials (see `railway/env/`).
- OpenAI API key with embedding quota.
- Qdrant endpoint (cloud or self-hosted) reachable from the app.

## Environment Setup

1. Copy `.env.example` to `.env` and supply at least:
   - `DJANGO_SETTINGS_MODULE=parliament.settings`
   - `DATABASE_URL` (Railway internal) and `DATABASE_PUBLIC_URL` (proxy) – tests use the public proxy
   - `OPENAI_API_KEY`
   - `EMBEDDING_MODEL=text-embedding-3-large`
   - Qdrant variables: `QDRANT_URL`, `QDRANT_API_KEY`, `QDRANT_COLLECTION`
2. Install backend dependencies:

   ```bash
   uv sync --frozen --no-dev
   ```

3. Install frontend dependencies:

   ```bash
   cd frontend
   npm install
   ```

4. (Optional) Link Railway locally:

   ```bash
   railway link --project <project-id> --environment production
   railway variables download --service Postgres
   ```

## Running Locally

- Start Django (hot reload):

  ```bash
  uv run python manage.py runserver
  ```

- Start Next.js dev server:

  ```bash
  cd frontend
  npm run dev
  ```

Visit `http://localhost:3000` for the chat UI and `http://localhost:3000/bills/<id>` for bill summaries.

## Data Ingestion & Integrity

- Trigger RAG ingestion (Hansards and bills):

  ```bash
  uv run python manage.py shell -c "from parliament.rag.ingest import RagIngestor; from src.services.ai.embedding_service import EmbeddingService, EmbeddingConfig; RagIngestor(EmbeddingService(EmbeddingConfig.from_env())).sync_recent_bills()"
  ```

- Verify embeddings and Qdrant payloads (also run on container startup):

  ```bash
  uv run python manage.py verify_embeddings --jurisdiction canada-federal --language en
  ```

The integrity command backfills missing embeddings and reindexes absent Qdrant points, logging a summary per scope.

## API Endpoints

- `POST /api/rag/context/` – hybrid retrieval for chat prompts.
- `GET /api/rag/chunks/` – summary chunks filtered by jurisdiction, language, and optional `source_identifier` (for example `bill:<id>`).

Requests require matching jurisdiction and language parameters; see `parliament/rag/api_views.py` for details.

## Frontend Integration

- `frontend/lib/rag.ts` fetches chunk summaries with optional endpoint overrides (`NEXT_PUBLIC_RAG_CHUNKS_ENDPOINT`).
- `frontend/components/bill-summary-panel.tsx` renders bill insight cards.
- Bill pages live at `frontend/app/bills/[identifier]/page.tsx` and link back to the chat experience.

## Testing

1. Ensure `DATABASE_PUBLIC_URL`, `PGHOST`, and `PGPORT` point to a reachable Railway proxy (for example `shinkansen.proxy.rlwy.net:55535`).
2. Run the targeted suite:

   ```bash
   uv run python manage.py test parliament.rag
   ```

API tests expect HTTPS; either supply `SECURE_SSL_REDIRECT=False` in your test settings override or keep requests `secure=True` as implemented.

Frontend tests are not yet present; consider adding Storybook or Playwright coverage for UI regression.

## Deployment Notes

- `Dockerfile` uses `uv` for deterministic builds, collects static assets, and runs migrations followed by `verify_embeddings` before starting Gunicorn.
- Configure OpenAI and Qdrant secrets in the hosting environment prior to rollout; the startup integrity check will skip gracefully if they are absent.
- Railway Postgres variables live under `railway/env/`. Use `DATABASE_URL` (internal) for production workloads.

## Troubleshooting

- **Embedding errors (HTTP 400):** ensure chunking guards are intact and `MAX_EMBEDDING_TOKENS` aligns with OpenAI limits.
- **Qdrant connectivity:** confirm `prefer_grpc=False` and timeout values in `QdrantConfig`. Use `scripts/manual/qdrant_smoke_test.py` for diagnostics.
- **Test DB auth issues:** export the public proxy credentials before running `manage.py test`.

## License

Code is released under the GNU Affero General Public License v3 (AGPLv3). Any derived site must not use the TrueCivic name or logo without explicit permission. See `LICENSE` for full terms.
