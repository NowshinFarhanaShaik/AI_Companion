import type { ReactNode } from "react";

const tones = {
  gray: "bg-slate-100 text-slate-700",
  green: "bg-green-100 text-green-800",
  yellow: "bg-amber-100 text-amber-800",
  red: "bg-red-100 text-red-800",
  blue: "bg-blue-100 text-blue-800",
};

export type BadgeTone = keyof typeof tones;

export function Badge({ tone = "gray", children }: { tone?: BadgeTone; children: ReactNode }) {
  return <span className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${tones[tone]}`}>{children}</span>;
}
