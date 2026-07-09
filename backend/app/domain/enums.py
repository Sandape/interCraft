"""Phase 2 domain enums — 9 enums per data-model-phase-2.md §9."""
from __future__ import annotations

from enum import Enum


class AbilityDimension(str, Enum):
    TECH_DEPTH = "tech_depth"
    ARCHITECTURE = "architecture"
    ENGINEERING_PRACTICE = "engineering_practice"
    COMMUNICATION = "communication"
    ALGORITHM = "algorithm"
    BUSINESS = "business"


class ErrorStatus(str, Enum):
    FRESH = "fresh"
    PRACTICING = "practicing"
    MASTERED = "mastered"
    ARCHIVED = "archived"


class JobStatus(str, Enum):
    APPLIED = "applied"
    TEST = "test"
    OA = "oa"
    HR = "hr"
    OFFER = "offer"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"


class TaskType(str, Enum):
    INTERVIEW_PREP = "interview_prep"
    BRANCH_OPTIMIZE = "branch_optimize"
    APPLICATION_FOLLOWUP = "application_followup"
    MANUAL = "manual"


class TaskStatus(str, Enum):
    TODO = "todo"
    DOING = "doing"
    DONE = "done"
    ARCHIVED = "archived"


class ActivityType(str, Enum):
    TASK_CREATED = "task_created"
    TASK_COMPLETED = "task_completed"
    JOB_CREATED = "job_created"
    JOB_STATUS_CHANGED = "job_status_changed"
    INTERVIEW_STARTED = "interview_started"
    INTERVIEW_COMPLETED = "interview_completed"
    BRANCH_CREATED = "branch_created"
    ERROR_LOGGED = "error_logged"
    MANUAL = "manual"


class ActivityActor(str, Enum):
    USER = "user"
    SYSTEM = "system"
    AGENT = "agent"


class InterviewStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    ABORTED = "aborted"


class InterviewMode(str, Enum):
    TEXT = "text"
    VOICE = "voice"


JOB_STATUS_CN = {
    "applied": "已投递",
    "test": "笔试中",
    "interview_1": "一面中",
    "interview_2": "二面中",
    "interview_3": "三面中",
    "failed": "已失败",
    "passed": "已通过",
}


# REQ-053: New state machine. interview_1 -> interview_2 -> interview_3 is the
# recommended path, but skipping intermediate rounds is allowed (e.g., applied -> interview_3).
# Terminal states (failed, passed) have no outgoing transitions.
JOB_TRANSITIONS: dict[str, set[str]] = {
    "applied":     {"test", "interview_1", "interview_2", "interview_3", "failed", "passed"},
    "test":        {"interview_1", "interview_2", "interview_3", "failed", "passed"},
    "interview_1": {"interview_2", "interview_3", "failed", "passed"},
    "interview_2": {"interview_3", "failed", "passed"},
    "interview_3": {"failed", "passed"},
    "failed":      set(),
    "passed":      set(),
}


# REQ-053: Statuses that REQUIRE an interview_time when transitioning to them.
INTERVIEW_STATUSES = {"test", "interview_1", "interview_2", "interview_3"}


__all__ = [
    "AbilityDimension",
    "ErrorStatus",
    "JobStatus",
    "TaskType",
    "TaskStatus",
    "ActivityType",
    "ActivityActor",
    "InterviewStatus",
    "InterviewMode",
    "JOB_STATUS_CN",
    "JOB_TRANSITIONS",
]
