from datetime import date, timedelta
from sqlalchemy.orm import Session
from app.models.models import Goal, Assessment, Roadmap, Milestone, Task, Profile
from app.ai_orchestration.provider import get_ai_provider
from app.core.errors import AIUnavailableError

ai = get_ai_provider()


def _profile_dict(profile: Profile | None) -> dict:
    if not profile:
        return {}
    return {
        "daily_routine": profile.daily_routine,
        "available_time": profile.available_time,
        "preferred_schedule": profile.preferred_schedule,
        "existing_knowledge": profile.existing_knowledge,
        "constraints": profile.constraints or [],
        "preferences": profile.preferences or [],
    }


def create_goal_with_plan(db: Session, user_id: str, payload: dict) -> Goal:
    """
    Implements the Data Flow in Architecture §10:
    Onboarding data -> Assessment -> Roadmap gen -> Milestones + Tasks stored.
    Everything the AI returns is schema-shaped (dataclasses) and validated by
    construction before it's written to the DB (NFR-9).
    """
    profile = db.query(Profile).filter(Profile.user_id == user_id).first()
    profile_dict = _profile_dict(profile)

    goal = Goal(
        user_id=user_id,
        title=payload["title"],
        target_outcome=payload.get("target_outcome", ""),
        current_level=payload.get("current_level", ""),
        target_date=payload.get("target_date"),
        status="active",
    )
    db.add(goal)
    db.flush()

    try:
        assessment_result = ai.generate_assessment(profile_dict, {
            "title": goal.title, "current_level": goal.current_level, "target_date": goal.target_date,
        })
    except Exception:
        raise AIUnavailableError()

    assessment = Assessment(
        goal_id=goal.id,
        ai_summary=assessment_result.ai_summary,
        difficulty_level=assessment_result.difficulty_level,
        recommended_workload=assessment_result.recommended_workload,
        raw_ai_output=assessment_result.raw,
    )
    db.add(assessment)

    try:
        roadmap_result = ai.generate_roadmap(assessment_result, profile_dict, {"title": goal.title, "target_date": goal.target_date})
    except Exception:
        raise AIUnavailableError()

    roadmap = Roadmap(goal_id=goal.id, version=1, status="active")
    db.add(roadmap)
    db.flush()

    milestones = []
    for i, m in enumerate(roadmap_result.milestones):
        milestone = Milestone(
            roadmap_id=roadmap.id,
            title=m.title,
            order_index=m.order_index,
            target_date=m.target_date,
            status="in_progress" if i == 0 else "upcoming",
        )
        db.add(milestone)
        milestones.append((milestone, m.tasks_preview))
    db.flush()

    # Seed daily tasks for the first (current) milestone, spread over the
    # coming week, so /tasks has real data immediately without waiting on a
    # separate "generate today's tasks" call.
    if milestones:
        current_milestone, preview = milestones[0]
        try:
            task_plans = ai.generate_daily_tasks(
                {"title": current_milestone.title, "tasks_preview": preview}, profile_dict, remaining_days=7,
            )
        except Exception:
            # Same fail-safe pattern as the assessment/roadmap calls above:
            # a failed AI call here must surface as a clean 503, not an
            # unhandled 500 (this call was previously the one unguarded AI
            # call in this function). Nothing has been committed yet at this
            # point (see db.commit() below), so raising here leaves no
            # partial Goal/Assessment/Roadmap/Milestone behind — get_db()'s
            # `finally: db.close()` rolls back the still-open transaction.
            raise AIUnavailableError()
        today = date.today()
        for i, tp in enumerate(task_plans):
            db.add(Task(
                milestone_id=current_milestone.id,
                user_id=user_id,
                title=tp.title,
                description=tp.description,
                priority=tp.priority if i > 0 else "high",
                estimated_duration=tp.estimated_duration,
                due_date=(today + timedelta(days=i)).isoformat(),
                status="pending",
            ))

    db.commit()
    db.refresh(goal)
    return goal
