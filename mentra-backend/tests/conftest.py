"""
Pytest loads this file before collecting (importing) any test module in this
directory — that ordering guarantee is exactly what this file relies on.

Root cause this fixes ("pop from empty list" / many adaptive+e2e failures):
`app/core/config.py` calls `load_dotenv()` on first import, which pulls
whatever is in the developer's real local `.env` into the process
environment. Once a real `AI_API_KEY` is filled in there (as the Gemini
integration work instructed the user to do, e.g. `AI_PROVIDER=gemini` +
a real key), every module-level `ai = get_ai_provider()` singleton in
goals/service.py, tasks/service.py, adaptation/service.py and
conversation/router.py resolves to a *real* `GeminiAIProvider` instead of
the deterministic `StubAIProvider` these integration tests were written
against — because `get_ai_provider()` correctly, faithfully honors
whatever AI_PROVIDER/AI_API_KEY it's given, exactly as designed.

Separately, `tests/test_gemini_provider.py` registers a *fake* `google.genai`
module into `sys.modules` (by design, so its own unit tests never need the
real package or network access). Because pytest imports every test module
during collection before any test runs, that fake is already installed in
`sys.modules` by the time the real `GeminiAIProvider()` above gets
constructed — so `from google import genai` inside it picks up the fake
SDK, not a real (or even missing) one. The fake's response queue is only
ever populated per-test by `test_gemini_provider.py`'s own `provider`
fixture; the app's own singleton instance never gets anything queued, so
its very first real call hits `queue.pop(0)` on an empty list — raising
exactly the reported `IndexError: pop from empty list`, retried once, then
converted to a 503 by the existing (correct, unmodified) AIUnavailableError
handling. That 503 on `POST /goals` is what then cascades into the
`/goals/current/roadmap` 404 and the many other downstream failures in
test_e2e_flow.py / test_adaptive_intelligence.py — those tests assume a
successfully created goal/roadmap/tasks, and the StubAIProvider they were
written against never even ran.

The fix: tests must not depend on whatever happens to be in a developer's
local `.env`. Forcing AI_PROVIDER=stub (and clearing AI_API_KEY) here, before
`app.core.config` is ever imported, makes `load_dotenv()` a no-op for these
two variables specifically (python-dotenv's default `load_dotenv()` never
overrides a variable that's already set in the environment) — restoring the
StubAIProvider behavior every existing test was written against, regardless
of the real provider configured for actually running the app. This changes
no application code, no StubAIProvider behavior, and no Gemini/Claude
provider code — it only fixes which provider the test *environment* selects.
`test_ai_provider.py` and `test_gemini_provider.py` are unaffected either
way: they construct `ClaudeAIProvider`/`GeminiAIProvider` directly in their
own fixtures via `monkeypatch.setattr(settings, ...)`, which overrides the
already-constructed `settings` object's attributes directly and doesn't
depend on the process environment at all.
"""
import os

os.environ["AI_PROVIDER"] = "stub"
os.environ["AI_API_KEY"] = ""
