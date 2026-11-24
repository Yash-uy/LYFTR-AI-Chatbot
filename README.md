# LYFTR AI — LLM Chatbot with Key Failover and Response Caching

A React + FastAPI chatbot using LiteLLM, an ordered API-key pool, LiteLLM local response caching, and SQLite-backed multi-turn sessions.

## Live URLs

- Frontend: **Not deployed yet** — add the public URL after deployment.
- Backend: **Not deployed yet** — add the public URL after deployment.
- Health check: `<BACKEND_URL>/health`

Do not submit placeholder URLs. The live services must be deployed and reachable without login.

## Run locally: with Docker and without

### Prerequisites

- Docker Desktop with Docker Compose, or Python 3.11+ and Node.js 20+.
- At least two valid Google AI Studio API keys. The application never stores or displays key values in responses.

### Docker (required local path)

1. Copy `.env.example` to `.env`.
2. Set `LLM_API_KEYS` to two comma-separated valid Google AI Studio keys. Keep `.env` private.
3. Keep `VITE_API_URL=http://localhost:8000` for local Docker use.
4. Run `make up` from the repository root.
5. Open `http://localhost:3000`; check `http://localhost:8000/health`.
6. Stop with `make down`. The named `lyftr_data` volume preserves `/data/app.db`.

### Without Docker

Backend (terminal 1):

```bash
cd backend
python -m venv .venv
# Windows PowerShell: .venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
# Set LLM_API_KEYS, DATABASE_URL=sqlite:///./app.db, ALLOWED_ORIGINS=http://localhost:3000
uvicorn app.main:app --reload --port 8000
```

Frontend (terminal 2):

```bash
cd frontend
npm install
# Windows PowerShell: $env:VITE_API_URL="http://localhost:8000"
# macOS/Linux: VITE_API_URL=http://localhost:8000
npm run dev -- --port 3000
```

The frontend creates a fresh session ID on each page load. It sends only the new user message; the backend rebuilds the model prompt from the stored SQLite history.

## Design decisions: key fallback, caching, SQLite session storage

- **Key fallback:** `LLM_API_KEYS` is parsed in order into `key_1`, `key_2`, etc. The gateway attempts keys sequentially. Retryable rate-limit, quota, authentication and provider/server errors advance to the next key. The response exposes only the key identifier, never the secret.
- **Failure simulation:** when `ENABLE_FAILURE_SIMULATION=true`, `X-Simulate-Failure` can simulate `key_1=429`, `key_1=429,key_2=500`, or `*=429` for one request. The hook does not exhaust or modify real keys. It is intended for the required demonstration and should be disabled when no longer needed.
- **Caching:** LiteLLM's built-in local cache is enabled. The explicit cache identity is derived from model plus the full system/user/assistant message list. The LiteLLM response cache retains the original response usage; cache metadata reports `key_id: null` and `fallback_attempts: 0` when LiteLLM marks a cache hit.
- **SQLite:** the `messages` table is created at startup. A small `sessions` table retains the optional per-session system prompt. Docker mounts a named volume at `/data`; the database URL is configured by `DATABASE_URL`.
- **Failure safety:** a user/assistant pair is written only after successful inference. Failed 422/503 requests do not add history. API errors use JSON `detail` messages.
- **Token counts:** input/output counts are read from the provider/LiteLLM response for that completion, not accumulated across the conversation.

## Verification: how to see failover, cache hits and per-message token usage

1. Run the backend with two valid keys and `ENABLE_FAILURE_SIMULATION=true`.
2. Send a new chat request normally. The metadata should show `LIVE_INFERENCE`, `key_1`, and request-specific token counts.
3. Repeat the same first message with a different `session_id`. With identical model and full prompt, LiteLLM should return `LLM_CACHE`; the reply and token usage should match, and `key_id` should be null. Cache hit detection is based on LiteLLM response metadata, not a UI-only label.
4. Send a fresh message with header `X-Simulate-Failure: key_1=429`. It should return a real model answer with `key_id: key_2` and check `fallback_attempts` in the response metadata. It counts failed provider/model attempts before success and may be greater than 1.
5. Send a fresh message with `X-Simulate-Failure: *=429`. It should return HTTP 503 and `{"detail":"all providers unavailable"}`. The failed request must not appear in history.
6. Check `GET /sessions/{session_id}/messages`; it returns messages oldest-first without the system prompt.
7. `cd backend && python -m pytest -q` runs the backend API contract tests. The automated tests stub the provider boundary for deterministic API tests; real-provider cache/failover checks still require two working keys.

Example curl:

```bash
curl -X POST http://localhost:8000/chat \
  -H 'Content-Type: application/json' \
  -H 'X-Simulate-Failure: key_1=429' \
  -d '{"session_id":"fallback-demo","message":"Explain failover in one sentence."}'
```

## Setup Used

- Editor: VS Code (project is structured for local development).
- AI tools: ChatGPT-assisted implementation; review and verification should be completed before submission.
- Runtime: Python 3.11, FastAPI, LiteLLM, SQLAlchemy, SQLite, React 18, Vite, Node 20 and Docker Compose.

## Bonus features (if any)

- Optional per-session system prompt persisted between turns.
- Responsive dark interface with connection status, suggestion prompts and readable API errors.
- Database index on `(session_id, id)` for ordered session-history reads.

## Deployment checklist

- Deploy the backend as a Docker web service with persistent storage mounted at `/data`.
- Set `DATABASE_URL=sqlite:////data/app.db`, configure two valid `LLM_API_KEYS`, set `LLM_MODEL`, and configure `ALLOWED_ORIGINS` to the exact frontend origin.
- Set `ENABLE_FAILURE_SIMULATION=true` only when failure simulation is needed for the demo. Disable it in normal production use.
- Deploy the frontend as a static site or Docker service. Set build-time `VITE_API_URL` to the deployed backend base URL, then rebuild and redeploy.
- Verify `/health`, `/chat`, and `/sessions/{session_id}/messages` on the public backend.
- Verify browser CORS from the public frontend.
- Update the Live URLs section with the actual deployed frontend and backend URLs after deployment.
- Never commit `.env`, API keys, or other secrets to the public repository.


