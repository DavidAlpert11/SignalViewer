/* MF05: which parameter matters, in numbers - for the active group's sets and a column (the goal by
   default): each parameter's share of the variance (its main effect, its interactions), its Sobol
   indices and correlations; the strongest pairs; what nothing explains. Under the threshold a
   parameter is weak (greyed): *take the weak ones off the lines* leaves the parameters that matter. */
import { useEffect, useMemo, useState } from "react";
import { useT, type TKey } from "../../i18n";
import { sweepApi, type Sensitivity } from "../../sweeps/api";
import { maskOfKey } from "../../sweeps/groups";
import { useSweeps, wireQuestion, type Study } from "../../sweeps/state";
import { colLabel } from "../../sweeps/view";
import NumField from "./NumField";

const pct = (x: number | null | undefined) => (x === null || x === undefined || !Number.isFinite(x) ? "–" : `${(x * 100).toFixed(1)}%`);
const r2 = (x: number | null) => (x === null ? "–" : x.toFixed(2));

export default function SensitivityTable({ study }: { study: Study }) {
  const t = useT();
  const a = study.answer!;
  const v = study.view;
  const [column, setColumn] = useState<string>("");
  const [threshold, setThreshold] = useState(5);
  const [r, setR] = useState<Sensitivity | null>(null);
  const [err, setErr] = useState("");
  const group = v.activeGroup ?? "all";
  const sets = useMemo(() => {
    if (group === "all") return null;
    const m = maskOfKey(a, v.groups ?? [], group, v.rerun);
    return m ? [...m.keys()].filter((i) => m[i]) : null;
  }, [a, v.groups, v.rerun, group]);
  const choices = a.sets.filter((c) => c.kind === "num" && (c.group === "goal" || c.group === "output" || c.group === "derived" || (c.group === "condition" && c.part === "worst") || c.name === "#holds"));
  const qk = JSON.stringify(wireQuestion(study));
  useEffect(() => {
    let live = true;
    setErr("");
    sweepApi.sensitivity(study.tableId, wireQuestion(study), column || null, sets, threshold / 100)
      .then((x) => live && setR(x)).catch((x) => live && setErr((x as Error).message));
    return () => { live = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [study.tableId, qk, column, JSON.stringify(sets), threshold]);
  const AUTO: Record<string, TKey> = { all: "swGrpAll", holds: "swGrpHolds", pareto: "swGrpPareto", fails: "swGrpFails", error: "swGrpError", marked: "swGrpMarked" };
  const groupName = AUTO[group] ? t(AUTO[group]) : v.groups?.find((g) => g.id === group)?.name ?? group;
  const weak = r?.params.filter((p) => p.weak).map((p) => p.name) ?? [];
  const offLines = () => useSweeps.getState().setView({ axes: v.axes.filter((x) => !weak.includes(x)) });
  const max = Math.max(1e-9, ...(r?.params.map((p) => p.main + p.interactions) ?? [0]));
  return (
    <section className="sw-sens" aria-label={t("swSensTitle")}>
      <div className="sw-row sw-sens-head">
        <b>{t("swSensTitle")}</b>
        <label>{t("swSensOf")} <select aria-label={t("swSensOf")} value={column} onChange={(e) => setColumn(e.target.value)}>
          <option value="">{study.question.goal ? t("swSensGoal") : t("swRepItHolding")}</option>
          {choices.map((c) => <option key={c.name} value={c.name}>{colLabel(t, study, c.name)}</option>)}
        </select></label>
        <span className="hint">{t("swSensGroup", { g: groupName })}</span>
        <label>{t("swSensThreshold")} <NumField value={threshold} lo={0} hi={50} label={t("swSensThreshold")} onChange={(x) => setThreshold(Math.max(0, Math.min(100, x)))} />%</label>
        <button className="btn outline" disabled={!weak.some((w) => v.axes.includes(w))} onClick={offLines} title={t("swSensOffHint")}>{t("swSensOff", { n: weak.length })}</button>
      </div>
      {err && <p className="sw-error">{err}</p>}
      {r?.flat && <p className="hint">{t("swSensFlat")}</p>}
      {r && !r.flat && (
        <div className="sw-table-wrap">
          <table className="sw-table sw-sens-table">
            <thead><tr><th>{t("swPName")}</th><th>{t("swSensShare")}</th><th className="num">{t("swSensMain")}</th><th className="num">{t("swSensInter")}</th>
              <th className="num" title={t("swSensFirstHint")}>S₁</th><th className="num" title={t("swSensTotalHint")}>Sₜ</th><th className="num">Pearson</th><th className="num">Spearman</th></tr></thead>
            <tbody>
              {r.params.map((p) => (
                <tr key={p.name} data-param={p.name} className={p.weak ? "weak" : ""} title={p.weak ? t("swSensWeak") : undefined}>
                  <td className="mono">{p.name}</td>
                  <td><span className="sw-sens-bar"><i className="main" style={{ width: `${(p.main / max) * 100}%` }} /><i className="inter" style={{ width: `${(p.interactions / max) * 100}%` }} /></span></td>
                  <td className="num">{pct(p.main)}</td><td className="num">{pct(p.interactions)}</td>
                  <td className="num">{r2(p.first)}</td><td className="num">{r2(p.total)}</td>
                  <td className="num">{r2(p.pearson)}</td><td className="num">{r2(p.spearman)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="hint">{t("swSensPairs")}: {r.pairs.filter((p) => p.share >= 0.005).slice(0, 5).map((p) => `${p.a} × ${p.b} ${pct(p.share)}`).join(" · ") || "–"}
            {" · "}{t("swSensRest", { p: pct(r.rest) })} · {t("swSensN", { n: r.n })}</p>
        </div>
      )}
    </section>
  );
}
