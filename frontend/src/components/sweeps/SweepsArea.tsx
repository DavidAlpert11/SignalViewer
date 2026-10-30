/* The Sweeps area (areas.ts): a results table - one row per run, parameters and scenario columns
   first, outputs last - and the question asked of it.

   This file is layout only. The pieces, each its own file:
     QuestionPanel / ColumnsPanel   the left side (the question; the columns and their roles)
     CenterTabs                     what the middle shows:
       PlotToolbar + ParallelPlot + SetsTable   the lines (+ AxisMenu) and the sets, best first
       EffectsView  which parameter matters      MapView      two parameters as a map
       ScatterView  any two columns as points    NextRunsView what to run next
       HealthView   missing, failed, odd runs    CompareView  two studies, same question
     SetDetail                      one set on the right: why it fails, its runs, its recordings
   State: sweeps/state.ts. Styles: ./sweeps.css (its own file, to restyle the area alone). */
import { useEffect, useMemo, useState } from "react";
import { pickPath } from "../../store";
import { useApp } from "../../store";
import { useT } from "../../i18n";
import { Icon } from "../../icons";
import { sweepApi } from "../../sweeps/api";
import { useSweeps, useStudy, wireQuestion, type Study } from "../../sweeps/state";
import { colLabel, scaleOf, scopedColumns, scopeKey, shownAxes } from "../../sweeps/view";
import { keptMask } from "../../sweeps/filters";
import { studyReport } from "../../sweeps/report";
import { fits } from "../../sweeps/state";
import { prompt } from "../Overlays";
import type { SavedStudy } from "../../sweeps/state";
import AxisMenu from "./AxisMenu";
import CenterTabs from "./CenterTabs";
import CompareView from "./CompareView";
import EffectsView from "./EffectsView";
import HealthView from "./HealthView";
import MapView from "./MapView";
import NextRunsView from "./NextRunsView";
import ScatterView from "./ScatterView";
import ColumnsPanel from "./ColumnsPanel";
import ParallelPlot from "./ParallelPlot";
import PlotToolbar from "./PlotToolbar";
import QuestionPanel from "./QuestionPanel";
import SetDetail from "./SetDetail";
import SetsTable from "./SetsTable";
import "./sweeps.css";

const TABLE_EXTS = [".csv", ".tsv", ".txt", ".parquet", ".pq", ".xlsx", ".xls"];
const STUDY_EXT = ".svsweep";

async function openTable(title: string) {
  const p = await pickPath({ mode: "open", title, exts: TABLE_EXTS });
  if (p) await useSweeps.getState().open(p);
}
async function openFolder(title: string) {
  const p = await pickPath({ mode: "folder", title });
  if (p) await useSweeps.getState().open(p);
}
async function openStudy(title: string): Promise<string> {
  const p = await pickPath({ mode: "open", title, exts: [STUDY_EXT] });
  if (!p) return "";
  try {
    const doc = JSON.parse((await sweepApi.loadText(p)).text) as SavedStudy;
    if (doc.kind !== "signalviewer-sweep") return "not a study";
    await useSweeps.getState().open(doc.path, doc);
    return "";
  } catch (e) { return (e as Error).message; }
}

/** The whole area: its bar (the app's second row) and what is under it (the third). */
export default function SweepsScreen() {
  const study = useStudy();
  return <><SweepsBar />{study ? <StudyView study={study} /> : <SweepsWelcome />}</>;
}

function SweepsBar() {
  const t = useT();
  const lang = useApp((s) => s.lang);
  const studies = useSweeps((s) => s.studies);
  const active = useSweeps((s) => s.active);
  const study = studies[active];
  const [note, setNote] = useState("");
  const say = (r: Promise<string>) => r.then(setNote).catch((e) => setNote((e as Error).message));
  const exportRerun = async () => {
    const p = await pickPath({ mode: "save", title: t("swExportRerun"), exts: [".csv"], defaultName: "rerun.csv" });
    if (!p) return;
    say(useSweeps.getState().exportRerun(p).then((r) => t("swExported", { n: r.rows, path: r.path })));
  };
  const saveStudy = async () => {
    const doc = useSweeps.getState().saved();
    if (!doc) return;
    if (!doc.path) { setNote(t("swCannotSaveRows")); return; }
    const p = await pickPath({ mode: "save", title: t("swSaveStudy"), exts: [STUDY_EXT], defaultName: study.name.replace(/\.[^.]+$/, "") + STUDY_EXT });
    if (p) say(sweepApi.saveText(p, JSON.stringify(doc, null, 1)).then((r) => t("swSaved", { path: r.path })));
  };
  const report = async () => {
    const p = await pickPath({ mode: "save", title: t("swReport"), exts: [".html"], defaultName: study.name.replace(/\.[^.]+$/, "") + "_report.html" });
    if (!p) return;
    const canvas = document.querySelector<HTMLCanvasElement>(".pp canvas");
    say(sweepApi.saveText(p, studyReport(t, study, canvas ? canvas.toDataURL("image/png") : null, lang)).then((r) => t("swSaved", { path: r.path })));
  };
  return (
    <div className="areabar" role="toolbar" aria-label={t("areaSweeps")}>
      <nav className="tabs-wrap">
        <div className="tabs" role="tablist">
          {studies.map((s, i) => (
            <div key={s.tableId} role="tab" tabIndex={0} aria-selected={i === active} className={`tab${i === active ? " active" : ""}`}
              onClick={() => useSweeps.setState({ active: i })} onKeyDown={(e) => { if (e.key === "Enter") useSweeps.setState({ active: i }); }}>
              <span>{s.name}</span>
              <span className="x" role="button" aria-label={t("swCloseStudy")} title={t("swCloseStudy")}
                onClick={(e) => { e.stopPropagation(); useSweeps.getState().close(i); }}><Icon.X width={12} height={12} /></span>
            </div>
          ))}
        </div>
      </nav>
      <button className="btn outline" onClick={() => openTable(t("swOpenTable"))}><Icon.Open /> {t("swOpenTable")}</button>
      <button className="iconbtn" aria-label={t("swOpenFolder")} title={t("swOpenFolder")} onClick={() => openFolder(t("swOpenFolder"))}><Icon.Folder /></button>
      <button className="iconbtn" aria-label={t("swOpenStudy")} title={t("swOpenStudy")} onClick={() => say(openStudy(t("swOpenStudy")))}><Icon.Open /></button>
      {study && <button className="iconbtn" aria-label={t("swSaveStudy")} title={t("swSaveStudy")} onClick={saveStudy}><Icon.Save /></button>}
      {study?.answer && <button className="iconbtn" aria-label={t("swReport")} title={t("swReport")} onClick={report}><Icon.Report /></button>}
      {study && <span className="sep" />}
      {study?.path && <button className="iconbtn" aria-label={t("swRefresh")} title={t("swRefresh")} onClick={() => useSweeps.getState().reload()}><Icon.Reload /></button>}
      {study?.path && <label className="acheck" title={t("swFollowHint")}><input type="checkbox" checked={study.view.follow}
        onChange={(e) => useSweeps.getState().setView({ follow: e.target.checked })} />{t("swFollow")}</label>}
      {study && <TemplatesMenu />}
      <div className="spacer" />
      {note && <span className="hint sw-note" title={note}>{note}</span>}
      {study && (
        <>
          <label className="acheck"><input type="checkbox" checked={study.view.onlyMissing}
            onChange={(e) => useSweeps.getState().setView({ onlyMissing: e.target.checked })} />{t("swOnlyMissing")}</label>
          <button className="btn primary" disabled={!study.view.rerun.length} onClick={exportRerun}>{t("swExportRerunN", { n: study.view.rerun.length })}</button>
        </>
      )}
    </div>
  );
}

/** Templates: apply one (those that fit this table's columns first), save this study as one, delete. */
function TemplatesMenu() {
  const t = useT();
  const study = useStudy()!;
  const templates = useSweeps((s) => s.templates);
  const st = useSweeps.getState();
  useEffect(() => { st.loadTemplates(); }, [st]);
  const ok = templates.filter((x) => fits(x, study.columns)), other = templates.filter((x) => !fits(x, study.columns));
  const act = async (v: string) => {
    if (v === "#save") {
      const name = await prompt(t("swSaveTemplate"), t("swTemplateName"), study.name.replace(/\.[^.]+$/, ""));
      if (name?.trim()) await st.saveTemplate(name.trim());
    } else if (v.startsWith("del:")) {
      st.deleteTemplate(v.slice(4));
    } else if (v) st.applyTemplate(v);
  };
  return (
    <select className="sw-templates" aria-label={t("swTemplates")} value="" onChange={(e) => act(e.target.value)}>
      <option value="">{t("swTemplates")}</option>
      <option value="#save">{t("swSaveTemplate")}</option>
      {ok.length > 0 && <optgroup label={t("swTemplatesFit")}>{ok.map((x) => <option key={x.name} value={x.name}>{x.name}</option>)}</optgroup>}
      {other.length > 0 && <optgroup label={t("swTemplatesOther")}>{other.map((x) => <option key={x.name} value={x.name}>{x.name}</option>)}</optgroup>}
      {templates.length > 0 && <optgroup label={t("swTemplatesDelete")}>{templates.map((x) => <option key={x.name} value={`del:${x.name}`}>× {x.name}</option>)}</optgroup>}
    </select>
  );
}

/* a few rows of the example table, to show what a results table looks like */
const SAMPLE: { name: string; role: "hold" | "param" | "output" | "ignore" }[] = [
  { name: "scenario_terrain", role: "hold" }, { name: "payload_kg", role: "param" }, { name: "scenario_wind_mps", role: "hold" },
  { name: "kp_roll", role: "param" }, { name: "range_m", role: "output" }, { name: "max_roll_deg", role: "output" }, { name: "sim_version", role: "ignore" },
];
const SAMPLE_ROWS = [
  ["flat", "0.5", "0", "0.10", "1907.2", "11.78", "4.2.1"],
  ["flat", "0.5", "4", "0.10", "1871.5", "13.02", "4.2.1"],
  ["hills", "1.0", "8", "0.18", "1631.9", "19.40", "4.2.1"],
  ["urban", "2.0", "8", "0.22", "1180.3", "27.55", "4.2.1"],
];

function SweepsWelcome() {
  const t = useT();
  const busy = useSweeps((s) => s.busy);
  const error = useSweeps((s) => s.error);
  const [note, setNote] = useState("");
  const example = async () => { const { path } = await sweepApi.example(); await useSweeps.getState().open(path); };
  // the example's second sweep - finer where the first looked good - merged into it
  const merged = async () => {
    const { path } = await sweepApi.example();
    await useSweeps.getState().open(path);
    const r = await useSweeps.getState().merge(path.replace(/sweep_payload\.csv$/, "sweep_payload_refine.csv"), "new");
    setNote(t("swMerged", { added: r.added, replaced: r.replaced }));
  };
  return (
    <div className="sw-welcome">
      <div className="welcome-card sw-welcome-card">
        <h1>{t("swWelcomeTitle")}</h1>
        <p className="tagline">{t("swWelcomeTagline")}</p>
        <div className="sw-sample" aria-label={t("swSampleTitle")}>
          <div className="sw-sample-head"><b>{t("swSampleTitle")}</b><span className="hint">{t("swSampleHint")}</span></div>
          <div className="sw-sample-wrap">
            <table className="sw-table">
              <thead><tr>{SAMPLE.map((c) => <th key={c.name} className={`sw-th-${c.role}`}>{c.name}</th>)}</tr></thead>
              <tbody>{SAMPLE_ROWS.map((r, i) => <tr key={i}>{r.map((v, j) => <td key={j} className={SAMPLE[j].role === "ignore" ? "sw-dim" : ""}>{v}</td>)}</tr>)}
                <tr><td colSpan={SAMPLE.length} className="hint">…</td></tr></tbody>
            </table>
          </div>
          <div className="sw-sample-legend">
            <span className="sw-th-param">■ {t("swRoleParam")}</span><span className="hint">{t("swWhatWeChoose")}</span>
            <span className="sw-th-hold">■ {t("swRoleHold")}</span><span className="hint">{t("swWhatWeDont")}</span>
            <span className="sw-th-output">■ {t("swRoleOutput")}</span><span className="hint">{t("swSampleOutputs")}</span>
          </div>
          <p className="hint">{t("swSampleNote")}</p>
        </div>
        <div className="sw-welcome-actions">
          <button className="btn primary" disabled={busy} onClick={() => openTable(t("swOpenTable"))}><Icon.Open /> {t("swOpenTable")}</button>
          <button className="btn outline" disabled={busy} onClick={() => openFolder(t("swOpenFolder"))}><Icon.Folder /> {t("swOpenFolder")}</button>
          <button className="btn outline" disabled={busy} onClick={() => openStudy(t("swOpenStudy")).then(setNote)}>{t("swOpenStudy")}</button>
          <button className="btn outline" disabled={busy} onClick={example}>{t("swTryExample")}</button>
          <button className="btn outline" disabled={busy} onClick={merged}>{t("swTryMerged")}</button>
        </div>
        {busy && <p className="hint">{t("swReading")}</p>}
        {(error || note) && <p className="sw-error" role="alert">{error || note}</p>}
      </div>
    </div>
  );
}

function StudyView({ study }: { study: Study }) {
  const t = useT();
  const st = useSweeps.getState();
  const side = study.view.left;
  const setSide = (left: "question" | "columns") => st.setView({ left });
  // follow the file: is it newer than what is on screen? (every few seconds, only this study)
  useEffect(() => {
    if (!study.path) return;
    const h = window.setInterval(() => useSweeps.getState().checkChanged(), 3000);
    return () => window.clearInterval(h);
  }, [study.tableId, study.path]);
  const noParams = !study.columns.some((c) => c.role === "param");
  const [menu, setMenu] = useState<{ name: string; at: DOMRect } | null>(null);
  const v = study.view;
  const { cols, n, index } = useMemo(() => scopedColumns(study), [study]);
  const axes = shownAxes(study);
  const scale = useMemo(() => (name: string) => scaleOf(study, name, cols.get(name)), [study, cols]);
  const shown = useMemo(() => { const m = keptMask(cols, v.filters, n); let k = 0; for (let i = 0; i < n; i++) k += m[i]; return k; }, [cols, v.filters, n]);
  // the open set drawn thick: its line, or every run of it
  const setOfRow = (r: number) => (v.mode === "sets" ? (index ? index[r] : r) : (cols.get("#set")?.values[r] ?? -1));
  const highlight = useMemo(() => {
    if (v.pinned === null || !n) return null;
    const h = new Uint8Array(n);
    for (let i = 0; i < n; i++) if (setOfRow(i) === v.pinned) h[i] = 1;
    return h;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [v.pinned, v.mode, cols, n, index]);
  // what is selected now: the lines every filter keeps - as parameter sets, and as runs (table rows)
  const selection = () => {
    const m = keptMask(cols, v.filters, n);
    const sets = new Set<number>(), rows: number[] = [];
    const rowCol = cols.get("#row")?.values;
    for (let i = 0; i < n; i++) if (m[i]) { sets.add(setOfRow(i)); if (rowCol) rows.push(rowCol[i]); }
    return { sets: [...sets], rows };
  };
  const exportShown = async () => {
    const p = await pickPath({ mode: "save", title: t("swExportShown"), exts: [".csv"], defaultName: study.name.replace(/\.[^.]+$/, "") + "_selected.csv" });
    if (!p) return;
    const sel = selection();
    try {
      const r = await sweepApi.exportRows(study.tableId, wireQuestion(study), v.mode === "runs" ? { rows: sel.rows } : { sets: sel.sets }, p);
      setNote(t("swExported", { n: r.rows, path: r.path }));
    } catch (e) { setNote((e as Error).message); }
  };
  const [note, setNote] = useState("");
  const menuCol = menu ? cols.get(menu.name) : undefined;
  return (
    <div className={`sw-study${v.pinned !== null ? " with-detail" : ""}`}>
      <aside className="side sw-left" aria-label={t("swQuestion")}>
        <div className="sw-tabs" role="tablist">
          <button role="tab" aria-selected={side === "question"} className={side === "question" ? "on" : ""} onClick={() => setSide("question")}>{t("swQuestion")}</button>
          <button role="tab" aria-selected={side === "columns"} className={side === "columns" ? "on" : ""} onClick={() => setSide("columns")}>{t("swColumns")} <span className="hint">{study.columns.length}</span></button>
        </div>
        <div className="sw-left-body">
          {side === "question" ? <QuestionPanel study={study} onColumns={() => setSide("columns")} /> : <ColumnsPanel study={study} />}
        </div>
      </aside>
      <main className="sw-center">
        {study.changed && (
          <div className="sw-banner" role="status">{t("swFileChanged")}
            <button className="btn primary" onClick={() => st.reload()}>{t("swRefresh")}</button>
            <button className="btn outline" onClick={() => { st.setView({ follow: true }); st.reload(); }}>{t("swFollowFromNow")}</button></div>
        )}
        {study.offer && (
          <div className="sw-banner" role="status">{t("swTemplateFits", { n: study.offer })}
            <button className="btn primary" onClick={() => st.applyTemplate(study.offer!)}>{t("swApply")}</button>
            <button className="iconbtn" aria-label={t("swDismiss")} onClick={() => useSweeps.setState((x) => ({ studies: x.studies.map((y) => (y.tableId === study.tableId ? { ...y, offer: null } : y)) }))}>×</button></div>
        )}
        {noParams && (
          <div className="sw-banner" role="status">{t("swChooseParams")}
            {side !== "columns" && <button className="btn primary" onClick={() => setSide("columns")}>{t("swColumns")}</button>}</div>
        )}
        <CenterTabs study={study} studies={useSweeps.getState().studies.length} />
        {study.answer && v.center === "effects" && <EffectsView study={study} />}
        {study.answer && v.center === "map" && <MapView study={study} />}
        {study.answer && v.center === "scatter" && <ScatterView study={study} />}
        {study.answer && v.center === "next" && <NextRunsView study={study} />}
        {v.center === "health" && <HealthView study={study} />}
        {study.answer && v.center === "compare" && <CompareView study={study} />}
        {v.center === "lines" && (study.answer ? (
          <>
            <PlotToolbar study={study} shown={shown} total={n}
              onKeep={() => st.narrow("keep", selection().sets, scopeKey(study))}
              onExclude={() => st.narrow("exclude", selection().sets, scopeKey(study))}
              onExport={exportShown} />
            {note && <p className="hint">{note}</p>}
            {study.answer.runs?.sampled && v.mode === "runs" && <p className="hint">{t("swSampled", { n: study.answer.runs.n.toLocaleString(), of: study.answer.runs.total.toLocaleString() })}</p>}
            {axes.length ? (
              <ParallelPlot cols={cols} n={n} axes={axes} scaleOf={scale} reversed={v.reversed} colorBy={v.colorBy && cols.has(v.colorBy) ? v.colorBy : null}
                filters={v.filters} highlight={highlight} labelOf={(a) => colLabel(t, study, a)}
                onPick={(r) => st.setView({ pinned: setOfRow(r) })}
                onFilter={(name, f) => st.setFilter(name, f)} onAxisMenu={(name, at) => setMenu({ name, at })} />
            ) : <p className="empty-note">{t("swNoAxes")}</p>}
            <SetsTable study={study} />
          </>
        ) : <p className="empty-note">{study.evalError || t("swReading")}</p>)}
        {!study.answer && v.center !== "lines" && v.center !== "health" && <p className="empty-note">{study.evalError || t("swReading")}</p>}
      </main>
      {v.pinned !== null && study.answer && <SetDetail study={study} set={v.pinned} />}
      {menu && menuCol && (
        <AxisMenu col={menuCol} label={colLabel(t, study, menu.name)} at={menu.at} scale={scale(menu.name)} reversed={!!v.reversed[menu.name]}
          filter={v.filters[menu.name]} colouring={v.colorBy === menu.name}
          onScale={(s) => st.setScale(menu.name, s)}
          onReverse={() => st.setView({ reversed: { ...v.reversed, [menu.name]: !v.reversed[menu.name] } })}
          onColour={() => st.setView({ colorBy: menu.name })}
          onHide={() => { st.toggleAxis(menu.name, false); setMenu(null); }}
          onFilter={(f) => st.setFilter(menu.name, f)} onClose={() => setMenu(null)} />
      )}
    </div>
  );
}
