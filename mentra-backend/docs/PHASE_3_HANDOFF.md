# Phase 3 Handoff — Backend + Database + API

Status: **Implemented and verified end-to-end.** Backend runs, all 14
automated tests pass, and a live curl walkthrough of the entire user journey
(signup → onboarding → goal → assessment → roadmap → tasks → chat/extraction
→ dashboard → adaptive adjustment → notifications) against the running
server succeeded using the exact request shapes the real frontend sends.
The frontend build (`npm run build`) also succeeds against the updated
`api/client.js`.

## 1. Backend structure

See `backend/README.md` for the full tree. Modular monolith, one module per
Architecture §7/§9 group, mirroring the folder plan in Architecture §17
almost exactly (only addition: `core/` for config/security/errors/shared
resolvers, and `docs/` for this audit).

## 2. Database schema

All 13 entities from Architecture §8 are implemented as SQLAlchemy models in
`app/models/models.py`, with foreign keys, cascades, and indexes on every
foreign key used for per-user filtering. String UUID primary keys throughout
(portable across SQLite and Postgres). `Task.status` and
`PlanAdjustment.status` are constrained to the exact enums from FR-9 and
§13 respectively (validated in the router layer, not just by convention).

User-data isolation: every query in every router filters by
`Task.user_id`/`Goal.user_id`/etc. `== current_user.id`, or walks the
relationship chain to the owning user (e.g. milestone → roadmap → goal →
user) and raises 403/404 on mismatch. Verified by two dedicated tests
(`test_task_ownership_protection`, `test_cross_user_isolation_for_adjustment`).

## 3. API endpoints

Exactly the list in Architecture §9 / Phase 2 §G, plus `GET /goals` and
`GET /goals/:id` (specified in §9, not currently called by the frontend but
implemented for completeness and future screens):

```
POST   /auth/signup
POST   /auth/login
POST   /auth/logout
GET    /profile
PUT    /profile
POST   /onboarding
POST   /goals
GET    /goals
GET    /goals/{goal_id}
GET    /goals/{goal_id}/assessment
GET    /goals/{goal_id}/roadmap
PUT    /milestones/{milestone_id}
GET    /tasks
PUT    /tasks/{task_id}/status
GET    /conversations/{conversation_id}/messages
POST   /conversations/{conversation_id}/messages
GET    /progress/summary
GET    /plan-adjustments
GET    /plan-adjustments/{adjustment_id}
POST   /plan-adjustments/{adjustment_id}/respond
GET    /notifications
PUT    /notifications/{notification_id}/read
GET    /health
```

`goal_id` and `conversation_id` accept the literal value `"current"` as an
alias for the signed-in user's single active goal / conversation (see
contract audit, deviation #2).

## 4. Request/response schemas

All defined in `app/schemas/schemas.py` (Pydantic v2, `from_attributes=True`
for ORM→JSON). Field names match Architecture §8 exactly, since the frontend
binds to those field names directly (Phase 2 §J final note).

## 5. Authentication flow

`POST /auth/signup` and `/login` return `{token, user}`. Token is a JWT
(HS256, 60 min expiry by default, configurable via `JWT_EXPIRES_MINUTES`),
signed with `JWT_SECRET` from the environment. Passwords are hashed with
PBKDF2-HMAC-SHA256 (260k iterations, random salt) — deliberately not bcrypt,
to avoid a native-extension build dependency in restricted install
environments; equally safe for this MVP's threat model. Protected routes
depend on `get_current_user` (`app/auth/dependencies.py`), which decodes the
bearer token and loads the user or raises 401. `/auth/logout` is a no-op
(stateless JWT) that returns `{ok:true}` to match the existing frontend call
shape — a token-blacklist can be added later without changing the contract.

## 6. Frontend ↔ backend integration status

**Done.** `src/api/client.js`'s `USE_MOCKS` now defaults to `false` and reads
`VITE_API_BASE_URL` (defaults to `http://localhost:8000`); the pre-existing
`realRequest` function needed no changes — it already sent exactly the
requests this backend expects (`Authorization: Bearer <token>`, JSON body).
Two singleton placeholder ids were switched from `"g1"`/`"c1"` to `"current"`
(see contract audit). Mock layer is untouched and still reachable by setting
`VITE_USE_MOCKS=true`, per the phase instructions ("keep it available as a
fallback/development reference"). `npm run build` succeeds with these
changes; a full backend+frontend manual run was not executed in this
environment (no browser available here), but the identical HTTP calls the
frontend makes were exercised directly against the live server and returned
exactly the shapes each screen/context expects.

## 7. AI orchestration interfaces

`app/ai_orchestration/provider.py` — `AIProvider` abstract base class:

```python
generate_assessment(profile: dict, goal: dict) -> AssessmentResult
generate_roadmap(assessment: AssessmentResult, profile: dict, goal: dict) -> RoadmapResult
generate_daily_tasks(milestone: dict, profile: dict, remaining_days: int) -> list[TaskPlan]
process_conversation(message: str, history: list, open_tasks: list) -> ConversationResult
generate_adaptive_adjustment(recent_extractions: list, snapshot_trend: dict, roadmap: dict) -> AdjustmentResult
```

`get_ai_provider()` is the single factory function every caller uses — Phase
4 changes its body to return a real provider; no caller changes.

## 8. Exact input/output per AI function (for Phase 4)

| Function | Input | Must return |
|---|---|---|
| `generate_assessment` | `profile` dict (routine, available_time, preferred_schedule, existing_knowledge, constraints[], preferences[]); `goal` dict (title, current_level, target_date) | `AssessmentResult(ai_summary: str, difficulty_level: str, recommended_workload: str, raw: dict)` |
| `generate_roadmap` | `assessment` (the `AssessmentResult` just generated); `profile` dict; `goal` dict | `RoadmapResult(milestones: list[MilestonePlan(title, target_date, order_index, tasks_preview: list[str])])` |
| `generate_daily_tasks` | `milestone` dict (title, tasks_preview); `profile` dict; `remaining_days: int` | `list[TaskPlan(title, description, priority, estimated_duration, due_date)]` |
| `process_conversation` | `message: str`; `history: list[{sender, content}]` (last 6 messages); `open_tasks: list[{id, title}]` | `ConversationResult(reply: str, task_id: str\|None, status: str\|None [must be a valid Task status if set], reason: str, availability_changed: bool, difficulty_flag: bool, topic_reference: str\|None, sentiment: str)` |
| `generate_adaptive_adjustment` | `recent_extractions: list`; `snapshot_trend: dict` (tasks_missed, consistency_pct, total); `roadmap: dict` (id) | `AdjustmentResult(trigger_reason, change_summary, expected_effect, change_payload: dict, current_plan: list[str], proposed_plan: list[str], confidence: float)` |

All fields are validated/schema-checked by the caller before being persisted
(NFR-9) — e.g. `process_conversation`'s `status` is rejected if it isn't one
of the five valid `Task` statuses, and `task_id` is rejected if it doesn't
belong to the current user or is already completed.

## 9. What Phase 4 needs to implement

1. A real `AIProvider` subclass (e.g. `ClaudeAIProvider` / `GeminiAIProvider`)
   implementing the five methods above against a live model, reading
   `AI_API_KEY`/`AI_PROVIDER` from settings.
2. Update `get_ai_provider()` to branch on `settings.AI_PROVIDER` and return
   the real provider when configured, stub otherwise (keeps local dev/tests
   working without a key).
3. Real prompts for each function — the stub's docstrings and dataclass
   shapes are the exact contract to target.
4. Optional: persist `ProgressSnapshot` rows on a schedule instead of
   computing `/progress/summary` live, once real usage volume justifies it.
5. Optional: populate `tasks_preview` / generate real tasks for milestones
   2+ as the user progresses (currently only the first/current milestone is
   seeded with tasks at goal-creation time, matching "daily tasks derived
   from the roadmap's *current* week/milestone" in FR-7).

## 10. Known issues / intentional MVP simplifications

- Adaptive planning's `apply_adjustment` (on accept) does a simple,
  deterministic patch (reschedules up to 2 upcoming pending tasks for
  `reduce_workload`; acknowledges but doesn't yet compress the timeline for
  `accelerate`). Full timeline math is future scope per Architecture §8's
  note on roadmap versioning.
- `/progress/summary`'s `daily` and `monthly` blocks omit `goal_progress_pct`/
  `trend`/`streak_days` (`null`) — only `weekly` carries them, matching the
  existing frontend's mock data shape and `Dashboard.jsx`'s actual field
  reads exactly. This looks asymmetric but is intentional (see contract
  audit).
- Milestones beyond the first have no seeded tasks until Phase 4's real
  daily-task generation (or a scheduled job) populates them as the user
  progresses through the roadmap.
- No token refresh/blacklist endpoint; 60-minute JWT expiry is a flat
  session length for MVP.
- No rate limiting or request throttling (explicitly out of scope per
  Architecture §16's "avoid enterprise complexity").

## 11. Recommended next steps

1. Run `backend/` and `frontend/` side by side locally (`uvicorn` on :8000,
   `vite` on :5173) and click through the full flow in a browser to catch
   any visual/runtime issue this environment's curl-only verification
   couldn't (no browser available here).
2. Point `DATABASE_URL` at a real Postgres instance before any shared/staging
   deployment — SQLite is dev-only.
3. Start Phase 4: implement the real `AIProvider`, using the stub's exact
   method signatures and the input/output table in §8 above as the spec.
4. Set a real `JWT_SECRET` (not the `.env.example` placeholder) in any
   non-local environment.
