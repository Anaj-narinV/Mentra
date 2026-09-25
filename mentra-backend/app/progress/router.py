from datetime import date, timedelta
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.auth.dependencies import get_current_user
from app.models.models import User, Task, Milestone, Roadmap, Goal
from app.schemas.schemas import ProgressSummaryOut

router = APIRouter(tags=["progress"])


def _period_metrics(db: Session, user_id: str, start: date, end: date) -> dict:
    tasks = db.query(Task).filter(
        Task.user_id == user_id, Task.due_date >= start.isoformat(), Task.due_date <= end.isoformat()
    ).all()
    total = len(tasks)
    completed = len([t for t in tasks if t.status == "completed"])
    missed = len([t for t in tasks if t.status in ("skipped", "partially_completed")])
    consistency = round((completed / total) * 100) if total else 0
    return {"tasks_completed": completed, "tasks_missed": missed, "consistency_pct": consistency, "_total": total}


def _goal_progress_pct(db: Session, user_id: str) -> int:
    goal = db.query(Goal).filter(Goal.user_id == user_id, Goal.status == "active").order_by(Goal.created_at.desc()).first()
    if not goal:
        return 0
    all_tasks = db.query(Task).join(Milestone, Task.milestone_id == Milestone.id, isouter=True).filter(Task.user_id == user_id).all()
    if not all_tasks:
        return 0
    completed = len([t for t in all_tasks if t.status == "completed"])
    return round((completed / len(all_tasks)) * 100)


def _streak_days(db: Session, user_id: str) -> int:
    streak = 0
    day = date.today()
    for _ in range(60):
        tasks = db.query(Task).filter(Task.user_id == user_id, Task.due_date == day.isoformat()).all()
        if not tasks:
            day -= timedelta(days=1)
            continue
        if all(t.status == "completed" for t in tasks):
            streak += 1
            day -= timedelta(days=1)
        else:
            break
    return streak


@router.get("/progress/summary", response_model=ProgressSummaryOut)
def progress_summary(period: str = Query("weekly"), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    today = date.today()

    daily = _period_metrics(db, user.id, today, today)
    weekly_start = today - timedelta(days=6)
    weekly = _period_metrics(db, user.id, weekly_start, today)
    monthly_start = today - timedelta(days=29)
    monthly = _period_metrics(db, user.id, monthly_start, today)

    # goal_progress_pct is a goal-level snapshot (not computed per-period),
    # so it should read the same regardless of which period is selected —
    # previously `daily` never got this field at all, which was an
    # inconsistency (not an intentional part of the weekly-only trend/streak
    # design) since Dashboard.jsx always reads it off `data.weekly`
    # specifically anyway, so this doesn't change any UI behavior, just
    # completes the API response (Phase 5 fix M8). trend/streak_days remain
    # weekly-only, exactly as documented — not adding new metrics elsewhere.
    goal_pct = _goal_progress_pct(db, user.id)
    daily["goal_progress_pct"] = goal_pct
    weekly["goal_progress_pct"] = goal_pct
    monthly["goal_progress_pct"] = goal_pct
    weekly["streak_days"] = _streak_days(db, user.id)

    if weekly["_total"] == 0:
        weekly["trend"] = "Your progress will show up here once you complete a few tasks."
    else:
        weekly["trend"] = f"You've completed {weekly['tasks_completed']} of your last {weekly['_total']} tasks."

    for d in (daily, weekly, monthly):
        d.pop("_total", None)

    upcoming = (
        db.query(Task)
        .filter(Task.user_id == user.id, Task.status == "pending", Task.due_date >= today.isoformat())
        .order_by(Task.due_date.asc())
        .limit(3)
        .all()
    )

    return {"daily": daily, "weekly": weekly, "monthly": monthly, "upcoming": upcoming}
