"""
Phase 4 integration tests, run against the deterministic StubAIProvider
(AI_PROVIDER defaults to "stub" whenever AI_API_KEY isn't set — exactly the
"tests keep working without a live key" behaviour `get_ai_provider()` is
built for). These exercise the *shared* validation/extraction/adaptation
logic in conversation/router.py and adaptation/service.py that runs
identically regardless of which AIProvider is behind it — the same paths a
real Claude response would flow through.

Separate sqlite file + its own TestClient from test_e2e_flow.py so this file
can be run/read independently and doesn't disturb the existing suite's
fixture ordering.
"""
import os
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_mentra_ai.db")

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    if os.path.exists("test_mentra_ai.db"):
        os.remove("test_mentra_ai.db")
    from app.main import app
    from app.database.session import engine
    with TestClient(app) as c:
        yield c
    # Windows keeps an OS-level file lock on a SQLite file for as long as any
    # pooled DB connection referencing it stays open. Exiting the TestClient
    # context manager above closes the HTTP test client, but the app's
    # module-level SQLAlchemy `engine` (app/database/session.py) is a
    # separate, longer-lived object whose connection pool isn't torn down by
    # that alone — so without disposing it first, the `os.remove` below can
    # raise `PermissionError: [WinError 32] ... being used by another
    # process` on Windows (harmless no-op difference on POSIX, where
    # unlinking an open file is allowed).
    engine.dispose()
    if os.path.exists("test_mentra_ai.db"):
        os.remove("test_mentra_ai.db")


@pytest.fixture(scope="module")
def auth_header(client):
    r = client.post("/auth/signup", json={"name": "Riya", "email": "riya@example.com", "password": "hunter22"})
    assert r.status_code == 200, r.text
    token = r.json()["token"]
    header = {"Authorization": f"Bearer {token}"}

    client.post("/onboarding", json={
        "daily_routine": "Work 9-5",
        "available_time": "40 minutes",
        "preferred_schedule": "evenings",
        "existing_knowledge": "None",
        "constraints": [],
        "preferences": [],
    }, headers=header)

    client.post("/goals", json={
        "title": "Learn recursion and DP",
        "target_outcome": "Solve medium DP problems",
        "current_level": "Beginner",
        "target_date": "2026-12-01",
    }, headers=header)

    return header


# ---------- conversational progress extraction (§12) ----------

def _open_task_id(client, header):
    tasks = client.get("/tasks?range=week", headers=header).json()
    pending = [t for t in tasks if t["status"] == "pending"]
    assert pending, "expected at least one seeded pending task"
    return pending[0]["id"]


def test_completed_task_extraction(client, auth_header):
    task_id = _open_task_id(client, auth_header)
    r = client.post(
        "/conversations/current/messages",
        json={"content": "I finished today's practice, done!", "task_id": task_id},
        headers=auth_header,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["task_update"] is not None
    assert body["task_update"]["status"] == "completed"
    assert body["task_update"]["task_id"] == task_id

    t = client.get("/tasks?range=week", headers=auth_header).json()
    updated = next(x for x in t if x["id"] == task_id)
    assert updated["status"] == "completed"


def test_partial_completion_extraction(client, auth_header):
    tasks = client.get("/tasks?range=week", headers=auth_header).json()
    pending = [t for t in tasks if t["status"] == "pending"]
    task_id = pending[0]["id"]
    r = client.post(
        "/conversations/current/messages",
        json={"content": "I couldn't finish it, ran out of time halfway through", "task_id": task_id},
        headers=auth_header,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["task_update"]["status"] == "partially_completed"


def test_reschedule_and_availability_change_extraction(client, auth_header):
    tasks = client.get("/tasks?range=week", headers=auth_header).json()
    pending = [t for t in tasks if t["status"] == "pending"]
    task_id = pending[0]["id"]
    r = client.post(
        "/conversations/current/messages",
        json={"content": "I have an exam tomorrow, can we move this?", "task_id": task_id},
        headers=auth_header,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["task_update"]["status"] == "rescheduled"


def test_difficulty_detection_without_forcing_a_task_status(client, auth_header):
    r = client.post(
        "/conversations/current/messages",
        json={"content": "I don't understand recursion at all, it's really confusing"},
        headers=auth_header,
    )
    assert r.status_code == 200
    # A difficulty statement with no explicit completion claim must not
    # silently mark a task as skipped/completed — the stub provider (and the
    # real provider's prompt contract) leave status null here.
    body = r.json()
    assert body["task_update"] is None


def test_general_question_produces_no_task_update(client, auth_header):
    r = client.post(
        "/conversations/current/messages",
        json={"content": "By the way, what's the weather like today"},
        headers=auth_header,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["task_update"] is None
    assert body["reply"]  # still gets a conversational reply


# ---------- adaptive intelligence: Rule 4, repeated difficulty ----------

def test_repeated_difficulty_on_same_topic_triggers_adjustment(client, auth_header):
    # An earlier test (availability change) may have already left a
    # 'proposed' adjustment pending — clear it first so this test cleanly
    # isolates Rule 4 (repeated difficulty), not whichever rule fired first.
    pending = client.get("/plan-adjustments?status=proposed", headers=auth_header).json()
    for adj in pending:
        client.post(f"/plan-adjustments/{adj['id']}/respond", json={"action": "decline"}, headers=auth_header)

    # Two separate messages flagging difficulty with the same topic within
    # the lookback window should trigger Rule 4 even with no missed tasks.
    client.post(
        "/conversations/current/messages",
        json={"content": "I'm really stuck on recursion, it's confusing"},
        headers=auth_header,
    )
    r = client.post(
        "/conversations/current/messages",
        json={"content": "Still stuck on recursion, I don't get it at all"},
        headers=auth_header,
    )
    assert r.status_code == 200

    proposed = client.get("/plan-adjustments?status=proposed", headers=auth_header).json()
    assert len(proposed) >= 1
    # trigger_reason should be a plain-language, observable-data explanation,
    # not a dump of internal reasoning.
    assert proposed[0]["trigger_reason"]


# ---------- security / isolation ----------

def test_conversation_and_adjustments_are_isolated_per_user(client):
    client.post("/auth/signup", json={"name": "Other2", "email": "other2@example.com", "password": "hunter22"})
    r = client.post("/auth/login", json={"email": "other2@example.com", "password": "hunter22"})
    other_header = {"Authorization": f"Bearer {r.json()['token']}"}

    convo = client.get("/conversations/current/messages", headers=other_header).json()
    # Fresh user only sees their own seeded greeting, never Riya's messages.
    assert all("recursion" not in m["content"].lower() for m in convo)

    adjustments = client.get("/plan-adjustments?status=proposed", headers=other_header).json()
    assert adjustments == []


# ---------- _recent_extractions DateTime comparison (Phase 5 fix #5) ----------

def test_recent_extractions_filters_by_cutoff_correctly(client):
    """
    Directly exercises adaptation.service._recent_extractions' DateTime
    comparison: inserts one ProgressExtraction well outside the lookback
    window and one well inside it (bypassing the API so we control
    created_at precisely), then asserts only the recent one comes back.
    Guards against the cutoff/column type mismatch this was fixed for
    (comparing a `date` against a `DateTime` column vs. a proper `datetime`).
    """
    from datetime import datetime, timedelta, timezone
    from app.database.session import SessionLocal
    from app.models.models import Conversation, Message, ProgressExtraction
    from app.adaptation.service import _recent_extractions, DIFFICULTY_LOOKBACK_DAYS

    r = client.post("/auth/signup", json={"name": "Priya", "email": "priya@example.com", "password": "hunter22"})
    assert r.status_code == 200, r.text
    user_id = r.json()["user"]["id"]

    db = SessionLocal()
    convo = Conversation(user_id=user_id)
    db.add(convo)
    db.flush()

    recent_msg = Message(conversation_id=convo.id, sender="user", content="recent")
    old_msg = Message(conversation_id=convo.id, sender="user", content="old")
    db.add_all([recent_msg, old_msg])
    db.flush()

    now = datetime.now(timezone.utc)
    db.add_all([
        ProgressExtraction(
            message_id=recent_msg.id, reason="recent", difficulty_flag=True,
            topic_reference="recursion", created_at=now - timedelta(days=1),
        ),
        ProgressExtraction(
            message_id=old_msg.id, reason="old", difficulty_flag=True,
            topic_reference="recursion", created_at=now - timedelta(days=DIFFICULTY_LOOKBACK_DAYS + 5),
        ),
    ])
    db.commit()

    results = _recent_extractions(db, user_id)
    reasons = {e.reason for e in results}
    assert "recent" in reasons
    assert "old" not in reasons
    db.close()


# ---------- daily task intelligence: milestone continuation ----------

def test_milestone_advances_and_next_milestone_gets_tasks(client):
    """
    PHASE_3_HANDOFF.md §9 item 5 flagged this as a known gap: only the first
    milestone was ever seeded with tasks. Phase 4's `ensure_current_milestone_tasks`
    (called on every GET /tasks) should advance the roadmap and generate the
    next milestone's tasks once the current one's are all resolved.
    """
    client.post("/auth/signup", json={"name": "Devon", "email": "devon@example.com", "password": "hunter22"})
    r = client.post("/auth/login", json={"email": "devon@example.com", "password": "hunter22"})
    header = {"Authorization": f"Bearer {r.json()['token']}"}

    client.post("/onboarding", json={
        "daily_routine": "Free evenings",
        "available_time": "30 minutes",
        "preferred_schedule": "evenings",
        "existing_knowledge": "None",
        "constraints": [],
        "preferences": [],
    }, headers=header)

    goal = client.post("/goals", json={
        "title": "Learn guitar basics",
        "target_outcome": "Play simple songs",
        "current_level": "Complete beginner",
        "target_date": "2026-12-01",
    }, headers=header).json()

    roadmap_before = client.get(f"/goals/{goal['id']}/roadmap", headers=header).json()
    milestone_1_id = roadmap_before["milestones"][0]["id"]
    assert roadmap_before["milestones"][0]["status"] == "in_progress"
    assert roadmap_before["milestones"][1]["status"] == "upcoming"

    # Resolve every task on milestone 1.
    all_tasks = client.get("/tasks?range=week", headers=header).json()
    m1_task_ids = [t["id"] for t in all_tasks if t["milestone_id"] == milestone_1_id]
    assert m1_task_ids, "expected milestone 1 to be seeded with tasks at goal creation"
    for tid in m1_task_ids:
        resp = client.put(f"/tasks/{tid}/status", json={"status": "completed"}, headers=header)
        assert resp.status_code == 200

    # Next GET /tasks should trigger advancement + generation for milestone 2.
    client.get("/tasks?range=week", headers=header)

    roadmap_after = client.get(f"/goals/{goal['id']}/roadmap", headers=header).json()
    m1_after = next(m for m in roadmap_after["milestones"] if m["id"] == milestone_1_id)
    m2_after = roadmap_after["milestones"][1]
    assert m1_after["status"] == "completed"
    assert m2_after["status"] == "in_progress"
    assert m2_after["tasks_preview"], "milestone 2 should now have generated tasks"


# ---------- Phase 6 fix: unguarded generate_daily_tasks call in POST /goals ----------

def test_goal_creation_ai_failure_during_task_seeding_is_graceful(client, monkeypatch):
    """
    Regression test for the bug report: generate_daily_tasks() failing
    during POST /goals (e.g. a Gemini provider raising AIProviderError on
    truncated JSON) must surface as a clean 503 AIUnavailableError, not an
    unhandled 500 — and must leave no partial Goal/Assessment/Roadmap/
    Milestone behind, since nothing was committed before the failure.
    generate_assessment and generate_roadmap were already wrapped in
    try/except in goals/service.py; this call was the one that wasn't.
    """
    r = client.post("/auth/signup", json={"name": "Failer", "email": "failer@example.com", "password": "hunter22"})
    assert r.status_code == 200
    header = {"Authorization": f"Bearer {r.json()['token']}"}
    client.post("/onboarding", json={
        "daily_routine": "x", "available_time": "30 minutes", "preferred_schedule": "evenings",
        "existing_knowledge": "", "constraints": [], "preferences": [],
    }, headers=header)

    import app.goals.service as goals_service

    def _boom(*args, **kwargs):
        raise RuntimeError("simulated truncated Gemini response: Unterminated string")

    monkeypatch.setattr(goals_service.ai, "generate_daily_tasks", _boom)

    r = client.post("/goals", json={
        "title": "Learn recursion", "target_outcome": "y", "current_level": "Beginner", "target_date": "2026-12-01",
    }, headers=header)
    assert r.status_code == 503
    assert r.json()["detail"]

    # No partial Goal should have been persisted — the failure happened
    # before db.commit(), so the rolled-back transaction must leave nothing.
    goals = client.get("/goals", headers=header).json()
    assert goals == []
