from datetime import date, timedelta
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.auth.dependencies import get_current_user
from app.core.errors import NotFoundError, ForbiddenError, ValidationAppError
from app.models.models import User, Task, TASK_STATUSES
from app.schemas.schemas import TaskOut, TaskStatusUpdate, OkResponse
from app.tasks.service import ensure_current_milestone_tasks

router = APIRouter(tags=["tasks"])


@router.get("/tasks", response_model=list[TaskOut])
def list_tasks(
    date_: str | None = Query(None, alias="date"),
    range_: str | None = Query(None, alias="range"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ensure_current_milestone_tasks(db, user.id)
    q = db.query(Task).filter(Task.user_id == user.id)
    today = date.today()
    if range_ == "week":
        start, end = today, today + timedelta(days=7)
        q = q.filter(Task.due_date >= start.isoformat(), Task.due_date <= end.isoformat())
    elif date_ and date_ != "today":
        q = q.filter(Task.due_date == date_)
    else:
        # default / date=today
        q = q.filter(Task.due_date == today.isoformat())
    return q.order_by(Task.due_date.asc(), Task.created_at.asc()).all()


@router.put("/tasks/{task_id}/status", response_model=OkResponse)
def update_task_status(task_id: str, payload: TaskStatusUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise NotFoundError("Task not found.")
    if task.user_id != user.id:
        raise ForbiddenError()
    if payload.status not in TASK_STATUSES:
        raise ValidationAppError(f"Invalid status. Must be one of {TASK_STATUSES}.")
    task.status = payload.status
    db.commit()
    return {"ok": True}
