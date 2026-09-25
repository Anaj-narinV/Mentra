"""
Real AI provider implementation (Phase 4), behind the same `AIProvider`
interface Phase 3 defined in `provider.py`. No other module imports this
file directly — everything goes through `get_ai_provider()`, so the provider
stays swappable (Architecture §7, NFR-6) and this file could be replaced
with a different vendor's SDK without touching goals/service.py,
adaptation/service.py, or conversation/router.py.

Design notes (Phase 4 instructions):
- Structured output only: every call asks for a single JSON object and the
  response is parsed + schema-checked before it's turned into the same
  dataclasses the stub returns. Callers (goals/service.py,
  adaptation/service.py, conversation/router.py) already wrap every AI call
  in try/except -> AIUnavailableError, so raising AIProviderError here is
  the correct way to "fail safe" without leaking provider internals to the
  frontend (NFR-9, Phase 4 "AI output validation" / "error handling").
- One bounded retry: if the model's first reply isn't valid JSON, we ask
  again once with a sharper reminder before giving up. No unbounded loops,
  no silent corruption of task/roadmap data either way.
- Never sends passwords, JWT secrets, DB credentials, or other users' data —
  callers only ever pass the small per-request dicts already assembled by
  goals/service.py, adaptation/service.py, conversation/router.py.
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


class AIProviderError(Exception):
    """Raised when the provider can't be reached or returns unusable output.
    Every caller already catches this (as a broad Exception) and converts it
    to the safe, user-facing `AIUnavailableError` (503) — nothing here should
    ever propagate a raw provider error or secret to the frontend."""


def _strip_code_fences(text: str) -> str:
    text = text.strip()
    text = _CODE_FENCE_RE.sub("", text).strip()
    return text


def _extract_text(message) -> str:
    parts = [b.text for b in getattr(message, "content", []) if getattr(b, "type", None) == "text"]
    return "".join(parts)


class ClaudeAIProvider(AIProvider):
    """AIProvider backed by the Anthropic Claude API."""

    def __init__(self):
        if not settings.AI_API_KEY:
            raise AIProviderError("AI_API_KEY is not configured.")
        try:
            import anthropic
        except ImportError as e:  # pragma: no cover - exercised only if dependency missing
            raise AIProviderError("The 'anthropic' package is not installed.") from e
        self._client = anthropic.Anthropic(api_key=settings.AI_API_KEY)
        self._model = settings.AI_MODEL or "claude-sonnet-5"

    # ---- low-level: one JSON-producing call, with one bounded retry ----

    def _complete_json(self, system: str, user: str, max_tokens: int = 1600) -> dict:
        last_error: Exception | None = None
        for attempt in range(2):
            prompt = user if attempt == 0 else (
                user + "\n\nYour previous reply was not valid JSON. Return ONLY a single "
                "valid JSON object this time — no markdown fences, no commentary."
            )
            try:
                message = self._client.messages.create(
                    model=self._model,
                    max_tokens=max_tokens,
                    system=system,
                    messages=[{"role": "user", "content": prompt}],
                )
            except Exception as e:  # network error, auth error, rate limit, timeout, ...
                last_error = e
                logger.warning("AI provider request failed (attempt %d): %s", attempt, e)
                continue

            text = _strip_code_fences(_extract_text(message))
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

    # ---- AIProvider interface ----

    def generate_assessment(self, profile: dict, goal: dict) -> AssessmentResult:
        system, user = prompts.assessment_prompt(profile, goal)
        data = self._complete_json(system, user)

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
        data = self._complete_json(system, user, max_tokens=2000)

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
        data = self._complete_json(system, user)

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
        data = self._complete_json(system, user, max_tokens=1000)

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
        data = self._complete_json(system, user)

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
