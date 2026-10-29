/* The Sweeps area (areas.ts): a results table - one row per run, parameters and scenario columns
   first, outputs last. Step 0: open the table, see each column's guessed role and scale, correct
   them, and see the shape of the study (sets, combinations, what is missing). */
import { pickPath } from "../../store";
import { useT, type TKey } from "../../i18n";
import { Icon } from "../../icons";
import { ROLES, SCALES, sweepApi, type Role, type SweepColumn } from "../../sweeps/api";
import { useSweeps, type Study } from "../../sweeps/state";

const ROLE_KEY: Record<Role, TKey> = { param: "swRoleParam", hold: "swRoleHold", output: "swRoleOutput", id: "swRoleId", ignore: "swRoleIgnore" };
const ROLE_HINT: Record<Role, TKey> = { param: "swRoleParamHint", hold: "swRoleHoldHint", output: "swRoleOutputHint", id: "swRoleIdHint", ignore: "swRoleIgnoreHint" };
const SCALE_KEY = { linear: "swScaleLinear", log: "swScaleLog", category: "swScaleCategory", ordinal: "swScaleOrdinal" } as const;
const TABLE_EXTS = [".csv", ".tsv", ".txt", ".parquet", ".pq", ".xlsx", ".xls"];

async function openTable(title: string) {
  const p = await pickPath({ mode: "open", title, exts: TABLE_EXTS });
  if (p) await useSweeps.getState().open(p);
}

/** The area's bar: its studies (one table each) and opening another. */
function SweepsBar() {
  const t = useT();
  const studies = useSweeps((s) => s.studies);
  const active = useSweeps((s) => s.active);
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
    </div>
  );
}

/** The whole area: its bar (the app's second row) and what is under it (the third). */
export default function SweepsScreen() {
  return <><SweepsBar /><SweepsArea /></>;
}

function SweepsArea() {
  const study = useSweeps((s) => s.studies[s.active]);
  return study ? <StudyView study={study} /> : <SweepsWelcome />;
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
  const s = study.summary;
  const error = useSweeps((st) => st.error);
  return (
    <div className="sw-main">
      <aside className="side sw-columns" aria-label={t("swColumns")}>
        <div className="side-head"><h2>{t("swColumns")}</h2><span className="hint">{study.columns.length}</span></div>
        <div className="sw-col-list">
          {ROLES.map((role) => {
            const cols = study.columns.filter((c) => c.role === role);
            if (!cols.length) return null;
            return (
              <section key={role} className={`sw-role sw-role-${role}`}>
                <h3 title={t(ROLE_HINT[role])}>{t(ROLE_KEY[role])} <span className="hint">· {cols.length}</span></h3>
                {cols.map((c) => <ColumnRow key={c.name} c={c} />)}
              </section>
            );
          })}
        </div>
      </aside>
      <main className="sw-stage">
        <div className="sw-summary">
          <Stat label={t("swRuns")} value={s.rows.toLocaleString()} />
          <Stat label={t("swSets")} value={s.sets.toLocaleString()} note={t("swSetsOf", { n: s.params.length })} />
          <Stat label={t("swCombos")} value={s.combos.toLocaleString()} note={t("swCombosOf", { n: s.holds.length })} />
          <Stat label={t("swMissing")} value={s.missing.toLocaleString()} warn={s.missing > 0} note={t("swMissingNote")} />
          <Stat label={t("swFailed")} value={s.failedRuns.toLocaleString()} warn={s.failedRuns > 0} note={t("swFailedNote")} />
        </div>
        {s.duplicates > 0 && <p className="sw-warn">{t("swDuplicates", { n: s.duplicates })}</p>}
        {error && <p className="sw-error" role="alert">{error}</p>}
        <p className="hint">{t("swReadIn", { s: study.seconds.toFixed(2), path: study.path })}</p>
        <div className="sw-head-wrap">
          <table className="sw-head">
            <thead><tr>{study.columns.map((c) => <th key={c.name} className={`sw-th-${c.role}`}>{c.name}</th>)}</tr></thead>
            <tbody>{study.head.map((row, i) => (
              <tr key={i}>{row.map((v, j) => <td key={j} className={study.columns[j].role === "ignore" ? "sw-dim" : ""}>{v === null ? "–" : String(v)}</td>)}</tr>
            ))}</tbody>
          </table>
        </div>
      </main>
    </div>
  );
}

function ColumnRow({ c }: { c: SweepColumn }) {
  const t = useT();
  const { setRole, setScale } = useSweeps.getState();
  const why = c.constant ? t("swConstant") : c.empty ? t("swEmpty") : c.kind === "text" ? t("swDistinct", { n: c.distinct })
    : c.min !== undefined ? `${fmt(c.min)} – ${fmt(c.max!)} · ${t("swDistinct", { n: c.distinct })}` : "";
  return (
    <div className="sw-col">
      <div className="sw-col-name" title={c.name}>{c.name}</div>
      <div className="sw-col-why">{why}</div>
      <div className="sw-col-pick">
        <select aria-label={t("swRoleOf", { c: c.name })} value={c.role} onChange={(e) => setRole(c.name, e.target.value as Role)}>
          {ROLES.map((r) => <option key={r} value={r}>{t(ROLE_KEY[r])}</option>)}
        </select>
        <select aria-label={t("swScaleOf", { c: c.name })} value={c.scale} onChange={(e) => setScale(c.name, e.target.value as SweepColumn["scale"])}>
          {SCALES.map((sc) => <option key={sc} value={sc} disabled={c.kind === "text" && (sc === "linear" || sc === "log")}>{t(SCALE_KEY[sc])}</option>)}
        </select>
      </div>
    </div>
  );
}

function Stat({ label, value, note, warn }: { label: string; value: string; note?: string; warn?: boolean }) {
  return (
    <div className={`sw-stat${warn ? " warn" : ""}`}>
      <div className="sw-stat-label">{label}</div>
      <div className="sw-stat-value">{value}</div>
      {note && <div className="sw-stat-note">{note}</div>}
    </div>
  );
}

const fmt = (v: number) => (Math.abs(v) >= 1e5 || (v !== 0 && Math.abs(v) < 1e-3) ? v.toExponential(2) : String(+v.toPrecision(4)));
