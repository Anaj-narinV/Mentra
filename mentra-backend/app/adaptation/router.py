from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.auth.dependencies import get_current_user
from app.core.errors import NotFoundError, ForbiddenError, ValidationAppError
from app.models.models import User, PlanAdjustment, ADJUSTMENT_STATUSES, Notification
from app.schemas.schemas import AdjustmentOut, AdjustmentRespond, OkResponse
from app.adaptation.service import check_and_propose_adjustment, apply_adjustment

router = APIRouter(tags=["adaptation"])

ACTION_TO_STATUS = {
    "accept": "accepted",
    "decline": "declined",
    "edit": "edited",
    "request_changes": "requested_changes",
}


@router.get("/plan-adjustments", response_model=list[AdjustmentOut])
def list_adjustments(status: str = Query("proposed"), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if status == "proposed":
        # Lazily evaluate Layer 1 trigger rules on read, so a pending
        # adjustment appears as soon as conditions are met even if the chat
        # flow that would normally trigger it hasn't fired this session.
        check_and_propose_adjustment(db, user.id)
    q = db.query(PlanAdjustment).filter(PlanAdjustment.user_id == user.id, PlanAdjustment.status == status)
    return q.order_by(PlanAdjustment.created_at.desc()).all()


@router.get("/plan-adjustments/{adjustment_id}", response_model=AdjustmentOut)
def get_adjustment(adjustment_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    adj = db.query(PlanAdjustment).filter(PlanAdjustment.id == adjustment_id).first()
    if not adj:
        raise NotFoundError("Adjustment not found.")
    if adj.user_id != user.id:
        raise ForbiddenError()
    return adj


@router.post("/plan-adjustments/{adjustment_id}/respond", response_model=OkResponse)
def respond_adjustment(adjustment_id: str, payload: AdjustmentRespond, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    adj = db.query(PlanAdjustment).filter(PlanAdjustment.id == adjustment_id).first()
    if not adj:
        raise NotFoundError("Adjustment not found.")
    if adj.user_id != user.id:
        raise ForbiddenError()
    if payload.action not in ACTION_TO_STATUS:
        raise ValidationAppError(f"Invalid action. Must be one of {list(ACTION_TO_STATUS)}.")

    adj.status = ACTION_TO_STATUS[payload.action]
    db.add(Notification(
        user_id=user.id,
        type="adjustment",
        message=f"Plan adjustment {adj.status}: {adj.change_summary}",
        related_adjustment_id=adj.id,
    ))
    if adj.status == "accepted":
        apply_adjustment(db, adj)
    db.commit()
    return {"ok": True}
