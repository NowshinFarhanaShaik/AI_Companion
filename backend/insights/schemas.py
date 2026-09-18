from datetime import date, datetime
from uuid import UUID

from ninja import Schema

from learning.schemas import TrendOut


class DayCount(Schema):
    day: date
    count: int


class TypeCount(Schema):
    type: str
    count: int


class ActivityOut(Schema):
    total: int
    per_day: list[DayCount]
    by_type: list[TypeCount]


class SessionScore(Schema):
    session_id: UUID
    project_id: UUID
    completed_at: datetime | None
    average_score: float | None
    answered: int


class QuizOut(Schema):
    sessions_started: int
    sessions_completed: int
    questions_answered: int
    average_score: float | None
    per_session: list[SessionScore]


class MasteryOut(Schema):
    concepts: int
    average: float | None
    unpractised: int
    low: int
    medium: int
    high: int


class AIFeatureRow(Schema):
    feature: str
    calls: int
    input_tokens: int
    output_tokens: int
    estimated_cost_usd: float
    errors: int


class AIActivityOut(Schema):
    calls: int
    input_tokens: int
    output_tokens: int
    estimated_cost_usd: float
    errors: int
    by_feature: list[AIFeatureRow]


class ProjectAnalyticsOut(Schema):
    project_id: UUID
    activity: ActivityOut
    quiz: QuizOut
    mastery: MasteryOut
    trends: list[TrendOut]
    trend_counts: dict[str, int]
    ai: AIActivityOut


class ProjectBreakdownRow(Schema):
    project_id: UUID
    name: str
    space_id: UUID
    space_name: str
    last_activity_at: datetime | None
    events: int
    materials: int
    concepts: int
    average_mastery: float | None
    questions_answered: int
    average_score: float | None


class SpaceBreakdownRow(Schema):
    space_id: UUID
    name: str
    projects: int
    events: int
    average_mastery: float | None


class GlobalAnalyticsOut(Schema):
    activity: ActivityOut
    quiz: QuizOut
    mastery: MasteryOut
    ai: AIActivityOut
    spaces: list[SpaceBreakdownRow]
    projects: list[ProjectBreakdownRow]
