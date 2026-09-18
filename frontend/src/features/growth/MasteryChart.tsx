import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { ConceptSeries } from "../../api/types";
import { ChartDataTable } from "../../components/shared/ChartDataTable";
import { ChartTooltip } from "../../components/shared/ChartTooltip";
import { axisProps, chartColors, formatDateTime, timeTickFormatter } from "../../components/shared/chartTheme";

const marker = { r: 4, fill: chartColors.series, stroke: chartColors.surface, strokeWidth: 2 };

// One series, so the card title names it and no legend is drawn.
export function MasteryChart({ series }: { series: ConceptSeries }) {
  const data = series.points.map((point) => ({
    time: new Date(point.at).getTime(),
    mastery: Math.round(point.score * 100),
  }));

  return (
    <>
      <div className="h-64 w-full" role="img" aria-label={`Mastery of ${series.name} over time`}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 8, right: 16, bottom: 0, left: -12 }}>
            <CartesianGrid stroke={chartColors.grid} vertical={false} />
            <XAxis
              dataKey="time"
              type="number"
              scale="time"
              domain={["dataMin", "dataMax"]}
              tickFormatter={timeTickFormatter(data.map((point) => point.time))}
              {...axisProps}
            />
            <YAxis domain={[0, 100]} ticks={[0, 25, 50, 75, 100]} tickFormatter={(v) => `${v}%`} {...axisProps} />
            <Tooltip
              cursor={{ stroke: chartColors.muted, strokeWidth: 1 }}
              content={<ChartTooltip formatValue={(v) => `${v}%`} formatLabel={formatDateTime} />}
            />
            <Line
              dataKey="mastery"
              stroke={chartColors.series}
              strokeWidth={2}
              strokeLinecap="round"
              strokeLinejoin="round"
              dot={marker}
              activeDot={{ ...marker, r: 5 }}
              isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <ChartDataTable
        headers={["When", "Mastery"]}
        rows={data.map((point) => [formatDateTime(point.time), `${point.mastery}%`])}
      />
    </>
  );
}
