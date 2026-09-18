from datetime import date, datetime
from typing import Any
from uuid import UUID

from ninja import Schema

from insights.schemas import ActivityOut, AIActivityOut, ProjectBreakdownRow


class MaterialStatusCount(Schema):
    status: str
    count: int


class OverviewOut(Schema):
    users: int
    spaces: int
    projects: int
    materials: int
    materials_by_status: list[MaterialStatusCount]
    quiz_sessions: int
    questions_answered: int
    active_users_7d: int
    events: ActivityOut


class AdminUserRow(Schema):
    id: UUID
    email: str
    name: str
    is_staff: bool
    is_active: bool
    project_count: int
    last_activity: datetime | None
    ai_calls: int
    ai_cost_usd: float

    @staticmethod
    def resolve_project_count(obj):
        return obj.project_count or 0

    @staticmethod
    def resolve_ai_calls(obj):
        return obj.ai_call_count or 0

    @staticmethod
    def resolve_ai_cost_usd(obj):
        return round(float(obj.ai_cost or 0), 6)


class AdminUserSummary(Schema):
    id: UUID
    email: str
    name: str
    is_staff: bool
    is_active: bool
    joined_at: datetime | None


class AdminSpaceRow(Schema):
    id: UUID
    name: str
    project_count: int


class AdminEventRow(Schema):
    id: UUID
    created_at: datetime
    type: str
    project_id: UUID | None
    project_name: str | None
    payload: dict[str, Any]


class AdminAssessmentRow(Schema):
    id: UUID
    project_id: UUID
    project_name: str
    status: str
    created_at: datetime
    completed_at: datetime | None
    average_score: float | None
    answered: int


class AdminUserDetailOut(Schema):
    user: AdminUserSummary
    spaces: list[AdminSpaceRow]
    projects: list[ProjectBreakdownRow]
    recent_activity: list[AdminEventRow]
    assessments: list[AdminAssessmentRow]
    ai: AIActivityOut


class ActivityFilters(Schema):
    user_id: UUID | None = None
    space_id: UUID | None = None
    project_id: UUID | None = None
    type: str | None = None
    date_from: date | None = None
    date_to: date | None = None


class ActivityRowOut(Schema):
    id: UUID
    created_at: datetime
    type: str
    payload: dict[str, Any]
    user_id: UUID
    user_email: str
    project_id: UUID | None
    project_name: str | None
    space_id: UUID | None
    space_name: str | None

    @staticmethod
    def resolve_user_email(obj):
        return obj.user.email

    @staticmethod
    def resolve_project_name(obj):
        return obj.project.name if obj.project_id else None

    @staticmethod
    def resolve_space_id(obj):
        if obj.space_id:
            return obj.space_id
        return obj.project.space_id if obj.project_id else None

    @staticmethod
    def resolve_space_name(obj):
        if obj.space_id:
            return obj.space.name
        return obj.project.space.name if obj.project_id else None


class AIUsageTotals(Schema):
    calls: int
    errors: int
    error_rate: float
    input_tokens: int
    output_tokens: int
    estimated_cost_usd: float


class AILatency(Schema):
    p50_ms: float | None
    p95_ms: float | None
    average_ms: float | None


class AIGroupRow(Schema):
    calls: int
    errors: int
    input_tokens: int
    output_tokens: int
    estimated_cost_usd: float
    average_latency_ms: float | None


class AIFeatureUsageRow(AIGroupRow):
    feature: str


class AIModelUsageRow(AIGroupRow):
    model: str


class AICallRow(Schema):
    id: UUID
    created_at: datetime
    feature: str
    model: str
    status: str
    error_type: str
    latency_ms: int
    retries: int
    input_tokens: int
    output_tokens: int
    trace_id: str
    user_email: str | None
    project_name: str | None


class AIUsageOut(Schema):
    days: int
    totals: AIUsageTotals
    latency: AILatency
    by_feature: list[AIFeatureUsageRow]
    by_model: list[AIModelUsageRow]
    slowest: list[AICallRow]
    recent_failures: list[AICallRow]


class EvalRunOut(Schema):
    id: UUID
    created_at: datetime
    suite: str
    git_sha: str
    passed: bool
    metrics: dict[str, Any]
    case_results: list[Any]
    case_count: int

    @staticmethod
    def resolve_case_count(obj):
        return len(obj.case_results)


class JobFilters(Schema):
    status: str | None = None
    type: str | None = None


class JobRowOut(Schema):
    id: UUID
    type: str
    status: str
    attempts: int
    max_attempts: int
    run_after: datetime | None
    locked_at: datetime | None
    last_error: str
    payload: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class JobTypeCount(Schema):
    type: str
    count: int


class JobsSummaryOut(Schema):
    by_status: dict[str, int]
    by_type: list[JobTypeCount]


class HealthCheck(Schema):
    key: str
    label: str
    status: str          # green | amber | red
    value: str
    detail: str


class HealthOut(Schema):
    status: str          # the worst check
    checked_at: datetime
    checks: list[HealthCheck]
