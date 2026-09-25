from datetime import datetime
from typing import Optional, List, Any
from pydantic import BaseModel, EmailStr, Field, ConfigDict

# ---------- Auth ----------

class SignupRequest(BaseModel):
    name: str
    email: EmailStr
    password: str = Field(min_length=6)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    email: str


class AuthResponse(BaseModel):
    token: str
    user: UserOut


# ---------- Profile / Onboarding ----------

class ProfileIn(BaseModel):
    daily_routine: Optional[str] = None
    available_time: Optional[str] = None
    preferred_schedule: Optional[str] = None
    existing_knowledge: Optional[str] = None
    constraints: Optional[List[str]] = None
    preferences: Optional[List[str]] = None


class ProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    daily_routine: str
    available_time: str
    preferred_schedule: str
    existing_knowledge: str
    constraints: List[str]
    preferences: List[str]
    onboarding_complete: bool


# ---------- Goals ----------

class GoalCreate(BaseModel):
    title: str
    target_outcome: str = ""
    current_level: str = ""
    target_date: Optional[str] = None


class GoalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    title: str
    target_outcome: str
    current_level: str
    target_date: Optional[str]
    status: str


# ---------- Assessment ----------

class AssessmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    goal_id: str
    ai_summary: str
    difficulty_level: str
    recommended_workload: str


# ---------- Roadmap ----------

class MilestoneOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    title: str
    target_date: Optional[str]
    status: str
    progress_pct: int = 0
    tasks_preview: List[str] = []


class RoadmapOut(BaseModel):
    goal_id: str
    milestones: List[MilestoneOut]


class MilestoneUpdate(BaseModel):
    title: Optional[str] = None
    target_date: Optional[str] = None
    order_index: Optional[int] = None
    status: Optional[str] = None


# ---------- Tasks ----------

class TaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    milestone_id: Optional[str]
    title: str
    description: str
    priority: str
    estimated_duration: str
    due_date: Optional[str]
    status: str


class TaskStatusUpdate(BaseModel):
    status: str


# ---------- Conversation ----------

class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    sender: str
    content: str
    created_at: datetime


class MessageCreate(BaseModel):
    content: str
    task_id: Optional[str] = None


class TaskUpdateOut(BaseModel):
    task_id: str
    status: str


class MessageResponse(BaseModel):
    reply: str
    task_update: Optional[TaskUpdateOut] = None


# ---------- Progress ----------

class PeriodMetrics(BaseModel):
    tasks_completed: int
    tasks_missed: int
    consistency_pct: int
    goal_progress_pct: Optional[int] = None
    trend: Optional[str] = None
    streak_days: Optional[int] = None


class ProgressSummaryOut(BaseModel):
    daily: PeriodMetrics
    weekly: PeriodMetrics
    monthly: PeriodMetrics
    upcoming: List[TaskOut]


# ---------- Plan Adjustments ----------

class AdjustmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    status: str
    trigger_reason: str
    change_summary: str
    expected_effect: str
    current_plan: List[str]
    proposed_plan: List[str]


class AdjustmentRespond(BaseModel):
    action: str  # accept | decline | request_changes / edit


# ---------- Notifications ----------

class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    type: str
    message: str
    related_task_id: Optional[str]
    related_adjustment_id: Optional[str] = None
    is_read: bool
    created_at: datetime


class OkResponse(BaseModel):
    ok: bool = True
