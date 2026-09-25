import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column, String, Boolean, Integer, Float, ForeignKey, DateTime, Text, JSON, UniqueConstraint
)
from sqlalchemy.orm import relationship
from app.database.session import Base


def gen_id() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True, default=gen_id)
    name = Column(String, nullable=False)
    email = Column(String, nullable=False, unique=True, index=True)
    password_hash = Column(String, nullable=False)
    timezone = Column(String, default="UTC")
    created_at = Column(DateTime, default=utcnow)

    profile = relationship("Profile", back_populates="user", uselist=False, cascade="all, delete-orphan")
    goals = relationship("Goal", back_populates="user", cascade="all, delete-orphan")
    tasks = relationship("Task", back_populates="user", cascade="all, delete-orphan")
    conversations = relationship("Conversation", back_populates="user", cascade="all, delete-orphan")
    plan_adjustments = relationship("PlanAdjustment", back_populates="user", cascade="all, delete-orphan")
    progress_snapshots = relationship("ProgressSnapshot", back_populates="user", cascade="all, delete-orphan")
    notifications = relationship("Notification", back_populates="user", cascade="all, delete-orphan")


class Profile(Base):
    __tablename__ = "profiles"
    user_id = Column(String, ForeignKey("users.id"), primary_key=True)
    daily_routine = Column(Text, default="")
    available_time = Column(String, default="")
    preferred_schedule = Column(String, default="")
    existing_knowledge = Column(Text, default="")
    constraints = Column(JSON, default=list)
    preferences = Column(JSON, default=list)
    onboarding_complete = Column(Boolean, default=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    user = relationship("User", back_populates="profile")


class Goal(Base):
    __tablename__ = "goals"
    id = Column(String, primary_key=True, default=gen_id)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    title = Column(String, nullable=False)
    target_outcome = Column(Text, default="")
    current_level = Column(Text, default="")
    target_date = Column(String, nullable=True)  # ISO date string
    status = Column(String, default="active")  # active | completed | paused
    created_at = Column(DateTime, default=utcnow)

    user = relationship("User", back_populates="goals")
    assessment = relationship("Assessment", back_populates="goal", uselist=False, cascade="all, delete-orphan")
    roadmaps = relationship("Roadmap", back_populates="goal", cascade="all, delete-orphan")


class Assessment(Base):
    __tablename__ = "assessments"
    id = Column(String, primary_key=True, default=gen_id)
    goal_id = Column(String, ForeignKey("goals.id"), nullable=False, unique=True, index=True)
    ai_summary = Column(Text, default="")
    difficulty_level = Column(String, default="")
    recommended_workload = Column(String, default="")
    raw_ai_output = Column(JSON, default=dict)
    created_at = Column(DateTime, default=utcnow)

    goal = relationship("Goal", back_populates="assessment")


class Roadmap(Base):
    __tablename__ = "roadmaps"
    id = Column(String, primary_key=True, default=gen_id)
    goal_id = Column(String, ForeignKey("goals.id"), nullable=False, index=True)
    version = Column(Integer, default=1)
    status = Column(String, default="active")  # active | superseded
    created_at = Column(DateTime, default=utcnow)

    goal = relationship("Goal", back_populates="roadmaps")
    milestones = relationship(
        "Milestone", back_populates="roadmap", cascade="all, delete-orphan",
        order_by="Milestone.order_index",
    )
    plan_adjustments = relationship("PlanAdjustment", back_populates="roadmap", cascade="all, delete-orphan")


class Milestone(Base):
    __tablename__ = "milestones"
    id = Column(String, primary_key=True, default=gen_id)
    roadmap_id = Column(String, ForeignKey("roadmaps.id"), nullable=False, index=True)
    title = Column(String, nullable=False)
    description = Column(Text, default="")
    order_index = Column(Integer, default=0)
    target_date = Column(String, nullable=True)
    status = Column(String, default="upcoming")  # upcoming | in_progress | completed

    roadmap = relationship("Roadmap", back_populates="milestones")
    tasks = relationship("Task", back_populates="milestone", cascade="all, delete-orphan")


TASK_STATUSES = ("pending", "completed", "partially_completed", "skipped", "rescheduled")


class Task(Base):
    __tablename__ = "tasks"
    id = Column(String, primary_key=True, default=gen_id)
    milestone_id = Column(String, ForeignKey("milestones.id"), nullable=True, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    title = Column(String, nullable=False)
    description = Column(Text, default="")
    priority = Column(String, default="medium")  # low | medium | high
    estimated_duration = Column(String, default="")
    due_date = Column(String, nullable=True)  # ISO date string
    status = Column(String, default="pending")
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    user = relationship("User", back_populates="tasks")
    milestone = relationship("Milestone", back_populates="tasks")
    progress_extractions = relationship("ProgressExtraction", back_populates="task")


class Conversation(Base):
    __tablename__ = "conversations"
    id = Column(String, primary_key=True, default=gen_id)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    started_at = Column(DateTime, default=utcnow)

    user = relationship("User", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan", order_by="Message.created_at")


class Message(Base):
    __tablename__ = "messages"
    id = Column(String, primary_key=True, default=gen_id)
    conversation_id = Column(String, ForeignKey("conversations.id"), nullable=False, index=True)
    sender = Column(String, nullable=False)  # user | ai
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=utcnow)

    conversation = relationship("Conversation", back_populates="messages")
    progress_extractions = relationship("ProgressExtraction", back_populates="message")


class ProgressExtraction(Base):
    __tablename__ = "progress_extractions"
    id = Column(String, primary_key=True, default=gen_id)
    message_id = Column(String, ForeignKey("messages.id"), nullable=False, index=True)
    task_id = Column(String, ForeignKey("tasks.id"), nullable=True, index=True)
    extracted_status = Column(String, nullable=True)
    reason = Column(Text, default="")
    availability_changed = Column(Boolean, default=False)
    difficulty_flag = Column(Boolean, default=False)
    topic_reference = Column(String, nullable=True)
    sentiment = Column(String, nullable=True)  # low_urgency | neutral | high_urgency (free-ish label)
    raw_ai_output = Column(JSON, default=dict)
    created_at = Column(DateTime, default=utcnow)

    message = relationship("Message", back_populates="progress_extractions")
    task = relationship("Task", back_populates="progress_extractions")


ADJUSTMENT_STATUSES = ("proposed", "accepted", "edited", "declined", "requested_changes")


class PlanAdjustment(Base):
    __tablename__ = "plan_adjustments"
    id = Column(String, primary_key=True, default=gen_id)
    roadmap_id = Column(String, ForeignKey("roadmaps.id"), nullable=False, index=True)
    goal_id = Column(String, ForeignKey("goals.id"), nullable=False, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    trigger_reason = Column(Text, default="")
    change_summary = Column(Text, default="")
    expected_effect = Column(Text, default="")
    change_payload = Column(JSON, default=dict)
    current_plan = Column(JSON, default=list)
    proposed_plan = Column(JSON, default=list)
    status = Column(String, default="proposed")
    created_at = Column(DateTime, default=utcnow)

    roadmap = relationship("Roadmap", back_populates="plan_adjustments")
    user = relationship("User", back_populates="plan_adjustments")


class ProgressSnapshot(Base):
    __tablename__ = "progress_snapshots"
    id = Column(String, primary_key=True, default=gen_id)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    period_type = Column(String, nullable=False)  # daily | weekly | monthly
    period_start = Column(String, nullable=False)
    period_end = Column(String, nullable=False)
    tasks_completed = Column(Integer, default=0)
    tasks_missed = Column(Integer, default=0)
    consistency_pct = Column(Integer, default=0)
    time_spent = Column(String, default="")
    goal_progress_pct = Column(Integer, default=0)
    top_missed_reasons = Column(JSON, default=list)
    created_at = Column(DateTime, default=utcnow)

    user = relationship("User", back_populates="progress_snapshots")

    __table_args__ = (UniqueConstraint("user_id", "period_type", "period_start", name="uq_snapshot_period"),)


class Notification(Base):
    __tablename__ = "notifications"
    id = Column(String, primary_key=True, default=gen_id)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    type = Column(String, nullable=False)  # task_due | task_missed | milestone | adjustment
    message = Column(Text, nullable=False)
    related_task_id = Column(String, ForeignKey("tasks.id"), nullable=True)
    related_adjustment_id = Column(String, ForeignKey("plan_adjustments.id"), nullable=True, index=True)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=utcnow)

    user = relationship("User", back_populates="notifications")
