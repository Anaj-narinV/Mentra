import os
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_mentra.db")

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    if os.path.exists("test_mentra.db"):
        os.remove("test_mentra.db")
    from app.main import app
    with TestClient(app) as c:
        yield c
    if os.path.exists("test_mentra.db"):
        os.remove("test_mentra.db")


@pytest.fixture(scope="module")
def auth_header(client):
    r = client.post("/auth/signup", json={"name": "Jana", "email": "jana@example.com", "password": "hunter22"})
    assert r.status_code == 200, r.text
    token = r.json()["token"]
    return {"Authorization": f"Bearer {token}"}


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_signup_duplicate_conflict(client, auth_header):
    r = client.post("/auth/signup", json={"name": "Jana", "email": "jana@example.com", "password": "hunter22"})
    assert r.status_code == 409


def test_login_success_and_failure(client, auth_header):
    r = client.post("/auth/login", json={"email": "jana@example.com", "password": "hunter22"})
    assert r.status_code == 200
    assert "token" in r.json()
    r2 = client.post("/auth/login", json={"email": "jana@example.com", "password": "wrong"})
    assert r2.status_code == 401


def test_protected_route_requires_auth(client):
    r = client.get("/profile")
    assert r.status_code == 401


def test_profile_and_onboarding(client, auth_header):
    r = client.get("/profile", headers=auth_header)
    assert r.status_code == 200
    assert r.json()["onboarding_complete"] is False

    payload = {
        "daily_routine": "College 9-4, free evenings",
        "available_time": "45 minutes",
        "preferred_schedule": "evenings",
        "existing_knowledge": "Basic Python",
        "constraints": ["College classes"],
        "preferences": ["Short daily sessions"],
    }
    r2 = client.post("/onboarding", json=payload, headers=auth_header)
    assert r2.status_code == 200
    assert r2.json()["ok"] is True

    r3 = client.get("/profile", headers=auth_header)
    assert r3.json()["onboarding_complete"] is True
    assert r3.json()["available_time"] == "45 minutes"


GOAL_ID = {}


def test_create_goal_triggers_assessment_and_roadmap(client, auth_header):
    payload = {
        "title": "Learn DSA for placements",
        "target_outcome": "Clear technical interviews",
        "current_level": "Comfortable with basic Python, new to DSA",
        "target_date": "2026-12-15",
    }
    r = client.post("/goals", json=payload, headers=auth_header)
    assert r.status_code == 200, r.text
    goal = r.json()
    assert goal["status"] == "active"
    GOAL_ID["id"] = goal["id"]

    r2 = client.get(f"/goals/{goal['id']}/assessment", headers=auth_header)
    assert r2.status_code == 200
    assert len(r2.json()["ai_summary"]) > 10

    r3 = client.get(f"/goals/{goal['id']}/roadmap", headers=auth_header)
    assert r3.status_code == 200
    milestones = r3.json()["milestones"]
    # The AI roadmap contract (Architecture §11, prompts.py::roadmap_prompt)
    # allows 3-6 milestones — the exact count is a provider decision, not
    # part of the contract. The StubAIProvider happens to always return 4,
    # but a real AI provider legitimately may not, so this asserts the
    # contract's bounds rather than one provider's specific behavior.
    assert 3 <= len(milestones) <= 6
    assert milestones[0]["status"] == "in_progress"


def test_goal_current_alias(client, auth_header):
    r = client.get("/goals/current/roadmap", headers=auth_header)
    assert r.status_code == 200
    assert r.json()["milestones"]


def test_tasks_today_and_week(client, auth_header):
    r = client.get("/tasks?date=today", headers=auth_header)
    assert r.status_code == 200
    tasks = r.json()
    assert len(tasks) >= 1
    task_id = tasks[0]["id"]

    r2 = client.get("/tasks?range=week", headers=auth_header)
    assert r2.status_code == 200
    assert len(r2.json()) >= len(tasks)

    r3 = client.put(f"/tasks/{task_id}/status", json={"status": "completed"}, headers=auth_header)
    assert r3.status_code == 200

    r4 = client.put(f"/tasks/{task_id}/status", json={"status": "bogus_status"}, headers=auth_header)
    assert r4.status_code == 422


def test_task_ownership_protection(client):
    client.post("/auth/signup", json={"name": "Other", "email": "other@example.com", "password": "hunter22"})
    r = client.post("/auth/login", json={"email": "other@example.com", "password": "hunter22"})
    other_header = {"Authorization": f"Bearer {r.json()['token']}"}
    r2 = client.get("/tasks?date=today", headers=other_header)
    assert r2.status_code == 200
    assert r2.json() == []  # no tasks yet for this user - isolation holds


def test_conversation_flow(client, auth_header):
    r = client.get("/conversations/current/messages", headers=auth_header)
    assert r.status_code == 200
    assert len(r.json()) >= 1  # greeting seeded

    r2 = client.post("/conversations/current/messages", json={"content": "I finished today's task!"}, headers=auth_header)
    assert r2.status_code == 200
    body = r2.json()
    assert "reply" in body

    r3 = client.get("/conversations/current/messages", headers=auth_header)
    assert len(r3.json()) >= 3


def test_progress_summary(client, auth_header):
    r = client.get("/progress/summary?period=weekly", headers=auth_header)
    assert r.status_code == 200
    data = r.json()
    assert "daily" in data and "weekly" in data and "monthly" in data
    assert "upcoming" in data


def test_plan_adjustment_flow(client, auth_header):
    # Simulate 3 missed tasks in the trailing 7 days (the seeded demo tasks
    # are dated today..today+6, so we backdate a few to exercise the
    # Layer-1 trigger rule the way it would fire in real usage).
    from datetime import date, timedelta
    from app.database.session import SessionLocal
    from app.models.models import Task

    r = client.get("/tasks?range=week", headers=auth_header)
    task_ids = [t["id"] for t in r.json() if t["status"] == "pending"][:3]

    db = SessionLocal()
    for i, tid in enumerate(task_ids):
        t = db.query(Task).filter(Task.id == tid).first()
        t.due_date = (date.today() - timedelta(days=i + 1)).isoformat()
        t.status = "skipped"
    db.commit()
    db.close()

    r2 = client.get("/plan-adjustments?status=proposed", headers=auth_header)
    assert r2.status_code == 200
    proposed = r2.json()
    assert len(proposed) >= 1
    adj_id = proposed[0]["id"]

    r3 = client.get(f"/plan-adjustments/{adj_id}", headers=auth_header)
    assert r3.status_code == 200

    r4 = client.post(f"/plan-adjustments/{adj_id}/respond", json={"action": "accept"}, headers=auth_header)
    assert r4.status_code == 200

    r5 = client.get(f"/plan-adjustments/{adj_id}", headers=auth_header)
    assert r5.json()["status"] == "accepted"


def test_notifications_flow(client, auth_header):
    r = client.get("/notifications", headers=auth_header)
    assert r.status_code == 200
    notifs = r.json()
    assert len(notifs) >= 1
    nid = notifs[0]["id"]
    r2 = client.put(f"/notifications/{nid}/read", headers=auth_header)
    assert r2.status_code == 200
    r3 = client.get("/notifications", headers=auth_header)
    assert any(n["id"] == nid and n["is_read"] for n in r3.json())


def test_cross_user_isolation_for_adjustment(client):
    r = client.post("/auth/login", json={"email": "other@example.com", "password": "hunter22"})
    other_header = {"Authorization": f"Bearer {r.json()['token']}"}
    r2 = client.get("/plan-adjustments?status=proposed", headers=other_header)
    assert r2.json() == []
