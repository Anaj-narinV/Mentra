"""
AI Orchestration boundary.

This is the SINGLE choke point through which the rest of the backend talks to
"the AI". Per the Architecture doc (§7, §14): the AI is a stateless function
of the input it's given — it never touches the database directly, and every
function here returns *structured, schema-defined output* that the caller
validates before persisting (NFR-9).

Phase 3 scope: define the interface + a deterministic stub implementation so
the whole product works end-to-end without a live LLM key. Phase 4 swaps in
a real provider (e.g. Claude or Gemini) behind the same `AIProvider`
interface — no other module should need to change.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional
from app.core.config import settings


# ---------- Structured I/O contracts (see Architecture doc §11) ----------

@dataclass
class AssessmentResult:
    ai_summary: str
    difficulty_level: str
    recommended_workload: str
    raw: dict = field(default_factory=dict)


@dataclass
class MilestonePlan:
    title: str
    target_date: Optional[str]
    order_index: int
    tasks_preview: list


@dataclass
class RoadmapResult:
    milestones: list  # list[MilestonePlan]


@dataclass
class TaskPlan:
    title: str
    description: str
    priority: str
    estimated_duration: str
    due_date: Optional[str]


@dataclass
class ConversationResult:
    reply: str
    task_id: Optional[str]
    status: Optional[str]
    reason: str
    availability_changed: bool
    difficulty_flag: bool
    topic_reference: Optional[str]
    sentiment: str = "neutral"


@dataclass
class AdjustmentResult:
    trigger_reason: str
    change_summary: str
    expected_effect: str
    change_payload: dict
    current_plan: list
    proposed_plan: list
    confidence: float = 0.7


class AIProvider(ABC):
    """Provider-agnostic interface. Phase 4 implements this against a real LLM."""

    @abstractmethod
    def generate_assessment(self, profile: dict, goal: dict) -> AssessmentResult: ...

    @abstractmethod
    def generate_roadmap(self, assessment: AssessmentResult, profile: dict, goal: dict) -> RoadmapResult: ...

    @abstractmethod
    def generate_daily_tasks(self, milestone: dict, profile: dict, remaining_days: int) -> list:
        """Returns list[TaskPlan]."""
        ...

    @abstractmethod
    def process_conversation(self, message: str, history: list, open_tasks: list) -> ConversationResult: ...

    @abstractmethod
    def generate_adaptive_adjustment(self, recent_extractions: list, snapshot_trend: dict, roadmap: dict) -> AdjustmentResult: ...


class StubAIProvider(AIProvider):
    """
    Deterministic, template-based placeholder used until Phase 4 wires up a
    real model. Intentionally has no network calls and no randomness, so the
    rest of the app (and its tests) are stable. Every method's *shape* is
    exactly what a real provider must return.
    """

    def generate_assessment(self, profile: dict, goal: dict) -> AssessmentResult:
        title = goal.get("title", "your goal")
        current_level = goal.get("current_level") or "a starting point you've described"
        available_time = profile.get("available_time") or "the time you have available"
        summary = (
            f"Here's how I see it: you're working toward \"{title}\", starting from "
            f"{current_level.lower() if current_level else 'the basics'}. Given {available_time} on most days, "
            "I've kept the early plan short and focused rather than long and exhausting — we'll build "
            "fundamentals first, then layer on harder material once the basics feel automatic."
        )
        return AssessmentResult(
            ai_summary=summary,
            difficulty_level="Moderate — foundational concepts, steady pace",
            recommended_workload=f"{available_time or '30–45 minutes'} on most days",
            raw={"stub": True},
        )

    def generate_roadmap(self, assessment: AssessmentResult, profile: dict, goal: dict) -> RoadmapResult:
        base_titles = [
            ("Foundations", ["Orientation & baseline check", "Core concepts, part 1", "Core concepts, part 2"]),
            ("Building Skills", ["Applied practice set 1", "Applied practice set 2", "Mixed review"]),
            ("Deepening", ["Harder problems", "Weak-spot focus", "Integration exercise"]),
            ("Consolidation & Review", ["Timed practice", "Full review", "Final check-in"]),
        ]
        milestones = [
            MilestonePlan(title=t, target_date=None, order_index=i, tasks_preview=preview)
            for i, (t, preview) in enumerate(base_titles)
        ]
        return RoadmapResult(milestones=milestones)

    def generate_daily_tasks(self, milestone: dict, profile: dict, remaining_days: int) -> list:
        preview = milestone.get("tasks_preview") or ["Focused practice session"]
        count = max(remaining_days, len(preview))
        return [
            TaskPlan(
                title=preview[i % len(preview)] if i < len(preview) else f"{preview[i % len(preview)]} (cont'd)",
                description=f"Work on: {preview[i % len(preview)]}.",
                priority="medium",
                estimated_duration=profile.get("available_time") or "30 min",
                due_date=None,
            )
            for i in range(count)
        ]

    def process_conversation(self, message: str, history: list, open_tasks: list) -> ConversationResult:
        text = (message or "").lower()
        done = any(k in text for k in ["finish", "complet", "done"])
        struggling = any(k in text for k in ["confus", "don't understand", "dont understand", "hard", "stuck", "difficult"])
        cant_finish = any(k in text for k in ["couldn't", "couldnt", "didn't finish", "didnt finish", "ran out of time"])
        reschedule = any(k in text for k in ["move", "reschedule", "busy", "exam", "can't today", "cant today"])

        target_task = open_tasks[0] if open_tasks else None
        task_id = target_task["id"] if target_task else None

        # `cant_finish` is checked before `done`: "couldn't finish it" contains
        # the substring "finish" (one of `done`'s keywords), so without this
        # ordering a clear partial-completion message would be misclassified
        # as "completed" purely from that substring match. The negated/partial
        # phrasing is the more specific, more reliable signal and should win.
        if cant_finish:
            reply = "That's alright — I've logged it as partially done. We'll pick it back up next session."
            status = "partially_completed"
        elif done:
            reply = (
                "Nice work — I've marked that as complete. Keep this pace up and we might even "
                "move a little faster than planned."
            )
            status = "completed"
        elif reschedule:
            reply = (
                "Thanks for the heads-up — I've noted the schedule change. If this keeps happening "
                "this week, I'll suggest lightening the load a bit."
            )
            status = "rescheduled"
        elif struggling:
            reply = (
                "Got it — that one's clearly tricky. I've flagged the topic; if it keeps coming up "
                "I'll bring in some extra support material."
            )
            status = None
        else:
            reply = "Thanks for telling me — I've noted it."
            status = None

        return ConversationResult(
            reply=reply,
            task_id=task_id if (done or reschedule or cant_finish) else None,
            status=status,
            reason=message[:280],
            availability_changed=reschedule,
            difficulty_flag=struggling,
            topic_reference=target_task["title"] if (struggling and target_task) else None,
            sentiment="high_urgency" if (struggling or cant_finish) else "neutral",
        )

    def generate_adaptive_adjustment(self, recent_extractions: list, snapshot_trend: dict, roadmap: dict) -> AdjustmentResult:
        missed = snapshot_trend.get("tasks_missed", 0)
        ahead = snapshot_trend.get("consistency_pct", 0) >= 90
        if ahead:
            summary = "You've been consistent — want me to speed things up a little?"
            effect = "Slightly compresses the timeline while keeping daily sessions manageable."
            payload = {"type": "accelerate", "delta": "+1 task/week"}
        else:
            summary = "You've missed a few tasks recently — I'd like to lighten the next few days."
            effect = "Keeps you on the same overall target date without the daily crunch."
            payload = {"type": "reduce_workload", "delta": "-20% this week"}
        reason = f"{missed} missed/partial tasks in the trailing 7 days." if not ahead else "90%+ completion, ahead of schedule."
        return AdjustmentResult(
            trigger_reason=reason,
            change_summary=summary,
            expected_effect=effect,
            change_payload=payload,
            current_plan=["Current week's tasks as scheduled"],
            proposed_plan=["Adjusted week per change_summary"],
            confidence=0.65,
        )


def get_ai_provider() -> AIProvider:
    """
    Single factory every caller uses (Architecture §7). When AI_PROVIDER is
    "claude" or "gemini" and AI_API_KEY is set, return the matching real
    provider; otherwise fall back to the deterministic stub so local dev and
    tests keep working without a live key. If the real provider fails to
    initialize (missing dependency, bad key format, etc.), log it and fall
    back to the stub rather than crashing the whole app at import time.
    """
    provider = (settings.AI_PROVIDER or "stub").strip().lower()
    if provider == "claude" and settings.AI_API_KEY:
        try:
            from app.ai_orchestration.claude_provider import ClaudeAIProvider
            return ClaudeAIProvider()
        except Exception as e:  # pragma: no cover - defensive fallback
            import logging
            logging.getLogger("mentra.ai").error(
                "Failed to initialize ClaudeAIProvider, falling back to stub: %s", e
            )
            return StubAIProvider()
    if provider == "gemini" and settings.AI_API_KEY:
        try:
            from app.ai_orchestration.gemini_provider import GeminiAIProvider
            return GeminiAIProvider()
        except Exception as e:  # pragma: no cover - defensive fallback
            import logging
            logging.getLogger("mentra.ai").error(
                "Failed to initialize GeminiAIProvider, falling back to stub: %s", e
            )
            return StubAIProvider()
    return StubAIProvider()
