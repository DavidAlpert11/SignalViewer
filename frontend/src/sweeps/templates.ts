/* What applying a template did, in words (the Columns step's Template ▾, the templates dialog, the
   offer when a table opens). */
import type { TFn } from "../i18n";
import type { TemplateResult } from "./state";

/** "Template applied: 12 of 14 columns matched, 2 new columns need a role, 1 formula skipped (missing payload_kg)" */
export function templateSummary(t: TFn, r: TemplateResult): string {
  const parts = [t("swTplMatched", { n: r.matched, of: r.of })];
  if (r.newColumns.length) parts.push(t("swTplNewCols", { n: r.newColumns.length }));
  if (r.skippedFormulas.length) parts.push(t("swTplSkippedFormulas", { n: r.skippedFormulas.length, list: r.skippedFormulas.map((x) => x.missing).join(", ") }));
  if (r.skippedLimits) parts.push(t("swTplSkippedLimits", { n: r.skippedLimits }));
  return `${t("swTplAppliedLead")} ${parts.join(", ")}.`;
}

