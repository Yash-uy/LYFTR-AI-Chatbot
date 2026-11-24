# 

# \# LYFTR AI — LLM Chatbot with Key Failover and Response Caching

# 

# A React + FastAPI chatbot using LiteLLM, an ordered API-key pool, LiteLLM response caching, and SQLite-backed multi-turn sessions.

# 

# \## Live URLs

# 

# \- Frontend: https://lyftr-ai-chatbot-dusky.vercel.app

# \- Backend: https://lyftr-ai-backend-3kev.onrender.com

# \- Health check: https://lyftr-ai-backend-3kev.onrender.com/health

# \- GitHub: https://github.com/Yash-uy/LYFTR-AI-Chatbot

# 

# The frontend and backend are publicly accessible. The Render Free backend may take some time to respond after inactivity because free services can spin down.

# 

# \## Run locally: with Docker and without

# 

# \### Prerequisites

# 

# \- Docker Desktop with Docker Compose, or Python 3.11+ and Node.js 20+.

# \- At least two valid Google AI Studio API keys. API key values must remain private.

# 

# \### Docker (required local path)

# 

# 1\. Copy `.env.example` to `.env`.

# 2\. Set `LLM\_API\_KEYS` to two comma-separated valid Google AI Studio API keys.

# 3\. Keep `.env` private and never commit it.

# 4\. Keep `VITE\_API\_URL=http://localhost:8000` for local Docker use.

# 5\. Run `make up` from the repository root.

# 6\. Open `http://localhost:3000`.

# 7\. Check `http://localhost:8000/health`.

# 8\. Stop with `make down`.

# 

# Docker Compose mounts a named volume at `/data`, preserving `/data/app.db` across container restarts.

# 

# \### Without Docker

# 

# Backend (terminal 1):

# 

# ```bash

# cd backend

# python -m venv .venv

# \# Windows PowerShell:

# .venv\\Scripts\\Activate.ps1

# \# macOS/Linux:

# source .venv/bin/activate

# pip install -r requirements.txt

# \# Configure LLM\_API\_KEYS, DATABASE\_URL and ALLOWED\_ORIGINS.

# uvicorn app.main:app --reload --port 8000

# ```

# 

# Frontend (terminal 2):

# 

# ```bash

# cd frontend

# npm install

# \# Windows PowerShell:

# $env:VITE\_API\_URL="http://localhost:8000"

# \# macOS/Linux:

# VITE\_API\_URL=http://localhost:8000 npm run dev -- --port 3000

# ```

# 

# The frontend creates a fresh session ID on each page load. It sends only the new user message; the backend rebuilds the model prompt from stored SQLite history.

# 

# \## Design decisions: key fallback, caching, SQLite session storage

# 

# \- \*\*Key fallback:\*\* `LLM\_API\_KEYS` is parsed in order into `key\_1`, `key\_2`, etc. The gateway attempts keys sequentially for each configured model. Failed provider attempts advance to the next key/model. The response exposes only the key identifier, never the secret.

# \- \*\*Failure simulation:\*\* When `ENABLE\_FAILURE\_SIMULATION=true`, `X-Simulate-Failure` can simulate `key\_1=429`, `key\_1=429,key\_2=500`, or `\*=429`. The hook skips the selected key for that request without modifying real keys.

# \- \*\*Caching:\*\* LiteLLM's built-in local cache is enabled. The explicit cache identity is derived from the model and the full system/user/assistant message list. A cache hit reports `resolution\_source: LLM\_CACHE`, `key\_id: null`, and `fallback\_attempts: 0`.

# \- \*\*SQLite:\*\* The `messages` table stores conversation messages. A `sessions` table retains the optional per-session system prompt. Docker mounts a named volume at `/data`; the database URL is configured through `DATABASE\_URL`.

# \- \*\*Failure safety:\*\* Messages are written only after successful inference. Failed 422/503 requests do not add messages to session history. API errors use JSON `detail` responses.

# \- \*\*Token counts:\*\* Input/output token counts are read from the provider/LiteLLM response for each completion, not accumulated across the conversation.

# 

# \### Deployment storage limitation

# 

# The local Docker configuration uses a named persistent volume mounted at `/data`.

# 

# The deployed Render Free service uses `/tmp/app.db` because persistent disks are not included in the selected free setup. This filesystem is ephemeral: database contents can be lost when the service restarts, redeploys, or spins down. Therefore, deployed SQLite history is not guaranteed to persist. The local Docker configuration provides persistent SQLite storage.

# 

# The LiteLLM local cache is also instance-local and may be cleared when the service restarts.

# 

# \## Verification: how to see failover, cache hits and per-message token usage

# 

# 1\. Configure at least two valid API keys and set `ENABLE\_FAILURE\_SIMULATION=true`.

# 2\. Send a new chat request. Metadata should show `LIVE\_INFERENCE`, the key identifier, and request-specific token counts.

# 3\. Repeat the identical first message with a different `session\_id`. LiteLLM should return `LLM\_CACHE`; the reply and token usage should match, with `key\_id: null`.

# 4\. Send a fresh message with `X-Simulate-Failure: key\_1=429`. It should return a real model answer using `key\_2`. Check `fallback\_attempts` in response metadata; it can be greater than 1 because it counts failed provider/model attempts.

# 5\. Send a fresh message with `X-Simulate-Failure: \*=429`. It should return HTTP 503 with `{"detail":"all providers unavailable"}`.

# 6\. Check `GET /sessions/{session\_id}/messages`. It returns messages oldest-first without the system prompt. A failed request should not create a session or add messages.

# 7\. Run backend tests:

# 

# ```bash

# cd backend

# python -m pytest -q

# ```

# 

# The automated tests stub the provider boundary for deterministic API tests. Real-provider cache and failover checks require two working API keys.

# 

# Example curl:

# 

# ```bash

# curl -X POST http://localhost:8000/chat \\

# &#x20; -H 'Content-Type: application/json' \\

# &#x20; -H 'X-Simulate-Failure: key\_1=429' \\

# &#x20; -d '{"session\_id":"fallback-demo","message":"Explain failover in one sentence."}'

# ```

# 

# \## Setup Used

# 

# \- Editor: Visual Studio Code.

# \- AI tools: ChatGPT-assisted implementation and debugging.

# \- Backend: Python 3.11, FastAPI, LiteLLM, SQLAlchemy and SQLite.

# \- Frontend: React 18 and Vite.

# \- Containerization: Docker and Docker Compose.

# \- Backend hosting: Render Free.

# \- Frontend hosting: Vercel Hobby.

# \- Source control: Git and GitHub.

# 

# \## Bonus features (if any)

# 

# \- Optional per-session system prompt persisted between turns.

# \- Responsive dark interface with connection status, suggestion prompts and readable API errors.

# \- Database index on `(session\_id, id)` for ordered session-history reads.

# \- Safe provider diagnostics that log model, key identifier, status and exception type without exposing API key values.

# 

# \## Deployment checklist

# 

# \- Backend deployed as a Docker web service.

# \- Frontend deployed as a Vercel static site.

# \- `VITE\_API\_URL` configured to the deployed backend URL.

# \- `ALLOWED\_ORIGINS` configured to the exact frontend origin.

# \- Two API keys configured in the backend environment.

# \- `DATABASE\_URL` configured for the deployment environment.

# \- `/health`, `/chat` and `/sessions/{session\_id}/messages` verified.

# \- Cache hit and simulated failover verified against the live service.

# \- `.env`, API keys and other secrets excluded from the public repository.

# \- Note: Render Free does not provide persistent SQLite storage in this deployment; see Deployment storage limitation above.



