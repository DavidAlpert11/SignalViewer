/* Explore (S21, S23): a draft of the active goal - its conditions dragged as "what if" (and more
   added here), a limit on every parameter, the objectives with direction, weight and a threshold -
   applied together to the parameter sets at every move. Every control is on screen from the start
   (S23). Beside them the lines and the table of sets - the same components as the goal's view - show
   what the draft leaves, in its order, and export it (explore.ts draftStudy). Nothing here is the
   goal until "Save as a goal"; "Back to the goal" drops the draft and shows the goal's lines again.
   The logic: sweeps/explore.ts. */
import { useEffect, useMemo, useRef, useState } from "react";
import { useT, type TFn } from "../../i18n";
import { sweepApi } from "../../sweeps/api";
import { decodeCol } from "../../sweeps/decode";
import { draftChanges, draftOf, draftStudy, explore, exploreAxes, goalOfDraft, isLimited, limitMarks, limitOf, needsAnd, objectiveCol, structureKey,
  thresholdOf, thresholdOffEnd, withLevels, withLimit, type Draft, type DraftObjective, type Explored } from "../../sweeps/explore";
import { OPS, type Answer, type Col, type Condition, type Filter, type Op } from "../../sweeps/model";
import { fmtValue, labelOf } from "../../sweeps/scales";
import { useSweeps, wireQuestion, type Study } from "../../sweeps/state";
import { notify } from "../../sweeps/notify";
import { activeColumns, activeParams, colLabel, scaleOf } from "../../sweeps/view";
import { confirmAsk, openMenu } from "../Overlays";
import ColumnPicker from "./ColumnPicker";
import { goalName } from "./GoalsStep";
import ParallelPlot from "./ParallelPlot";
import SetsTable from "./SetsTable";
import NumField from "./NumField";
import DecidePanel from "./DecidePanel";

const BINS = 24;
/** more parameters than this: a box to find one */
const FIND_FROM = 6;

export default function ExploreView({ study }: { study: Study }) {
  const t = useT();
  const q = study.question;
  const goal = q.goals[q.active];
  const saved = study.view.explore;
  // the draft: kept with the study; a new one from the goal when there is none (or its goal is gone)
  const draft: Draft = saved && saved.from < q.goals.length ? saved.draft : draftOf(goal);
  const from = saved && saved.from < q.goals.length ? saved.from : q.active;
  const setDraft = (d: Draft) => useSweeps.getState().setView({ explore: { draft: d, from } });
  const robust = Object.keys(q.robust ?? {}).length > 0;

  // the answer to the draft's structure (values applied here; with robustness, a moment after a move)
  const [ans, setAns] = useState<{ key: string; shape: string; draft: Draft; a: Answer } | null>(null);
  const [err, setErr] = useState("");
  const base = JSON.stringify(wireQuestion(study));
  const key = structureKey(draft, robust) + base;
  const shape = structureKey(draft, false) + base;
  const live = useRef(0);
  useEffect(() => {
    const id = ++live.current;
    const asked = draft;
    const timer = window.setTimeout(() => {
      const objs = asked.objectives;
      const wq = { ...wireQuestion(study), conditions: asked.conditions, combine: asked.combine,
        goal: objs[0] ? { column: objs[0].column, direction: objs[0].direction } : null,
        objectives: objs.length > 1 ? objs.map(({ column, direction, weight }) => ({ column, direction, weight })) : [] };
      sweepApi.evaluate(study.tableId, wq, false).then((w) => {
        if (id !== live.current) return;
        setAns({ key, shape, draft: asked, a: { counts: w.counts, conditions: w.conditions, seconds: w.seconds, sets: w.sets.map((c) => decodeCol(c)) } });
        setErr("");
      }).catch((e) => id === live.current && setErr((e as Error).message));
    }, robust ? 250 : 0);
    return () => window.clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, study.tableId]);

  const a = ans?.a;
  // while the server answers a new structure (a condition or an objective added...), the last answer
  // stays on screen with the draft it was asked for: its columns are that draft's
  const shown = ans && ans.shape === shape ? draft : ans?.draft;
  const busy = !ans || ans.key !== key;
  const ex = useMemo(() => (a && shown ? explore(a, shown, robust) : null), [a, shown, robust]);
  const cols = useMemo(() => new Map<string, Col>((a?.sets ?? []).map((c) => [c.name, c])), [a]);
  const paramsKey = activeParams(study).join("\n");
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const params = useMemo(() => activeParams(study), [paramsKey]);
  // the numeric parameters' ranges (a limit each)
  const ranges = useMemo(() => {
    const out: Record<string, [number, number]> = {};
    for (const p of params) {
      const c = cols.get(p);
      if (!c || c.kind !== "num") continue;
      let lo = Infinity, hi = -Infinity;
      for (const v of c.values) if (Number.isFinite(v)) { lo = Math.min(lo, v); hi = Math.max(hi, v); }
      if (lo < hi) out[p] = [lo, hi];
    }
    return out;
  }, [cols, params]);
  const outputs = [...activeColumns(study, "output"), ...q.derived.map((d) => d.name)];
  // categorical parameters: their levels chosen (MF01)
  const catParams = useMemo(() => params.filter((p) => cols.get(p)?.kind === "cat" && (cols.get(p)?.labels?.length ?? 0) > 1), [cols, params]);
  const changes = draftChanges(draft, goal, ranges);
  const blocked = needsAnd(draft, ranges);
  // the lines and the table: the study as the draft makes it (nothing stored)
  const axes = useMemo(() => (a && shown ? exploreAxes(a, shown, params) : []), [a, shown, params]);
  const dstudy = useMemo(() => (a && shown && ex ? draftStudy(study, shown, a, ex, ranges, axes) : null), [study, shown, a, ex, ranges, axes]);
  const dcols = useMemo(() => new Map<string, Col>((dstudy?.answer?.sets ?? []).map((c) => [c.name, c])), [dstudy]);
  const keep = useMemo(() => { if (!ex) return null; const m = new Uint8Array(ex.n); for (const s of ex.survivors) m[s] = 1; return m; }, [ex]);
  const bestMask = useMemo(() => { if (!ex || ex.ranked[0] === undefined) return null; const m = new Uint8Array(ex.n); m[ex.ranked[0]] = 1; return m; }, [ex]);
  const scale = useMemo(() => (name: string) => (dstudy ? scaleOf(dstudy, name, dcols.get(name)) : "linear" as const), [dstudy, dcols]);
  const [find, setFind] = useState("");

  // the best set and the note when a move changed it
  const best = ex?.ranked[0];
  const prevBest = useRef<number | undefined>(undefined);
  const [moved, setMoved] = useState(false);
  useEffect(() => {
    if (best === undefined) return;
    setMoved(prevBest.current !== undefined && prevBest.current !== best);
    prevBest.current = best;
  }, [best]);

  const save = async (e: React.MouseEvent) => {
    if (blocked) { notify(t("swExploreOrGoal"), "error"); return; }
    const r = (e.currentTarget as HTMLElement).getBoundingClientRect();
    const st = useSweeps.getState();
    const name = goalName(t, goal, from);
    openMenu({ clientX: r.left, clientY: r.bottom + 4, preventDefault() {}, stopPropagation() {} } as React.MouseEvent, [
      { label: t("swExploreSaveNew"), run: () => {
        st.addGoal(false);
        st.updateGoal(goalOfDraft(draft, "", ranges));
        const n = useSweeps.getState().studies[useSweeps.getState().active]!;
        useSweeps.getState().setView({ explore: { draft: draftOf(n.question.goals[n.question.active]), from: n.question.active } });
        notify(t("swExploreSaved", { n: goalName(t, n.question.goals[n.question.active], n.question.active) }));
      } },
      { label: t("swExploreReplace", { n: name }), run: async () => {
        if (!(await confirmAsk(t("swExploreReplace", { n: name }), t("swExploreReplaceAsk", { n: name })))) return;
        st.setActiveGoal(from);
        st.updateGoal(goalOfDraft(draft, goal.name, ranges));
        st.setView({ explore: { draft: draftOf(goalOfDraft(draft, goal.name, ranges)), from } });
        notify(t("swExploreSaved", { n: name }));
      } },
    ]);
  };
  // back to the goal: the draft dropped, the goal's own lines and table
  const back = () => useSweeps.getState().setView({ explore: { draft: draftOf(goal), from: q.active }, center: "lines" });

  if (err) return <p className="sw-error">{err}</p>;
  if (!a || !ex || !dstudy) return <p className="hint">{t("swReading")}</p>;
  const setCond = (i: number, p: Partial<Condition>) => setDraft({ ...draft, conditions: draft.conditions.map((c, j) => (j === i ? { ...c, ...p } : c)) });
  const setObj = (k: number, p: Partial<DraftObjective>) => setDraft({ ...draft, objectives: draft.objectives.map((o, j) => (j === k ? { ...o, ...p } : o)) });
  // a value that keeps every set: the far end of the column's values for that comparison
  const openValue = (column: string, op: Op) => { const [lo, hi] = extent(cols.get(column)); return op.startsWith("<") ? hi : lo; };
  const holdingMask = new Set(ex.survivors);
  const asTable = study.view.exploreAs === "table";
  const fresh = (i: number) => !busy || i < (ans?.draft.conditions.length ?? 0);
  const goalConds = goal.conditions.filter((x) => x.column);
  const limited = Object.keys(ranges).filter((p) => isLimited(draft.limits[p], ranges[p])).length + Object.keys(draft.levels ?? {}).length;
  const limitList = Object.keys(ranges).filter((p) => !find || p.toLowerCase().includes(find.toLowerCase()));
  const brushed = (name: string, f: Filter | null) => {
    const r = ranges[name];
    if (!r) return;                                                 // only a parameter has a limit to drag
    if (!f) { setDraft(withLimit(draft, name, r, ranges)); return; }
    const vs = f.kind === "ranges" ? f.ranges.flat() : f.values;
    if (vs.length) setDraft(withLimit(draft, name, [Math.max(r[0], Math.min(...vs)), Math.min(r[1], Math.max(...vs))], ranges));
  };
  return (
    <div className="sw-explore" aria-busy={busy}>
      <div className="sw-explore-head">
        <Funnel t={t} f={ex.funnel} />
        <span className="sw-explore-status">
          {changes ? t("swExploreDiffers", { n: changes, g: goalName(t, goal, from) }) : t("swExploreSame", { g: goalName(t, goal, from) })}
          {changes > 0 && <>
            <button className="btn primary" onClick={save}>{t("swExploreSave")} ▾</button>
            <button className="btn outline" onClick={back}>{t("swExploreBack")}</button>
          </>}
        </span>
      </div>
      {blocked && <p className="sw-warn">{t("swExploreOrGoal")}</p>}
      <div className="sw-explore-body">
        <div className="sw-explore-controls">
          <div className="sw-seg sw-explore-as" role="radiogroup" aria-label={t("swProblemAs")}>
            <button role="radio" aria-checked={!asTable} className={!asTable ? "on" : ""} onClick={() => useSweeps.getState().setView({ exploreAs: "sliders" })}>{t("swProblemSliders")}</button>
            <button role="radio" aria-checked={asTable} className={asTable ? "on" : ""} onClick={() => useSweeps.getState().setView({ exploreAs: "table" })}>{t("swProblemTable")}</button>
          </div>
          {asTable ? <ProblemTable t={t} draft={draft} setDraft={setDraft} ranges={ranges} catParams={catParams} cols={cols} ex={ex}
            fresh={fresh} objFresh={(k) => !busy || k < (ans?.draft.objectives.length ?? 0)} outputs={outputs} params={params} openValue={openValue} /> : <>
          <h3>{t("swExploreLimits")}{limited > 0 && <span className="sw-limited">{t("swExploreLimited", { n: limited })}</span>}</h3>
          {Object.keys(ranges).length > FIND_FROM && (
            <input type="search" className="sw-explore-find" value={find} placeholder={t("swExploreFind")} aria-label={t("swExploreFind")} onChange={(e) => setFind(e.target.value)} />
          )}
          {limitList.map((p) => {
            const [min, max] = ranges[p];
            const [lo, hi] = limitOf(draft, p, ranges);
            const on = isLimited(draft.limits[p], ranges[p]);
            const pct = (v: number) => ((v - min) / (max - min)) * 100;
            return (
              <div key={p} className={`sw-explore-row${on ? " limited" : ""}`}>
                <div className="sw-explore-label"><span className="mono">{p}</span>
                  <span className="hint sw-num-pair">
                    <NumField value={lo} lo={min} hi={max} label={t("swExploreFrom", { c: p })}
                      onChange={(v) => setDraft(withLimit(draft, p, [Math.min(v, hi), hi], ranges))} />
                    {" – "}
                    <NumField value={hi} lo={min} hi={max} label={t("swExploreTo", { c: p })}
                      onChange={(v) => setDraft(withLimit(draft, p, [lo, Math.max(v, lo)], ranges))} />
                  </span>
                  <Cut t={t} n={ex.alone[`p:${p}`]} /></div>
                <Strip col={cols.get(p)} keep={holdingMask} lo={min} hi={max} />
                <div className="sw-range2">
                  <span className="sw-range2-fill" style={{ insetInlineStart: `${pct(lo)}%`, insetInlineEnd: `${100 - pct(hi)}%` }} />
                  <input type="range" min={min} max={max} step="any" value={lo} aria-label={t("swExploreFrom", { c: p })}
                    onChange={(e) => setDraft(withLimit(draft, p, [Math.min(Number(e.target.value), hi), hi], ranges))} />
                  <input type="range" min={min} max={max} step="any" value={hi} aria-label={t("swExploreTo", { c: p })}
                    onChange={(e) => setDraft(withLimit(draft, p, [lo, Math.max(Number(e.target.value), lo)], ranges))} />
                </div>
              </div>
            );
          })}
          {catParams.map((p) => {
            const all = cols.get(p)!.labels ?? [];
            const keep = draft.levels?.[p] ?? all;
            return (
              <div key={p} className={`sw-explore-row${draft.levels?.[p] ? " limited" : ""}`}>
                <div className="sw-explore-label"><span className="mono">{p}</span>
                  <span className="hint">{t("swLevelsOf", { n: keep.length, of: all.length })}</span>
                  <Cut t={t} n={ex.alone[`p:${p}`]} /></div>
                <div className="sw-levels" role="group" aria-label={p}>
                  {all.map((l) => (
                    <label key={l} className="acheck sw-level">
                      <input type="checkbox" checked={keep.includes(l)} disabled={keep.length === 1 && keep.includes(l)}
                        onChange={(e) => setDraft(withLevels(draft, p, e.target.checked ? [...keep, l] : keep.filter((x) => x !== l), all))} />
                      {l}
                    </label>
                  ))}
                </div>
              </div>
            );
          })}
          {!Object.keys(ranges).length && !catParams.length && <p className="hint">{t("swExploreNoLimits")}</p>}

          <h3>{t("swExploreObjs")}</h3>
          {draft.objectives.length === 0 && <p className="hint">{t("swExploreNoObjs")}</p>}
          {draft.objectives.map((o, k) => {
            const v = !busy || k < (ans?.draft.objectives.length ?? 0) ? cols.get(objectiveCol(k)) : undefined;
            const [lo, hi] = extent(v);
            const value = o.threshold ?? thresholdOffEnd(o.direction, lo, hi);
            return (
              <div key={o.column} className="sw-explore-row sw-explore-obj">
                <div className="sw-explore-label"><span className="mono">{o.column}</span>
                  <button className="btn outline sw-dir" onClick={() => setObj(k, { direction: o.direction === "max" ? "min" : "max", threshold: undefined })}>
                    {o.direction === "max" ? `↑ ${t("swMax")}` : `↓ ${t("swMin")}`}</button>
                  <button className="iconbtn" aria-label={t("swRemove")} title={t("swRemove")}
                    onClick={() => setDraft({ ...draft, objectives: draft.objectives.filter((_, j) => j !== k) })}>×</button></div>
                <label className="sw-explore-line">{t("swWeight")}
                  <input type="range" min={0} max={10} step={1} value={o.weight} aria-label={t("swWeight")} disabled={draft.objectives.length < 2}
                    onChange={(e) => setObj(k, { weight: Number(e.target.value) })} />
                  <span className="mono">{o.weight}</span></label>
                {draft.objectives.length < 2 && <p className="hint sw-explore-note">{t("swExploreWeightOne")}</p>}
                <label className="sw-explore-line">{t("swExploreThreshold")}
                  <input type="range" min={lo} max={hi} step="any" value={value} aria-label={t("swExploreThresholdOf", { c: o.column })}
                    onChange={(e) => setObj(k, { threshold: thresholdOf(o.direction, Number(e.target.value), lo, hi) })} />
                  <NumField className="sw-explore-th" value={o.threshold} lo={lo} hi={hi} prefix={`${o.direction === "min" ? "≤" : "≥"} `}
                    empty={t("swExploreNoThreshold")} label={t("swExploreThresholdOf", { c: o.column })} onChange={(v) => setObj(k, { threshold: v })} />
                </label>
                <div className="sw-explore-label"><Cut t={t} n={ex.alone[`o${k}`]} /></div>
                <Strip col={v} keep={holdingMask} lo={lo} hi={hi} mark={o.threshold} />
              </div>
            );
          })}
          <ColumnPicker options={outputs.map((o) => ({ id: o, label: o, group: t("swRoleOutput") }))} value={draft.objectives.map((o) => o.column)}
            label={t("swExploreObjsPick", { n: draft.objectives.length })}
            onChange={(ids) => setDraft({ ...draft, objectives: ids.map((c) => draft.objectives.find((o) => o.column === c) ?? { column: c, direction: "max", weight: 1 }) })} />

          <h3>{t("swExploreConds")}</h3>
          {draft.conditions.length === 0 && <p className="hint">{t("swExploreNoConds")}</p>}
          {draft.conditions.map((c, i) => {
            const w = fresh(i) ? cols.get(`#c${i}.worst`) : undefined;
            const [lo, hi] = extent(w ?? cols.get(c.column), c.value);
            const [dlo, dhi] = extent(w ?? cols.get(c.column));          // the results' own range (Q129: outside it is said)
            const g = goalConds[i];
            const changed = !g || g.column !== c.column || g.op !== c.op || g.value !== c.value;
            return (
              <div key={i} className="sw-explore-row sw-explore-cond">
                <div className="sw-explore-label">
                  <select aria-label={t("swCondColumn")} value={c.column} onChange={(e) => setCond(i, { column: e.target.value, value: openValue(e.target.value, c.op) })}>
                    <optgroup label={t("swRoleOutput")}>{outputs.map((o) => <option key={o} value={o}>{o}</option>)}</optgroup>
                    {params.length > 0 && <optgroup label={t("swRoleParam")}>{params.map((o) => <option key={o} value={o}>{o}</option>)}</optgroup>}
                  </select>
                  <select aria-label={t("swCondOp")} value={c.op} onChange={(e) => setCond(i, { op: e.target.value as Op })}>
                    {OPS.map((o) => <option key={o} value={o}>{o}</option>)}
                  </select>
                  <NumField className={changed ? "sw-whatif" : ""} value={c.value} lo={dlo} hi={dhi} label={t("swCondValueOf", { c: c.column })}
                    onChange={(v) => setCond(i, { value: v })} />
                  <Cut t={t} n={ex.alone[`c${i}`]} />
                  <button className="iconbtn" aria-label={t("swRemove")} title={t("swRemove")}
                    onClick={() => setDraft({ ...draft, conditions: draft.conditions.filter((_, j) => j !== i) })}>×</button>
                </div>
                <Strip col={w} keep={holdingMask} lo={lo} hi={hi} mark={c.value} />
                <input type="range" min={lo} max={hi} step="any" value={c.value} aria-label={`${c.column} ${c.op}`} onChange={(e) => setCond(i, { value: Number(e.target.value) })} />
              </div>
            );
          })}
          <button className="btn outline sw-add-btn" disabled={!outputs.length && !params.length}
            onClick={() => { const column = outputs[0] ?? params[0]; setDraft({ ...draft, conditions: [...draft.conditions, { column, op: "<=", value: openValue(column, "<="), mode: "all" }] }); }}>
            {t("swAddCondition")}</button>
          </>}
        </div>

        <div className="sw-explore-result">
          <p className="sw-explore-left" aria-live="polite">{t("swExploreLeft", { n: ex.survivors.length.toLocaleString(), of: ex.n.toLocaleString() })}</p>
          <p className="hint">{t("swExploreLinesHint")}</p>
          {axes.length > 1 ? (
            <ParallelPlot sliderLabel={(x, y, n) => t("swAxesOnScreen", { a: x, b: y, n })} cols={dcols} n={ex.n} axes={axes} scaleOf={scale}
              reversed={study.view.reversed} colorBy={study.view.colorBy && dcols.has(study.view.colorBy) ? study.view.colorBy : null}
              filters={limitMarks(shown!)} keep={keep} highlight={bestMask} labelOf={(x) => colLabel(t, dstudy, x)} fit={!!study.view.fitAxes} height={300}
              onPick={(r) => useSweeps.getState().setView({ pinned: r })} onFilter={brushed} onAxisMenu={() => {}} onMoveAxis={() => {}} />
          ) : <p className="empty-note">{t("swNoAxes")}</p>}
          <div className="sw-explore-extras">
            <Best t={t} study={study} cols={cols} ex={ex} draft={shown!} moved={moved} />
            {shown!.objectives.length >= 2 && <Pareto cols={cols} ex={ex} draft={shown!} t={t} />}
          </div>
          {shown!.objectives.length >= 2 && <DecidePanel t={t} study={study} a={a} cols={cols} ex={ex} draft={shown!}
            setDraft={(d) => setDraft({ ...draft, decide: d.decide })} />}
          <SetsTable study={dstudy} draft />
        </div>
      </div>
    </div>
  );
}

/** The finite range of a column (and a value that must be in it). */
function extent(c: Col | undefined, also?: number): [number, number] {
  let lo = Infinity, hi = -Infinity;
  if (c) for (const v of c.values) if (Number.isFinite(v)) { lo = Math.min(lo, v); hi = Math.max(hi, v); }
  if (also !== undefined && Number.isFinite(also)) { lo = Math.min(lo, also); hi = Math.max(hi, also); }
  return Number.isFinite(lo) ? (lo === hi ? [lo - 1, hi + 1] : [lo, hi]) : [0, 1];
}

function Funnel({ t, f }: { t: TFn; f: [number, number, number, number] }) {
  const steps: [string, number][] = [[t("swFunnelAll"), f[0]], [t("swFunnelConds"), f[1]], [t("swFunnelLimits"), f[2]], [t("swFunnelThresholds"), f[3]]];
  return (
    <ol className="sw-funnel" aria-label={t("swFunnel")}>
      {steps.map(([label, n], i) => <li key={i} className={i === 3 ? "last" : ""}><b>{n.toLocaleString()}</b><span>{label}</span></li>)}
    </ol>
  );
}

const Cut = ({ t, n }: { t: TFn; n: number | undefined }) =>
  n ? <span className="sw-cut" title={t("swExploreAloneHint")}>{t("swExploreAlone", { n })}</span> : null;

/** Where the sets are along a slider: a bar per bin, the part still standing coloured. */
function Strip({ col, keep, lo, hi, mark }: { col?: Col; keep: Set<number>; lo: number; hi: number; mark?: number }) {
  if (!col) return null;
  const all = new Array(BINS).fill(0), kept = new Array(BINS).fill(0);
  col.values.forEach((v, s) => {
    if (!Number.isFinite(v)) return;
    const b = Math.max(0, Math.min(BINS - 1, Math.floor(((v - lo) / (hi - lo || 1)) * BINS)));
    all[b]++;
    if (keep.has(s)) kept[b]++;
  });
  const top = Math.max(1, ...all);
  return (
    <svg className="sw-strip" viewBox={`0 0 ${BINS * 6} 18`} preserveAspectRatio="none" aria-hidden="true">
      {all.map((n, b) => <rect key={b} x={b * 6 + 0.5} y={18 - (n / top) * 18} width={5} height={(n / top) * 18} className="all" />)}
      {kept.map((n, b) => n > 0 && <rect key={`k${b}`} x={b * 6 + 0.5} y={18 - (n / top) * 18} width={5} height={(n / top) * 18} className="kept" />)}
      {mark !== undefined && <line x1={((mark - lo) / (hi - lo || 1)) * BINS * 6} x2={((mark - lo) / (hi - lo || 1)) * BINS * 6} y1={0} y2={18} className="mark" />}
    </svg>
  );
}

function Best({ t, study, cols, ex, draft, moved }: { t: TFn; study: Study; cols: Map<string, Col>; ex: Explored; draft: Draft; moved: boolean }) {
  const s = ex.ranked[0];
  if (s === undefined) return <div className="sw-hide-box sw-best"><b>★ {t("swBestSetTitle")}</b><span className="hint">{t("swExploreNone")}</span></div>;
  const show = (c: string) => { const col = cols.get(c); return col ? labelOf(col, col.values[s]) : "–"; };
  return (
    <div className="sw-hide-box sw-best">
      <b>★ {t("swBestSetTitle")}{moved && <span className="sw-moved-note"> · {t("swExploreBestMoved")}</span>}</b>
      <div className="sw-best-params">{activeParams(study).map((p) => <span key={p}>{p} = <b>{show(p)}</b></span>)}</div>
      {draft.objectives.map((o, k) => <div key={o.column} className="sw-best-goal"><span>{o.direction === "max" ? "↑" : "↓"} {o.column}</span><b>{show(objectiveCol(k))}</b></div>)}
      {draft.objectives.length > 1 && <div className="sw-best-goal"><span>{t("swScoreCol")}</span><b>{fmtValue(ex.value.get(s)!)}</b></div>}
      <button className="btn outline" onClick={() => useSweeps.getState().setView({ pinned: s, step: "results", center: "lines" })}>{t("swOpenBestSet")}</button>
    </div>
  );
}

function Pareto({ t, cols, ex, draft }: { t: TFn; cols: Map<string, Col>; ex: Explored; draft: Draft }) {
  const x = cols.get(objectiveCol(0))?.values, y = cols.get(objectiveCol(1))?.values;
  if (!x || !y) return null;
  // scaled to the sets that are left (a far one elsewhere squeezed them into a corner), a margin round
  const keep = new Set(ex.survivors), best = ex.ranked[0];
  const span = (v: Float32Array): [number, number] => {
    let lo = Infinity, hi = -Infinity;
    for (const s of (ex.survivors.length > 1 ? ex.survivors : v.map((_, i) => i))) if (Number.isFinite(v[s])) { lo = Math.min(lo, v[s]); hi = Math.max(hi, v[s]); }
    if (!Number.isFinite(lo)) return [0, 1];
    const pad = (hi - lo || Math.abs(hi) || 1) * 0.08;
    return [lo - pad, hi + pad];
  };
  const [x0, x1] = span(x), [y0, y1] = span(y);
  const W = 320, H = 200, L = 52, B = 34, T = 8, R = 10;
  const px = (v: number) => L + ((v - x0) / (x1 - x0)) * (W - L - R), py = (v: number) => H - B - ((v - y0) / (y1 - y0)) * (H - B - T);
  const inside = (s: number) => x[s] >= x0 && x[s] <= x1 && y[s] >= y0 && y[s] <= y1;
  return (
    <figure className="sw-explore-pareto">
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={t("swExplorePareto")}>
        <line x1={L} y1={H - B} x2={W - R} y2={H - B} className="sw-axis-line" /><line x1={L} y1={T} x2={L} y2={H - B} className="sw-axis-line" />
        <text x={L} y={H - B + 13} textAnchor="start" className="sw-ax">{fmtValue(x0)}</text>
        <text x={W - R} y={H - B + 13} textAnchor="end" className="sw-ax">{fmtValue(x1)}</text>
        <text x={L - 4} y={H - B} textAnchor="end" className="sw-ax">{fmtValue(y0)}</text>
        <text x={L - 4} y={T + 8} textAnchor="end" className="sw-ax">{fmtValue(y1)}</text>
        {Array.from(x).map((v, s) => Number.isFinite(v) && Number.isFinite(y[s]) && inside(s) &&
          <circle key={s} cx={px(v)} cy={py(y[s])} r={ex.front.has(s) ? 4.5 : 3} className={keep.has(s) ? (ex.front.has(s) ? "front" : "kept") : "out"} />)}
        {best !== undefined && <text x={px(x[best])} y={py(y[best]) - 7} textAnchor="middle" className="sw-best-star">★</text>}
        <text x={(L + W - R) / 2} y={H - 4} textAnchor="middle" className="sw-ax-title">{draft.objectives[0].direction === "max" ? "↑" : "↓"} {draft.objectives[0].column}</text>
        <text x={10} y={(T + H - B) / 2} textAnchor="middle" className="sw-ax-title" transform={`rotate(-90 10 ${(T + H - B) / 2})`}>{draft.objectives[1].direction === "max" ? "↑" : "↓"} {draft.objectives[1].column}</text>
      </svg>
      <figcaption className="hint">{t("swExploreParetoKey", { n: ex.front.size })}</figcaption>
    </figure>
  );
}

/* MF01: the problem as one table - the same draft as the sliders (parameters, objectives,
   conditions), every value typed (NumField), how many sets each line cuts. Columns for later tasks
   (distribution, DOE levels) are added by those tasks. */
function ProblemTable({ t, draft, setDraft, ranges, catParams, cols, ex, fresh, objFresh, outputs, params, openValue }: {
  t: TFn; draft: Draft; setDraft: (d: Draft) => void; ranges: Record<string, [number, number]>; catParams: string[];
  cols: Map<string, Col>; ex: Explored; fresh: (i: number) => boolean; objFresh: (k: number) => boolean;
  outputs: string[]; params: string[]; openValue: (c: string, op: Op) => number;
}) {
  const setCond = (i: number, p: Partial<Condition>) => setDraft({ ...draft, conditions: draft.conditions.map((c, j) => (j === i ? { ...c, ...p } : c)) });
  const setObj = (k: number, p: Partial<DraftObjective>) => setDraft({ ...draft, objectives: draft.objectives.map((o, j) => (j === k ? { ...o, ...p } : o)) });
  const kindOf = (p: string): string => {
    const c = cols.get(p);
    if (c?.kind === "cat") return t("swTypeCategorical");
    return c && Array.from(c.values).every((v) => !Number.isFinite(v) || Number.isInteger(v)) ? t("swTypeInteger") : t("swTypeContinuous");
  };
  const distinct = (p: string) => new Set(Array.from(cols.get(p)?.values ?? []).filter(Number.isFinite)).size;
  const best = ex.ranked[0];
  return (
    <div className="sw-problem">
      <table className="sw-table sw-problem-table">
        <thead><tr><th colSpan={7}>{t("swRoleParam")}</th></tr>
          <tr><th>{t("swPName")}</th><th>{t("swPType")}</th><th>{t("swPFrom")}</th><th>{t("swPTo")}</th><th>{t("swPInData")}</th><th /><th>{t("swPCuts")}</th></tr></thead>
        <tbody>
          {params.filter((p) => ranges[p]).map((p) => {
            const [min, max] = ranges[p];
            const [lo, hi] = limitOf(draft, p, ranges);
            return (
              <tr key={p} data-param={p} className={isLimited(draft.limits[p], ranges[p]) ? "limited" : ""}>
                <td className="mono">{p}</td><td>{kindOf(p)}</td>
                <td><NumField value={lo} lo={min} hi={max} label={t("swExploreFrom", { c: p })} onChange={(v) => setDraft(withLimit(draft, p, [Math.min(v, hi), hi], ranges))} /></td>
                <td><NumField value={hi} lo={min} hi={max} label={t("swExploreTo", { c: p })} onChange={(v) => setDraft(withLimit(draft, p, [lo, Math.max(v, lo)], ranges))} /></td>
                <td className="hint">{fmtValue(min)} – {fmtValue(max)} · {t("swNValues", { n: distinct(p) })}</td><td />
                <td><Cut t={t} n={ex.alone[`p:${p}`]} /></td>
              </tr>
            );
          })}
          {catParams.map((p) => {
            const all = cols.get(p)!.labels ?? [];
            const keep = draft.levels?.[p] ?? all;
            return (
              <tr key={p} data-param={p} className={draft.levels?.[p] ? "limited" : ""}>
                <td className="mono">{p}</td><td>{kindOf(p)}</td>
                <td colSpan={2}><span className="sw-levels">{all.map((l) => (
                  <label key={l} className="acheck sw-level"><input type="checkbox" checked={keep.includes(l)} disabled={keep.length === 1 && keep.includes(l)}
                    onChange={(e) => setDraft(withLevels(draft, p, e.target.checked ? [...keep, l] : keep.filter((x) => x !== l), all))} />{l}</label>))}</span></td>
                <td className="hint">{t("swLevelsOf", { n: keep.length, of: all.length })}</td><td />
                <td><Cut t={t} n={ex.alone[`p:${p}`]} /></td>
              </tr>
            );
          })}
        </tbody>
        <thead><tr><th colSpan={7}>{t("swExploreObjs")}</th></tr>
          <tr><th>{t("swPName")}</th><th>{t("swPDirection")}</th><th>{t("swWeight")}</th><th>{t("swExploreThreshold")}</th><th>{t("swPInData")}</th><th>{t("swPBest")}</th><th>{t("swPCuts")}</th></tr></thead>
        <tbody>
          {draft.objectives.map((o, k) => {
            const v = objFresh(k) ? cols.get(objectiveCol(k)) : undefined;
            const [lo, hi] = extent(v);
            return (
              <tr key={o.column}>
                <td className="mono">{o.column}</td>
                <td><button className="btn outline sw-dir" onClick={() => setObj(k, { direction: o.direction === "max" ? "min" : "max", threshold: undefined })}>
                  {o.direction === "max" ? `↑ ${t("swMax")}` : `↓ ${t("swMin")}`}</button></td>
                <td><NumField value={o.weight} lo={0} hi={10} label={t("swWeight")} onChange={(w) => setObj(k, { weight: Math.max(0, w) })} /></td>
                <td><NumField value={o.threshold} lo={lo} hi={hi} prefix={`${o.direction === "min" ? "≤" : "≥"} `} empty={t("swExploreNoThreshold")}
                  label={t("swExploreThresholdOf", { c: o.column })} onChange={(x) => setObj(k, { threshold: x })} /></td>
                <td className="hint">{fmtValue(lo)} – {fmtValue(hi)}</td>
                <td className="mono">{best !== undefined && v ? fmtValue(v.values[best]) : "–"}</td>
                <td><Cut t={t} n={ex.alone[`o${k}`]} /></td>
              </tr>
            );
          })}
          <tr><td colSpan={7}><ColumnPicker options={outputs.map((x) => ({ id: x, label: x, group: t("swRoleOutput") }))} value={draft.objectives.map((o) => o.column)}
            label={t("swExploreObjsPick", { n: draft.objectives.length })}
            onChange={(ids) => setDraft({ ...draft, objectives: ids.map((c) => draft.objectives.find((o) => o.column === c) ?? { column: c, direction: "max", weight: 1 }) })} /></td></tr>
        </tbody>
        <thead><tr><th colSpan={7}>{t("swExploreConds")}</th></tr>
          <tr><th>{t("swCondColumn")}</th><th>{t("swCondOp")}</th><th>{t("swCondValue")}</th><th>{t("swPWhere")}</th><th>{t("swPInData")}</th><th /><th>{t("swPCuts")}</th></tr></thead>
        <tbody>
          {draft.conditions.map((c, i) => {
            const w = fresh(i) ? cols.get(`#c${i}.worst`) : undefined;
            const [lo, hi] = extent(w ?? cols.get(c.column));
            return (
              <tr key={i}>
                <td><select aria-label={t("swCondColumn")} value={c.column} onChange={(e) => setCond(i, { column: e.target.value, value: openValue(e.target.value, c.op) })}>
                  <optgroup label={t("swRoleOutput")}>{outputs.map((x) => <option key={x} value={x}>{x}</option>)}</optgroup>
                  {params.length > 0 && <optgroup label={t("swRoleParam")}>{params.map((x) => <option key={x} value={x}>{x}</option>)}</optgroup>}
                </select></td>
                <td><select aria-label={t("swCondOp")} value={c.op} onChange={(e) => setCond(i, { op: e.target.value as Op })}>{OPS.map((x) => <option key={x} value={x}>{x}</option>)}</select></td>
                <td><NumField value={c.value} lo={lo} hi={hi} label={t("swCondValueOf", { c: c.column })} onChange={(v) => setCond(i, { value: v })} /></td>
                <td className="hint">{c.mode === "atLeast" ? t("swPAtLeast", { k: c.k ?? 1 }) : t("swPEvery")}</td>
                <td className="hint">{fmtValue(lo)} – {fmtValue(hi)}</td>
                <td><button className="iconbtn" aria-label={t("swRemove")} title={t("swRemove")}
                  onClick={() => setDraft({ ...draft, conditions: draft.conditions.filter((_, j) => j !== i) })}>×</button></td>
                <td><Cut t={t} n={ex.alone[`c${i}`]} /></td>
              </tr>
            );
          })}
          <tr><td colSpan={7}><button className="btn outline sw-add-btn" disabled={!outputs.length && !params.length}
            onClick={() => { const column = outputs[0] ?? params[0]; setDraft({ ...draft, conditions: [...draft.conditions, { column, op: "<=", value: openValue(column, "<="), mode: "all" }] }); }}>
            {t("swAddCondition")}</button></td></tr>
        </tbody>
      </table>
    </div>
  );
}
