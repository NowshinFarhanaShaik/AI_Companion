from datetime import datetime
from uuid import UUID

from ninja import Schema


class ConceptMasteryOut(Schema):
    concept_id: UUID
    name: str
    importance: int
    score: float
    evidence_count: int
    consecutive_misses: int
    last_practiced_at: datetime | None

    @staticmethod
    def resolve_name(obj) -> str:
        return obj.concept.name

    @staticmethod
    def resolve_importance(obj) -> int:
        return obj.concept.importance


class TrendOut(Schema):
    concept_id: UUID
    name: str
    score: float
    delta: float
    label: str
    evidence_count: int

    @staticmethod
    def resolve_concept_id(obj) -> UUID:
        return obj.concept.id

    @staticmethod
    def resolve_name(obj) -> str:
        return obj.concept.name


class SeriesPointOut(Schema):
    at: datetime
    score: float


class ConceptSeriesOut(Schema):
    concept_id: UUID
    name: str
    points: list[SeriesPointOut]


class GrowthOut(Schema):
    trends: list[TrendOut]
    series: list[ConceptSeriesOut]


class RecommendationOut(Schema):
    id: UUID
    project_id: UUID
    project_name: str
    concept_id: UUID | None
    concept_name: str | None
    action_type: str
    text: str
    reason: str
    status: str
    created_at: datetime

    @staticmethod
    def resolve_project_name(obj) -> str:
        return obj.project.name

    @staticmethod
    def resolve_concept_name(obj) -> str | None:
        return obj.concept.name if obj.concept_id else None


class ActivityOut(Schema):
    id: UUID
    type: str
    payload: dict
    project_id: UUID | None
    created_at: datetime


class LatestQuizOut(Schema):
    session_id: UUID
    completed_at: datetime | None
    question_count: int
    average_score: float


class ProjectDashboardOut(Schema):
    project_id: UUID
    name: str
    learning_goal: str
    overall_progress: float
    concept_count: int
    top_concepts: list[ConceptMasteryOut]
    attention_concepts: list[TrendOut]
    recent_activity: list[ActivityOut]
    latest_quiz: LatestQuizOut | None
    material_counts: dict[str, int]
    recommendation: RecommendationOut | None


class ProjectSummaryOut(Schema):
    id: UUID
    name: str
    space_id: UUID
    space_name: str
    overall_progress: float
    concept_count: int
    attention_count: int
    last_activity_at: datetime | None


class SpaceDashboardOut(Schema):
    space_id: UUID
    name: str
    project_count: int
    overall_progress: float
    projects: list[ProjectSummaryOut]
    recent_activity: list[ActivityOut]


class AttentionAreaOut(Schema):
    project_id: UUID
    project_name: str
    concept_id: UUID
    concept_name: str
    score: float
    label: str


class HomeOut(Schema):
    continue_learning: ProjectSummaryOut | None
    recent_projects: list[ProjectSummaryOut]
    overall_progress: float
    attention_areas: list[AttentionAreaOut]
    next_action: RecommendationOut | None
