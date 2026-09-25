"""
Mentra's MVP supports one active goal (and one conversation) per user
(Architecture §14). The approved frontend contract (Phase 2) sometimes
references that singleton with a fixed placeholder id (e.g. Roadmap.jsx's
`GOAL_ID = "g1"`) rather than looking it up dynamically.

Rather than forcing the frontend to thread real UUIDs through every screen
(a Phase-2 UI change outside this phase's scope), the backend accepts the
literal path segment "current" anywhere a goal_id/conversation_id is expected,
and resolves it to the user's single active goal / conversation, creating one
on first access if none exists yet. Real ids also work everywhere, so the
contract keeps working when the frontend is later updated to pass real ids
(e.g. right after goal creation).
"""
from sqlalchemy.orm import Session
from app.models.models import Goal, Conversation
from app.core.errors import NotFoundError


def resolve_goal(db: Session, user_id: str, goal_id: str) -> Goal:
    if goal_id == "current":
        goal = (
            db.query(Goal)
            .filter(Goal.user_id == user_id, Goal.status == "active")
            .order_by(Goal.created_at.desc())
            .first()
        )
        if not goal:
            raise NotFoundError("No active goal yet — create a goal first.")
        return goal
    goal = db.query(Goal).filter(Goal.id == goal_id, Goal.user_id == user_id).first()
    if not goal:
        raise NotFoundError("Goal not found.")
    return goal


def get_or_create_conversation(db: Session, user_id: str, conversation_id: str) -> Conversation:
    if conversation_id == "current":
        convo = (
            db.query(Conversation)
            .filter(Conversation.user_id == user_id)
            .order_by(Conversation.started_at.desc())
            .first()
        )
        if not convo:
            convo = Conversation(user_id=user_id)
            db.add(convo)
            db.commit()
            db.refresh(convo)
        return convo
    convo = db.query(Conversation).filter(Conversation.id == conversation_id, Conversation.user_id == user_id).first()
    if not convo:
        raise NotFoundError("Conversation not found.")
    return convo
