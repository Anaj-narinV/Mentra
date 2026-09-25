"""
Unit tests for `app.ai_orchestration.claude_provider.ClaudeAIProvider`.

These test the provider's JSON parsing, one-retry-then-fail behaviour, and
output validation/sanitization — the "never blindly trust model output" and
"handle malformed AI responses / provider failures gracefully" requirements
from the Phase 4 spec. No real network call or API key is used: the
`anthropic` SDK is faked out with a minimal stand-in so these tests run in
any environment (including ones without the package installed or network
access), while still exercising exactly the code path a real call would take
(`self._client.messages.create(...)` -> parse `.content[0].text` as JSON).
"""
import json
import sys
import types

import pytest


# ---------- fake `anthropic` module (see module docstring) ----------

class _FakeBlock:
    def __init__(self, text):
        self.type = "text"
        self.text = text


class _FakeMessage:
    def __init__(self, text):
        self.content = [_FakeBlock(text)]


class _FakeMessagesEndpoint:
    def __init__(self):
        self.queue = []  # list of str (assistant text) or Exception, consumed in order
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        item = self.queue.pop(0)
        if isinstance(item, Exception):
            raise item
        return _FakeMessage(item)


class _FakeAnthropicClient:
    def __init__(self, api_key=None):
        self.api_key = api_key
        self.messages = _FakeMessagesEndpoint()


if "anthropic" not in sys.modules:
    fake_module = types.ModuleType("anthropic")
    fake_module.Anthropic = _FakeAnthropicClient
    sys.modules["anthropic"] = fake_module


from app.core.config import settings  # noqa: E402
from app.ai_orchestration.claude_provider import ClaudeAIProvider, AIProviderError  # noqa: E402


@pytest.fixture
def provider(monkeypatch):
    monkeypatch.setattr(settings, "AI_API_KEY", "test-key")
    monkeypatch.setattr(settings, "AI_MODEL", "claude-test-model")
    p = ClaudeAIProvider()
    return p


def queue(provider, *items):
    provider._client.messages.queue.extend(items)


# ---------- construction ----------

def test_missing_api_key_raises(monkeypatch):
    monkeypatch.setattr(settings, "AI_API_KEY", "")
    with pytest.raises(AIProviderError):
        ClaudeAIProvider()


# ---------- assessment ----------

def test_generate_assessment_valid_response(provider):
    queue(provider, json.dumps({
        "ai_summary": "You're starting from the basics and have 45 minutes a day.",
        "difficulty_level": "Moderate",
        "recommended_workload": "45 minutes on most days",
    }))
    result = provider.generate_assessment({"available_time": "45 minutes"}, {"title": "Learn DSA"})
    assert "45 minutes" in result.recommended_workload
    assert result.ai_summary.startswith("You're starting")


def test_generate_assessment_malformed_json_then_retry_succeeds(provider):
    # First attempt: garbage. Second attempt (after the sharper retry prompt): valid.
    queue(provider, "not json at all", json.dumps({
        "ai_summary": "Recovered on retry.",
        "difficulty_level": "Easy",
        "recommended_workload": "30 minutes",
    }))
    result = provider.generate_assessment({}, {"title": "x"})
    assert result.ai_summary == "Recovered on retry."
    assert len(provider._client.messages.calls) == 2


def test_generate_assessment_malformed_both_attempts_raises(provider):
    queue(provider, "nope", "still not json")
    with pytest.raises(AIProviderError):
        provider.generate_assessment({}, {"title": "x"})


def test_generate_assessment_missing_summary_raises(provider):
    queue(provider, json.dumps({"difficulty_level": "Easy", "recommended_workload": "30 min"}))
    with pytest.raises(AIProviderError):
        provider.generate_assessment({}, {"title": "x"})


def test_provider_call_failure_raises(provider):
    queue(provider, RuntimeError("connection reset"), RuntimeError("still down"))
    with pytest.raises(AIProviderError):
        provider.generate_assessment({}, {"title": "x"})


def test_provider_strips_markdown_code_fences(provider):
    queue(provider, "```json\n" + json.dumps({
        "ai_summary": "Fenced response.",
        "difficulty_level": "Easy",
        "recommended_workload": "20 min",
    }) + "\n```")
    result = provider.generate_assessment({}, {"title": "x"})
    assert result.ai_summary == "Fenced response."


# ---------- roadmap ----------

def test_generate_roadmap_valid_response(provider):
    queue(provider, json.dumps({
        "milestones": [
            {"title": "Foundations", "target_date": None, "order_index": 0, "tasks_preview": ["A", "B"]},
            {"title": "Practice", "target_date": "2026-05-01", "order_index": 1, "tasks_preview": ["C"]},
        ]
    }))
    from app.ai_orchestration.provider import AssessmentResult
    assessment = AssessmentResult(ai_summary="x", difficulty_level="Easy", recommended_workload="30 min")
    result = provider.generate_roadmap(assessment, {}, {"title": "Learn X"})
    assert len(result.milestones) == 2
    assert result.milestones[0].order_index == 0
    assert result.milestones[1].tasks_preview == ["C"]


def test_generate_roadmap_missing_milestones_raises(provider):
    queue(provider, json.dumps({"not_milestones": []}))
    from app.ai_orchestration.provider import AssessmentResult
    assessment = AssessmentResult(ai_summary="x", difficulty_level="Easy", recommended_workload="30 min")
    with pytest.raises(AIProviderError):
        provider.generate_roadmap(assessment, {}, {"title": "Learn X"})


def test_generate_roadmap_milestone_missing_title_raises(provider):
    queue(provider, json.dumps({"milestones": [{"target_date": None, "order_index": 0}]}))
    from app.ai_orchestration.provider import AssessmentResult
    assessment = AssessmentResult(ai_summary="x", difficulty_level="Easy", recommended_workload="30 min")
    with pytest.raises(AIProviderError):
        provider.generate_roadmap(assessment, {}, {"title": "Learn X"})


def test_generate_roadmap_fills_missing_tasks_preview(provider):
    queue(provider, json.dumps({"milestones": [{"title": "Foundations", "order_index": 0}]}))
    from app.ai_orchestration.provider import AssessmentResult
    assessment = AssessmentResult(ai_summary="x", difficulty_level="Easy", recommended_workload="30 min")
    result = provider.generate_roadmap(assessment, {}, {"title": "Learn X"})
    assert result.milestones[0].tasks_preview  # never empty


# ---------- daily tasks ----------

def test_generate_daily_tasks_valid_and_invalid_priority_normalized(provider):
    queue(provider, json.dumps({"tasks": [
        {"title": "Task A", "description": "do it", "priority": "URGENT!!", "estimated_duration": "30 min", "due_date": None},
        {"title": "Task B", "description": "do it too", "priority": "high", "estimated_duration": "20 min", "due_date": None},
    ]}))
    tasks = provider.generate_daily_tasks({"title": "M1", "tasks_preview": ["Task A"]}, {}, remaining_days=2)
    assert len(tasks) == 2
    assert tasks[0].priority == "medium"  # invalid priority falls back safely
    assert tasks[1].priority == "high"


def test_generate_daily_tasks_skips_malformed_entries(provider):
    queue(provider, json.dumps({"tasks": [
        {"description": "no title here"},  # malformed, should be skipped
        {"title": "Valid task"},
    ]}))
    tasks = provider.generate_daily_tasks({"title": "M1"}, {}, remaining_days=2)
    assert len(tasks) == 1
    assert tasks[0].title == "Valid task"


def test_generate_daily_tasks_all_malformed_raises(provider):
    queue(provider, json.dumps({"tasks": [{"description": "no title"}]}))
    with pytest.raises(AIProviderError):
        provider.generate_daily_tasks({"title": "M1"}, {}, remaining_days=1)


# ---------- conversation ----------

def test_process_conversation_valid_completed_task(provider):
    open_tasks = [{"id": "t1", "title": "Python practice"}]
    queue(provider, json.dumps({
        "reply": "Nice work finishing that!",
        "task_id": "t1",
        "status": "completed",
        "reason": "finished python practice",
        "availability_changed": False,
        "difficulty_flag": False,
        "topic_reference": None,
        "sentiment": "positive",
    }))
    result = provider.process_conversation("I finished the python practice", [], open_tasks)
    assert result.task_id == "t1"
    assert result.status == "completed"


def test_process_conversation_rejects_task_id_not_in_open_tasks(provider):
    open_tasks = [{"id": "t1", "title": "Python practice"}]
    queue(provider, json.dumps({
        "reply": "Got it.",
        "task_id": "t99-hallucinated",
        "status": "completed",
        "reason": "x",
        "availability_changed": False,
        "difficulty_flag": False,
        "topic_reference": None,
        "sentiment": "neutral",
    }))
    result = provider.process_conversation("something", [], open_tasks)
    # Fail-safe: a task_id the model invented (not in the provided open list)
    # must never be trusted, and a status with no verified task is not kept.
    assert result.task_id is None
    assert result.status is None


def test_process_conversation_rejects_invalid_status_enum(provider):
    open_tasks = [{"id": "t1", "title": "Python practice"}]
    queue(provider, json.dumps({
        "reply": "Noted.",
        "task_id": "t1",
        "status": "definitely_done",  # not a valid Task status
        "reason": "x",
        "availability_changed": False,
        "difficulty_flag": False,
        "topic_reference": None,
        "sentiment": "neutral",
    }))
    result = provider.process_conversation("something", [], open_tasks)
    assert result.status is None


def test_process_conversation_ambiguous_message_stays_null(provider):
    # "Today was difficult" — no task reference, no clear status. The AI is
    # instructed to leave these null rather than invent an update, and the
    # provider must pass that through untouched (not backfill a guess).
    queue(provider, json.dumps({
        "reply": "Sorry to hear that — want to tell me what happened?",
        "task_id": None,
        "status": None,
        "reason": "",
        "availability_changed": False,
        "difficulty_flag": False,
        "topic_reference": None,
        "sentiment": "low_urgency",
    }))
    result = provider.process_conversation("Today was difficult.", [], [{"id": "t1", "title": "Some task"}])
    assert result.task_id is None
    assert result.status is None


def test_process_conversation_difficulty_flag_with_topic(provider):
    queue(provider, json.dumps({
        "reply": "Recursion trips a lot of people up — want a different explanation?",
        "task_id": None,
        "status": None,
        "reason": "confused about recursion",
        "availability_changed": False,
        "difficulty_flag": True,
        "topic_reference": "recursion",
        "sentiment": "high_urgency",
    }))
    result = provider.process_conversation("I don't understand recursion", [], [])
    assert result.difficulty_flag is True
    assert result.topic_reference == "recursion"


def test_process_conversation_missing_reply_raises(provider):
    queue(provider, json.dumps({"task_id": None, "status": None}))
    with pytest.raises(AIProviderError):
        provider.process_conversation("hello", [], [])


# ---------- adaptive adjustment ----------

def test_generate_adaptive_adjustment_valid(provider):
    queue(provider, json.dumps({
        "trigger_reason": "3 tasks missed in the last 7 days.",
        "change_summary": "I'll lighten the next few days.",
        "expected_effect": "Less daily pressure.",
        "change_payload": {"type": "reduce_workload"},
        "current_plan": ["5 tasks this week"],
        "proposed_plan": ["3 tasks this week"],
        "confidence": 0.8,
    }))
    result = provider.generate_adaptive_adjustment([], {"tasks_missed": 3}, {"id": "r1"})
    assert result.change_payload["type"] == "reduce_workload"
    assert result.confidence == 0.8


def test_generate_adaptive_adjustment_clamps_confidence_and_fixes_bad_type(provider):
    queue(provider, json.dumps({
        "trigger_reason": "reason",
        "change_summary": "summary",
        "expected_effect": "",
        "change_payload": {"type": "not_a_real_type"},
        "current_plan": [],
        "proposed_plan": [],
        "confidence": 5.0,  # out of range
    }))
    result = provider.generate_adaptive_adjustment([], {}, {"id": "r1"})
    assert result.confidence == 1.0
    assert result.change_payload["type"] == "reduce_workload"  # safe fallback
    assert result.current_plan and result.proposed_plan  # never empty


def test_generate_adaptive_adjustment_missing_required_fields_raises(provider):
    queue(provider, json.dumps({"expected_effect": "x"}))
    with pytest.raises(AIProviderError):
        provider.generate_adaptive_adjustment([], {}, {"id": "r1"})


# ---------- factory fallback ----------

def test_get_ai_provider_falls_back_to_stub_when_no_key(monkeypatch):
    from app.ai_orchestration import provider as provider_module
    monkeypatch.setattr(provider_module.settings, "AI_PROVIDER", "claude")
    monkeypatch.setattr(provider_module.settings, "AI_API_KEY", "")
    result = provider_module.get_ai_provider()
    assert isinstance(result, provider_module.StubAIProvider)


def test_get_ai_provider_falls_back_to_stub_on_init_failure(monkeypatch):
    from app.ai_orchestration import provider as provider_module
    monkeypatch.setattr(provider_module.settings, "AI_PROVIDER", "claude")
    monkeypatch.setattr(provider_module.settings, "AI_API_KEY", "test-key")

    def _boom():
        raise AIProviderError("simulated init failure")

    monkeypatch.setattr(
        "app.ai_orchestration.claude_provider.ClaudeAIProvider.__init__",
        lambda self: (_ for _ in ()).throw(AIProviderError("simulated init failure")),
    )
    result = provider_module.get_ai_provider()
    assert isinstance(result, provider_module.StubAIProvider)


def test_get_ai_provider_defaults_to_stub(monkeypatch):
    from app.ai_orchestration import provider as provider_module
    monkeypatch.setattr(provider_module.settings, "AI_PROVIDER", "stub")
    result = provider_module.get_ai_provider()
    assert isinstance(result, provider_module.StubAIProvider)
