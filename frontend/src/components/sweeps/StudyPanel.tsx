/* W14 / W15 / W17: Sweeps → Common parameters - one parameter set for many systems.
   Left: the study (tables, their columns' roles, constraints, goal; the shared parameters; the ranking; the
   search space). Middle: the ranked values (pass / fail per table, score, local choice, the deciding scenario,
   why a value fails), the shared values' space, the next runs and the launcher. State: sweeps/studyStore.ts;
   the study file is the one definition (docs/dev/study.schema.json). The demo (W18) is DemoView. */
import { useEffect, useMemo, useState } from "react";
import { fmtNum, useT, type TFn } from "../../i18n";
import { pickPath, useApp } from "../../store";
import { Icon } from "../../icons";
import { confirmAsk } from "../Overlays";
import { studyApi } from "../../sweeps/studyApi";
import {
  closePanel, editStudy, isUnsaved, launcherCommand, openStudyFile, redoStudy, reqOf, saveStudyAs, sendToLauncher,
  suggestNext, undoStudy, useStudyPanel,
} from "../../sweeps/studyStore";
import type { CommonRow, Role, Study, StudyTable } from "../../sweeps/studyTypes";
import SpaceView, { type SpacePoint } from "./SpaceView";
import DemoView from "./DemoView";

const ROLES: Role[] = ["shared", "scenario", "local", "output", "ignore"];
const STUDY_EXT = ".svstudy.json";
const TABLE_EXTS = [".csv", ".tsv", ".txt", ".parquet", ".pq", ".xlsx", ".xls"];
let confirmedThisSession = false;                // W17: the launcher command is shown once per session

const say = (text: string, kind: "info" | "error" = "info") => useApp.getState().toast({ kind, text, ms: kind === "error" ? 12000 : 6000 });
const fmtVals = (v: Record<string, number | string> | null | undefined, lang: "en" | "he") =>
  v ? Object.entries(v).map(([k, x]) => `${k} = ${typeof x === "number" ? fmtNum(x, lang) : x}`).join(", ") : "";

export async function saveStudyDialog(t: TFn, as = false): Promise<boolean> {
  const st = useStudyPanel.getState();
  let path = st.path;
  if (as || !path || st.demo) {
    const p = await pickPath({ mode: "save", title: t("cpSaveTitle"), exts: [STUDY_EXT], defaultName: (st.study?.name || "study") + STUDY_EXT });
    if (!p) return false;
    path = p;
  }
  try { await saveStudyAs(path); say(t("savedTo" as never, { path })); return true; }
  catch (e) { say((e as Error).message, "error"); return false; }
}

export async function openStudyDialog(t: TFn): Promise<void> {
  const p = await pickPath({ mode: "open", title: t("cpOpen"), exts: [STUDY_EXT, ".json"] });
  if (p) await openStudyFile(p);
}

export default function StudyPanel() {
  const t = useT();
  const s = useStudyPanel();
  if (!s.open) return null;
  if (s.demo) return <DemoView />;
  const study = s.study;
  const pending = (study?.history ?? []).flatMap((r) => r.proposals.filter((p) => p.state === "pending" || p.state === "submitted").map(() => r.round));
  const lastRound = study?.history?.length ? study.history[study.history.length - 1].round : 0;
  return (
    <div className="cp-panel" data-testid="study-panel">
      <div className="cp-head">
        <h2>{t("cpTitle")}{study?.name ? `: ${study.name}` : ""}</h2>
        <span className="cp-state">{pending.length ? t("cpPending", { n: pending.length, k: lastRound }) : t("cpNoRounds")}
          {isUnsaved(s) && <> · <b>{t("cpUnsaved")}</b></>}</span>
        <span className="spacer" />
        <button className="iconbtn" disabled={!s.past.length} onClick={undoStudy} aria-label={t("undo")} title={`${t("undo")} (Ctrl+Z)`}><Icon.Undo /></button>
        <button className="iconbtn" disabled={!s.future.length} onClick={redoStudy} aria-label={t("redo")} title={`${t("redo")} (Ctrl+Y)`}><Icon.Redo /></button>
        <button className="btn outline" onClick={() => saveStudyDialog(t)}><Icon.Save /> {t("cpSave")}</button>
        <button className="iconbtn" onClick={closePanel} aria-label={t("cpClose")} title={t("cpClose")}><Icon.X /></button>
      </div>
      <div className="cp-body">
        <aside className="cp-side">{study && <StudyEditor study={study} />}</aside>
        <main className="cp-main">
          {s.error && <p className="sw-error" role="alert">{s.error}</p>}
          {study && study.tables.length < 2 ? <p className="empty-note">{t("cpEmpty")}</p> : <Results />}
        </main>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ the study (left) */

function StudyEditor({ study }: { study: Study }) {
  const t = useT();
  const [open, setOpen] = useState<string | null>(study.tables[0]?.id ?? null);
  const [columns, setColumns] = useState<Record<string, string[]>>({});
  const [proposed, setProposed] = useState<{ table: string; column: string; name: string }[]>([]);
  const path = useStudyPanel((s) => s.path);
  const folder = path ? path.replace(/[\\/][^\\/]*$/, "") : "";
  const abs = (p: string) => (/^([a-zA-Z]:)?[\\/]/.test(p) || !folder ? p : `${folder}/${p}`);
  // the columns of each table (its first file) and the names proposed to pair across tables
  const key = study.tables.map((x) => `${x.id}:${x.paths.join("|")}`).join(";");
  useEffect(() => {
    if (!study.tables.length) return;
    studyApi.mapping(Object.fromEntries(study.tables.map((x) => [x.id, x.paths.map(abs)])))
      .then((r) => { setColumns(r.columns); setProposed(r.mapping.filter((m) => !(study.tables.find((x) => x.id === m.table)?.rename ?? {})[m.column])); })
      .catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, folder]);
  const edit = (id: string, f: (x: StudyTable) => void) => editStudy((s) => { const x = s.tables.find((y) => y.id === id); if (x) f(x); return s; });
  const addTable = async () => {
    const p = await pickPath({ mode: "open", title: t("cpAddTableTitle"), exts: TABLE_EXTS });
    if (!p) return;
    const name = p.replace(/^.*[\\/]/, "").replace(/\.[^.]+$/, "");
    const rel = folder && p.startsWith(folder + "/") ? p.slice(folder.length + 1) : p;
    editStudy((s) => {
      const id = String.fromCharCode(65 + s.tables.length);
      s.tables.push({ id, name, paths: [rel], roles: {}, constraints: [], objective: { expr: "", sense: "min" }, aggregate: "worst" });
      return s;
    });
  };
  const shared = (study.shared ?? []).map((x) => x.name);
  return (
    <div className="cp-editor">
      <label className="afield"><span>{t("cpStudyName")}</span>
        <input value={study.name ?? ""} onChange={(e) => editStudy((s) => ({ ...s, name: e.target.value }))} /></label>
      <h3>{t("cpTables")}</h3>
      {proposed.length > 0 && (
        <div className="cp-mapping" role="status"><b>{t("cpMapping")}</b>
          <ul>{proposed.map((m) => <li key={`${m.table}-${m.column}`}><bdi>{m.table}: {m.column} → {m.name}</bdi></li>)}</ul>
          <button className="btn sm" onClick={() => editStudy((s) => { for (const m of proposed) { const x = s.tables.find((y) => y.id === m.table); if (x) x.rename = { ...(x.rename ?? {}), [m.column]: m.name }; } return s; })}>
            {t("cpMappingUse")}</button>
        </div>
      )}
      {study.tables.map((tb) => {
        const cols = (columns[tb.id] ?? []).map((c) => tb.rename?.[c] ?? c);
        return (
          <section key={tb.id} className={`cp-table${open === tb.id ? " open" : ""}`}>
            <button className="cp-table-head" aria-expanded={open === tb.id} onClick={() => setOpen(open === tb.id ? null : tb.id)}>
              <Icon.Chevron width={12} height={12} /> <b>{tb.id}</b> <span>{tb.name}</span>
            </button>
            {open === tb.id && <div className="cp-table-body">
              <label className="afield"><span>{t("cpTableName")}</span><input value={tb.name ?? ""} onChange={(e) => edit(tb.id, (x) => { x.name = e.target.value; })} /></label>
              <label className="afield"><span>{t("cpPaths")}</span><input dir="ltr" value={tb.paths.join("; ")}
                onChange={(e) => edit(tb.id, (x) => { x.paths = e.target.value.split(";").map((v) => v.trim()).filter(Boolean); })} /></label>
              <div className="cp-row"><span>{t("cpObjective")}</span>
                <input dir="ltr" className="cp-expr" value={tb.objective?.expr ?? ""} aria-label={t("cpObjective")}
                  onChange={(e) => edit(tb.id, (x) => { x.objective = { expr: e.target.value, sense: x.objective?.sense ?? "min" }; })} />
                <select value={tb.objective?.sense ?? "min"} aria-label={t("cpObjective")} onChange={(e) => edit(tb.id, (x) => { x.objective = { expr: x.objective?.expr ?? "", sense: e.target.value as "min" | "max" }; })}>
                  <option value="min">{t("cpMin")}</option><option value="max">{t("cpMax")}</option></select></div>
              <label className="afield"><span>{t("cpConstraints")}</span>
                <textarea dir="ltr" rows={2} value={(tb.constraints ?? []).join("\n")}
                  onChange={(e) => edit(tb.id, (x) => { x.constraints = e.target.value.split("\n").map((v) => v.trim()).filter(Boolean); })} /></label>
              <div className="cp-row"><span>{t("cpAggregate")}</span>
                <select value={tb.aggregate ?? "worst"} onChange={(e) => edit(tb.id, (x) => { x.aggregate = e.target.value as "worst" | "mean"; })}>
                  <option value="worst">{t("cpWorst")}</option><option value="mean">{t("cpMean")}</option></select></div>
              {cols.length > 0 && <details className="cp-roles"><summary>{t("cpRoles")}</summary>
                {cols.map((c) => (
                  <div key={c} className="cp-row"><bdi className="cp-col">{c}</bdi>
                    <select value={shared.includes(c) ? "shared" : (tb.roles?.[c] ?? "")} aria-label={c}
                      onChange={(e) => editStudy((s) => {
                        const r = e.target.value as Role;
                        if (r === "shared") s.shared = [...(s.shared ?? []).filter((x) => x.name !== c), { name: c }];
                        else s.shared = (s.shared ?? []).filter((x) => x.name !== c);
                        const x = s.tables.find((y) => y.id === tb.id)!;
                        x.roles = { ...(x.roles ?? {}) };
                        if (r !== "shared") x.roles[c] = r; else delete x.roles[c];
                        return s;
                      })}>
                      <option value="" disabled>–</option>
                      {ROLES.map((r) => <option key={r} value={r}>{t(`cpRole_${r}` as never)}</option>)}
                    </select></div>
                ))}</details>}
              <label className="afield"><span>{t("cpDrop")}</span>
                <input dir="ltr" placeholder="wind = 10" value={Object.entries(tb.drop ?? {}).map(([k, v]) => `${k} = ${v.join(", ")}`).join("; ")}
                  onChange={(e) => edit(tb.id, (x) => {
                    const d: Record<string, (number | string)[]> = {};
                    for (const part of e.target.value.split(";")) {
                      const [k, v] = part.split("=");
                      if (k?.trim() && v?.trim()) d[k.trim()] = v.split(",").map((y) => y.trim()).filter(Boolean).map((y) => (Number.isFinite(Number(y)) ? Number(y) : y));
                    }
                    x.drop = d;
                  })} /></label>
              <button className="linkbtn danger" onClick={() => editStudy((s) => ({ ...s, tables: s.tables.filter((x) => x.id !== tb.id) }))}>{t("cpRemoveTable")}</button>
            </div>}
          </section>
        );
      })}
      <button className="btn sm" onClick={addTable}><Icon.Plus /> {t("cpAddTable")}</button>
      <h3>{t("cpShared")}</h3>
      {(study.shared ?? []).map((p) => {
        const sp = study.search?.params?.[p.name] ?? {};
        const num = (v: string) => (v.trim() === "" ? null : Number(v));
        const setSp = (k: "min" | "max" | "step", v: string) => editStudy((s) => {
          s.search = { params: { ...(s.search?.params ?? {}) }, constraints: s.search?.constraints ?? [] };
          s.search.params[p.name] = { ...(s.search.params[p.name] ?? {}), [k]: num(v) };
          return s;
        });
        return (
          <div key={p.name} className="cp-shared">
            <b><bdi>{p.name}</bdi></b>
            <label>{t("cpTolerance")} <input type="number" min={0} step="any" value={p.tolerance ?? 0}
              onChange={(e) => editStudy((s) => { const x = s.shared!.find((y) => y.name === p.name)!; x.tolerance = Math.max(0, Number(e.target.value) || 0); return s; })} /></label>
            <span className="cp-search" title={t("cpSearch")}>
              {(["min", "max", "step"] as const).map((k) => <label key={k}>{k} <input type="number" step="any" value={sp[k] ?? ""} onChange={(e) => setSp(k, e.target.value)} /></label>)}
            </span>
          </div>
        );
      })}
      <label className="afield"><span>{t("cpSearchConstraints")}</span>
        <input dir="ltr" placeholder="Kp * Ki < 3" value={(study.search?.constraints ?? []).join("; ")}
          onChange={(e) => editStudy((s) => { s.search = { params: s.search?.params ?? {}, constraints: e.target.value.split(";").map((v) => v.trim()).filter(Boolean) }; return s; })} /></label>
      <div className="cp-row"><span>{t("cpCombine")}</span>
        <select value={study.combine?.mode ?? "auto"} onChange={(e) => editStudy((s) => ({ ...s, combine: { ...(s.combine ?? {}), mode: e.target.value as "auto" } }))}>
          {(["auto", "minworst", "pareto"] as const).map((m) => <option key={m} value={m}>{t(`cpCombine_${m}`)}</option>)}</select></div>
      <div className="cp-row"><span>{t("cpBatch")}</span>
        <input type="number" min={1} max={500} value={study.next?.batch ?? 20}
          onChange={(e) => editStudy((s) => ({ ...s, next: { ...(s.next ?? {}), batch: Math.max(1, Math.round(Number(e.target.value) || 20)) } }))} /></div>
    </div>
  );
}

/* ------------------------------------------------------------------ the answer (middle) */

function Results() {
  const t = useT();
  const lang = useApp((s) => s.lang);
  const r = useStudyPanel((s) => s.result);
  const busy = useStudyPanel((s) => s.busy);
  const next = useStudyPanel((s) => s.next);
  const pinned = useStudyPanel((s) => s.pinned);
  const status = useStudyPanel((s) => s.status);
  const path = useStudyPanel((s) => s.path);
  const study = useStudyPanel((s) => s.study);
  const points = useMemo<SpacePoint[]>(() => [
    ...(r?.rows ?? []).map((x) => ({ values: x.values, feasible: x.feasible })),
    ...(next?.candidates ?? []).map((c) => ({ values: c.values, proposed: c.reason })),
  ], [r, next]);
  if (!r) return <p className="empty-note">{busy ? t("swReading") : ""}</p>;
  const best = r.rows.find((x) => x.feasible) ?? null;
  const suggest = async () => {
    if (!path || isUnsaved()) { if (!(await saveStudyDialog(t))) { say(t("cpSaveFirst"), "error"); return; } }
    try {
      const n = await suggestNext();
      say(n.exhausted ? t("cpExhausted") : t("cpNextDone", { k: n.round, c: n.counts.candidates, r: n.counts.runs, f: n.files.join(", ") }), n.exhausted ? "error" : "info");
    } catch (e) { say((e as Error).message, "error"); }
  };
  const send = async () => {
    if (!path || isUnsaved()) { if (!(await saveStudyDialog(t))) return; }
    try {
      const cmd = await launcherCommand();
      if (!confirmedThisSession) {
        if (!(await confirmAsk(t("cpSendTitle"), t("cpSendText", { cwd: cmd.cwd, n: cmd.submitted, cmd: cmd.command.join(" ") }), t("cpSendOk")))) return;
        confirmedThisSession = true;
      }
      await sendToLauncher();
    } catch (e) { say((e as Error).message, "error"); }
  };
  const exportCsv = async () => {
    const p = await pickPath({ mode: "save", title: t("cpExport"), exts: [".csv"], defaultName: (study?.name || "ranking") + ".csv" });
    if (!p) return;
    try { const x = await studyApi.exportCsv(reqOf(), p); say(t("cpExported", { n: x.rows, path: x.path })); }
    catch (e) { say((e as Error).message, "error"); }
  };
  return (
    <div className="cp-results" data-shot="study" data-settled={busy ? "0" : "1"}>
      <div className="cp-results-head">
        <b className="cp-count">{t("cpRanked", { feasible: r.counts.feasible, values: r.counts.values })}</b>
        <span className="hint">{r.mode === "minworst" ? t("cpModeMinworst") : t("cpModePareto")}</span>
        <span className="spacer" />
        <button className="btn outline" onClick={exportCsv}><Icon.Download /> {t("cpExport")}</button>
        <button className="btn outline" onClick={send} title={study?.launcher?.submit?.length ? undefined : t("cpNoLauncher")} disabled={!study?.launcher?.submit?.length}>
          <Icon.Send /> {t("cpSend")}</button>
        <button className="btn primary" onClick={suggest}><Icon.Plus /> {t("cpSuggest")}</button>
      </div>
      {status && (
        <p className="cp-run-states" role="status" data-finished={status.finished ? "1" : "0"}>
          {t("cpRunsCount", { k: status.round, done: status.counts.done, sub: status.counts.submitted, failed: status.counts.failed, missing: status.counts.missing })}</p>
      )}
      <div className="cp-results-body">
        <div className="cp-rank-wrap">
          <table className="sw-table cp-rank">
            <thead><tr><th>#</th>{r.shared.map((c) => <th key={c}><bdi>{c}</bdi></th>)}{r.tables.map((x) => <th key={x.id} title={`${x.name}: ${x.sense === "min" ? t("cpMin") : t("cpMax")} ${x.objective}`}>{x.id}</th>)}</tr></thead>
            <tbody>
              {(next?.candidates ?? []).map((c, i) => (
                <tr key={`n${i}`} className="cp-proposed" title={c.note}><td>◇</td>{r.shared.map((k) => <td key={k}>{fmtNum(Number(c.values[k]), lang)}</td>)}
                  <td colSpan={r.tables.length}>{t("cpProposed")}: {t(`cpReason_${c.reason}` as never)}</td></tr>
              ))}
              {r.rows.map((row, i) => (
                <tr key={i} className={`${row.feasible ? "cp-ok" : "cp-no"}${row.pareto ? " cp-pareto" : ""}${pinned === i ? " on" : ""}`}
                  onClick={() => useStudyPanel.setState({ pinned: pinned === i ? null : i })} data-rank={row.rank ?? ""}>
                  <td>{row.rank ?? ""}{row.pareto && r.mode === "pareto" ? "★" : ""}</td>
                  {r.shared.map((k) => <td key={k}>{fmtNum(Number(row.values[k]), lang)}</td>)}
                  {row.tables.map((x) => <td key={x.table} className={`cp-cell ${x.status}`} title={cellTitle(t, x, lang)}>
                    {x.status === "pass" ? fmtNum(x.score, lang, 4) : x.status === "not_run" ? t("cpNotRun") : t("cpFails")}</td>)}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="cp-aside">
          <SpaceView axes={r.shared} points={points} best={best?.values} />
          {pinned !== null && r.rows[pinned] && <RunsOf row={r.rows[pinned]} />}
        </div>
      </div>
    </div>
  );
}

function cellTitle(t: TFn, x: CommonRow["tables"][number], lang: "en" | "he"): string {
  if (x.status === "pass") return [x.local && fmtVals(x.local, lang), x.worst && t("cpWorstAt", { s: fmtVals(x.worst, lang) })].filter(Boolean).join(" · ");
  if (!x.failed) return "";
  const why = x.failed.constraint === "not run" ? t("cpNotRun") : x.failed.by !== null ? t("cpFailedBy", { c: x.failed.constraint, by: fmtNum(x.failed.by, lang) }) : x.failed.constraint;
  return x.failed.scenario ? `${why} ${t("cpAt", { s: fmtVals(x.failed.scenario, lang) })}` : why;
}

/** The runs of the opened value, table by table - the deciding scenario's run marked. */
function RunsOf({ row }: { row: CommonRow }) {
  const t = useT();
  const lang = useApp((s) => s.lang);
  const [runs, setRuns] = useState<{ table: string; columns: string[]; rows: (number | string | null)[][] }[]>([]);
  useEffect(() => {
    let live = true;
    Promise.all(row.tables.filter((x) => x.runs.length).map((x) => studyApi.runs(reqOf(), x.table, x.runs)))
      .then((r) => { if (live) setRuns(r); }).catch(() => {});
    return () => { live = false; };
  }, [row]);
  return (
    <section className="cp-runs" aria-label={t("cpRunsOf", { v: fmtVals(row.values, lang) })}>
      <h3>{t("cpRunsOf", { v: fmtVals(row.values, lang) })}</h3>
      {runs.map((r) => {
        const tr = row.tables.find((x) => x.table === r.table);
        const mark = (vals: (number | string | null)[]) => !!tr?.worst && Object.entries(tr.worst).every(([k, v]) => vals[r.columns.indexOf(k)] === v)
          && (!tr.local || Object.entries(tr.local).every(([k, v]) => vals[r.columns.indexOf(k)] === v));
        return (
          <div key={r.table} className="cp-runs-table">
            <b>{r.table}</b> <span className={`cp-cell ${tr?.status}`}>{tr ? cellTitle(t, tr, lang) : ""}</span>
            <div className="cp-rank-wrap"><table className="sw-table">
              <thead><tr>{r.columns.map((c) => <th key={c}><bdi>{c}</bdi></th>)}</tr></thead>
              <tbody>{r.rows.map((v, i) => <tr key={i} className={mark(v) ? "cp-deciding" : ""}>{v.map((x, j) => <td key={j}>{typeof x === "number" ? fmtNum(x, lang) : x}</td>)}</tr>)}</tbody>
            </table></div>
          </div>
        );
      })}
    </section>
  );
}
