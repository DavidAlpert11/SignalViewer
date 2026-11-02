/* Small pieces several steps share: the shape of the study (runs, sets, combinations, what is
   missing). */
import { useT } from "../../i18n";
import type { Study } from "../../sweeps/state";

export function Stat({ label, value, warn }: { label: string; value: number | string; warn?: boolean }) {
  return (
    <div className={`sw-stat${warn ? " warn" : ""}`}>
      <div className="sw-stat-value">{typeof value === "number" ? value.toLocaleString() : value}</div>
      <div className="sw-stat-label">{label}</div>
    </div>
  );
}

/** The shape for the roles as they are now - it changes as soon as a role does. */
export function ShapeStats({ study }: { study: Study }) {
  const t = useT();
  const sm = study.summary;
  return (
    <div className="sw-shape">
      <Stat label={t("swRuns")} value={sm.rows} />
      <Stat label={t("swSets")} value={sm.sets} />
      <Stat label={t("swCombos")} value={sm.combos} />
      <Stat label={t("swMissing")} value={sm.missing} warn={sm.missing > 0} />
      <Stat label={t("swFailed")} value={sm.failedRuns} warn={sm.failedRuns > 0} />
    </div>
  );
}
