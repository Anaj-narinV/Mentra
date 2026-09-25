"""
Unit tests for `app.ai_orchestration.gemini_provider.GeminiAIProvider`.

Mirrors `tests/test_ai_provider.py` (the Claude provider's test suite)
exactly in structure and coverage, since both providers must satisfy the
identical downstream contract. The `google-genai` SDK is faked out with a
minimal stand-in — no real network call or API key is used, and no request
ever reaches Google's servers.

If the real `google-genai` package happens to be installed in the
environment this runs in, the fake is only registered when it isn't already
present (same guard pattern as test_ai_provider.py's `anthropic` fake), so
this never shadows a real installation.
"""
import json
import sys
import types as pytypes

import pytest


# ---------- fake `google.genai` module (see module docstring) ----------

class _FakeResponse:
    def __init__(self, text):
        self.text = text


class _FakeModelsEndpoint:
    def __init__(self):
        self.queue = []  # list of str (response text) or Exception, consumed in order
        self.calls = []

    def generate_content(self, **kwargs):
        self.calls.append(kwargs)
        item = self.queue.pop(0)
        if isinstance(item, Exception):
            raise item
        return _FakeResponse(item)


class _FakeGenaiClient:
    def __init__(self, api_key=None):
        self.api_key = api_key
        self.models = _FakeModelsEndpoint()


class _FakeGenerateContentConfig:
    """Stand-in for google.genai.types.GenerateContentConfig — just needs to
    accept and remember the kwargs the provider passes it."""
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


if "google.genai" not in sys.modules:
    google_pkg = sys.modules.get("google") or pytypes.ModuleType("google")
    genai_mod = pytypes.ModuleType("google.genai")
    genai_mod.Client = _FakeGenaiClient
    types_mod = pytypes.ModuleType("google.genai.types")
    types_mod.GenerateContentConfig = _FakeGenerateContentConfig
    genai_mod.types = types_mod
    google_pkg.genai = genai_mod
    sys.modules["google"] = google_pkg
    sys.modules["google.genai"] = genai_mod
    sys.modules["google.genai.types"] = types_mod


from app.core.config import settings  # noqa: E402
from app.ai_orchestration.gemini_provider import GeminiAIProvider, AIProviderError  # noqa: E402


@pytest.fixture
def provider(monkeypatch):
    monkeypatch.setattr(settings, "AI_API_KEY", "test-key")
    monkeypatch.setattr(settings, "AI_MODEL", "gemini-test-model")
    p = GeminiAIProvider()
    return p


def queue(provider, *items):
    provider._client.models.queue.extend(items)


# ---------- construction ----------

def test_missing_api_key_raises(monkeypatch):
    monkeypatch.setattr(settings, "AI_API_KEY", "")
    with pytest.raises(AIProviderError):
        GeminiAIProvider()


def test_model_defaults_when_ai_model_unset(monkeypatch):
    monkeypatch.setattr(settings, "AI_API_KEY", "test-key")
    monkeypatch.setattr(settings, "AI_MODEL", "")
    p = GeminiAIProvider()
    assert p._model == "gemini-3.5-flash"


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
    queue(provider, "not json at all", json.dumps({
        "ai_summary": "Recovered on retry.",
        "difficulty_level": "Easy",
        "recommended_workload": "30 minutes",
    }))
    result = provider.generate_assessment({}, {"title": "x"})
    assert result.ai_summary == "Recovered on retry."
    assert len(provider._client.models.calls) == 2


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


def test_generate_content_called_with_json_mime_type(provider):
    queue(provider, json.dumps({
        "ai_summary": "x", "difficulty_level": "Easy", "recommended_workload": "30 min",
    }))
    provider.generate_assessment({}, {"title": "x"})
    call = provider._client.models.calls[0]
    assert call["model"] == "gemini-test-model"
    assert call["config"].response_mime_type == "application/json"


# ---------- native structured-output schema (Phase 6 truncation-bug fix) ----------
# Regression coverage for: POST /goals returning 500 because
# generate_daily_tasks() received truncated JSON from Gemini. Root cause was
# two-fold — (1) no explicit response_schema constraining Gemini's
# controlled generation, and (2) generate_daily_tasks had no max_tokens
# override at all, silently using _complete_json's 1600-token default sized
# for a single small object rather than an array of daily tasks.

def test_generate_assessment_passes_explicit_response_schema(provider):
    queue(provider, json.dumps({
        "ai_summary": "x", "difficulty_level": "Easy", "recommended_workload": "30 min",
    }))
    provider.generate_assessment({}, {"title": "x"})
    schema = provider._client.models.calls[0]["config"].response_schema
    assert schema["type"] == "OBJECT"
    assert "ai_summary" in schema["properties"]
    assert "ai_summary" in schema["required"]


def test_generate_daily_tasks_passes_explicit_response_schema(provider):
    queue(provider, json.dumps({"tasks": [{"title": "Task A", "description": "x", "priority": "medium"}]}))
    provider.generate_daily_tasks({"title": "M1"}, {}, remaining_days=1)
    schema = provider._client.models.calls[0]["config"].response_schema
    assert schema["type"] == "OBJECT"
    assert schema["properties"]["tasks"]["type"] == "ARRAY"
    assert schema["properties"]["tasks"]["items"]["properties"]["priority"]["enum"] == ["low", "medium", "high"]


def test_generate_daily_tasks_token_budget_scales_with_remaining_days(provider):
    queue(provider, json.dumps({"tasks": [{"title": "Task A", "description": "x", "priority": "medium"}]}))
    provider.generate_daily_tasks({"title": "M1"}, {}, remaining_days=1)
    small_budget = provider._client.models.calls[0]["config"].max_output_tokens

    queue(provider, json.dumps({"tasks": [{"title": "Task A", "description": "x", "priority": "medium"}]}))
    provider.generate_daily_tasks({"title": "M1"}, {}, remaining_days=7)
    large_budget = provider._client.models.calls[1]["config"].max_output_tokens

    # A week of tasks must get meaningfully more room than a single day —
    # this is the actual fix for the truncation bug, not just a schema.
    assert large_budget > small_budget
    assert large_budget == min(4096, 500 + 7 * 260)  # matches the sizing formula exactly


def test_generate_daily_tasks_still_raises_on_genuinely_truncated_response(provider):
    # Confirms the fix does NOT weaken validation: a response that is still
    # unparseable JSON (e.g. truly cut off mid-string, reproducing the
    # bug-report symptom) on both attempts must still raise AIProviderError,
    # not silently return partial/corrupt task data.
    truncated = '{"tasks": [{"title": "Practice recursion problems", "description": "Work through the har'
    queue(provider, truncated, truncated)
    with pytest.raises(AIProviderError):
        provider.generate_daily_tasks({"title": "M1"}, {}, remaining_days=7)


def test_generate_daily_tasks_recovers_if_retry_is_complete(provider):
    truncated = '{"tasks": [{"title": "Practice recursion problems", "description": "Work through the har'
    complete = json.dumps({"tasks": [{"title": "Practice recursion problems", "description": "Work through the hard cases.", "priority": "medium"}]})
    queue(provider, truncated, complete)
    tasks = provider.generate_daily_tasks({"title": "M1"}, {}, remaining_days=7)
    assert len(tasks) == 1
    assert tasks[0].title == "Practice recursion problems"


def test_all_five_operations_pass_a_response_schema(provider):
    # Broad sweep confirming every operation was updated, not just the one
    # that happened to trip the bug report.
    from app.ai_orchestration.provider import AssessmentResult

    queue(provider, json.dumps({"ai_summary": "x", "difficulty_level": "e", "recommended_workload": "w"}))
    provider.generate_assessment({}, {"title": "x"})

    queue(provider, json.dumps({"milestones": [{"title": "M", "order_index": 0, "tasks_preview": ["t"]}]}))
    assessment = AssessmentResult(ai_summary="x", difficulty_level="e", recommended_workload="w")
    provider.generate_roadmap(assessment, {}, {"title": "x"})

    queue(provider, json.dumps({"tasks": [{"title": "t", "description": "d", "priority": "medium"}]}))
    provider.generate_daily_tasks({"title": "M1"}, {}, remaining_days=1)

    queue(provider, json.dumps({
        "reply": "ok", "task_id": None, "status": None, "reason": "", "availability_changed": False,
        "difficulty_flag": False, "topic_reference": None, "sentiment": "neutral",
    }))
    provider.process_conversation("hi", [], [])

    queue(provider, json.dumps({
        "trigger_reason": "r", "change_summary": "s", "expected_effect": "e",
        "change_payload": {"type": "reduce_workload"}, "current_plan": [], "proposed_plan": [], "confidence": 0.5,
    }))
    provider.generate_adaptive_adjustment([], {}, {"id": "r1"})

    for call in provider._client.models.calls:
        assert call["config"].response_schema is not None
        assert call["config"].response_schema["type"] == "OBJECT"


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
    assert result.milestones[0].tasks_preview


# ---------- daily tasks ----------

def test_generate_daily_tasks_valid_and_invalid_priority_normalized(provider):
    queue(provider, json.dumps({"tasks": [
        {"title": "Task A", "description": "do it", "priority": "URGENT!!", "estimated_duration": "30 min", "due_date": None},
        {"title": "Task B", "description": "do it too", "priority": "high", "estimated_duration": "20 min", "due_date": None},
    ]}))
    tasks = provider.generate_daily_tasks({"title": "M1", "tasks_preview": ["Task A"]}, {}, remaining_days=2)
    assert len(tasks) == 2
    assert tasks[0].priority == "medium"
    assert tasks[1].priority == "high"


def test_generate_daily_tasks_skips_malformed_entries(provider):
    queue(provider, json.dumps({"tasks": [
        {"description": "no title here"},
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
    assert result.task_id is None
    assert result.status is None


def test_process_conversation_rejects_invalid_status_enum(provider):
    open_tasks = [{"id": "t1", "title": "Python practice"}]
    queue(provider, json.dumps({
        "reply": "Noted.",
        "task_id": "t1",
        "status": "definitely_done",
        "reason": "x",
        "availability_changed": False,
        "difficulty_flag": False,
        "topic_reference": None,
        "sentiment": "neutral",
    }))
    result = provider.process_conversation("something", [], open_tasks)
    assert result.status is None


def test_process_conversation_ambiguous_message_stays_null(provider):
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
        "confidence": 5.0,
    }))
    result = provider.generate_adaptive_adjustment([], {}, {"id": "r1"})
    assert result.confidence == 1.0
    assert result.change_payload["type"] == "reduce_workload"
    assert result.current_plan and result.proposed_plan


def test_generate_adaptive_adjustment_missing_required_fields_raises(provider):
    queue(provider, json.dumps({"expected_effect": "x"}))
    with pytest.raises(AIProviderError):
        provider.generate_adaptive_adjustment([], {}, {"id": "r1"})


# ---------- factory selection ----------

def test_get_ai_provider_selects_gemini_when_configured(monkeypatch):
    from app.ai_orchestration import provider as provider_module
    monkeypatch.setattr(provider_module.settings, "AI_PROVIDER", "gemini")
    monkeypatch.setattr(provider_module.settings, "AI_API_KEY", "test-key")
    monkeypatch.setattr(provider_module.settings, "AI_MODEL", "gemini-test-model")
    result = provider_module.get_ai_provider()
    assert isinstance(result, GeminiAIProvider)


def test_get_ai_provider_falls_back_to_stub_when_gemini_key_missing(monkeypatch):
    from app.ai_orchestration import provider as provider_module
    monkeypatch.setattr(provider_module.settings, "AI_PROVIDER", "gemini")
    monkeypatch.setattr(provider_module.settings, "AI_API_KEY", "")
    result = provider_module.get_ai_provider()
    assert isinstance(result, provider_module.StubAIProvider)


def test_get_ai_provider_falls_back_to_stub_on_gemini_init_failure(monkeypatch):
    from app.ai_orchestration import provider as provider_module
    monkeypatch.setattr(provider_module.settings, "AI_PROVIDER", "gemini")
    monkeypatch.setattr(provider_module.settings, "AI_API_KEY", "test-key")
    monkeypatch.setattr(
        "app.ai_orchestration.gemini_provider.GeminiAIProvider.__init__",
        lambda self: (_ for _ in ()).throw(AIProviderError("simulated init failure")),
    )
    result = provider_module.get_ai_provider()
    assert isinstance(result, provider_module.StubAIProvider)


def test_claude_and_gemini_selection_dont_interfere(monkeypatch):
    # Regression guard for the shared AI_MODEL default change: switching
    # AI_PROVIDER between claude/gemini with AI_MODEL unset must give each
    # provider its own correct default, never leak the other's.
    from app.ai_orchestration import provider as provider_module
    from app.ai_orchestration.claude_provider import ClaudeAIProvider

    monkeypatch.setattr(provider_module.settings, "AI_PROVIDER", "gemini")
    monkeypatch.setattr(provider_module.settings, "AI_API_KEY", "test-key")
    monkeypatch.setattr(provider_module.settings, "AI_MODEL", "")
    gemini = provider_module.get_ai_provider()
    assert isinstance(gemini, GeminiAIProvider)
    assert gemini._model == "gemini-3.5-flash"

    monkeypatch.setattr(provider_module.settings, "AI_PROVIDER", "claude")
    claude = provider_module.get_ai_provider()
    assert isinstance(claude, ClaudeAIProvider)
    assert claude._model == "claude-sonnet-5"
