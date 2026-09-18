import type { BadgeTone } from "../../components/ui/Badge";

export const scoreTone = (score: number): BadgeTone => (score >= 0.75 ? "green" : score >= 0.5 ? "yellow" : "red");
