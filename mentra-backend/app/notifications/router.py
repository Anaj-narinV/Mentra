from datetime import date
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.auth.dependencies import get_current_user
from app.core.errors import NotFoundError, ForbiddenError
from app.models.models import User, Notification, Task, PlanAdjustment
from app.schemas.schemas import NotificationOut, OkResponse

router = APIRouter(tags=["notifications"])


def _seed_notifications_if_needed(db: Session, user_id: str):
    """Deterministically derive in-app notifications (MVP: no push/email —
    Architecture §1.7) from due/missed tasks and pending adjustments, without
    duplicating ones already created."""
    existing_task_ids = {
        n.related_task_id for n in db.query(Notification).filter(Notification.user_id == user_id).all() if n.related_task_id
    }
    today = date.today().isoformat()
    due_today = db.query(Task).filter(Task.user_id == user_id, Task.due_date == today, Task.status == "pending").all()
    for t in due_today:
        if t.id not in existing_task_ids:
            db.add(Notification(user_id=user_id, type="task_due", message=f"\u201c{t.title}\u201d is due today.", related_task_id=t.id))

    missed = db.query(Task).filter(Task.user_id == user_id, Task.status == "skipped").all()
    for t in missed:
        if t.id not in existing_task_ids:
            db.add(Notification(user_id=user_id, type="task_missed", message=f"You missed \u201c{t.title}\u201d.", related_task_id=t.id))

    # Scoped to the *specific* pending adjustment via `related_adjustment_id`
    # (mirrors the existing `related_task_id` pattern). Checking "any
    # adjustment notification ever for this user" (the old behavior) would
    # incorrectly suppress the notification for a second, later, different
    # adjustment — this checks per-adjustment instead, so each new proposal
    # still gets its own notification.
    pending_adj = db.query(PlanAdjustment).filter(PlanAdjustment.user_id == user_id, PlanAdjustment.status == "proposed").first()
    if pending_adj:
        already_notified = (
            db.query(Notification)
            .filter(
                Notification.user_id == user_id,
                Notification.type == "adjustment",
                Notification.related_adjustment_id == pending_adj.id,
            )
            .first()
        )
        if not already_notified:
            db.add(Notification(
                user_id=user_id,
                type="adjustment",
                message="Mentra has a plan adjustment for you to review.",
                related_adjustment_id=pending_adj.id,
            ))

    db.commit()


@router.get("/notifications", response_model=list[NotificationOut])
def list_notifications(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _seed_notifications_if_needed(db, user.id)
    return (
        db.query(Notification)
        .filter(Notification.user_id == user.id)
        .order_by(Notification.created_at.desc())
        .all()
    )


@router.put("/notifications/{notification_id}/read", response_model=OkResponse)
def mark_read(notification_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    n = db.query(Notification).filter(Notification.id == notification_id).first()
    if not n:
        raise NotFoundError("Notification not found.")
    if n.user_id != user.id:
        raise ForbiddenError()
    n.is_read = True
    db.commit()
    return {"ok": True}
