/* Explore (S21): a draft of the active goal - its conditions dragged as "what if", limits on the
   parameters, the objectives with direction, weight and an optional threshold - applied together to
   the parameter sets at every move: a funnel of what is left, each control's own cut, the best set,
   the leading candidates and (two objectives) the Pareto front. Nothing here is the goal until
   "Save as a goal"; "Back to the goal" drops the draft. The logic: sweeps/explore.ts. */
import { useEffect, useMemo, useRef, useState } from "react";
import { useT, type TFn } from "../../i18n";
import { sweepApi } from "../../sweeps/api";
import { decodeCol } from "../../sweeps/decode";
import { draftChanges, draftOf, explore, goalOfDraft, needsAnd, objectiveCol, structureKey, type Draft, type DraftObjective, type Explored } from "../../sweeps/explore";
import type { Answer, Col } from "../../sweeps/model";
import { fmtValue, labelOf } from "../../sweeps/scales";
import { useSweeps, wireQuestion, type Study } from "../../sweeps/state";
import { notify } from "../../sweeps/notify";
import { activeColumns, activeParams } from "../../sweeps/view";
import { confirmAsk, openMenu } from "../Overlays";
import ColumnPicker from "./ColumnPicker";
import { goalName } from "./GoalsStep";

const BINS = 24;

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
  const [ans, setAns] = useState<{ key: string; a: Answer } | null>(null);
  const [err, setErr] = useState("");
  const key = structureKey(draft, robust) + JSON.stringify(wireQuestion(study));
  const live = useRef(0);
  useEffect(() => {
    const id = ++live.current;
    const timer = window.setTimeout(() => {
      const base = wireQuestion(study);
      const objs = draft.objectives;
      const wq = { ...base, conditions: draft.conditions, combine: draft.combine,
        goal: objs[0] ? { column: objs[0].column, direction: objs[0].direction } : null,
        objectives: objs.length > 1 ? objs.map(({ column, direction, weight }) => ({ column, direction, weight })) : [] };
      sweepApi.evaluate(study.tableId, wq, false).then((w) => {
        if (id !== live.current) return;
        setAns({ key, a: { counts: w.counts, conditions: w.conditions, seconds: w.seconds, sets: w.sets.map((c) => decodeCol(c)) } });
        setErr("");
      }).catch((e) => id === live.current && setErr((e as Error).message));
    }, robust ? 250 : 0);
    return () => window.clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, study.tableId]);

  const a = ans?.a;
  const ex = useMemo(() => (a ? explore(a, draft, robust) : null), [a, draft, robust]);
  const cols = useMemo(() => new Map<string, Col>((a?.sets ?? []).map((c) => [c.name, c])), [a]);
  // the numeric parameters' ranges (for limits) and every output that can be an objective
  const ranges = useMemo(() => {
    const out: Record<string, [number, number]> = {};
    for (const p of activeParams(study)) {
      const c = cols.get(p);
      if (!c || c.kind !== "num") continue;
      let lo = Infinity, hi = -Infinity;
      for (const v of c.values) if (Number.isFinite(v)) { lo = Math.min(lo, v); hi = Math.max(hi, v); }
      if (lo < hi) out[p] = [lo, hi];
    }
    return out;
  }, [cols, study]);
  const outputs = [...activeColumns(study, "output"), ...q.derived.map((d) => d.name)];
  const changes = draftChanges(draft, goal, ranges);
  const blocked = needsAnd(draft, ranges);

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

  if (err) return <p className="sw-error">{err}</p>;
  if (!a || !ex) return <p className="hint">{t("swReading")}</p>;
  const setCond = (i: number, value: number) => setDraft({ ...draft, conditions: draft.conditions.map((c, j) => (j === i ? { ...c, value } : c)) });
  const setObj = (k: number, p: Partial<DraftObjective>) => setDraft({ ...draft, objectives: draft.objectives.map((o, j) => (j === k ? { ...o, ...p } : o)) });
  const holdingMask = new Set(ex.survivors);
  return (
    <div className="sw-explore">
      <div className="sw-explore-head">
        <Funnel t={t} f={ex.funnel} />
        <span className="sw-explore-status">
          {changes ? t("swExploreDiffers", { n: changes, g: goalName(t, goal, from) }) : t("swExploreSame", { g: goalName(t, goal, from) })}
          {changes > 0 && <>
            <button className="btn primary" onClick={save}>{t("swExploreSave")} ▾</button>
            <button className="btn outline" onClick={() => setDraft(draftOf(goal))}>{t("swExploreBack")}</button>
          </>}
        </span>
      </div>
      {blocked && <p className="sw-warn">{t("swExploreOrGoal")}</p>}
      <div className="sw-explore-body">
        <div className="sw-explore-controls">
          <h3>{t("swExploreConds")}</h3>
          {draft.conditions.length === 0 && <p className="hint">{t("swExploreNoConds")}</p>}
          {draft.conditions.map((c, i) => {
            const w = cols.get(`#c${i}.worst`);
            const [lo, hi] = extent(w, c.value);
            return (
              <Slider key={i} t={t} label={`${c.column} ${c.op}`} value={c.value} lo={lo} hi={hi} col={w} keep={holdingMask}
                alone={ex.alone[`c${i}`]} changed={c.value !== goal.conditions.filter((x) => x.column)[i]?.value} onChange={(v) => setCond(i, v)} />
            );
          })}
          <h3>{t("swExploreLimits")}</h3>
          <ColumnPicker options={Object.keys(ranges).map((p) => ({ id: p, label: p, group: t("swRoleParam") }))} value={Object.keys(draft.limits)}
            label={t("swExploreLimitsPick", { n: Object.keys(draft.limits).length })}
            onChange={(ids) => setDraft({ ...draft, limits: Object.fromEntries(ids.map((p) => [p, draft.limits[p] ?? ranges[p]])) })} />
          {Object.entries(draft.limits).map(([p, [lo, hi]]) => {
            const [min, max] = ranges[p] ?? [lo, hi];
            return (
              <div key={p} className="sw-explore-row">
                <div className="sw-explore-label"><span className="mono">{p}</span>
                  <span className="hint">{fmtValue(lo)} – {fmtValue(hi)}</span>
                  <Cut t={t} n={ex.alone[`p:${p}`]} /></div>
                <Strip col={cols.get(p)} keep={holdingMask} lo={min} hi={max} />
                <div className="sw-range2">
                  <input type="range" min={min} max={max} step="any" value={lo} aria-label={t("swExploreFrom", { c: p })}
                    onChange={(e) => setDraft({ ...draft, limits: { ...draft.limits, [p]: [Math.min(Number(e.target.value), hi), hi] } })} />
                  <input type="range" min={min} max={max} step="any" value={hi} aria-label={t("swExploreTo", { c: p })}
                    onChange={(e) => setDraft({ ...draft, limits: { ...draft.limits, [p]: [lo, Math.max(Number(e.target.value), lo)] } })} />
                </div>
              </div>
            );
          })}
          <h3>{t("swExploreObjs")}</h3>
          <ColumnPicker options={outputs.map((o) => ({ id: o, label: o, group: t("swRoleOutput") }))} value={draft.objectives.map((o) => o.column)}
            label={t("swExploreObjsPick", { n: draft.objectives.length })}
            onChange={(ids) => setDraft({ ...draft, objectives: ids.map((c) => draft.objectives.find((o) => o.column === c) ?? { column: c, direction: "max", weight: 1 }) })} />
          {draft.objectives.map((o, k) => {
            const v = cols.get(objectiveCol(k));
            const [lo, hi] = extent(v);
            return (
              <div key={o.column} className="sw-explore-row sw-explore-obj">
                <div className="sw-explore-label"><span className="mono">{o.column}</span>
                  <button className="btn outline sw-dir" onClick={() => setObj(k, { direction: o.direction === "max" ? "min" : "max", threshold: undefined })}>
                    {o.direction === "max" ? `↑ ${t("swMax")}` : `↓ ${t("swMin")}`}</button></div>
                {draft.objectives.length > 1 && (
                  <label className="sw-explore-line">{t("swWeight")}
                    <input type="range" min={0} max={10} step={1} value={o.weight} onChange={(e) => setObj(k, { weight: Number(e.target.value) })} />
                    <span className="mono">{o.weight}</span></label>
                )}
                <label className="sw-explore-line">
                  <input type="checkbox" checked={o.threshold !== undefined}
                    onChange={(e) => setObj(k, { threshold: e.target.checked ? (o.direction === "min" ? hi : lo) : undefined })} />
                  {t("swExploreThreshold")}
                  {o.threshold !== undefined && <>
                    <input type="range" min={lo} max={hi} step="any" value={o.threshold} onChange={(e) => setObj(k, { threshold: Number(e.target.value) })} />
                    <span className="mono">{o.direction === "min" ? "≤" : "≥"} {fmtValue(o.threshold)}</span>
                    <Cut t={t} n={ex.alone[`o${k}`]} />
                  </>}
                </label>
                {o.threshold !== undefined && <Strip col={v} keep={holdingMask} lo={lo} hi={hi} mark={o.threshold} />}
              </div>
            );
          })}
        </div>
        <div className="sw-explore-result">
          <Best t={t} study={study} cols={cols} ex={ex} draft={draft} moved={moved} />
          {draft.objectives.length >= 2 && <Pareto cols={cols} ex={ex} draft={draft} t={t} />}
          <Candidates t={t} study={study} cols={cols} ex={ex} draft={draft} />
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

function Slider({ t, label, value, lo, hi, col, keep, alone, changed, onChange }: {
  t: TFn; label: string; value: number; lo: number; hi: number; col?: Col; keep: Set<number>; alone: number | undefined; changed: boolean; onChange: (v: number) => void;
}) {
  return (
    <div className="sw-explore-row">
      <div className="sw-explore-label"><span className="mono">{label}</span>
        <span className={`mono${changed ? " sw-whatif" : ""}`} title={changed ? t("swExploreWhatIf") : undefined}>{fmtValue(value)}</span>
        <Cut t={t} n={alone} /></div>
      <Strip col={col} keep={keep} lo={lo} hi={hi} mark={value} />
      <input type="range" min={lo} max={hi} step="any" value={value} aria-label={label} onChange={(e) => onChange(Number(e.target.value))} />
    </div>
  );
}

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

function Candidates({ t, study, cols, ex, draft }: { t: TFn; study: Study; cols: Map<string, Col>; ex: Explored; draft: Draft }) {
  const params = activeParams(study);
  const rows = ex.ranked.slice(0, 10);
  if (!rows.length) return null;
  const v = (c: string, s: number) => { const col = cols.get(c); return col ? labelOf(col, col.values[s]) : "–"; };
  return (
    <div className="sw-table-wrap">
      <table className="sw-table">
        <thead><tr><th>#</th>{params.map((p) => <th key={p}>{p}</th>)}
          {draft.objectives.map((o, k) => <th key={k} className="num">{o.direction === "max" ? "↑" : "↓"} {o.column}</th>)}
          {draft.conditions.map((c, i) => <th key={`m${i}`} className="num">{t("swExploreMargin", { c: c.column })}</th>)}</tr></thead>
        <tbody>{rows.map((s, r) => (
          <tr key={s} className={ex.front.has(s) ? "sw-on-front" : ""} onClick={() => useSweeps.getState().setView({ pinned: s, step: "results", center: "lines" })}>
            <td className="num">{r + 1}</td>{params.map((p) => <td key={p}>{v(p, s)}</td>)}
            {draft.objectives.map((_, k) => <td key={k} className="num">{v(objectiveCol(k), s)}</td>)}
            {draft.conditions.map((c, i) => {
              const w = cols.get(`#c${i}.worst`)?.values[s];
              const m = w === undefined || !Number.isFinite(w) ? NaN : c.op.startsWith("<") ? c.value - w : w - c.value;
              return <td key={`m${i}`} className="num">{Number.isFinite(m) ? fmtValue(m) : "–"}</td>;
            })}
          </tr>
        ))}</tbody>
      </table>
    </div>
  );
}
