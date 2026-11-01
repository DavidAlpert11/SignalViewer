/* MF03: a design of experiments - new parameter sets to run. Each parameter varied in a range (or
   by level), or held at one value (off); a method; how many. The preview shows the new sets (and,
   grey, the ones already run) two parameters at a time. The output: a run list to run in one's own
   tool, and a group "DOE n" of these sets' ids - once their results are merged into the study, the
   group holds them (matched by set id). */
import { useMemo, useState } from "react";
import { pickPath } from "../../store";
import { useT, type TKey } from "../../i18n";
import { sweepApi, type DoeMethod, type DoeResult, type DoeSpec } from "../../sweeps/api";
import { FAILS, HOLDS } from "../../sweeps/colors";
import { idOfParams, maskOfKey, setIds } from "../../sweeps/groups";
import { labelOf } from "../../sweeps/scales";
import { notify, notifyError } from "../../sweeps/notify";
import { useSweeps, wireQuestion, type Study } from "../../sweeps/state";
import NumField from "./NumField";

const METHODS: DoeMethod[] = ["space", "sobol", "random", "factorial", "boxbehnken", "ccd", "fill"];
const METHOD_KEY: Record<DoeMethod, TKey> = { space: "swDoeSpace", sobol: "swDoeSobol", random: "swDoeRandom", factorial: "swDoeFactorial",
  boxbehnken: "swDoeBoxBehnken", ccd: "swDoeCcd", fill: "swDoeFill" };
export type Row = { on: boolean; spec: DoeSpec; fixed: string | number | null };

/** The parameters as the data has them: range, integer or not, levels; held at the best set's value. */
export function rowsOf(study: Study): Row[] {
  const a = study.answer!;
  const rank = a.sets.find((c) => c.name === "#rank")?.values;
  let best = 0;
  if (rank) for (let i = 0; i < rank.length; i++) if (Number.isFinite(rank[i]) && (!Number.isFinite(rank[best]) || rank[i] < rank[best])) best = i;
  return a.sets.filter((c) => c.group === "param").map((c) => {
    const fixed = c.kind === "cat" ? labelOf(c, c.values[best]) : c.values[best];
    if (c.kind === "cat") return { on: true, spec: { name: c.name, kind: "categorical", levels: c.labels ?? [] }, fixed };
    let lo = Infinity, hi = -Infinity, int = true;
    for (const v of c.values) if (Number.isFinite(v)) { lo = Math.min(lo, v); hi = Math.max(hi, v); int &&= Number.isInteger(v); }
    return { on: true, spec: { name: c.name, kind: int ? "integer" : "continuous", lo: +lo.toPrecision(7), hi: +hi.toPrecision(7) }, fixed };
  });
}

export default function DoeSheet({ study }: { study: Study }) {
  const t = useT();
  const v = study.view;
  const [rows, setRows] = useState<Row[]>(() => rowsOf(study));
  const [method, setMethod] = useState<DoeMethod>("space");
  const varied = rows.filter((r) => r.on).length;
  const objectives = Math.max(1, study.question.objectives.length || (study.question.goal ? 1 : 1));
  const [n, setN] = useState(Math.max(10, 2 * varied * objectives));
  const [levels, setLevels] = useState(3);
  const [seed, setSeed] = useState(0);
  const [res, setRes] = useState<DoeResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [combos, setCombos] = useState(true);
  const group = v.activeGroup ?? "all";
  const order = useMemo(() => study.answer!.sets.filter((c) => c.group === "param").map((c) => c.name), [study.answer]);
  const specs = (): DoeSpec[] => rows.map((r) => (r.on ? r.spec : { name: r.spec.name, kind: "fixed", value: r.fixed }));
  const setRow = (i: number, p: Partial<Row>) => { setRows(rows.map((r, j) => (j === i ? { ...r, ...p } : r))); setRes(null); };
  const run = async () => {
    setBusy(true);
    try {
      const a = study.answer!;
      const m = group !== "all" ? maskOfKey(a, v.groups ?? [], group, v.rerun) : null;
      const sets = m ? [...m.keys()].filter((i) => m[i]) : null;
      setRes(await sweepApi.doe(study.tableId, wireQuestion(study), specs(), method, n, seed, levels, sets));
    } catch (e) { notifyError(e); } finally { setBusy(false); }
  };
  const exportList = async () => {
    if (!res) return;
    const base = study.name.replace(/\.[^.]+$/, "");
    const p = await pickPath({ mode: "save", title: t("swDoeExport"), exts: [".csv", ".tsv", ".json", ".m", ".py"], defaultName: `${base}_doe.csv` });
    if (!p) return;
    try {
      const r = await sweepApi.suggestExport(study.tableId, wireQuestion(study), res.sets, p, combos);
      notify(t("swExported", { n: r.rows, path: r.path }));
      useSweeps.getState().journal("export", { path: r.path, n: r.rows });
    } catch (e) { notifyError(e); }
  };
  const saveGroup = () => {
    if (!res) return;
    const st = useSweeps.getState();
    const gs = study.view.groups ?? [];
    const k = gs.filter((g) => g.source === "doe").length + 1;
    const ids = res.sets.map((p) => idOfParams(p, order));
    let color = 0;
    while (gs.some((g) => g.color === color)) color++;
    st.setView({ groups: [...gs, { id: `g${Date.now().toString(36)}d`, name: t("swDoeGroup", { n: k }), color, source: "doe", frozen: true, ids }], colorBy: "#group" });
    notify(t("swDoeSaved", { n: res.n }));
  };
  const already = useMemo(() => { if (!res) return 0; const have = new Set(setIds(study.answer!)); return res.sets.filter((p) => have.has(idOfParams(p, order))).length; }, [res, study.answer, order]);
  return (
    <section className="sw-doe" aria-label={t("swDoeTitle")}>
      <h3>{t("swDoeTitle")}</h3>
      <p className="hint">{t("swDoeHint")}</p>
      <div className="sw-table-wrap">
        <table className="sw-table sw-doe-table">
          <thead><tr><th>{t("swDoeVary")}</th><th>{t("swPName")}</th><th>{t("swPType")}</th><th>{t("swPFrom")}</th><th>{t("swPTo")}</th></tr></thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={r.spec.name} data-param={r.spec.name} className={r.on ? "" : "off"}>
                <td><input type="checkbox" aria-label={t("swDoeVaryThis", { c: r.spec.name })} checked={r.on} onChange={(e) => setRow(i, { on: e.target.checked })} /></td>
                <td className="mono">{r.spec.name}</td>
                {!r.on ? <td colSpan={3} className="hint">{t("swDoeHeldAt", { v: String(r.fixed) })}</td>
                  : r.spec.kind === "categorical" ? <><td>{t("swTypeCategorical")}</td><td colSpan={2} className="hint">{r.spec.levels.join(", ")}</td></>
                  : r.spec.kind === "fixed" ? null : <>
                    <td><select aria-label={t("swPType")} value={r.spec.kind} onChange={(e) => setRow(i, { spec: { ...r.spec, kind: e.target.value as "continuous" | "integer" } as DoeSpec })}>
                      <option value="continuous">{t("swTypeContinuous")}</option><option value="integer">{t("swTypeInteger")}</option></select></td>
                    <td><NumField value={r.spec.lo} lo={r.spec.lo} hi={r.spec.hi} label={t("swExploreFrom", { c: r.spec.name })}
                      onChange={(x) => r.spec.kind !== "categorical" && r.spec.kind !== "fixed" && setRow(i, { spec: { ...r.spec, lo: x } })} /></td>
                    <td><NumField value={r.spec.hi} lo={r.spec.lo} hi={r.spec.hi} label={t("swExploreTo", { c: r.spec.name })}
                      onChange={(x) => r.spec.kind !== "categorical" && r.spec.kind !== "fixed" && setRow(i, { spec: { ...r.spec, hi: x } })} /></td>
                  </>}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="sw-row sw-doe-controls">
        <label>{t("swDoeMethod")} <select aria-label={t("swDoeMethod")} value={method} onChange={(e) => { setMethod(e.target.value as DoeMethod); setRes(null); }}>
          {METHODS.map((m) => <option key={m} value={m}>{t(METHOD_KEY[m])}</option>)}</select></label>
        {method === "factorial" ? <label>{t("swDoeLevels")} <NumField value={levels} lo={2} hi={9} label={t("swDoeLevels")} onChange={(x) => setLevels(Math.max(2, Math.round(x)))} /></label>
          : method === "boxbehnken" || method === "ccd" ? null
          : <label>{t("swDoeN")} <NumField value={n} lo={2} hi={500} label={t("swDoeN")} onChange={(x) => setN(Math.max(1, Math.round(x)))} />
            <span className="hint">{t("swDoeNHint", { n: 2 * varied * objectives })}</span></label>}
        {(method === "space" || method === "sobol" || method === "random") && <label>{t("swDoeSeed")} <NumField value={seed} lo={0} hi={100} label={t("swDoeSeed")} onChange={(x) => setSeed(Math.round(x))} /></label>}
        {method === "fill" && <span className="hint">{t("swDoeFillOf", { g: group })}</span>}
        <button className="btn primary" disabled={busy || !varied} onClick={run}>{t("swDoeMake")}</button>
      </div>
      {res && <>
        <p className="sw-doe-result" aria-live="polite">{t("swDoeMade", { n: res.n })}
          {res.discrepancy !== null && <span className="hint"> · {t("swDoeDisc", { d: res.discrepancy.toFixed(4) })}</span>}
          {res.min_distance !== null && <span className="hint"> · {t("swDoeMinDist", { d: res.min_distance.toFixed(3) })}</span>}
          {already > 0 && <span className="hint"> · {t("swDoeAlready", { n: already })}</span>}</p>
        <DoePreview study={study} res={res} rows={rows} />
        <div className="sw-row">
          <label className="acheck"><input type="checkbox" checked={combos} onChange={(e) => setCombos(e.target.checked)} />{t("swDoeCombos", { n: study.answer!.counts.combos })}</label>
          <button className="btn outline" onClick={exportList}>{t("swDoeExport")}</button>
          <button className="btn outline" onClick={saveGroup}>{t("swDoeSave")}</button>
        </div>
      </>}
    </section>
  );
}

/** The new sets two parameters at a time (the first varied ones), the sets already run in grey. */
function DoePreview({ study, res, rows }: { study: Study; res: DoeResult; rows: Row[] }) {
  const a = study.answer!;
  const vs = rows.filter((r) => r.on).slice(0, 4).map((r) => r.spec);
  if (vs.length < 2) return null;
  const unit = (s: DoeSpec, x: string | number | null): number => {
    if (s.kind === "categorical") { const i = s.levels.map(String).indexOf(String(x)); return (i + 0.5) / s.levels.length; }
    if (s.kind === "fixed") return 0.5;
    return s.hi > s.lo ? (Number(x) - s.lo) / (s.hi - s.lo) : 0.5;
  };
  const old = vs.map((s) => { const c = a.sets.find((x) => x.name === s.name)!; return Array.from(c.values, (v) => unit(s, c.kind === "cat" ? labelOf(c, v) : v)); });
  const S = 110, P = 6;
  const pairs: [number, number][] = [];
  for (let i = 0; i < vs.length; i++) for (let j = i + 1; j < vs.length; j++) pairs.push([i, j]);
  return (
    <svg className="sw-chart sw-doe-preview" viewBox={`0 0 ${pairs.length * (S + 10)} ${S + 18}`} role="img" aria-label="preview">
      {pairs.map(([i, j], k) => (
        <g key={k} transform={`translate(${k * (S + 10)},0)`}>
          <rect width={S} height={S} className="sw-matrix-cell" fill="none" />
          {old[i].map((x, r) => <circle key={`o${r}`} cx={P + x * (S - 2 * P)} cy={S - P - old[j][r] * (S - 2 * P)} r={1.5} fill={FAILS} />)}
          {res.sets.map((p, r) => <circle key={`n${r}`} cx={P + unit(vs[i], p[vs[i].name]) * (S - 2 * P)} cy={S - P - unit(vs[j], p[vs[j].name]) * (S - 2 * P)} r={2.5} fill={HOLDS} />)}
          <text x={S / 2} y={S + 13} textAnchor="middle" className="sw-ax">{vs[i].name} × {vs[j].name}</text>
        </g>
      ))}
    </svg>
  );
}
