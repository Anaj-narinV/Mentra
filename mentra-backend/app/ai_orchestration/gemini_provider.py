"""
Gemini-backed AI provider implementation, behind the same `AIProvider`
interface as `claude_provider.py`. No other module imports this file
directly — everything goes through `get_ai_provider()`, so switching
AI_PROVIDER between "claude" and "gemini" (or back to "stub") never touches
goals/service.py, adaptation/service.py, or conversation/router.py.

This deliberately mirrors claude_provider.py's structure (same validation
rules, same one-bounded-retry policy, same fail-safe error type) rather than
sharing code with it, so each provider file stays a single, self-contained
unit that can be read, tested, or replaced independently — exactly how
claude_provider.py was written relative to the stub before it.

Design notes (same as claude_provider.py):
- Structured output only: every call asks Gemini for a single JSON object
  (via `response_mime_type="application/json"`) and the response is parsed
  + schema-checked before it's turned into the same dataclasses the stub and
  Claude provider return. Callers already wrap every AI call in
  try/except -> AIUnavailableError, so raising AIProviderError here is the
  correct way to fail safe without leaking provider internals to the
  frontend (NFR-9).
- One bounded retry on malformed JSON, then a clean failure — no unbounded
  loops, no silent corruption of task/roadmap data.
- Never sends passwords, JWT secrets, DB credentials, or other users' data —
  only the small per-request dicts already assembled by the callers above.
"""
import json
import logging
import re

from app.ai_orchestration.provider import (
    AIProvider,
    AssessmentResult,
    RoadmapResult,
    MilestonePlan,
    TaskPlan,
    ConversationResult,
    AdjustmentResult,
)
from app.ai_orchestration import prompts
from app.core.config import settings

logger = logging.getLogger("mentra.ai")

TASK_STATUSES = ("pending", "completed", "partially_completed", "skipped", "rescheduled")
TASK_PRIORITIES = ("low", "medium", "high")
_ADJUSTMENT_TYPES = ("reduce_workload", "accelerate", "reschedule", "flag_support")

_CODE_FENCE_RE = re.compile(r"^```[a-zA-Z]*\n?|\n?```$")

# ---------- Native structured-output schemas (Gemini's OpenAPI-3.0 subset) ----------
#
# Passed as `response_schema` alongside `response_mime_type="application/json"`
# so Gemini's own controlled-generation decoding is constrained to this exact
# shape, rather than relying solely on prompt instructions + post-hoc JSON
# parsing. This is what actually fixes the truncated/malformed-JSON bug
# (generate_daily_tasks returning "Unterminated string..."): a schema-guided
# response is far less likely to wander into verbose free text that then
# gets cut off mid-token-budget. Field names/types mirror exactly what the
# validation code below already expects — this is an additional constraint
# layer on top of that validation, not a replacement for it (nothing below
# is relaxed because a schema is now in place).
#
# Only fields the model should actively decide go in `properties`; fields
# that are always true/independent of the model (like Task.status's literal
# enum members) are expressed as an explicit `enum` list so Gemini can't
# emit an invalid status string in the first place.

_ASSESSMENT_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "ai_summary": {"type": "STRING"},
        "difficulty_level": {"type": "STRING"},
        "recommended_workload": {"type": "STRING"},
        "current_level_assessment": {"type": "STRING"},
        "strengths": {"type": "ARRAY", "items": {"type": "STRING"}},
        "gaps": {"type": "ARRAY", "items": {"type": "STRING"}},
        "risks": {"type": "ARRAY", "items": {"type": "STRING"}},
        "recommended_approach": {"type": "STRING"},
    },
    "required": ["ai_summary", "difficulty_level", "recommended_workload"],
}

_ROADMAP_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "milestones": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "title": {"type": "STRING"},
                    "target_date": {"type": "STRING", "nullable": True},
                    "order_index": {"type": "INTEGER"},
                    "tasks_preview": {"type": "ARRAY", "items": {"type": "STRING"}},
                },
                "required": ["title", "order_index", "tasks_preview"],
            },
        },
    },
    "required": ["milestones"],
}

_DAILY_TASKS_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "tasks": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "title": {"type": "STRING"},
                    "description": {"type": "STRING"},
                    "priority": {"type": "STRING", "enum": list(TASK_PRIORITIES)},
                    "estimated_duration": {"type": "STRING"},
                    "due_date": {"type": "STRING", "nullable": True},
                },
                "required": ["title", "description", "priority"],
            },
        },
    },
    "required": ["tasks"],
}

_CONVERSATION_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "reply": {"type": "STRING"},
        "task_id": {"type": "STRING", "nullable": True},
        "status": {"type": "STRING", "enum": list(TASK_STATUSES), "nullable": True},
        "reason": {"type": "STRING"},
        "availability_changed": {"type": "BOOLEAN"},
        "difficulty_flag": {"type": "BOOLEAN"},
        "topic_reference": {"type": "STRING", "nullable": True},
        "sentiment": {"type": "STRING"},
    },
    "required": ["reply"],
}

_ADJUSTMENT_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "trigger_reason": {"type": "STRING"},
        "change_summary": {"type": "STRING"},
        "expected_effect": {"type": "STRING"},
        "change_payload": {
            "type": "OBJECT",
            "properties": {"type": {"type": "STRING", "enum": list(_ADJUSTMENT_TYPES)}},
            "required": ["type"],
        },
        "current_plan": {"type": "ARRAY", "items": {"type": "STRING"}},
        "proposed_plan": {"type": "ARRAY", "items": {"type": "STRING"}},
        "confidence": {"type": "NUMBER"},
    },
    "required": ["trigger_reason", "change_summary"],
}


class AIProviderError(Exception):
    """Raised when the provider can't be reached or returns unusable output.
    Every caller already catches this (as a broad Exception) and converts it
    to the safe, user-facing `AIUnavailableError` (503) — nothing here should
    ever propagate a raw provider error or secret to the frontend."""


def _strip_code_fences(text: str) -> str:
    text = text.strip()
    text = _CODE_FENCE_RE.sub("", text).strip()
    return text


def _extract_text(response) -> str:
    # google-genai's response.text is the convenience accessor for the
    # concatenated text of the first candidate. Depending on SDK version and
    # response state it can either be None (blocked/no candidates) or raise
    # (e.g. no valid candidate to read from) rather than returning None —
    # guard both so a blocked/empty generation is treated as "malformed,
    # retry" like any other bad response, instead of an unrelated
    # AttributeError/ValueError escaping _complete_json uncaught.
    try:
        text = getattr(response, "text", None)
    except Exception:
        return ""
    return text or ""


class GeminiAIProvider(AIProvider):
    """AIProvider backed by the Google Gemini API (google-genai SDK)."""

    def __init__(self):
        if not settings.AI_API_KEY:
            raise AIProviderError("AI_API_KEY is not configured.")
        try:
            from google import genai
        except ImportError as e:  # pragma: no cover - exercised only if dependency missing
            raise AIProviderError("The 'google-genai' package is not installed.") from e
        self._genai = genai
        self._client = genai.Client(api_key=settings.AI_API_KEY)
        self._model = settings.AI_MODEL or "gemini-3.5-flash"

    # ---- low-level: one JSON-producing call, with one bounded retry ----

    def _complete_json(self, system: str, user: str, response_schema: dict, max_tokens: int = 1600) -> dict:
        from google.genai import types

        last_error: Exception | None = None
        for attempt in range(2):
            prompt = user if attempt == 0 else (
                user + "\n\nYour previous reply was not valid JSON. Return ONLY a single "
                "valid JSON object this time — no markdown fences, no commentary."
            )
            try:
                response = self._client.models.generate_content(
                    model=self._model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=system,
                        response_mime_type="application/json",
                        response_schema=response_schema,
                        max_output_tokens=max_tokens,
                    ),
                )
            except Exception as e:  # network error, auth error, rate limit, timeout, ...
                last_error = e
                logger.warning("AI provider request failed (attempt %d): %s", attempt, e)
                continue

            text = _strip_code_fences(_extract_text(response))
            try:
                parsed = json.loads(text)
            except (json.JSONDecodeError, ValueError) as e:
                last_error = e
                logger.warning("AI provider returned malformed JSON (attempt %d): %s", attempt, e)
                continue

            if not isinstance(parsed, dict):
                last_error = ValueError("AI response was valid JSON but not an object.")
                continue

            return parsed

        raise AIProviderError(f"AI provider failed to produce usable output: {last_error}")

    # ---- AIProvider interface (validation identical to claude_provider.py,
    # since both must satisfy the exact same downstream schema/DB contract) ----

    def generate_assessment(self, profile: dict, goal: dict) -> AssessmentResult:
        system, user = prompts.assessment_prompt(profile, goal)
        data = self._complete_json(system, user, _ASSESSMENT_SCHEMA, max_tokens=2048)

        ai_summary = str(data.get("ai_summary") or "").strip()
        if not ai_summary:
            raise AIProviderError("Assessment response missing 'ai_summary'.")
        difficulty_level = str(data.get("difficulty_level") or "Moderate").strip()
        recommended_workload = str(
            data.get("recommended_workload") or profile.get("available_time") or "30 minutes on most days"
        ).strip()

        return AssessmentResult(
            ai_summary=ai_summary,
            difficulty_level=difficulty_level,
            recommended_workload=recommended_workload,
            raw=data,
        )

    def generate_roadmap(self, assessment: AssessmentResult, profile: dict, goal: dict) -> RoadmapResult:
        assessment_dict = {
            "ai_summary": assessment.ai_summary,
            "difficulty_level": assessment.difficulty_level,
            "recommended_workload": assessment.recommended_workload,
        }
        system, user = prompts.roadmap_prompt(assessment_dict, profile, goal)
        data = self._complete_json(system, user, _ROADMAP_SCHEMA, max_tokens=3000)

        raw_milestones = data.get("milestones")
        if not isinstance(raw_milestones, list) or not raw_milestones:
            raise AIProviderError("Roadmap response missing a non-empty 'milestones' list.")

        milestones = []
        for i, m in enumerate(raw_milestones):
            if not isinstance(m, dict) or not str(m.get("title") or "").strip():
                raise AIProviderError(f"Roadmap milestone {i} missing a title.")
            tasks_preview = m.get("tasks_preview")
            if not isinstance(tasks_preview, list) or not tasks_preview:
                tasks_preview = ["Focused practice session"]
            tasks_preview = [str(t) for t in tasks_preview if str(t).strip()][:6] or ["Focused practice session"]
            target_date = m.get("target_date")
            target_date = str(target_date) if target_date else None
            milestones.append(MilestonePlan(
                title=str(m["title"]).strip(),
                target_date=target_date,
                order_index=i,
                tasks_preview=tasks_preview,
            ))

        return RoadmapResult(milestones=milestones)

    def generate_daily_tasks(self, milestone: dict, profile: dict, remaining_days: int) -> list:
        remaining_days = max(int(remaining_days or 1), 1)
        system, user = prompts.daily_tasks_prompt(milestone, profile, remaining_days)
        # Root cause of the truncated-JSON bug this fixes: this call
        # previously had no max_tokens override at all, silently falling
        # back to _complete_json's 1600-token default — sized for a single
        # small object, not an array of up to `remaining_days` full task
        # objects (title + a 1-2 sentence description + priority/duration/
        # due_date each). Gemini would fill that budget mid-object and get
        # cut off, producing exactly the "Unterminated string" JSON error
        # seen in the bug report. Size the budget to the actual output shape
        # instead of reusing an unrelated fixed default.
        max_tokens = min(4096, 500 + remaining_days * 260)
        data = self._complete_json(system, user, _DAILY_TASKS_SCHEMA, max_tokens=max_tokens)

        raw_tasks = data.get("tasks")
        if not isinstance(raw_tasks, list) or not raw_tasks:
            raise AIProviderError("Daily task response missing a non-empty 'tasks' list.")

        tasks = []
        for i, t in enumerate(raw_tasks):
            if not isinstance(t, dict) or not str(t.get("title") or "").strip():
                continue  # skip malformed individual entries rather than failing the whole batch
            priority = str(t.get("priority") or "medium").strip().lower()
            if priority not in TASK_PRIORITIES:
                priority = "medium"
            due_date = t.get("due_date")
            tasks.append(TaskPlan(
                title=str(t["title"]).strip(),
                description=str(t.get("description") or "").strip(),
                priority=priority,
                estimated_duration=str(t.get("estimated_duration") or profile.get("available_time") or "30 min").strip(),
                due_date=str(due_date) if due_date else None,
            ))

        if not tasks:
            raise AIProviderError("Daily task response contained no usable tasks.")
        return tasks

    def process_conversation(self, message: str, history: list, open_tasks: list) -> ConversationResult:
        system, user = prompts.conversation_prompt(message, history, open_tasks)
        data = self._complete_json(system, user, _CONVERSATION_SCHEMA, max_tokens=1200)

        reply = str(data.get("reply") or "").strip()
        if not reply:
            raise AIProviderError("Conversation response missing 'reply'.")

        valid_task_ids = {t["id"] for t in open_tasks if isinstance(t, dict) and "id" in t}
        task_id = data.get("task_id")
        task_id = str(task_id) if task_id else None
        if task_id and task_id not in valid_task_ids:
            # Don't trust a task reference the model invented — fail safe per
            # "do not overwrite user intent" rather than guessing which task.
            task_id = None

        status = data.get("status")
        status = str(status) if status else None
        if status and status not in TASK_STATUSES:
            status = None
        if not task_id:
            # A status with no verified task to attach it to is not actionable.
            status = None

        availability_changed = bool(data.get("availability_changed", False))
        difficulty_flag = bool(data.get("difficulty_flag", False))
        topic_reference = data.get("topic_reference")
        topic_reference = str(topic_reference).strip() if (topic_reference and difficulty_flag) else None
        reason = str(data.get("reason") or "")[:280]
        sentiment = str(data.get("sentiment") or "neutral").strip() or "neutral"

        return ConversationResult(
            reply=reply,
            task_id=task_id,
            status=status,
            reason=reason,
            availability_changed=availability_changed,
            difficulty_flag=difficulty_flag,
            topic_reference=topic_reference,
            sentiment=sentiment,
        )

    def generate_adaptive_adjustment(self, recent_extractions: list, snapshot_trend: dict, roadmap: dict) -> AdjustmentResult:
        system, user = prompts.adaptive_adjustment_prompt(recent_extractions, snapshot_trend, roadmap)
        data = self._complete_json(system, user, _ADJUSTMENT_SCHEMA, max_tokens=2048)

        trigger_reason = str(data.get("trigger_reason") or "").strip()
        change_summary = str(data.get("change_summary") or "").strip()
        if not trigger_reason or not change_summary:
            raise AIProviderError("Adjustment response missing 'trigger_reason' or 'change_summary'.")

        expected_effect = str(data.get("expected_effect") or "").strip()
        change_payload = data.get("change_payload")
        if not isinstance(change_payload, dict):
            change_payload = {}
        if change_payload.get("type") not in _ADJUSTMENT_TYPES:
            change_payload["type"] = "reduce_workload"

        current_plan = data.get("current_plan")
        current_plan = [str(x) for x in current_plan][:6] if isinstance(current_plan, list) else []
        proposed_plan = data.get("proposed_plan")
        proposed_plan = [str(x) for x in proposed_plan][:6] if isinstance(proposed_plan, list) else []
        if not current_plan:
            current_plan = ["Current week's tasks as scheduled"]
        if not proposed_plan:
            proposed_plan = ["Adjusted week per change_summary"]

        try:
            confidence = float(data.get("confidence", 0.6))
        except (TypeError, ValueError):
            confidence = 0.6
        confidence = max(0.0, min(1.0, confidence))

        return AdjustmentResult(
            trigger_reason=trigger_reason,
            change_summary=change_summary,
            expected_effect=expected_effect or "This should make the plan easier to stick with.",
            change_payload=change_payload,
            current_plan=current_plan,
            proposed_plan=proposed_plan,
            confidence=confidence,
        )
