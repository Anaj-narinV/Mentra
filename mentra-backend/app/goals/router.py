from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.auth.dependencies import get_current_user
from app.core.resolvers import resolve_goal
from app.core.errors import NotFoundError
from app.models.models import User, Goal, Assessment
from app.schemas.schemas import GoalCreate, GoalOut, AssessmentOut
from app.goals.service import create_goal_with_plan

router = APIRouter(tags=["goals"])


@router.post("/goals", response_model=GoalOut)
def create_goal(payload: GoalCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    goal = create_goal_with_plan(db, user.id, payload.model_dump())
    return goal


@router.get("/goals", response_model=list[GoalOut])
def list_goals(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return db.query(Goal).filter(Goal.user_id == user.id).order_by(Goal.created_at.desc()).all()


@router.get("/goals/{goal_id}", response_model=GoalOut)
def get_goal(goal_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return resolve_goal(db, user.id, goal_id)


@router.get("/goals/{goal_id}/assessment", response_model=AssessmentOut)
def get_assessment(goal_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    goal = resolve_goal(db, user.id, goal_id)
    assessment = db.query(Assessment).filter(Assessment.goal_id == goal.id).first()
    if not assessment:
        raise NotFoundError("Assessment not found for this goal.")
    return assessment
