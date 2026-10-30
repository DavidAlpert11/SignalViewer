/* The Sweeps area (areas.ts): a results table - one row per run, parameters and scenario columns
   first, outputs last - and the question asked of it.

   This file is layout only. The pieces, each its own file:
     QuestionPanel / ColumnsPanel   the left side (the question; the columns and their roles)
     PlotToolbar + ParallelPlot     the plot (+ AxisMenu, an axis's menu)
     SetsTable                      the parameter sets, best first
     SetDetail                      one set on the right: why it fails, its runs
   State: sweeps/state.ts. Styles: ./sweeps.css (its own file, to restyle the area alone). */
import { useMemo, useState } from "react";
import { pickPath } from "../../store";
import { useT } from "../../i18n";
import { Icon } from "../../icons";
import { sweepApi } from "../../sweeps/api";
import { useSweeps, useStudy, type Study } from "../../sweeps/state";
import { colLabel, modeColumns, scaleOf, shownAxes } from "../../sweeps/view";
import { keptMask } from "../../sweeps/filters";
import AxisMenu from "./AxisMenu";
import ColumnsPanel from "./ColumnsPanel";
import ParallelPlot from "./ParallelPlot";
import PlotToolbar from "./PlotToolbar";
import QuestionPanel from "./QuestionPanel";
import SetDetail from "./SetDetail";
import SetsTable from "./SetsTable";
import "./sweeps.css";

const TABLE_EXTS = [".csv", ".tsv", ".txt", ".parquet", ".pq", ".xlsx", ".xls"];

async function openTable(title: string) {
  const p = await pickPath({ mode: "open", title, exts: TABLE_EXTS });
  if (p) await useSweeps.getState().open(p);
}

/** The whole area: its bar (the app's second row) and what is under it (the third). */
export default function SweepsScreen() {
  const study = useStudy();
  return <><SweepsBar />{study ? <StudyView study={study} /> : <SweepsWelcome />}</>;
}

function SweepsBar() {
  const t = useT();
  const studies = useSweeps((s) => s.studies);
  const active = useSweeps((s) => s.active);
  const study = studies[active];
  const [note, setNote] = useState("");
  const exportRerun = async () => {
    const p = await pickPath({ mode: "save", title: t("swExportRerun"), exts: [".csv"], defaultName: "rerun.csv" });
    if (!p) return;
    try { const r = await useSweeps.getState().exportRerun(p); setNote(t("swExported", { n: r.rows, path: r.path })); }
    catch (e) { setNote((e as Error).message); }
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

function SweepsWelcome() {
  const t = useT();
  const busy = useSweeps((s) => s.busy);
  const error = useSweeps((s) => s.error);
  const example = async () => { const { path } = await sweepApi.example(); await useSweeps.getState().open(path); };
  return (
    <div className="sw-welcome">
      <div className="welcome-card">
        <h1>{t("swWelcomeTitle")}</h1>
        <p className="tagline">{t("swWelcomeTagline")}</p>
        <p>{t("swWelcomeHint")}</p>
        <div className="sw-welcome-actions">
          <button className="btn primary" disabled={busy} onClick={() => openTable(t("swOpenTable"))}><Icon.Open /> {t("swOpenTable")}</button>
          <button className="btn outline" disabled={busy} onClick={example}>{t("swTryExample")}</button>
        </div>
        {busy && <p className="hint">{t("swReading")}</p>}
        {error && <p className="sw-error" role="alert">{error}</p>}
      </div>
    </div>
  );
}

function StudyView({ study }: { study: Study }) {
  const t = useT();
  const st = useSweeps.getState();
  const [side, setSide] = useState<"question" | "columns">("question");
  const [menu, setMenu] = useState<{ name: string; at: DOMRect } | null>(null);
  const v = study.view;
  const { cols, n } = useMemo(() => modeColumns(study), [study]);
  const axes = shownAxes(study);
  const scale = useMemo(() => (name: string) => scaleOf(study, name, cols.get(name)), [study, cols]);
  const shown = useMemo(() => { const m = keptMask(cols, v.filters, n); let k = 0; for (let i = 0; i < n; i++) k += m[i]; return k; }, [cols, v.filters, n]);
  // the open set drawn thick: its line, or every run of it
  const highlight = useMemo(() => {
    if (v.pinned === null || !n) return null;
    const h = new Uint8Array(n);
    if (v.mode === "sets") h[v.pinned] = 1;
    else { const s = cols.get("#set")?.values; if (s) for (let i = 0; i < n; i++) if (s[i] === v.pinned) h[i] = 1; }
    return h;
  }, [v.pinned, v.mode, cols, n]);
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
        {study.answer ? (
          <>
            <PlotToolbar study={study} shown={shown} total={n} />
            {study.answer.runs?.sampled && v.mode === "runs" && <p className="hint">{t("swSampled", { n: study.answer.runs.n.toLocaleString(), of: study.answer.runs.total.toLocaleString() })}</p>}
            {axes.length ? (
              <ParallelPlot cols={cols} n={n} axes={axes} scaleOf={scale} reversed={v.reversed} colorBy={v.colorBy && cols.has(v.colorBy) ? v.colorBy : null}
                filters={v.filters} highlight={highlight} labelOf={(a) => colLabel(t, study, a)}
                onPick={(r) => st.setView({ pinned: v.mode === "sets" ? r : (cols.get("#set")?.values[r] ?? null) })}
                onFilter={(name, f) => st.setFilter(name, f)} onAxisMenu={(name, at) => setMenu({ name, at })} />
            ) : <p className="empty-note">{t("swNoAxes")}</p>}
            <SetsTable study={study} />
          </>
        ) : <p className="empty-note">{study.evalError || t("swReading")}</p>}
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
