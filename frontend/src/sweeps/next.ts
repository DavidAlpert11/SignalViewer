/* Next runs' kinds of suggestion: their names, their marks on the maps (NextRunsView, MapView,
   the report). */
import type { TKey } from "../i18n";
import type { SuggestKind } from "./api";

export const KINDS: { k: SuggestKind; title: TKey; hint: TKey }[] = [
  { k: "edge", title: "swNextEdge", hint: "swNextEdgeHint" },
  { k: "best", title: "swNextBest", hint: "swNextBestHint" },
  { k: "disagree", title: "swNextDisagree", hint: "swNextDisagreeHint" },
  { k: "gaps", title: "swNextGaps", hint: "swNextGapsHint" },
  { k: "missing", title: "swNextMissing", hint: "swNextMissingHint" },
  { k: "robust", title: "swNextRobust", hint: "swNextRobustHint" },
];

export const MARK: Record<string, string> = { edge: "◆", best: "★", disagree: "▲", gaps: "○", missing: "↻", robust: "◇" };

/** When suggestions were made (kept with them). */
export const stamp = () => new Date().toISOString();
