/* C7: the study's navigator (plan §4.3 / §4.6 A, mock-up sweeps.html) - the left column of the area: the study's
   name; Set up (its four parts, ✓ each); Together (with two systems or more); Tables - every table open in the area
   (a click opens it in the four steps), a table's merged parts, and the study file's tables with their rounds
   (from /api/sweeps/study/tables, polled with the loop: a round's file opens like any table, *new* marked); Add
   table and Merge. It replaced the Data step's table list (one list of tables). */
import { useEffect, useMemo, useState } from "react";
import { pickPath } from "../../store";
import { useT } from "../../i18n";
import { Icon } from "../../icons";
import { recipeFiles, useSweeps, type Study } from "../../sweeps/state";
import { setupDone } from "../../sweeps/setup";
import { setupFromOpenTable } from "../../sweeps/studyStore";
import { studyApi, type StudyTables } from "../../sweeps/studyApi";
import { TABLE_EXTS } from "../../sweeps/studyFile";
import { notifyError } from "../../sweeps/notify";
import { MergeBox, exportTable } from "./RawStep";

const baseName = (p: string) => p.replace(/[\\/]+$/, "").split(/[\\/]/).pop() ?? p;
const stem = (n: string) => n.replace(/\.(svstudy\.json|svsweep|[^.]+)$/, "");
/** the open table read from this file (a tab's own file, or one of its tables'), or -1 */
const openIndex = (studies: Study[], file: string) =>
  studies.findIndex((s) => s.path === file || s.tables.some((tb) => recipeFiles(tb.recipe).includes(file)));

type FileTable = StudyTables["tables"][number];

export default function Navigator() {
  const t = useT();
  const studies = useSweeps((s) => s.studies);
  const active = useSweeps((s) => s.active);
  const part = useSweeps((s) => s.part);
  const common = useSweeps((s) => s.common);
  const study = studies[active];
  const tables = useStudyFileTables(common.open ? common.path : "", common.loopProgress?.round ?? common.demoProgress?.round ?? 0,
    common.loopProgress?.runs.done ?? common.demoProgress?.runs.done ?? 0);
  const name = common.open ? (common.study?.name || stem(baseName(common.path)) || t("nsTitle")) : study ? stem(study.name) : "";
  const done = common.open && common.study ? setupDone(common.study, !!common.guess) : null;
  const systems = common.study?.tables.length ?? 0;
  const tableOn = part !== "setup" && part !== "together" && part !== "about";
  const show = (p: "setup" | "together" | "about") => useSweeps.setState({ part: p });
  const openSetup = async () => {
    if (common.open) { show("setup"); return; }
    try { if (await setupFromOpenTable()) show("setup"); } catch (e) { notifyError(e); }
  };
  // the study file's tables: each matched to the open table read from one of its files (its rounds shown under
  // it), the others listed on their own
  const byTab = new Map<number, FileTable>();
  const alone: FileTable[] = [];
  for (const ft of tables?.tables ?? []) {
    const files = ft.rounds.flatMap((r) => r.files.map((f) => f.path));
    const i = files.map((f) => openIndex(studies, f)).find((k) => k >= 0) ?? -1;
    if (i >= 0 && !byTab.has(i)) byTab.set(i, ft); else alone.push(ft);
  }
  return (
    <aside className="side sw-nav" aria-label={t("nvTitle")}>
      <div className="panel-head sw-nav-head">
        <div className="sw-nav-name"><span className="eyebrow">{t("nvStudy")}</span><h2 className="ph-title" title={name}>{name}</h2></div>
      </div>
      <div className="sw-nav-tree">
        {(common.open || study) && <>
          <div className="sw-nav-sec"><span className="eyebrow">{t("suTitle")}</span>
            {done && <span className={`sw-nav-done${done.every(Boolean) ? " ok" : ""}`}>✓ {done.filter(Boolean).length}/4</span>}</div>
          <button className={`sw-nav-item${part === "setup" ? " on" : ""}`} data-nav="setup" aria-current={part === "setup" ? "true" : undefined}
            onClick={() => { void openSetup(); }}>
            <Icon.Settings width={14} height={14} /><span className="sw-ellipsis">{t("nvSetupItem")}</span>
          </button>
        </>}
        {common.open && common.demo && (
          <button className={`sw-nav-item${part === "about" ? " on" : ""}`} data-nav="about" aria-current={part === "about" ? "true" : undefined}
            onClick={() => show("about")}>
            <span aria-hidden="true">ⓘ</span><span className="sw-ellipsis">{t("nvAbout")}</span>
          </button>
        )}
        {common.open && systems >= 2 && <>
          <div className="sw-nav-sec"><span className="eyebrow">{t("nvTogether")}</span></div>
          <button className={`sw-nav-item${part === "together" ? " on" : ""}`} data-nav="together" aria-current={part === "together" ? "true" : undefined}
            onClick={() => show("together")}>
            <span aria-hidden="true">★</span><span className="sw-ellipsis">{t("cpTitle")}</span>
            <span className="sw-nav-n">{(common.study?.shared ?? []).map((x) => x.name).slice(0, 3).join(" ")}</span>
          </button>
        </>}
        <section className="sw-tables" aria-label={t("nvTables")}>
          <div className="sw-nav-sec"><span className="eyebrow">{t("nvTables")}</span><span className="eyebrow sw-nav-n">{t("nvRuns")}</span></div>
          {studies.map((s, i) => (
            <TabItem key={s.tableId} s={s} i={i} on={tableOn && i === active} fileTable={byTab.get(i)} />
          ))}
          {alone.map((ft) => <FileTableItem key={ft.id} ft={ft} />)}
          {study && <AddTable />}
        </section>
        {study && study.tables.length > 1 && <MergeBox study={study} />}
      </div>
    </aside>
  );
}

/** The study file's tables and rounds, asked again when the loop moves on (a round done, runs finished). */
function useStudyFileTables(path: string, round: number, runs: number): StudyTables | null {
  const [r, setR] = useState<StudyTables | null>(null);
  useEffect(() => {
    if (!path) { setR(null); return; }
    let live = true;
    studyApi.tables(path).then((x) => live && setR(x)).catch(() => live && setR(null));
    return () => { live = false; };
  }, [path, round, runs]);
  return r;
}

/** An open table: a click shows it in the four steps; with merged parts, they are listed under it. */
function TabItem({ s, i, on, fileTable }: { s: Study; i: number; on: boolean; fileTable?: FileTable }) {
  const t = useT();
  const rounds = (fileTable?.rounds ?? []).filter((r) => r.round !== null);
  const one = on && s.tables.length === 1 ? s.tables[0] : null;          // its tables listed below when there are several
  return (
    <>
      <div className="sw-nav-row">
        <button className={`sw-nav-item sw-nav-table${on ? " on" : ""}`} data-nav="table" aria-current={on ? "true" : undefined} title={s.name}
          onClick={() => useSweeps.setState({ active: i, part: "table" })}>
          <span className="sw-nav-dot" aria-hidden="true" /><span className="sw-ellipsis">{s.name}</span>
          <span className="sw-nav-n">{s.rows.toLocaleString()}</span>
        </button>
        {one && <button className="iconbtn sm" title={t("swExportDataHint")} aria-label={`${t("swExportDataHint")}: ${one.name}`}
          onClick={() => { void exportTable(t, s, one); }}><Icon.Download width={14} height={14} /></button>}
      </div>
      {on && s.tables.length > 1 && (
        <ul className="sw-table-list sw-nav-sub">{s.tables.map((tb, j) => <PartItem key={tb.id} s={s} j={j} />)}</ul>
      )}
      {rounds.map((r) => <RoundItem key={r.round} r={r} />)}
    </>
  );
}

/** One of an open table's tables (read from a file or merged): tick to merge, a click works on it, export, close. */
function PartItem({ s, j }: { s: Study; j: number }) {
  const t = useT();
  const st = useSweeps.getState();
  const tb = s.tables[j];
  const picked = s.picked.includes(tb.id);
  return (
    <li className={`sw-table-item${j === s.use ? " used on" : ""}`}>
      <input type="checkbox" checked={picked} aria-label={t("swTickToMerge", { n: tb.name })} title={t("swTickToMerge", { n: tb.name })}
        onChange={() => st.setPicked(picked ? s.picked.filter((x) => x !== tb.id) : [...s.picked, tb.id])} />
      <button className="sw-table-name" title={tb.name} aria-current={j === s.use ? "true" : undefined}
        onClick={() => { st.useTable(j); st.setShown(j); useSweeps.setState({ part: "table" }); }}>
        {tb.merged && <Icon.Merge width={13} height={13} />}<span className="sw-ellipsis">{tb.name}</span>
      </button>
      <span className="sw-nav-n sw-table-rows">{tb.opened.rows.toLocaleString()}</span>
      <button className="iconbtn sm" title={t("swExportDataHint")} aria-label={`${t("swExportDataHint")}: ${tb.name}`}
        onClick={() => { void exportTable(t, s, tb); }}><Icon.Download width={14} height={14} /></button>
      <button className="iconbtn sm" title={t("swCloseTableN", { n: tb.name })} aria-label={t("swCloseTableN", { n: tb.name })}
        onClick={() => st.closeTable(j)}><Icon.X width={13} height={13} /></button>
    </li>
  );
}

/** A table of the study file not open in the area: a click opens its first file. */
function FileTableItem({ ft }: { ft: FileTable }) {
  const first = ft.rounds[0]?.files[0]?.path ?? ft.paths[0];
  const rounds = ft.rounds.filter((r) => r.round !== null);
  return (
    <>
      <button className="sw-nav-item sw-nav-table" data-nav="file-table" title={ft.name} disabled={!first} onClick={() => first && openFile(first)}>
        <span className="sw-nav-dot off" aria-hidden="true" /><span className="sw-ellipsis">{ft.name}</span>
        <span className="sw-nav-n">{ft.rows.toLocaleString()}</span>
      </button>
      {rounds.map((r) => <RoundItem key={r.round} r={r} />)}
    </>
  );
}

/** A round of a table (`round_<k>` in its files' paths): a click opens its results in the four steps. */
function RoundItem({ r }: { r: FileTable["rounds"][number] }) {
  const t = useT();
  const studies = useSweeps((s) => s.studies);
  const active = useSweeps((s) => s.active);
  const part = useSweeps((s) => s.part);
  const file = r.files.find((f) => f.rows !== null)?.path ?? "";
  const i = useMemo(() => (file ? openIndex(studies, file) : -1), [studies, file]);
  const on = i >= 0 && i === active && part !== "setup" && part !== "together" && part !== "about";
  return (
    <button className={`sw-nav-item sw-nav-round${on ? " on" : ""}`} data-nav="round" data-round={r.round ?? ""} disabled={!file}
      aria-current={on ? "true" : undefined} title={file} onClick={() => openFile(file)}>
      <span className="sw-nav-tick" aria-hidden="true">└</span><span className="sw-ellipsis">{t("nvRound", { n: r.round ?? 0 })}</span>
      {r.new && <span className="pill on sw-nav-new">{t("nvNew")}</span>}
      <span className="sw-nav-n">{r.rows.toLocaleString()}</span>
    </button>
  );
}

/** A file shown in the four steps: the open table read from it, or opened now. */
function openFile(file: string) {
  const st = useSweeps.getState();
  const i = openIndex(st.studies, file);
  if (i >= 0) { useSweeps.setState({ active: i, part: "table" }); return; }
  void st.open(file).then(() => useSweeps.setState({ part: "table" })).catch(notifyError);
}

function AddTable() {
  const t = useT();
  const add = async () => {
    const p = await pickPath({ mode: "open", title: t("swAddTable"), exts: TABLE_EXTS });
    if (p) useSweeps.getState().addTable(p).catch(notifyError);
  };
  return <button className="btn ghost sm sw-nav-add" onClick={() => { void add(); }}><Icon.Plus width={14} height={14} /> {t("swAddTable")}</button>;
}
