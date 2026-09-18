from uuid import UUID

from ninja import Query, Router
from ninja.pagination import paginate

from accounts.auth import StaffJWTAuth
from insights import admin_ops, admin_queries
from insights.admin_schemas import (
    ActivityFilters,
    ActivityRowOut,
    AdminUserDetailOut,
    AdminUserRow,
    AIUsageOut,
    EvalRunOut,
    HealthOut,
    JobFilters,
    JobRowOut,
    JobsSummaryOut,
    OverviewOut,
)

router = Router(auth=StaffJWTAuth(), tags=["admin"])


@router.get("/overview", response=OverviewOut)
def overview(request):
    return admin_queries.overview()


@router.get("/users", response=list[AdminUserRow])
@paginate
def users(request, q: str = ""):
    return admin_queries.users(q)


@router.get("/users/{uuid:user_id}", response=AdminUserDetailOut)
def user_detail(request, user_id: UUID):
    return admin_queries.user_detail(user_id)


@router.get("/activity", response=list[ActivityRowOut])
@paginate
def activity(request, filters: ActivityFilters = Query(...)):
    return admin_queries.activity(**filters.dict())


@router.get("/ai-usage", response=AIUsageOut)
def ai_usage(request, days: int = 7):
    return admin_ops.ai_usage(days)


@router.get("/evals", response=list[EvalRunOut])
def evals(request):
    return list(admin_ops.eval_runs())


@router.get("/jobs/summary", response=JobsSummaryOut)
def jobs_summary(request):
    return admin_ops.jobs_summary()


@router.get("/jobs", response=list[JobRowOut])
@paginate
def jobs(request, filters: JobFilters = Query(...)):
    return admin_ops.jobs(**filters.dict())


@router.post("/jobs/{uuid:job_id}/retry", response=JobRowOut)
def retry_job(request, job_id: UUID):
    return admin_ops.retry_failed_job(job_id)


@router.get("/health", response=HealthOut)
def health(request):
    return admin_ops.system_health()
