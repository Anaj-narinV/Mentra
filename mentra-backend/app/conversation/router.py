from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.auth.dependencies import get_current_user
from app.core.resolvers import get_or_create_conversation
from app.core.errors import AIUnavailableError
from app.models.models import User, Message, Task, ProgressExtraction, TASK_STATUSES
from app.schemas.schemas import MessageOut, MessageCreate, MessageResponse
from app.ai_orchestration.provider import get_ai_provider
from app.adaptation.service import check_and_propose_adjustment

router = APIRouter(tags=["conversation"])
ai = get_ai_provider()

GREETING = "Hey — how's today going? Tell me about your progress, blockers, or anything that's changed."


@router.get("/conversations/{conversation_id}/messages", response_model=list[MessageOut])
def get_messages(conversation_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    convo = get_or_create_conversation(db, user.id, conversation_id)
    if not convo.messages:
        # First open: seed a mentor-voice greeting (Phase 2 §C.8 "Empty" spec).
        greeting = Message(conversation_id=convo.id, sender="ai", content=GREETING)
        db.add(greeting)
        db.commit()
        db.refresh(convo)
    return convo.messages


@router.post("/conversations/{conversation_id}/messages", response_model=MessageResponse)
def post_message(conversation_id: str, payload: MessageCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    convo = get_or_create_conversation(db, user.id, conversation_id)

    user_message = Message(conversation_id=convo.id, sender="user", content=payload.content)
    db.add(user_message)
    db.flush()

    history = [{"sender": m.sender, "content": m.content} for m in convo.messages[-6:]]
    open_tasks_q = db.query(Task).filter(Task.user_id == user.id, Task.status == "pending")
    if payload.task_id:
        open_tasks_q = open_tasks_q.filter(Task.id == payload.task_id)
    open_tasks = [{"id": t.id, "title": t.title} for t in open_tasks_q.all()]

    try:
        result = ai.process_conversation(payload.content, history, open_tasks)
    except Exception:
        raise AIUnavailableError()

    # Validate structured extraction before writing anything (NFR-9, §12 step 5).
    task_id = result.task_id
    status = result.status
    if task_id:
        task = db.query(Task).filter(Task.id == task_id, Task.user_id == user.id, Task.status != "completed").first()
        if not task or (status and status not in TASK_STATUSES):
            task_id, status = None, None

    ai_message = Message(conversation_id=convo.id, sender="ai", content=result.reply)
    db.add(ai_message)
    db.flush()

    db.add(ProgressExtraction(
        message_id=user_message.id,
        task_id=task_id,
        extracted_status=status,
        reason=result.reason,
        availability_changed=result.availability_changed,
        difficulty_flag=result.difficulty_flag,
        topic_reference=result.topic_reference,
        sentiment=result.sentiment,
        raw_ai_output={},
    ))

    task_update = None
    if task_id and status:
        task = db.query(Task).filter(Task.id == task_id).first()
        task.status = status
        task_update = {"task_id": task_id, "status": status}

    db.commit()

    # §12 step 6: flagged extractions get evaluated by the Adaptive Planning
    # Engine on its next pass — for the MVP's synchronous flow, "next pass"
    # is right now.
    if result.availability_changed or result.difficulty_flag or task_update:
        check_and_propose_adjustment(db, user.id)

    return {"reply": result.reply, "task_update": task_update}
