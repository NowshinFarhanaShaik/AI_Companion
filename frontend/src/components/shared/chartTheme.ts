// Series slot 1 of the dataviz reference palette, validated against the white card surface.
// Chrome stays recessive: hairline grid, muted axis text.
export const chartColors = { series: "#2a78d6", surface: "#ffffff", grid: "#e2e8f0", muted: "#64748b" };

export const axisProps = { stroke: chartColors.grid, tick: { fill: chartColors.muted, fontSize: 12 } };

export const formatShortDate = (value: number | string) =>
  new Date(value).toLocaleDateString(undefined, { month: "short", day: "numeric" });

export const formatDateTime = (value: number | string) =>
  new Date(value).toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });

const formatTime = (value: number | string) =>
  new Date(value).toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });

// A time axis spanning less than two days labels its ticks with times, not repeated dates.
export const timeTickFormatter = (times: number[]) =>
  Math.max(...times) - Math.min(...times) < 2 * 86_400_000 ? formatTime : formatShortDate;
