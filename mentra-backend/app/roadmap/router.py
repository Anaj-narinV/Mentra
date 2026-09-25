from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.auth.dependencies import get_current_user
from app.core.resolvers import resolve_goal
from app.core.errors import NotFoundError, ForbiddenError
from app.models.models import User, Roadmap, Milestone, Task
from app.schemas.schemas import RoadmapOut, MilestoneOut, MilestoneUpdate, OkResponse

router = APIRouter(tags=["roadmap"])


def _milestone_out(m: Milestone, db: Session) -> dict:
    tasks = db.query(Task).filter(Task.milestone_id == m.id).all()
    total = len(tasks)
    done = len([t for t in tasks if t.status == "completed"])
    pct = round((done / total) * 100) if total else 0
    preview = [t.title for t in tasks[:3]] if tasks else []
    return {
        "id": m.id,
        "title": m.title,
        "target_date": m.target_date,
        "status": m.status,
        "progress_pct": pct,
        "tasks_preview": preview,
    }


@router.get("/goals/{goal_id}/roadmap", response_model=RoadmapOut)
def get_roadmap(goal_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    goal = resolve_goal(db, user.id, goal_id)
    roadmap = db.query(Roadmap).filter(Roadmap.goal_id == goal.id, Roadmap.status == "active").first()
    if not roadmap:
        return {"goal_id": goal.id, "milestones": []}
    milestones = [_milestone_out(m, db) for m in roadmap.milestones]
    return {"goal_id": goal.id, "milestones": milestones}


@router.put("/milestones/{milestone_id}", response_model=OkResponse)
def update_milestone(milestone_id: str, payload: MilestoneUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    milestone = db.query(Milestone).filter(Milestone.id == milestone_id).first()
    if not milestone:
        raise NotFoundError("Milestone not found.")
    if milestone.roadmap.goal.user_id != user.id:
        raise ForbiddenError()
    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(milestone, key, value)
    db.commit()
    return {"ok": True}
