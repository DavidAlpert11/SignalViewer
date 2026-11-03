/* Step 2, the columns (owner's spec, 2026-11-02): what each column is - a PARAMETER (what we choose;
   each combination is a parameter set), an OUTPUT (a result to set goals on), a CONDITION (what we
   don't choose: a parameter set must hold in every combination of them), an IDENTIFIER (a run id,
   or a link to the run's recording) or NOT USED. The guess is only a start.
   The middle: a tool row (undo / redo; the guessed roles back; Template ▾), the shape of the study
   as one row of numbers, the table of columns. The side panel, short: one sentence, then two folding
   parts - each condition's values, and the new columns. */
import { useEffect, useMemo, useState } from "react";
import { pickPath } from "../../store";
import { useT, type TFn, type TKey } from "../../i18n";
import { Icon } from "../../icons";
import { sweepApi, type Role } from "../../sweeps/api";
import { useSweeps, type Study, type StudyColumn } from "../../sweeps/state";
import { templateSummary } from "../../sweeps/templates";
import { Stat } from "./Shape";
import DerivedEditor from "./DerivedEditor";
import { fmtValue } from "../../sweeps/scales";
import { StepFoot } from "./StepNav";
import { notify, notifyError } from "../../sweeps/notify";
import type { Derived } from "../../sweeps/model";

/** one value in every run, or empty */
const tellsNothing = (c: { constant: boolean; empty: boolean }) => c.constant || c.empty;

/** The table's role columns; Identifiers is a run id or a recording (chosen beside it). */
type Choice = "param" | "output" | "hold" | "ident" | "ignore";
const ROLE_ORDER: { r: Choice; key: TKey; tip: TKey }[] = [
  { r: "param", key: "swRoleParam", tip: "swRoleParamTip" }, { r: "output", key: "swRoleOutput", tip: "swRoleOutputTip" },
  { r: "hold", key: "swRoleHold", tip: "swRoleHoldTip" }, { r: "ident", key: "swRoleIdent", tip: "swRoleIdentTip" },
  { r: "ignore", key: "swRoleIgnore", tip: "swRoleIgnoreTip" },
];
const choiceOf = (r: Role): Choice => (r === "id" || r === "recording" ? "ident" : r);
/** a condition with more values than this gets a search and "+N more" */
const FEW = 8;

export function RolesSide({ study }: { study: Study }) {
  const t = useT();
  const q = study.question, sm = study.summary;
  const holds = study.columns.filter((c) => c.role === "hold" && !q.removed.includes(c.name));
  const tb = study.tables[study.use];
  return (
    <div className="sw-side-step">
      <p className="sw-step-intro">{t("swColumnsLead", { name: tb?.name ?? study.name, runs: (sm.rowsAll ?? sm.rows).toLocaleString(), cols: study.columns.length,
        p: sm.params.length, o: sm.outputs.length, h: sm.holds.length })}</p>
      {study.summary.duplicates > 0 && <p className="sw-warn">{t("swDuplicates", { n: study.summary.duplicates })}</p>}
      <details className="sw-fold" open>
        <summary><b>{t("swConditions")}</b> <span className="hint">{holds.length}</span></summary>
        {holds.length ? holds.map((c) => <ConditionCard key={c.name} study={study} c={c} />) : <p className="hint">{t("swNoConditions")}</p>}
      </details>
      <NothingBox study={study} />
      <NewColumns study={study} />
      <StepFoot study={study} />
    </div>
  );
}

/** A condition's values: a folding card, its kept values in its title ("8 of 24"). Few values:
 *  chips; many: a search, the first chips, "+N more" (the whole list, each with its runs, the kept
 *  first), All / None on what the search finds; a number with many values can be a range. */
function ConditionCard({ study, c }: { study: Study; c: StudyColumn }) {
  const t = useT();
  const st = useSweeps.getState();
  const all = c.values ?? [];
  const many = !c.values || all.length > FEW;
  const keptNow = study.question.holdValues[c.name] ?? [];
  const [full, setFull] = useState<{ values: [string | number, number][]; numeric: boolean } | null>(null);
  const [q, setQ] = useState("");
  const [more, setMore] = useState(false);
  const [range, setRange] = useState<{ lo: string; hi: string } | null>(null);
  // the whole list (a column with more than 50 values has none in its description), with each value's runs
  useEffect(() => {
    if (!many) return;
    let live = true;
    sweepApi.values(study.tableId, c.name).then((r) => live && setFull({ values: r.values, numeric: r.numeric })).catch(() => {});
    return () => { live = false; };
  }, [many, study.tableId, c.name]);
  const values: (string | number)[] = full ? full.values.map((x) => x[0]) : all;
  const runsOf = new Map((full?.values ?? []).map(([v, n]) => [String(v), n]));
  const kept = keptNow.length ? keptNow : values;
  const keptSet = new Set(kept.map(String));
  const set = (next: (string | number)[]) => { if (next.length) st.setHoldValues(c.name, next.length >= values.length ? [] : next); };
  const toggle = (v: string | number) => set(keptSet.has(String(v)) ? kept.filter((x) => String(x) !== String(v)) : [...kept, v]);
  const fq = q.trim().toLowerCase();
  const found = values.filter((v) => !fq || String(v).toLowerCase().includes(fq));
  const chip = (v: string | number) => {
    const on = keptSet.has(String(v));
    return <button key={String(v)} className={`sw-pill${on ? " on" : ""}`} aria-pressed={on} title={runsOf.has(String(v)) ? t("swRunsN", { n: runsOf.get(String(v))! }) : undefined}
      onClick={() => toggle(v)}>{String(v)}</button>;
  };
  // closed: the kept values are always shown (and the first others, to tick)
  const firstChips = [...found.filter((v) => keptSet.has(String(v)) && keptNow.length), ...found.filter((v) => !(keptSet.has(String(v)) && keptNow.length))].slice(0, FEW);
  const rest = found.length - firstChips.length;
  const listed = [...found].sort((a, b) => Number(!keptSet.has(String(a))) - Number(!keptSet.has(String(b))));
  return (
    <details className="sw-cond-card">
      <summary><span className="sw-ellipsis" title={c.name}>{c.name}</span>
        <span className="hint">{t("swKeptOf", { n: kept.length, of: values.length || c.distinct })}</span></summary>
      <label className="acheck sw-split-toggle" title={t("swSplitThisHint")}>
        <input type="checkbox" checked={study.question.split === c.name} onChange={(e) => st.setSplit(e.target.checked ? c.name : null)} /> {t("swSplitThis")}
      </label>
      {!many ? <div className="sw-hold-values">{values.map(chip)}</div> : (
        <>
          <div className="sw-row">
            <input className="sw-search" type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder={t("swSearchValues")} aria-label={t("swSearchValues")} />
            <button className="linklike" onClick={() => set([...new Set([...kept.filter((x) => !found.includes(x)), ...found])])}>{t("swAll")}</button>
            <button className="linklike" onClick={() => set(kept.filter((x) => !found.some((f) => String(f) === String(x))))}>{t("swNone")}</button>
          </div>
          {!more && <div className="sw-hold-values">{firstChips.map(chip)}
            {rest > 0 && <button className="sw-pill sw-more" onClick={() => setMore(true)}>{t("swNMore", { n: rest })}</button>}</div>}
          {!more && keptNow.length > 0 && keptNow.length > FEW && <p className="hint">{t("swKeptList", { list: keptNow.slice(0, 20).join(", ") + (keptNow.length > 20 ? "…" : "") })}</p>}
          {more && (
            <div className="sw-value-list" role="group" aria-label={c.name}>
              {listed.map((v) => (
                <label key={String(v)} className="acheck"><input type="checkbox" checked={keptSet.has(String(v))} onChange={() => toggle(v)} />
                  <span className="sw-ellipsis" title={String(v)}>{String(v)}</span><span className="hint">{runsOf.get(String(v)) ?? ""}</span></label>
              ))}
              <button className="linklike" onClick={() => setMore(false)}>{t("swFewer")}</button>
            </div>
          )}
          {(full?.numeric ?? c.kind === "number") && (range ? (
            <div className="sw-row sw-range">
              <input type="number" value={range.lo} onChange={(e) => setRange({ ...range, lo: e.target.value })} aria-label={t("swRangeFrom")} placeholder={c.min !== undefined ? fmtValue(c.min) : ""} />
              <span>–</span>
              <input type="number" value={range.hi} onChange={(e) => setRange({ ...range, hi: e.target.value })} aria-label={t("swRangeTo")} placeholder={c.max !== undefined ? fmtValue(c.max) : ""} />
              <button className="btn outline sm" onClick={() => {
                const lo = range.lo === "" ? -Infinity : Number(range.lo), hi = range.hi === "" ? Infinity : Number(range.hi);
                const inside = values.filter((v) => typeof v === "number" && v >= lo && v <= hi);
                if (!inside.length) { notify(t("swRangeEmpty"), "error"); return; }
                set(inside); setRange(null);
              }}>{t("swApply")}</button>
            </div>
          ) : <button className="linklike" onClick={() => setRange({ lo: "", hi: "" })}>{t("swPickRange")}</button>)}
        </>
      )}
    </details>
  );
}

/** The new columns: a list (change, delete); the form opens only on + Add. */
function NewColumns({ study }: { study: Study }) {
  const t = useT();
  const st = useSweeps.getState();
  const [form, setForm] = useState<{ i: number; d: Derived } | "new" | null>(null);
  const derived = study.question.derived;
  return (
    <details className="sw-fold" open>
      <summary><b>{t("swNewColumns")}</b> <span className="hint">{derived.length}</span></summary>
      {derived.map((d, i) => (form && form !== "new" && form.i === i ? null : (
        <div key={d.name} className="sw-derived">
          <b className="sw-ellipsis" title={d.name}>ƒ {d.name}</b>
          <span className="hint sw-ellipsis" dir="ltr" title={d.kind === "row" ? d.expr : `${d.op}(${d.column})`}>{d.kind === "row" ? d.expr : `${d.op}(${d.column})`}</span>
          <button className="iconbtn sm" aria-label={t("swEditColumn", { n: d.name })} title={t("swEditColumn", { n: d.name })} onClick={() => setForm({ i, d })}><Icon.Edit width={13} height={13} /></button>
          <button className="iconbtn sm" aria-label={t("swRemove")} title={t("swRemove")} onClick={() => st.removeDerived(i)}><Icon.X width={13} height={13} /></button>
        </div>
      )))}
      {form ? <DerivedEditor key={form === "new" ? "new" : form.i} study={study} edit={form === "new" ? undefined : form} onDone={() => setForm(null)} />
        : <button className="btn outline" onClick={() => setForm("new")}><Icon.Plus width={14} height={14} /> {t("swAdd")}</button>}
    </details>
  );
}

/** The columns that tell nothing (one value in every run, or empty): "not used" in one click. */
function NothingBox({ study }: { study: Study }) {
  const t = useT();
  const st = useSweeps.getState();
  const removed = new Set(study.question.removed);
  const nothing = study.columns.filter(tellsNothing).filter((c) => c.role !== "ignore" && !removed.has(c.name));
  if (!nothing.length) return null;
  return (
    <div className="sw-hide-box">
      <b>{t("swHideNothing")}</b>
      <span className="hint">{t("swCleanNothing", { n: nothing.length })} {nothing.map((c) => c.name).join(", ")}</span>
      <button className="btn outline" onClick={() => nothing.forEach((c) => st.setRole(c.name, "ignore"))}>{t("swNothingUnused", { n: nothing.length })}</button>
    </div>
  );
}

/** Save: the template as a JSON file to share (and kept in the templates); Load: one from a file. */
async function saveTemplateFile(t: TFn, study: Study) {
  const p = await pickPath({ mode: "save", title: t("swSaveTemplate"), exts: [".json"], defaultName: study.name.replace(/\.[^.]+$/, "") + "_template.json" });
  if (!p) return;
  const name = (p.split(/[\\/]/).pop() ?? "template").replace(/\.json$/i, "");
  try {
    await useSweeps.getState().saveTemplate(name);
    const r = await sweepApi.exportTemplate(name, p);
    notify(t("swSaved", { path: r.path }));
  } catch (e) { notifyError(e); }
}
async function loadTemplateFile(t: TFn) {
  const p = await pickPath({ mode: "open", title: t("swLoadTemplate"), exts: [".json"] });
  if (!p) return;
  try {
    const st = useSweeps.getState();
    const name = await st.importTemplate(p);
    const r = st.applyTemplate(name);
    if (r) notify(templateSummary(t, r), r.skippedFormulas.length || r.newColumns.length ? "info" : "info", 12000);
  } catch (e) { notifyError(e); }
}

export function RolesCenter({ study }: { study: Study }) {
  const t = useT();
  const st = useSweeps.getState();
  const removed = new Set(study.question.removed);
  const cols = study.columns;
  const check = new Set(study.toCheck ?? []);
  const sm = study.summary;
  const [tplOpen, setTplOpen] = useState(false);
  // a column taken out in the old "clean" step shows as not used; any other role brings it back
  const roleOf = (c: StudyColumn): Role => (removed.has(c.name) ? "ignore" : c.role);
  const choose = (c: StudyColumn, r: Choice) => {
    if (removed.has(c.name)) st.setRemoved([...removed].filter((x) => x !== c.name));
    const role: Role = r === "ident" ? (c.guessRole === "recording" || c.paths ? "recording" : "id") : r;
    st.setRole(c.name, role);
  };
  const changed = cols.some((c) => c.role !== c.guessRole);
  const runs = useMemo(() => (sm.rowsAll !== undefined && sm.rowsAll !== sm.rows
    ? t("swNOfM", { n: sm.rows.toLocaleString(), of: sm.rowsAll.toLocaleString() }) : sm.rows), [sm, t]);
  return (
    <>
      <div className="sw-toolrow" role="toolbar" aria-label={t("swStepColumns")}>
        <button className="btn outline" disabled={!study.history.past.length} onClick={st.undo} title={`${t("undo")} (Ctrl+Z)`}><Icon.Undo width={14} height={14} /> {t("undo")}</button>
        <button className="btn outline" disabled={!study.history.future.length} onClick={st.redo} title={`${t("redo")} (Ctrl+Y)`}><Icon.Redo width={14} height={14} /> {t("redo")}</button>
        <span className="spacer" />
        <button className="btn outline" disabled={!changed} onClick={st.resetRoles}>{t("swResetGuessed")}</button>
        <span className="sw-menu-wrap">
          <button className="btn outline" aria-expanded={tplOpen} onClick={() => setTplOpen(!tplOpen)}>{t("swTemplate")} ▾</button>
          {tplOpen && (
            <span className="sw-menu" role="menu" onMouseLeave={() => setTplOpen(false)}>
              <button role="menuitem" onClick={() => { setTplOpen(false); saveTemplateFile(t, study); }}>{t("swSaveTemplateFile")}</button>
              <button role="menuitem" onClick={() => { setTplOpen(false); loadTemplateFile(t); }}>{t("swLoadTemplate")}</button>
            </span>
          )}
        </span>
      </div>
      <div className="sw-shape sw-shape-bar">
        <Stat label={t("swRuns")} value={runs} />
        <Stat label={t("swSets")} value={sm.sets} />
        <Stat label={t("swCombos")} value={sm.combos} />
        <Stat label={t("swMissing")} value={sm.missing} warn={sm.missing > 0} />
        <Stat label={t("swFailed")} value={sm.failedRuns} warn={sm.failedRuns > 0} />
      </div>
      {check.size > 0 && <p className="hint sw-check-note">{t("swToCheck", { n: check.size })}</p>}
      <div className="sw-table-wrap">
        <table className="sw-table sw-roles sw-sticky-first">
          <thead><tr><th>{t("swColumn")}</th>{ROLE_ORDER.map(({ r, key, tip }) => <th key={r} className={`sw-th-${r === "ident" ? "id" : r}`} title={t(tip)}>{t(key)}</th>)}
            <th>{t("swKind")}</th><th>{t("swValuesShort")}</th></tr></thead>
          <tbody>{cols.map((c) => {
            const role = roleOf(c), ch = choiceOf(role);
            return (
              <tr key={c.name} className={`${role === "ignore" ? "sw-unused" : ""}${check.has(c.name) ? " sw-to-check" : ""}`}>
                <td className="sw-col-name" title={c.name}><span className="sw-ellipsis">{c.name}</span>{c.role !== c.guessRole && <span className="sw-changed"> · {t("swYourChoice")}</span>}</td>
                {ROLE_ORDER.map(({ r }) => (
                  <td key={r} className="sw-radio">
                    <input type="radio" name={`role-${c.name}`} checked={ch === r} aria-label={`${c.name}: ${r}`} title={t(ROLE_ORDER.find((x) => x.r === r)!.key)} onChange={() => choose(c, r)} />
                    {r === "ident" && ch === "ident" && (
                      <select className="sw-ident-kind" value={role} aria-label={t("swIdentKind")} onChange={(e) => st.setRole(c.name, e.target.value as Role)}>
                        <option value="id">{t("swRoleId")}</option><option value="recording">{t("swRoleRecording")}</option>
                      </select>
                    )}
                  </td>
                ))}
                <td className="hint">{c.kind === "number" ? t("swKindNumber") : t("swKindText")}</td>
                <td className="hint">{c.values && c.values.length <= 6 ? c.values.join(", ")
                  : `${t("swDistinct", { n: c.distinct })}${c.min !== undefined && c.max !== undefined ? ` · ${fmtValue(c.min)} – ${fmtValue(c.max)}` : ""}`}
                  {tellsNothing(c) ? <span className="sw-warn-txt"> · {t("swTellsNothing")}</span> : null}</td>
              </tr>
            );
          })}</tbody>
        </table>
      </div>
    </>
  );
}
