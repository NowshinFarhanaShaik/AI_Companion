export type User = { id: string; email: string; name: string; is_staff: boolean };
export type AuthResponse = { access: string; refresh: string; user: User };

export type Space = {
  id: string;
  name: string;
  description: string;
  color: string;
  icon: string;
  project_count: number;
  created_at: string;
};

export type Project = {
  id: string;
  space_id: string;
  space_name: string;
  name: string;
  description: string;
  learning_goal: string;
  last_activity_at: string | null;
  created_at: string;
};

export type MaterialStatus = "queued" | "processing" | "ready" | "failed";

export type Material = {
  id: string;
  project_id: string;
  title: string;
  status: MaterialStatus;
  error_message: string;
  page_count: number;
  chunk_count: number;
  created_at: string;
};

export type Concept = { id: string; name: string; description: string; importance: number; pages: number[] };

export type Conversation = {
  id: string;
  project_id: string;
  title: string;
  summary: string;
  created_at: string;
  updated_at: string;
};

export type Citation = {
  id: string;
  chunk_id: string | null;
  material_id: string;
  material_title: string;
  page_number: number;
  snippet: string;
};

export type TutorMessage = {
  id: string;
  conversation_id: string;
  role: "user" | "assistant";
  content: string;
  grounded: boolean | null;
  refusal_reason: string;
  citations: Citation[];
  created_at: string;
};

export type QuizFeedback = {
  understood: string[];
  missing: string[];
  misconceptions: string[];
  feedback: string;
};

export type QuizAttempt = {
  id: string;
  selected_option: number | null;
  answer_text: string;
  score: number;
  feedback: QuizFeedback;
  evaluated_at: string;
};

export type QuizQuestion = {
  id: string;
  session_id: string;
  concept_id: string;
  concept_name: string;
  type: "mcq" | "open";
  difficulty: number;
  body: string;
  options: string[];
  answered: boolean;
  attempt: QuizAttempt | null;
  correct_option: number | null;
  explanation: string | null;
  key_points: string[] | null;
};

export type QuizConceptSummary = {
  concept_id: string;
  concept_name: string;
  average_score: number;
  question_count: number;
};

export type QuizSummary = {
  answered_count: number;
  average_score: number;
  by_concept: QuizConceptSummary[];
};

export type QuizSession = {
  id: string;
  project_id: string;
  status: "active" | "completed";
  target_question_count: number;
  answered_count: number;
  completed_at: string | null;
  created_at: string;
  questions: QuizQuestion[];
  summary: QuizSummary | null;
};

export type NextQuestionResponse = { question: QuizQuestion | null; completed: boolean };
export type AnswerResponse = { question: QuizQuestion; session_completed: boolean };

export type TrendLabel = "improving" | "stable" | "needs_attention" | "not_enough_data";
export type RecommendationAction = "review_material" | "take_quiz" | "ask_tutor" | "upload_material";

export type ConceptMasteryItem = {
  concept_id: string;
  name: string;
  importance: number;
  score: number;
  evidence_count: number;
  consecutive_misses: number;
  last_practiced_at: string | null;
};

export type TrendItem = {
  concept_id: string;
  name: string;
  score: number;
  delta: number;
  label: TrendLabel;
  evidence_count: number;
};

export type ConceptSeries = {
  concept_id: string;
  name: string;
  points: { at: string; score: number }[];
};

export type GrowthData = { trends: TrendItem[]; series: ConceptSeries[] };

export type Recommendation = {
  id: string;
  project_id: string;
  project_name: string;
  concept_id: string | null;
  concept_name: string | null;
  action_type: RecommendationAction;
  text: string;
  reason: string;
  status: "active" | "done" | "superseded";
  created_at: string;
};

export type ActivityItem = {
  id: string;
  type: string;
  payload: Record<string, unknown>;
  project_id: string | null;
  created_at: string;
};

export type LatestQuiz = {
  session_id: string;
  completed_at: string | null;
  question_count: number;
  average_score: number;
};

export type ProjectDashboard = {
  project_id: string;
  name: string;
  learning_goal: string;
  overall_progress: number;
  concept_count: number;
  top_concepts: ConceptMasteryItem[];
  attention_concepts: TrendItem[];
  recent_activity: ActivityItem[];
  latest_quiz: LatestQuiz | null;
  material_counts: Record<"queued" | "processing" | "ready" | "failed", number>;
  recommendation: Recommendation | null;
};

export type ProjectSummary = {
  id: string;
  name: string;
  space_id: string;
  space_name: string;
  overall_progress: number;
  concept_count: number;
  attention_count: number;
  last_activity_at: string | null;
};

export type SpaceDashboard = {
  space_id: string;
  name: string;
  project_count: number;
  overall_progress: number;
  projects: ProjectSummary[];
  recent_activity: ActivityItem[];
};

export type AttentionArea = {
  project_id: string;
  project_name: string;
  concept_id: string;
  concept_name: string;
  score: number;
  label: TrendLabel;
};

export type HomeData = {
  continue_learning: ProjectSummary | null;
  recent_projects: ProjectSummary[];
  overall_progress: number;
  attention_areas: AttentionArea[];
  next_action: Recommendation | null;
};

export type DayCount = { day: string; count: number };
export type TypeCount = { type: string; count: number };
export type ActivitySummary = { total: number; per_day: DayCount[]; by_type: TypeCount[] };

export type SessionScore = {
  session_id: string;
  project_id: string;
  completed_at: string | null;
  average_score: number | null;
  answered: number;
};

export type QuizStats = {
  sessions_started: number;
  sessions_completed: number;
  questions_answered: number;
  average_score: number | null;
  per_session: SessionScore[];
};

export type MasterySummary = {
  concepts: number;
  average: number | null;
  unpractised: number;
  low: number;
  medium: number;
  high: number;
};

export type AIFeatureRow = {
  feature: string;
  calls: number;
  input_tokens: number;
  output_tokens: number;
  estimated_cost_usd: number;
  errors: number;
};

export type AIActivity = Omit<AIFeatureRow, "feature"> & { by_feature: AIFeatureRow[] };

export type ProjectAnalytics = {
  project_id: string;
  activity: ActivitySummary;
  quiz: QuizStats;
  mastery: MasterySummary;
  trends: TrendItem[];
  trend_counts: Record<string, number>;
  ai: AIActivity;
};

export type ProjectBreakdownRow = {
  project_id: string;
  name: string;
  space_id: string;
  space_name: string;
  last_activity_at: string | null;
  events: number;
  materials: number;
  concepts: number;
  average_mastery: number | null;
  questions_answered: number;
  average_score: number | null;
};

export type SpaceBreakdownRow = {
  space_id: string;
  name: string;
  projects: number;
  events: number;
  average_mastery: number | null;
};

export type GlobalAnalytics = {
  activity: ActivitySummary;
  quiz: QuizStats;
  mastery: MasterySummary;
  ai: AIActivity;
  spaces: SpaceBreakdownRow[];
  projects: ProjectBreakdownRow[];
};

export type AdminOverview = {
  users: number;
  spaces: number;
  projects: number;
  materials: number;
  materials_by_status: { status: string; count: number }[];
  quiz_sessions: number;
  questions_answered: number;
  active_users_7d: number;
  events: ActivitySummary;
};

export type AdminUserRow = {
  id: string;
  email: string;
  name: string;
  is_staff: boolean;
  is_active: boolean;
  project_count: number;
  last_activity: string | null;
  ai_calls: number;
  ai_cost_usd: number;
};

export type AdminEventRow = {
  id: string;
  created_at: string;
  type: string;
  project_id: string | null;
  project_name: string | null;
  payload: Record<string, unknown>;
};

export type AdminAssessmentRow = {
  id: string;
  project_id: string;
  project_name: string;
  status: string;
  created_at: string;
  completed_at: string | null;
  average_score: number | null;
  answered: number;
};

export type AdminUserDetail = {
  user: { id: string; email: string; name: string; is_staff: boolean; is_active: boolean; joined_at: string | null };
  spaces: { id: string; name: string; project_count: number }[];
  projects: ProjectBreakdownRow[];
  recent_activity: AdminEventRow[];
  assessments: AdminAssessmentRow[];
  ai: AIActivity;
};

export type AdminActivityRow = {
  id: string;
  created_at: string;
  type: string;
  payload: Record<string, unknown>;
  user_id: string;
  user_email: string;
  project_id: string | null;
  project_name: string | null;
  space_id: string | null;
  space_name: string | null;
};

export type AdminActivityFilters = {
  user_id?: string;
  space_id?: string;
  project_id?: string;
  type?: string;
  date_from?: string;
  date_to?: string;
  limit: number;
  offset: number;
};

export type AIGroupRow = {
  calls: number;
  errors: number;
  input_tokens: number;
  output_tokens: number;
  estimated_cost_usd: number;
  average_latency_ms: number | null;
};

export type AICallRow = {
  id: string;
  created_at: string;
  feature: string;
  model: string;
  status: string;
  error_type: string;
  latency_ms: number;
  retries: number;
  input_tokens: number;
  output_tokens: number;
  trace_id: string;
  user_email: string | null;
  project_name: string | null;
};

export type AdminAIUsage = {
  days: number;
  totals: Omit<AIGroupRow, "average_latency_ms"> & { error_rate: number };
  latency: { p50_ms: number | null; p95_ms: number | null; average_ms: number | null };
  by_feature: (AIGroupRow & { feature: string })[];
  by_model: (AIGroupRow & { model: string })[];
  slowest: AICallRow[];
  recent_failures: AICallRow[];
};

export type AdminEvalRun = {
  id: string;
  created_at: string;
  suite: string;
  git_sha: string;
  passed: boolean;
  metrics: Record<string, unknown>;
  case_results: unknown[];
  case_count: number;
};

export type AdminJob = {
  id: string;
  type: string;
  status: string;
  attempts: number;
  max_attempts: number;
  run_after: string | null;
  locked_at: string | null;
  last_error: string;
  payload: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

export type AdminJobsSummary = { by_status: Record<string, number>; by_type: { type: string; count: number }[] };

export type HealthStatus = "green" | "amber" | "red";

export type AdminHealth = {
  status: HealthStatus;
  checked_at: string;
  checks: { key: string; label: string; status: HealthStatus; value: string; detail: string }[];
};
