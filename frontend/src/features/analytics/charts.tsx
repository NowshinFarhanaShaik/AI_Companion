import { Bar, BarChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { DayCount, SessionScore } from "../../api/types";
import { ChartDataTable } from "../../components/shared/ChartDataTable";
import { ChartTooltip } from "../../components/shared/ChartTooltip";
import { axisProps, chartColors, formatDateTime, formatShortDate, timeTickFormatter } from "../../components/shared/chartTheme";

const marker = { r: 4, fill: chartColors.series, stroke: chartColors.surface, strokeWidth: 2 };

export function ActivityChart({ data }: { data: DayCount[] }) {
  const plural = (n: number | string) => `${n} ${Number(n) === 1 ? "event" : "events"}`;
  return (
    <>
      <div className="h-56 w-full" role="img" aria-label="Learning events per day">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
            <CartesianGrid stroke={chartColors.grid} vertical={false} />
            <XAxis dataKey="day" tickFormatter={formatShortDate} minTickGap={16} {...axisProps} />
            <YAxis allowDecimals={false} {...axisProps} />
            <Tooltip
              cursor={{ fill: "#f1f5f9" }}
              content={<ChartTooltip formatValue={plural} formatLabel={formatShortDate} />}
            />
            <Bar dataKey="count" fill={chartColors.series} maxBarSize={24} radius={[4, 4, 0, 0]} isAnimationActive={false} />
          </BarChart>
        </ResponsiveContainer>
      </div>
      <ChartDataTable headers={["Day", "Events"]} rows={data.map((row) => [formatShortDate(row.day), String(row.count)])} />
    </>
  );
}

export function QuizScoreChart({ data }: { data: SessionScore[] }) {
  const rows = data
    .filter((session) => session.completed_at && session.average_score !== null)
    .map((session) => ({
      time: new Date(session.completed_at!).getTime(),
      score: Math.round(session.average_score! * 100),
    }));
  return (
    <>
      <div className="h-56 w-full" role="img" aria-label="Average score per completed quiz">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={rows} margin={{ top: 8, right: 16, left: -16, bottom: 0 }}>
            <CartesianGrid stroke={chartColors.grid} vertical={false} />
            <XAxis
              dataKey="time"
              type="number"
              scale="time"
              domain={["dataMin", "dataMax"]}
              tickFormatter={timeTickFormatter(rows.map((point) => point.time))}
              {...axisProps}
            />
            <YAxis domain={[0, 100]} ticks={[0, 25, 50, 75, 100]} tickFormatter={(v) => `${v}%`} {...axisProps} />
            <Tooltip
              cursor={{ stroke: chartColors.muted, strokeWidth: 1 }}
              content={<ChartTooltip formatValue={(v) => `${v}%`} formatLabel={formatDateTime} />}
            />
            <Line
              dataKey="score"
              stroke={chartColors.series}
              strokeWidth={2}
              dot={marker}
              activeDot={{ ...marker, r: 5 }}
              isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <ChartDataTable
        headers={["Completed", "Average score"]}
        rows={rows.map((row) => [formatDateTime(row.time), `${row.score}%`])}
      />
    </>
  );
}
