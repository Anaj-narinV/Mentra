"""
Daily Task Intelligence (Phase 4, AI Function 3).

Phase 3 only ever seeded tasks for the *first* milestone, at goal-creation
time (see PHASE_3_HANDOFF.md §9, item 5 — an explicitly flagged gap: "no
seeded tasks until Phase 4's real daily-task generation... populates them as
the user progresses"). This module closes that gap without changing the API
contract, the database schema, or any frontend code: `GET /tasks` already
returns whatever Task rows exist for the user, so this only needs to make
sure the right rows exist before that query runs.

Kept as its own small service (not inlined in tasks/router.py) so the
"advance milestone + regenerate tasks" logic is independently testable and
so the router stays a thin HTTP layer, consistent with how goals/service.py
and adaptation/service.py are already split from their routers.
"""
from datetime import date, timedelta
from sqlalchemy.orm import Session
from app.models.models import Milestone, Task, Roadmap, Profile
from app.ai_orchestration.provider import get_ai_provider
from app.goals.service import _profile_dict

ai = get_ai_provider()

DAILY_TASK_WINDOW_DAYS = 7


def ensure_current_milestone_tasks(db: Session, user_id: str) -> None:
    """
    Called on every `GET /tasks` (cheap no-op in the common case — a couple
    of indexed queries). If the user's current (in_progress) milestone has no
    tasks yet, generates its first week via the AI provider. If the current
    milestone's tasks are all resolved (nothing left pending), advances it to
    'completed', activates the next milestone, and seeds tasks for it too.

    Never raises: if the AI call fails, this is a silent no-op for that
    milestone (NFR-9 — a failed background generation must not break the
    read path or corrupt existing data). The milestone simply stays without
    tasks until the next successful call.
    """
    roadmap = (
        db.query(Roadmap)
        .join(Roadmap.goal)
        .filter(Roadmap.status == "active")
        .filter(Roadmap.goal.has(user_id=user_id))
        .order_by(Roadmap.created_at.desc())
        .first()
    )
    if not roadmap:
        return

    current = (
        db.query(Milestone)
        .filter(Milestone.roadmap_id == roadmap.id, Milestone.status == "in_progress")
        .order_by(Milestone.order_index)
        .first()
    )
    if not current:
        return

    tasks = db.query(Task).filter(Task.milestone_id == current.id).all()
    if not tasks:
        _generate_tasks_for_milestone(db, current, user_id)
        return

    if any(t.status == "pending" for t in tasks):
        return  # still work left on the current milestone — nothing to do

    # Every task on the current milestone is resolved (completed / skipped /
    # partially_completed / rescheduled) — move the roadmap forward.
    current.status = "completed"
    next_milestone = (
        db.query(Milestone)
        .filter(Milestone.roadmap_id == roadmap.id, Milestone.order_index == current.order_index + 1)
        .first()
    )
    if not next_milestone:
        db.commit()
        return  # last milestone done — nothing further to generate

    next_milestone.status = "in_progress"
    db.commit()

    if not db.query(Task).filter(Task.milestone_id == next_milestone.id).first():
        _generate_tasks_for_milestone(db, next_milestone, user_id)


def _generate_tasks_for_milestone(db: Session, milestone: Milestone, user_id: str) -> None:
    profile = db.query(Profile).filter(Profile.user_id == user_id).first()
    profile_dict = _profile_dict(profile)
    preview = [t.title for t in db.query(Task).filter(Task.milestone_id == milestone.id).limit(3)]

    try:
        task_plans = ai.generate_daily_tasks(
            {"title": milestone.title, "tasks_preview": preview or [milestone.title]},
            profile_dict,
            remaining_days=DAILY_TASK_WINDOW_DAYS,
        )
    except Exception:
        return  # fail safe — see docstring above

    today = date.today()
    for i, tp in enumerate(task_plans):
        db.add(Task(
            milestone_id=milestone.id,
            user_id=user_id,
            title=tp.title,
            description=tp.description,
            priority=tp.priority,
            estimated_duration=tp.estimated_duration,
            due_date=tp.due_date or (today + timedelta(days=i)).isoformat(),
            status="pending",
        ))
    db.commit()
