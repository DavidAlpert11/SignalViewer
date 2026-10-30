/* The columns: each one's role (guessed, any can be changed), its scale, whether it is an axis,
   and hiding what tells nothing. "Back to the guess" undoes every change. */
import { useState } from "react";
import { useT, type TKey } from "../../i18n";
import { ROLES, SCALES, type Role, type Scale } from "../../sweeps/api";
import { useSweeps, type Study, type StudyColumn } from "../../sweeps/state";
import { fmtValue } from "../../sweeps/scales";

export const ROLE_KEY: Record<Role, TKey> = { param: "swRoleParam", hold: "swRoleHold", output: "swRoleOutput", id: "swRoleId", ignore: "swRoleIgnore" };
const ROLE_HINT: Record<Role, TKey> = { param: "swRoleParamHint", hold: "swRoleHoldHint", output: "swRoleOutputHint", id: "swRoleIdHint", ignore: "swRoleIgnoreHint" };
export const SCALE_KEY: Record<Scale, TKey> = { linear: "swScaleLinear", log: "swScaleLog", category: "swScaleCategory", ordinal: "swScaleOrdinal" };

export default function ColumnsPanel({ study }: { study: Study }) {
  const t = useT();
  const st = useSweeps.getState();
  const [q, setQ] = useState("");
  const meta = new Map((study.answer?.sets ?? []).map((c) => [c.name, c]));
  const nConst = [...meta.values()].filter((c) => c.constant).length;
  const nFlat = [...meta.values()].filter((c) => c.flat).length;
  const changed = study.columns.some((c) => c.role !== c.guessRole || c.scale !== c.guessScale);
  const match = (c: StudyColumn) => !q || c.name.toLowerCase().includes(q.toLowerCase());
  const sm = study.summary;
  return (
    <div className="sw-columns">
      {/* the shape of the study for these roles - it changes as soon as a role does */}
      <div className="sw-shape">
        <Stat label={t("swRuns")} value={sm.rows} />
        <Stat label={t("swSets")} value={sm.sets} />
        <Stat label={t("swCombos")} value={sm.combos} />
        <Stat label={t("swMissing")} value={sm.missing} warn />
        <Stat label={t("swFailed")} value={sm.failedRuns} warn />
      </div>
      {sm.duplicates > 0 && <p className="sw-warn">{t("swDuplicates", { n: sm.duplicates })}</p>}
      <p className="hint">{t("swReadIn", { s: study.seconds.toFixed(2), path: study.path })}</p>
      <input className="sw-search" placeholder={t("swSearchColumns")} value={q} onChange={(e) => setQ(e.target.value)} aria-label={t("swSearchColumns")} />
      <div className="sw-hide-box">
        <b>{t("swHideNothing")}</b>
        <label className="acheck"><input type="checkbox" checked={study.view.hideConstant} onChange={(e) => st.setView({ hideConstant: e.target.checked })} />
          {t("swHideConstant")} <span className="hint">· {nConst}</span></label>
        <label className="acheck"><input type="checkbox" checked={study.view.hideFlat} onChange={(e) => st.setView({ hideFlat: e.target.checked })} />
          {t("swHideFlat")} <span className="hint">· {nFlat}</span></label>
      </div>
      {changed && <button className="linklike" onClick={st.resetRoles}>{t("swBackToGuess")}</button>}
      {ROLES.map((role) => {
        const cols = study.columns.filter((c) => c.role === role && match(c));
        if (!cols.length) return null;
        return (
          <section key={role} className={`sw-role sw-role-${role}`}>
            <h3 title={t(ROLE_HINT[role])}>{t(ROLE_KEY[role])} <span className="hint">· {cols.length}</span></h3>
            {cols.map((c) => <ColumnRow key={c.name} study={study} c={c} />)}
          </section>
        );
      })}
    </div>
  );
}

function ColumnRow({ study, c }: { study: Study; c: StudyColumn }) {
  const t = useT();
  const st = useSweeps.getState();
  const why = c.constant ? t("swConstant") : c.empty ? t("swEmpty") : c.kind === "text" ? t("swDistinct", { n: c.distinct })
    : c.min !== undefined ? `${fmtValue(c.min)} – ${fmtValue(c.max!)} · ${t("swDistinct", { n: c.distinct })}` : "";
  const isAxis = study.view.axes.includes(c.name);
  const guessed = c.role === c.guessRole;
  return (
    <div className="sw-col">
      <label className="sw-col-name acheck" title={c.name}>
        <input type="checkbox" checked={isAxis} disabled={c.role === "ignore" || c.role === "id"} aria-label={t("swShowAxis", { c: c.name })}
          onChange={(e) => st.toggleAxis(c.name, e.target.checked)} />{c.name}
      </label>
      <div className="sw-col-why">{why}{!guessed && <span className="sw-changed"> · {t("swYourChoice")}</span>}</div>
      <div className="sw-col-pick">
        <select aria-label={t("swRoleOf", { c: c.name })} value={c.role} onChange={(e) => st.setRole(c.name, e.target.value as Role)}>
          {ROLES.map((r) => <option key={r} value={r}>{t(ROLE_KEY[r])}</option>)}
        </select>
        <select aria-label={t("swScaleOf", { c: c.name })} value={c.scale} onChange={(e) => st.setScale(c.name, e.target.value as Scale)}>
          {SCALES.map((sc) => <option key={sc} value={sc} disabled={c.kind === "text" && (sc === "linear" || sc === "log")}>{t(SCALE_KEY[sc])}</option>)}
        </select>
      </div>
    </div>
  );
}

function Stat({ label, value, warn }: { label: string; value: number; warn?: boolean }) {
  return (
    <div className={`sw-stat${warn && value > 0 ? " warn" : ""}`}>
      <div className="sw-stat-value">{value.toLocaleString()}</div>
      <div className="sw-stat-label">{label}</div>
    </div>
  );
}
