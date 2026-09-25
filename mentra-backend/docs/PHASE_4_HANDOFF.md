# Phase 4 Handoff — AI & Adaptive Intelligence

Status: **Real AI provider implemented behind the existing `AIProvider`
interface. No API contract, database schema, or frontend code changed.**
Full pytest execution could not be performed in the implementation sandbox
(no network access — see §7); logic was verified by static compilation of
every file plus a manual, line-by-line execution of the new provider's code
paths against a hand-built stand-in for the `anthropic` SDK. Run `pytest` for
real in an environment with network access before treating this as verified
(see §9).

## 1. What changed, and why so little

Per the Phase 4 brief's explicit instructions ("do not rebuild", "preserve
existing architecture", "make the smallest necessary changes"), and because
Phase 3 already built the AI boundary, the adaptation trigger rules, the
human-in-the-loop approval flow, and per-user data isolation correctly —
Phase 4 is almost entirely additive:

- One new file implements the real provider behind the interface Phase 3
  already defined (`AIProvider` in `provider.py`).
- One new file holds prompts, out of route functions, as instructed.
- `get_ai_provider()`'s body changed (as `PHASE_3_HANDOFF.md` §9 said it
  would) — no caller changed.
- `adaptation/service.py` changed to pass *real* context to the AI (it was
  always passing `recent_extractions=[]`) and to add the one deterministic
  rule Phase 1's Architecture §13 specifies that Phase 3's implementation
  had not yet coded (repeated-difficulty).
- One new file + a two-line router change close a gap Phase 3 explicitly
  flagged as unfinished in its own handoff doc (§9 item 5): milestones past
  the first never got tasks.
- Zero frontend files changed. Zero database migrations. Zero API route
  signatures changed.

## 2. Files created

| File | Purpose |
|---|---|
| `app/ai_orchestration/prompts.py` | Prompt templates (system + user) for all 5 AI functions. Pure string builders — no I/O, trivially unit-testable. |
| `app/ai_orchestration/claude_provider.py` | `ClaudeAIProvider(AIProvider)` — the real implementation, calling the Anthropic Messages API and validating every field of every response before it's turned into the same dataclasses (`AssessmentResult`, `RoadmapResult`, etc.) the stub already returns. |
| `app/tasks/service.py` | `ensure_current_milestone_tasks()` — Daily Task Intelligence: generates tasks for a milestone that has none, and advances the roadmap to the next milestone once the current one's tasks are all resolved. |
| `tests/test_ai_provider.py` | Unit tests for `ClaudeAIProvider`'s JSON parsing, retry-then-fail behavior, and output validation/sanitization. Fakes the `anthropic` SDK (see §7) so it needs no network or API key. |
| `tests/test_adaptive_intelligence.py` | Integration tests (real `TestClient`, own sqlite file): conversation extraction variety, the new repeated-difficulty rule, milestone continuation, and user isolation. Runs against the stub provider by default, exercising the exact same router/service validation code a real Claude response flows through. |
| `docs/PHASE_4_HANDOFF.md` | This document. |

## 3. Files modified

| File | Change |
|---|---|
| `app/ai_orchestration/provider.py` | `get_ai_provider()` now branches on `settings.AI_PROVIDER`/`AI_API_KEY`, returning `ClaudeAIProvider` when configured, `StubAIProvider` otherwise (including if the real provider fails to *initialize* — e.g. missing dependency — so a bad config degrades to the stub instead of crashing the app at import time). |
| `app/core/config.py` | Added `AI_MODEL` setting (env var, defaults to `claude-sonnet-5`). |
| `app/adaptation/service.py` | `check_and_propose_adjustment` now: (a) queries the last 14 days of `ProgressExtraction` rows and passes them to the AI as `recent_extractions` (was `[]`); (b) passes the active roadmap's milestones as context (was just `{"id": ...}`); (c) adds Rule 4 — repeated difficulty on the same topic (Architecture §13) — as a fourth deterministic trigger alongside the existing three. `apply_adjustment` now also handles the `reschedule` and `flag_support` `change_payload.type` values the richer AI output can produce (previously only `reduce_workload`/`accelerate` were handled; anything else was a silent no-op, which is still the safe fallback for a type it doesn't recognize). |
| `app/tasks/router.py` | `GET /tasks` now calls `ensure_current_milestone_tasks()` before querying — see §5. |
| `app/main.py` | Version bump / description string only (`0.3.0` "Phase 3" → `0.4.0` "Phase 4"). Cosmetic. |
| `requirements.txt` | Added `anthropic>=0.40.0,<1.0.0`. |
| `.env` / `.env.example` | Added `AI_MODEL`; expanded the `AI_PROVIDER`/`AI_API_KEY` comment to explain the fallback behavior. `.env` itself is left at `AI_PROVIDER=stub` since no real key is available in this environment — set it to `claude` with a real key before deploying. |

## 4. AI provider integration

- **Provider**: Anthropic Claude, via the official `anthropic` Python SDK,
  called only from `claude_provider.py` — the single choke point Architecture
  §7 requires. `get_ai_provider()` remains the one factory every module
  calls; swapping vendors later means writing a new `*_provider.py` file and
  changing one `if` branch, exactly as `PHASE_3_HANDOFF.md` §9 anticipated.
- **Model**: `AI_MODEL` env var, defaulting to `claude-sonnet-5`.
- **Structured output**: every prompt instructs "return ONLY a JSON object"
  with an exact key list; `_complete_json()` strips markdown code fences,
  `json.loads`s the result, and retries once with a sharper reminder if that
  fails. Two failed attempts raise `AIProviderError`, which every existing
  caller (`goals/service.py`, `conversation/router.py`,
  `adaptation/service.py`) already catches as a broad `Exception` and turns
  into `AIUnavailableError` → HTTP 503 with a safe, generic message. No
  caller code needed to change for this.
- **Output validation** (NFR-9, "never blindly trust model output"), all in
  `claude_provider.py`:
  - Assessment: rejects an empty `ai_summary`.
  - Roadmap: rejects a missing/empty `milestones` list or a milestone
    without a title; fills in a safe default `tasks_preview` if missing.
  - Daily tasks: skips individual malformed task entries rather than
    failing the whole batch; normalizes an invalid `priority` to `"medium"`;
    rejects only if *every* entry was unusable.
  - Conversation: **the important one** — `task_id` is rejected unless it's
    one of the `open_tasks` ids actually given to the model (defends against
    a hallucinated id even though the router re-validates ownership too);
    `status` is rejected unless it's one of the five real `Task` statuses;
    a `status` with no verified `task_id` is dropped. This is the concrete
    mechanism behind "if the user's message is ambiguous, do not invent a
    task update" — the prompt instructs the model to leave these null, and
    the provider layer enforces that even if the model doesn't comply.
  - Adaptive adjustment: rejects a missing `trigger_reason`/`change_summary`;
    clamps `confidence` to `[0,1]`; falls back an unrecognized
    `change_payload.type` to `"reduce_workload"`; never returns empty
    `current_plan`/`proposed_plan`.
- **Error handling**: every SDK call is wrapped; network errors, timeouts,
  and rate limits all become the same `AIProviderError` → 503 path. No
  provider exception text, stack trace, or key ever reaches the response
  body (`unhandled_error_handler` in `core/errors.py`, unchanged, already
  guarantees this for anything that isn't an `AppError`).
- **Security**: the provider only ever receives the small per-request dicts
  the existing callers already assemble (profile fields, goal fields, task
  titles, message text/history) — never passwords, JWTs, or another user's
  data. Verified by reading every call site; none was changed to pass
  anything new.

## 5. AI capabilities implemented

1. **Assessment** — `generate_assessment`: real prompt evaluates goal vs.
   profile (target outcome, current level, available time, routine,
   constraints, target date) and returns `ai_summary`,
   `difficulty_level`, `recommended_workload` (the exact fields
   `AssessmentOut`/`Assessment` require) plus extra fields
   (`strengths`, `gaps`, `risks`, `recommended_approach`) preserved only in
   `raw_ai_output` (the `Assessment.raw_ai_output` JSON column already
   existed for exactly this — "audit/debug" per Architecture §8) rather than
   invented as new top-level columns, per "do not invent unnecessary fields
   if the current contract does not support them."
2. **Roadmap generation** — `generate_roadmap`: 3–6 milestones, each with a
   title, optional target date, and a short list of concrete task titles,
   built from the assessment + profile + goal, matching `RoadmapResult`
   exactly.
3. **Daily task generation** — `generate_daily_tasks`, now actually invoked
   beyond the first milestone too (see §6 below) — realistic titles,
   descriptions, priority, and duration respecting the user's stated
   available time.
4. **Conversational progress understanding** — `process_conversation`: single
   AI call classifies the message (completed / partial / missed+reason /
   availability change / difficulty / reschedule request / general question)
   and produces both the user-facing reply and the structured extraction in
   one response, per Architecture §12.
5. **Structured progress extraction** — same call; validated fields are
   written to `ProgressExtraction` exactly as Phase 3's schema already
   defined; `raw_ai_output` was left as `{}` at the call site (unchanged —
   Phase 3's own choice, not part of this phase's scope) but could trivially
   be set to the parsed `dict` if a future phase wants that populated too.
6. **Progress analysis** — unchanged; `_trailing_task_stats` already computed
   this deterministically and correctly in Phase 3. Phase 4 only makes sure
   the *adaptive* layer now gets to see it (see next point).
7. **AI-assisted adaptive adjustment** — `generate_adaptive_adjustment`, now
   fed real recent extractions + real milestone context, producing a
   specific `trigger_reason` grounded in the actual data instead of a
   templated sentence, plus a `change_summary`, `expected_effect`, a
   machine-usable `change_payload`, and a before/after `current_plan`/
   `proposed_plan` diff.
8. **Human-in-the-loop approval** — **unchanged, by design**. Phase 3 already
   implemented this correctly end-to-end
   (`adaptation/router.py::respond_adjustment`, `PlanAdjustment.status`
   lifecycle, the frontend's `AdjustmentProposalCard`). Every adjustment is
   still written as `status="proposed"` and only patched into real
   tasks/milestones on explicit user accept. Nothing in Phase 4 touches this
   flow except that the *reason* text is now AI-generated instead of
   templated — the mechanism enforcing "never silently applied" is entirely
   Phase 3's, and it was correct.

## 6. Daily Task Intelligence — milestone continuation (new)

Phase 3's own handoff doc (§9, item 5) explicitly named this as unfinished:
only the goal's *first* milestone was ever seeded with tasks, at
goal-creation time. `GET /tasks` for a user who finished milestone 1 would
simply return nothing further.

`app/tasks/service.py::ensure_current_milestone_tasks()`, called at the top
of `GET /tasks`, closes this:

- If the current (`status="in_progress"`) milestone has zero `Task` rows,
  generate its first week via `ai.generate_daily_tasks`.
- If the current milestone's tasks are all resolved (none left `pending`),
  mark it `completed`, mark the next milestone `in_progress`, and generate
  *its* first week the same way.
- If the AI call fails, this is a **silent no-op** for that milestone (not a
  503) — a background/opportunistic generation failing must not break a
  read endpoint or corrupt anything; the milestone just stays empty until
  the next successful `GET /tasks`.
- Idempotent and cheap in the common case (a couple of indexed queries; no
  AI call at all once a milestone already has open tasks) — safe to run on
  every request rather than needing a scheduled job, consistent with
  Architecture §16's "avoid background job infrastructure" guidance for MVP.

**Known limitation** (documented rather than "fixed" with a schema change,
per the instruction to avoid unnecessary migrations): `Milestone` has no
column for the AI's original `tasks_preview` list from roadmap generation —
Phase 3 never persisted it (the roadmap endpoint derives `tasks_preview`
live from actual `Task` rows, see `FRONTEND_BACKEND_CONTRACT_AUDIT.md` note
#4). So when a later milestone's tasks are generated, the AI is re-seeded
with just the milestone's title rather than the richer preview titles
originally imagined for it at roadmap-creation time. The generated tasks are
still real, on-topic, and schema-valid — just slightly less specific than if
the original preview had been persisted. Adding a
`tasks_preview_seed JSON` column to `Milestone` would fix this cleanly; left
for Phase 5 as a small, optional, additive migration.

## 7. Environment variables

```
AI_PROVIDER=stub        # "stub" (default, no network) or "claude"
AI_API_KEY=              # required if AI_PROVIDER=claude — never hardcoded, never logged
AI_MODEL=claude-sonnet-5 # optional override
```

No other env vars changed. `.env` in this repo is left at `AI_PROVIDER=stub`
— there is no real API key available in the implementation environment, and
shipping a placeholder key would be worse than an explicit, working stub
fallback. Set `AI_PROVIDER=claude` and a real `AI_API_KEY` in any real
deployment's environment (not committed to source control).

## 8. Frontend changes

**None.** Confirmed by reading `ChatContext.jsx`, `client.js`, and
`api/index.js` directly: the frontend already sends/consumes exactly the
shapes every endpoint above returns (`{reply, task_update}`,
`AssessmentOut`, `RoadmapOut`, etc.). The real AI provider fills those same
fields with real content instead of templated stub content — the contract
Phase 2/3 built against didn't change.

## 9. Database changes

**None applied.** One optional future migration identified and documented,
not applied (§6, `Milestone.tasks_preview_seed`).

## 10. Tests

### Added
- `tests/test_ai_provider.py` — 20 unit tests covering: missing API key,
  valid response for each of the 5 functions, malformed-JSON-then-retry
  recovery, malformed-both-attempts failure, provider network-error failure,
  code-fence stripping, missing-required-field rejection for each function,
  priority/confidence/payload-type sanitization, and — most importantly —
  the "don't invent a task update" defenses (hallucinated `task_id`
  rejected, invalid `status` enum rejected, ambiguous message passthrough
  stays null). Uses a hand-built fake `anthropic` module (see below) so it
  needs no network access or real key.
- `tests/test_adaptive_intelligence.py` — 10 integration tests against a
  real `TestClient` + its own sqlite file, running the stub provider (no key
  in this environment): completed/partial/rescheduled/difficulty/
  general-question message classification end-to-end through the real
  router and validation code; the new repeated-difficulty (Rule 4) trigger;
  milestone continuation; and cross-user isolation of conversations and
  adjustments.

### Not removed
`tests/test_e2e_flow.py` (Phase 3's 14 tests) is untouched.

### Executed — **with an important caveat**

The implementation sandbox this work was done in has **no network access**
(`pip install` fails for every package, including ones already in
`requirements.txt` — `fastapi`, `sqlalchemy`, `pytest`, `anthropic`, etc. are
*all* unavailable, not just the new dependency) and no pre-existing
virtualenv. This means:

- ✅ Every modified/created `.py` file was checked with `python3 -m
  py_compile` — no syntax errors.
- ✅ `claude_provider.py`'s actual logic (JSON parsing, retry, every
  validation branch listed in §4) was manually executed end-to-end against
  a hand-built stand-in for the `anthropic.Anthropic` client (same approach
  `test_ai_provider.py` uses, run directly rather than via `pytest`) — all
  11 manual checks passed, output shown in-conversation.
- ❌ **`pytest` itself was never run** — not against the new tests, and not
  against the pre-existing `test_e2e_flow.py` — because `pytest` and every
  one of its runtime dependencies (`fastapi`, `sqlalchemy`, `httpx`, etc.)
  could not be installed in this sandbox.
- ❌ The full demo flow (signup → ... → notifications) was **not** clicked
  through or curled against a live server, for the same reason.

**Action required before this is considered done**: run, in an environment
with network access,

```
pip install -r requirements.txt
pytest -v
```

and separately, with a real key, confirm at least one live call per AI
function (`AI_PROVIDER=claude AI_API_KEY=... uvicorn app.main:app --reload`,
then repeat the curl walkthrough `PHASE_3_HANDOFF.md` §"Status" describes).
The unit tests in `test_ai_provider.py` validate the provider's parsing and
validation logic thoroughly, but they cannot catch a real prompt producing
subtly-wrong-but-valid JSON, real API latency/rate-limit behavior, or actual
Anthropic SDK version drift — only a live call can.

## 11. Known issues / intentional simplifications

- **Not run against the real stack** — see §10. This is the most important
  open item.
- `Milestone.tasks_preview_seed` not persisted — see §6.
- `ProgressExtraction.raw_ai_output` is still written as `{}` at the
  `conversation/router.py` call site (a one-line Phase 3 choice, unchanged);
  the parsed AI response is available (`ConversationResult` doesn't carry it
  through, only the individual validated fields do) but wiring the full
  `raw` dict through was left alone since it's outside what this phase's
  brief asked for and touches a file already carefully audited in Phase 3.
- `ensure_current_milestone_tasks()` runs synchronously inside `GET /tasks`.
  In the (rare) request where a milestone transition + AI generation
  actually happens, that one request is slower than a normal `GET /tasks`.
  This mirrors the existing synchronous-AI-call pattern in `POST /goals`
  (Phase 3's own design, not changed here) rather than introducing a new
  async job pattern the frontend doesn't have loading states for; the
  Tasks screen's existing skeleton-loading state (Phase 2 §I) covers it.
- `apply_adjustment`'s `flag_support` handling is still an MVP no-op
  (acknowledged, not acted on) — this is intentionally the RAG integration
  point Architecture §15 describes as future scope, not something Phase 4
  was asked to build out.
- No retry/backoff beyond the single JSON-format retry — a genuine rate
  limit or extended outage surfaces as a 503 to the user on the first
  affected request, same as any other `AIUnavailableError` path.

## 12. Exact remaining work for Phase 5

1. **Run the real test suite** (§10) in an environment with network access
   and a real `AI_API_KEY`; fix anything a live run surfaces that the
   offline manual verification couldn't catch.
2. Full integration + UI click-through of the demo flow (Phase 4 brief's
   17-step list) with `AI_PROVIDER=claude`, backend + frontend running
   side by side, in a real browser.
3. Decide whether to persist `Milestone.tasks_preview_seed` (§6) — small,
   additive, optional.
4. Load/latency check on `generate_roadmap` and `generate_daily_tasks`
   (largest prompts, `max_tokens=2000`/`1600`) against real response times;
   tune `max_tokens` down or add a lightweight async/loading affordance in
   `GoalCreation.jsx`'s already-loading Assessment transition if real
   latency is noticeably worse than the stub.
5. Point `DATABASE_URL` at real Postgres and set a real `JWT_SECRET` before
   any non-local deployment (carried over from `PHASE_3_HANDOFF.md` §11 —
   still not done, still not this phase's job).
6. Optional: wire `ConversationResult`'s full parsed dict into
   `ProgressExtraction.raw_ai_output` (currently `{}`) if audit/debug
   visibility into real model output becomes useful.
