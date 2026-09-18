import type { AIActivity, ActivitySummary, MasterySummary, QuizStats } from "../../api/types";
import { activityTypeLabel } from "../../components/shared/activityLabels";
import { SimpleTable } from "../../components/shared/SimpleTable";
import { StatTile } from "../../components/shared/StatTile";
import { Card } from "../../components/ui/Card";
import { ActivityChart, QuizScoreChart } from "./charts";
import { count, percent, usd } from "./format";

type Summary = { activity: ActivitySummary; quiz: QuizStats; mastery: MasterySummary; ai: AIActivity };

export function SummaryTiles({ activity, quiz, mastery, ai }: Summary) {
  return (
    <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
      <StatTile label="Learning events, last 14 days" value={activity.total} />
      <StatTile
        label="Average quiz score"
        value={percent(quiz.average_score)}
        hint={`${count(quiz.questions_answered, "answer")} in ${count(quiz.sessions_completed, "quiz", "quizzes")}`}
      />
      <StatTile
        label="Average mastery"
        value={percent(mastery.average)}
        hint={`${mastery.high} strong · ${mastery.medium} developing · ${mastery.low} weak · ${mastery.unpractised} not practised`}
      />
      <StatTile label="AI calls" value={ai.calls} hint={`${usd(ai.estimated_cost_usd)} estimated · ${ai.errors} failed`} />
    </div>
  );
}

export function ActivityPanel({ activity }: { activity: ActivitySummary }) {
  return (
    <Card title="Learning activity per day">
      {activity.total === 0 ? (
        <p className="text-sm text-slate-600">No activity in the last 14 days. Ask the Tutor a question or take a quiz.</p>
      ) : (
        <>
          <ActivityChart data={activity.per_day} />
          <ul className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-600">
            {activity.by_type.map((row) => (
              <li key={row.type}>
                <span className="font-medium text-slate-900">{row.count}</span> {activityTypeLabel(row.type)}
              </li>
            ))}
          </ul>
        </>
      )}
    </Card>
  );
}

export function QuizPanel({ quiz }: { quiz: QuizStats }) {
  return (
    <Card title="Average score per quiz">
      {quiz.per_session.length === 0 ? (
        <p className="text-sm text-slate-600">Finish a quiz to see your score trend.</p>
      ) : (
        <QuizScoreChart data={quiz.per_session} />
      )}
    </Card>
  );
}

export function AIUsagePanel({ ai }: { ai: AIActivity }) {
  return (
    <Card title="AI activity by feature">
      <SimpleTable
        rows={ai.by_feature}
        rowKey={(row) => row.feature}
        empty="No AI calls yet."
        columns={[
          { header: "Feature", cell: (row) => row.feature },
          { header: "Calls", numeric: true, cell: (row) => row.calls },
          { header: "Failed", numeric: true, cell: (row) => row.errors },
          { header: "Tokens in", numeric: true, cell: (row) => row.input_tokens.toLocaleString() },
          { header: "Tokens out", numeric: true, cell: (row) => row.output_tokens.toLocaleString() },
          { header: "Est. cost", numeric: true, cell: (row) => usd(row.estimated_cost_usd) },
        ]}
      />
    </Card>
  );
}
