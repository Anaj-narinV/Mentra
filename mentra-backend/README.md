# Mentra Backend — Phase 3

FastAPI + SQLAlchemy + JWT backend implementing the Requirements & Architecture
Foundation (Phase 1) and serving the existing Phase 2 frontend contract
exactly (see `docs/FRONTEND_BACKEND_CONTRACT_AUDIT.md` in the delivered
package for the full audit).

## Setup

```bash
cd backend
python -m venv venv && source venv/bin/activate   # optional but recommended
pip install -r requirements.txt
cp .env.example .env                               # edit if needed
uvicorn app.main:app --reload --port 8000
```

The API is now at `http://localhost:8000` (interactive docs at `/docs`).
`.env` is loaded automatically on startup (via `python-dotenv`) — no extra
flags needed. SQLite (`mentra.db`) is created automatically on first run —
no migration step needed for local dev. To use Postgres instead, set
`DATABASE_URL` in `.env` (e.g. `postgresql://user:pass@localhost:5432/mentra`)
— every model and query here is dialect-agnostic SQLAlchemy, so no code
changes are required.

To use a real AI provider instead of the deterministic stub, set in `.env`:
`AI_PROVIDER=claude` or `AI_PROVIDER=gemini`, `AI_API_KEY=<your key>` (for
whichever provider you chose), and optionally `AI_MODEL` (defaults to
`claude-sonnet-5` for Claude, `gemini-3.5-flash` for Gemini). Never commit a
real key — `.env` is for local dev only; a real deployment should set these
as actual platform environment variables instead.

## Running the tests

```bash
pytest tests/ -v
```

14 end-to-end tests cover the full user journey (signup → onboarding → goal
→ assessment → roadmap → tasks → chat/extraction → dashboard → adaptive
adjustment → notifications) plus cross-user data-isolation checks.

## Project structure

```
backend/
├── app/
│   ├── auth/              # signup, login, logout, JWT dependency
│   ├── profile/           # profile + onboarding
│   ├── goals/              # goal creation (triggers assessment+roadmap), retrieval
│   ├── roadmap/             # roadmap + milestone endpoints
│   ├── tasks/                # task list + status update
│   ├── conversation/          # chat messages + progress extraction pipeline
│   ├── progress/                # dashboard aggregation
│   ├── adaptation/                # plan-adjustment endpoints + Layer 1/2 engine
│   ├── notifications/              # in-app notifications
│   ├── ai_orchestration/            # AIProvider interface + StubAIProvider (Phase 4 swaps this in)
│   ├── models/                       # SQLAlchemy models (Architecture §8)
│   ├── schemas/                       # Pydantic request/response schemas
│   ├── database/                       # engine/session
│   ├── core/                            # config, security, errors, "current" alias resolvers
│   └── main.py                           # app entrypoint, router registration
└── tests/
    └── test_e2e_flow.py                  # full-journey + isolation tests
```

## Connecting the existing frontend

The frontend's `src/api/client.js` already contains a full `realRequest`
implementation — it just needed the mock switch flipped. That's done:

- `VITE_USE_MOCKS` (default `false`) — set to `"true"` to fall back to the
  original in-memory mocks for frontend-only development.
- `VITE_API_BASE_URL` (default `http://localhost:8000`) — where this backend
  is running.

Two hardcoded single-goal/single-conversation placeholder IDs in the
approved Phase 2 UI (`Roadmap.jsx`'s `GOAL_ID = "g1"`, `ChatContext.jsx`'s
`CONVERSATION_ID = "c1"`) were updated to `"current"` — the backend resolves
that literal segment to the signed-in user's one active goal / conversation
server-side (see `app/core/resolvers.py`), so the UI itself didn't need any
deeper changes. Real ids (e.g. straight after `POST /goals`) work everywhere
too.

## AI Orchestration boundary (for Phase 4)

`app/ai_orchestration/provider.py` defines the `AIProvider` interface and a
deterministic `StubAIProvider` that the whole app runs against today. Phase
4 implements a real provider against this exact interface — see the handoff
doc for the precise input/output contract per function.
