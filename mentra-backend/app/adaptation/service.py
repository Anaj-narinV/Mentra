from collections import Counter
from datetime import date, datetime, timedelta, timezone
from sqlalchemy.orm import Session
from app.models.models import Task, PlanAdjustment, Roadmap, Milestone, ProgressExtraction, Message, Conversation
from app.ai_orchestration.provider import get_ai_provider
from app.core.errors import AIUnavailableError

ai = get_ai_provider()

DIFFICULTY_REPEAT_THRESHOLD = 2
DIFFICULTY_LOOKBACK_DAYS = 14
RECENT_EXTRACTIONS_LIMIT = 15


def _trailing_task_stats(db: Session, user_id: str, days: int = 7) -> dict:
    start = (date.today() - timedelta(days=days)).isoformat()
    tasks = db.query(Task).filter(
        Task.user_id == user_id, Task.due_date >= start, Task.due_date <= date.today().isoformat()
    ).all()
    total = len(tasks)
    completed = len([t for t in tasks if t.status == "completed"])
    missed_or_partial = len([t for t in tasks if t.status in ("skipped", "partially_completed")])
    # Empty-period default aligned with progress/router.py::_period_metrics
    # (both now report 0%, not 100%, for "no data yet") — see Phase 5 fix
    # M7. Safe for Rule 2 specifically because that rule already requires
    # `total >= 5` alongside `consistency_pct >= 90`, so this default was
    # never actually reachable there; it matters for the *context* this
    # function's result is handed to the AI as (`snapshot_trend`), where a
    # misleading "100% consistent" on a genuinely empty week previously
    # contradicted the `total: 0` sitting right next to it.
    consistency_pct = round((completed / total) * 100) if total else 0
    return {"total": total, "completed": completed, "tasks_missed": missed_or_partial, "consistency_pct": consistency_pct}


def _recent_extractions(db: Session, user_id: str, days: int = DIFFICULTY_LOOKBACK_DAYS) -> list[ProgressExtraction]:
    # ProgressExtraction.created_at is a DateTime column populated via
    # app.models.models.utcnow() (timezone-aware UTC datetime) — the cutoff
    # passed to this comparison must be the same type for a correct,
    # dialect-independent comparison, so this uses a real datetime rather
    # than a date (unlike Task.due_date elsewhere, which is a String column
    # storing plain ISO date strings and is compared against isoformat()
    # strings deliberately — the two columns have different types on
    # purpose and are compared accordingly).
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    return (
        db.query(ProgressExtraction)
        .join(Message, ProgressExtraction.message_id == Message.id)
        .join(Conversation, Message.conversation_id == Conversation.id)
        .filter(Conversation.user_id == user_id, ProgressExtraction.created_at >= cutoff)
        .order_by(ProgressExtraction.created_at.desc())
        .limit(50)
        .all()
    )


def _repeated_difficulty_topic(extractions: list[ProgressExtraction]) -> str | None:
    """Architecture §13 Layer 1, Rule 4: same topic flagged as difficult 2+ times."""
    topics = Counter(
        e.topic_reference for e in extractions if e.difficulty_flag and e.topic_reference
    )
    for topic, count in topics.most_common(1):
        if count >= DIFFICULTY_REPEAT_THRESHOLD:
            return topic
    return None


def check_and_propose_adjustment(db: Session, user_id: str) -> PlanAdjustment | None:
    """
    Layer 1 (deterministic trigger rules) — run cheaply on every call. Only if
    a rule fires do we invoke the (slower, costlier) Layer 2 AI call.
    Never creates a duplicate while one is already 'proposed' for the user.
    """
    already_pending = (
        db.query(PlanAdjustment)
        .filter(PlanAdjustment.user_id == user_id, PlanAdjustment.status == "proposed")
        .first()
    )
    if already_pending:
        return already_pending

    stats = _trailing_task_stats(db, user_id)
    extractions = _recent_extractions(db, user_id)

    recent_extraction = extractions[0] if extractions else None
    availability_changed = bool(recent_extraction and recent_extraction.availability_changed)
    repeated_difficulty_topic = _repeated_difficulty_topic(extractions)

    triggered = (
        stats["tasks_missed"] >= 3  # Rule 1 — repeated missed/partial tasks
        or (stats["consistency_pct"] >= 90 and stats["total"] >= 5)  # Rule 2 — consistently ahead
        or availability_changed  # Rule 3 — availability changed
        or repeated_difficulty_topic is not None  # Rule 4 — repeated difficulty on one topic
    )
    if not triggered:
        return None

    roadmap = (
        db.query(Roadmap)
        .join(Roadmap.goal)
        .filter(Roadmap.status == "active")
        .filter(Roadmap.goal.has(user_id=user_id))
        .order_by(Roadmap.created_at.desc())
        .first()
    )
    if not roadmap:
        return None

    milestones = (
        db.query(Milestone)
        .filter(Milestone.roadmap_id == roadmap.id)
        .order_by(Milestone.order_index)
        .all()
    )
    roadmap_context = {
        "id": roadmap.id,
        "milestones": [
            {"id": m.id, "title": m.title, "status": m.status, "order_index": m.order_index}
            for m in milestones
        ],
    }
    extractions_context = [
        {
            "reason": e.reason,
            "extracted_status": e.extracted_status,
            "availability_changed": e.availability_changed,
            "difficulty_flag": e.difficulty_flag,
            "topic_reference": e.topic_reference,
            "sentiment": e.sentiment,
            "created_at": e.created_at.isoformat() if e.created_at else None,
        }
        for e in extractions[:RECENT_EXTRACTIONS_LIMIT]
    ]
    if repeated_difficulty_topic:
        stats = {**stats, "repeated_difficulty_topic": repeated_difficulty_topic}

    try:
        result = ai.generate_adaptive_adjustment(
            recent_extractions=extractions_context, snapshot_trend=stats, roadmap=roadmap_context,
        )
    except Exception:
        raise AIUnavailableError()

    adjustment = PlanAdjustment(
        roadmap_id=roadmap.id,
        goal_id=roadmap.goal_id,
        user_id=user_id,
        trigger_reason=result.trigger_reason,
        change_summary=result.change_summary,
        expected_effect=result.expected_effect,
        change_payload=result.change_payload,
        current_plan=result.current_plan,
        proposed_plan=result.proposed_plan,
        status="proposed",
    )
    db.add(adjustment)
    db.commit()
    db.refresh(adjustment)
    return adjustment


def apply_adjustment(db: Session, adjustment: PlanAdjustment):
    """
    MVP application of an accepted adjustment: patches tasks in place rather
    than versioning the whole roadmap (Architecture §8 note — full roadmap
    versioning is future scope).
    """
    payload = adjustment.change_payload or {}
    kind = payload.get("type")
    today = date.today().isoformat()
    upcoming = (
        db.query(Task)
        .filter(Task.user_id == adjustment.user_id, Task.status == "pending", Task.due_date >= today)
        .all()
    )
    if kind in ("reduce_workload", "reschedule"):
        for t in upcoming[:2]:
            t.status = "rescheduled"
    elif kind == "accelerate":
        pass  # MVP: acknowledged only; timeline compression is a Phase-4 richer op
    elif kind == "flag_support":
        pass  # MVP: acknowledged only; this is the RAG integration hook (Architecture §15)
    db.commit()
