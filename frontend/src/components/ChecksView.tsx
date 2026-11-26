/* D7: one *Checks* view for any file (plan §3.6) - the user's limits, the file's data quality and, for a
   log, its health check, as tinted cards under one verdict - plus F1 *The file* (its structure) and F3 the
   run's parameters for files that are not flight logs. Shown in the Log panel's place. */
import { useEffect, useMemo, useState } from "react";
import { api, type ChecksFile, type FileStructure, type HealthReport, type LimitResult, type ParamDiff, type RunOverview, type RunParam } from "../api";
import { actions, useApp } from "../store";
import { fmtNum, useT, type Lang, type TFn } from "../i18n";
import { Icon } from "../icons";
import { runLabels } from "../names";
import { signalLines } from "../quality";
import HealthRow from "./HealthRow";

const fmtTime = (t: number, lang: "en" | "he") => fmtNum(t, lang, Math.abs(t) >= 1000 ? 7 : 5);
const fmtVal = (v: number | string, lang: "en" | "he") => (typeof v === "number" ? fmtNum(v, lang, 7) : v);
const QUALITY_CARDS = 8;

type LimitItem = { id: string; lo: number | null; hi: number | null; scale: number; offset: number; tOffset: number };

/** The limits set on this run's signals in any tab (one entry per signal: the first plot that sets them). */
function useLimitItems(runId: string): LimitItem[] {
  const tabs = useApp((s) => s.ws.tabs);
  return useMemo(() => {
    const seen = new Map<string, LimitItem>();
    for (const tab of tabs) for (const p of tab.plots) for (const s of p.signals) {
      if (!s.sig.startsWith(`${runId}/`) || !s.limits || (s.limits.lo == null && s.limits.hi == null) || seen.has(s.sig)) continue;
      seen.set(s.sig, { id: s.sig, lo: s.limits.lo ?? null, hi: s.limits.hi ?? null, scale: s.scale, offset: s.offset, tOffset: s.tOffset ?? 0 });
    }
    return [...seen.values()];
  }, [tabs, runId]);
}

/** RV2: the checks file kept with the recording (`<name>.checks.json` or the folder's `checks.json`), run on it -
 *  the window's verdict is CI's. null while asked; {file: null} when there is none. */
export function useChecksFile(runId: string | undefined, key: unknown): ChecksFile | null {
  const [res, setRes] = useState<ChecksFile | null>(null);
  useEffect(() => {
    if (!runId) { setRes({ file: null, results: [] }); return; }
    let gone = false;
    setRes(null);
    api.runChecksFile(runId).then((r) => { if (!gone) setRes(r); }).catch(() => { if (!gone) setRes({ file: null, results: [] }); });
    return () => { gone = true; };
  }, [runId, key]);
  return res;
}
/** How many checks of a checks file failed / passed (an error or a skip counts as neither). */
export const checksFileCounts = (cf: ChecksFile | null) => ({
  bad: cf?.results.filter((r) => r.status === "fail").length ?? 0, ok: cf?.results.filter((r) => r.status === "pass").length ?? 0 });

/** An automatic flag (svcore/overview.py: stuck, saturated, gap, spike) in words - the strip's tooltip and the
 *  Checks list say it the same way. */
export const flagText = (t: TFn, lang: Lang, f: RunOverview["flags"][0]) => t(`ovFlag_${f.kind}` as "ovFlag_stuck", {
  signal: f.signal, a: fmtNum(f.a, lang, 5), b: fmtNum(f.b, lang, 5), s: fmtNum(f.b - f.a, lang, 3), v: f.value !== undefined ? fmtNum(f.value, lang, 5) : "" });
const FLAG_CARDS = 8;

/** The Checks tab: a verdict, then Limits · Data quality · Health check (logs only). */
export function Checks({ runId, isLog, runKey }: { runId: string; isLog: boolean; runKey: string }) {
  const t = useT();
  const lang = useApp((s) => s.lang);
  const q = useApp((s) => s.quality[runId]);
  const items = useLimitItems(runId);
  const [lim, setLim] = useState<Record<string, LimitResult> | null>(null);
  // CC12: every file has an automatic research (the "any data" profile); a log adds its health check
  const [health, setHealth] = useState<HealthReport | null | "none">(null);
  // review 2026-11-25 (C1): the automatic flags the strip shows (Motor3 flat at its limit) are findings too - a
  // verdict that left them out read "no problems" above a saturated motor
  const [flags, setFlags] = useState<RunOverview["flags"] | null>(null);

  useEffect(() => {
    if (q) return;
    api.runQuality(runId).then((r) => useApp.setState((s) => ({ quality: { ...s.quality, [runId]: r } }))).catch(() => {});
  }, [runId, q]);
  useEffect(() => {
    let gone = false;
    if (!items.length) { setLim({}); return; }
    api.limits(items, null, null).then((r) => { if (!gone) setLim(r.results); }).catch(() => { if (!gone) setLim({}); });
    return () => { gone = true; };
  }, [items, runKey]);
  useEffect(() => {
    let gone = false;
    api.runHealth(runId).then((r) => { if (!gone) setHealth(r); }).catch(() => { if (!gone) setHealth("none"); });
    return () => { gone = true; };
  }, [runId, runKey]);

  useEffect(() => {
    let gone = false;
    setFlags(null);
    api.overview(runId).then((r) => { if (!gone) setFlags(r.flags); }).catch(() => { if (!gone) setFlags([]); });
    return () => { gone = true; };
  }, [runId, runKey]);

  const cfile = useChecksFile(runId, runKey);
  const cf = checksFileCounts(cfile);
  const fileName = (p: string) => p.slice(Math.max(p.lastIndexOf("/"), p.lastIndexOf("\\")) + 1);
  const name = (id: string) => id.slice(id.indexOf("/") + 1);
  const range = (it: LimitItem) => `${it.lo ?? "−∞"} … ${it.hi ?? "∞"}`;
  // CC7: a failed limit in plain words - "above 85", "below 2", "outside 2 … 85" - not "outside −∞ … 85"
  const limitBad = (n: string, lo: number | null, hi: number | null, k: number, first: number | null) => {
    const at = first === null ? "–" : fmtTime(first, lang);
    return lo == null ? t("chkLimitBadHi", { name: n, hi: fmtVal(hi!, lang), n: k, t: at })
      : hi == null ? t("chkLimitBadLo", { name: n, lo: fmtVal(lo, lang), n: k, t: at })
      : t("chkLimitBad", { name: n, range: `${fmtVal(lo, lang)} … ${fmtVal(hi, lang)}`, n: k, t: at });
  };
  const limRows = items.map((it) => ({ it, r: lim?.[it.id] })).filter((x) => x.r);
  const badLim = limRows.filter((x) => !x.r!.pass).length;
  const qIssues = q ? q.signals.filter((s) => s.issues.length) : [];
  const hRep = health !== null && health !== "none" ? health : null;
  const bad = badLim + (hRep?.errors ?? 0) + cf.bad;
  const warn = qIssues.length + (hRep?.warnings ?? 0);
  const ok = limRows.length - badLim + cf.ok + (q && !qIssues.length ? 1 : 0) + (hRep ? hRep.findings.filter((f) => f.level === "ok").length : 0);
  const nFlags = flags?.length ?? 0;
  const ready = lim !== null && !!q && health !== null && cfile !== null && flags !== null;
  // green only means "checked and fine": with no limits, no checks file and no health check nothing was judged -
  // the verdict says so in grey (data quality alone is not a pass)
  const judged = items.length > 0 || !!hRep || cf.bad + cf.ok > 0;
  const tone = bad ? "error" : warn || nFlags ? "warning" : judged ? "ok" : "none";
  const parts = ([[bad, "chkBad"], [warn, "chkWarn"], [nFlags, nFlags === 1 ? "chkFlagsOne" : "chkFlags"], [ok, "chkFine"]] as const)
    .filter(([n]) => n > 0).map(([n, k]) => t(k, { n }));
  const verdict = tone === "ok" ? t("chkVerdictOk") : tone === "none" ? t("chkVerdictNone")
    : [...parts, ...(judged ? [] : [t("chkNotJudged")])].join(" · ");

  // review R1 (round 2): where the file has a judge of its own (a log's health check, a checks file) its findings come
  // first - the automatic flags (often a log's spikes, symptoms of what the health check found) after them, three
  // shown; a file with neither keeps them where they are its only findings
  const flagsLast = !!hRep || !!cfile?.file;
  const flagCards = flagsLast ? 3 : FLAG_CARDS;
  const flagsSec = nFlags > 0 && (
        <section className="checks-sec" aria-label={t("chkFlagsTitle")}>
          <h3 className="eyebrow" title={`${t("ovFlagsHint")}\n${t("chkFlagsNote")}`}>{t("chkFlagsTitle")}</h3>
          <ul className="card-list">
            {flags!.slice(0, flagCards).map((f, k) => (
              <li key={k} className="card warn" data-flag={f.kind} data-flag-signal={f.signal}>
                <p className="card-title">{flagText(t, lang, f)}</p>
                <div className="card-next"><button className="pchange span" title={t("healthSpan")}
                  onClick={() => actions.showSpan(f.a, f.b)}>
                  <bdi dir="ltr">{f.b > f.a ? `${fmtTime(f.a, lang)}–${fmtTime(f.b, lang)}` : fmtTime(f.a, lang)}</bdi></button></div>
              </li>
            ))}
            {nFlags > flagCards && <li className="card-meta">{t("chkFlagsMore", { n: nFlags - flagCards })}</li>}
          </ul>
        </section>
  );

  return (
    <div className="checks" data-checks-ready={ready ? "1" : "0"} data-bad={bad} data-warn={warn} data-flags={nFlags} data-judged={judged ? "1" : "0"} data-flags-last={flagsLast ? "1" : "0"}>
      {ready && <p className={`health-sum ${tone}`} data-testid="checks-verdict" data-tone={tone}>{verdict}</p>}

      {cfile?.file && (
        <section className="checks-sec" aria-label={t("chkFile")} data-checks-file={fileName(cfile.file)}>
          <h3 className="eyebrow">{t("chkFile")}</h3>
          {/* CC3: the file's name; what it is (the CLI's verdict) in the tooltip */}
          <p className="card-meta" title={`${cfile.file}\n${t("chkFileFrom", { file: fileName(cfile.file) })}`}>{fileName(cfile.file)}</p>
          {cfile.error ? <p className="empty-state"><span>{t("chkFileBroken", { file: fileName(cfile.file), why: cfile.error })}</span></p> : (
            <ul className="card-list">
              {cfile.results.map((r, k) => (
                <li key={k} className={`card ${r.status === "pass" ? "ok" : r.status === "fail" ? "bad" : "warn"}`} data-check={r.name} data-status={r.status}>
                  <p className="card-title">{r.status === "pass" ? t("chkFilePass", { name: r.name })
                    : r.status === "fail" && r.kind ? r.name
                    : r.status === "fail" ? limitBad(r.name, r.lo ?? null, r.hi ?? null, r.violations ?? 0, r.first ?? null)
                    : t("chkFileNotRun", { name: r.name, why: r.message ?? "" })}</p>
                  {/* CC11: a requirement says what it measured (overshoot 11 % of the step… at 1.9 s) */}
                  {r.kind && r.message && r.status !== "error" && r.status !== "skipped" && <p className="card-meta">{r.message.replace(/^[^:]*: /, "")}</p>}
                  {r.status === "fail" && (r.worstT ?? r.first) !== undefined && (
                    <div className="card-next"><button className="pchange span" onClick={() => actions.goToTime((r.worstT ?? r.first)!)} title={t("healthSpan")}>
                      {fmtTime((r.worstT ?? r.first)!, lang)}</button></div>
                  )}
                </li>
              ))}
            </ul>
          )}
        </section>
      )}

      <section className="checks-sec" aria-label={t("chkLimits")}>
        <h3 className="eyebrow">{t("chkLimits")}</h3>
        {!items.length ? (
          <p className="empty-state" title={t("chkNoLimitsHow")}><span>{t("chkNoLimits")}</span></p>
        ) : (
          <ul className="card-list">
            {limRows.map(({ it, r }) => (
              <li key={it.id} className={`card ${r!.pass ? "ok" : "bad"}`} data-limit={name(it.id)}>
                <p className="card-title">{r!.pass ? t("chkLimitOk", { name: name(it.id), range: range(it) })
                  : limitBad(name(it.id), it.lo, it.hi, r!.spans.length || r!.violations, r!.first)}</p>
                {!r!.pass && r!.spans.length > 0 && (
                  <div className="card-next">
                    {r!.spans.slice(0, 4).map(([a, b], k) => (
                      <button key={k} className="pchange span" onClick={() => actions.showSpan(a - (b - a) * 0.5, b + (b - a) * 0.5)}
                        title={t("healthSpan")}><bdi dir="ltr">{fmtTime(a, lang)}–{fmtTime(b, lang)}</bdi></button>))}
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="checks-sec" aria-label={t("chkQuality")}>
        <h3 className="eyebrow">{t("chkQuality")}</h3>
        {!q ? <p className="hint">…</p> : !qIssues.length ? (
          <ul className="card-list"><li className="card ok"><p className="card-title">{t("chkQualityOk", { n: q.checked })}</p></li></ul>
        ) : (
          <ul className="card-list">
            {qIssues.slice(0, QUALITY_CARDS).map((s) => (
              <li key={s.name} className="card warn" data-quality={s.name}>
                <p className="card-title"><button className="linklike" onClick={() => actions.addSignalLinked(`${runId}/${s.name}`)}
                  title={t("fsPlotHint")}>{s.name}</button></p>
                {signalLines(s, lang).map((l, i) => <p key={i} className="card-meta">{l}</p>)}
              </li>
            ))}
            {qIssues.length > QUALITY_CARDS && (
              <li><button className="linklike" onClick={() => useApp.setState({ qualityFor: runId })}>
                {t("chkQualityMore", { n: qIssues.length - QUALITY_CARDS })}</button></li>
            )}
          </ul>
        )}
      </section>

      {!flagsLast && flagsSec}

      {/* CC12: the automatic research by profile - a log's health check, "any data" for every file, the user's own;
          a file where nothing was found says nothing here (calm: no empty section) */}
      {(isLog || (hRep && hRep.findings.length > 0)) && (
        <section className="checks-sec" aria-label={t(isLog ? "chkHealth" : "chkHealthAny")} data-profiles={(hRep?.profiles ?? []).map((p) => p.name ?? p.id).join(",")}>
          <h3 className="eyebrow">{t(isLog ? "chkHealth" : "chkHealthAny")}</h3>
          {health === null ? <p className="hint">…</p> : health === "none" ? <p className="hint">{t("healthNone")}</p> : (
            <>
              {isLog && !health.findings.some((f) => f.level !== "ok") && (
                <p className="empty-state"><span>{t("emptyFindingsText")}</span>
                  <button className="linklike" onClick={() => useApp.setState({ logMarkers: "all" })}>{t("emptyFindingsAction")}</button></p>
              )}
              <ol className="health-list">{health.findings.map((f, i) => <HealthRow key={i} f={f} runId={runId} />)}</ol>
              <p className="hint log-note" title={t(isLog ? "healthNote" : "healthNoteAny")}>
                {t("chkProfiles", { list: (health.profiles ?? []).map((p) => p.id === "user" ? p.name ?? "" : t(`prof_${p.id}` as "prof_any")).join(", ") })}</p>
            </>
          )}
        </section>
      )}
      {flagsLast && flagsSec}
    </div>
  );
}

/** F1 *The file*: groups (message types, topics, structs, column prefixes) with their rate, samples and
 *  gaps; open one for its columns, their units and values at the cursor; a click plots a column. */
export function FileView({ runId, runKey }: { runId: string; runKey: string }) {
  const t = useT();
  const lang = useApp((s) => s.lang);
  const cursorT = useApp((s) => (s.cursor.on ? s.cursor.t1 : null));
  const [st, setSt] = useState<FileStructure | null>(null);
  const [open, setOpen] = useState<string | null>(null);
  const [q, setQ] = useState("");
  const [vals, setVals] = useState<Record<string, number | null>>({});
  useEffect(() => {
    let gone = false;
    api.runStructure(runId).then((r) => { if (!gone) setSt(r); }).catch(() => { if (!gone) setSt(null); });
    return () => { gone = true; };
  }, [runId, runKey]);
  const shown = useMemo(() => {
    if (!st) return [];
    const ql = q.trim().toLowerCase();
    if (!ql) return st.groups;
    return st.groups.map((g) => ({ ...g, columns: g.columns.filter((c) => c.name.toLowerCase().includes(ql)) })).filter((g) => g.columns.length);
  }, [st, q]);
  const openCols = shown.find((g) => g.name === open)?.columns ?? (q ? [] : undefined);
  useEffect(() => {
    if (cursorT === null || !openCols?.length) { setVals({}); return; }
    let gone = false;
    const ids = openCols.slice(0, 200).map((c) => `${runId}/${c.name}`);
    api.cursor(ids, cursorT).then((r) => { if (!gone) setVals(r.values); }).catch(() => {});
    return () => { gone = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cursorT, open, st, runId]);
  if (!st) return <p className="hint" style={{ padding: "0 14px" }}>…</p>;
  const tb = st.timeBase;
  const rate = (r?: number) => (r ? `${fmtNum(r, lang, 4)} Hz` : "–");
  return (
    <div className="fileview" data-groups={st.groups.length}>
      <p className="card-meta fv-sum">
        {t("fsSummary", { groups: st.groups.filter((g) => g.name).length, cols: st.columns, clocks: st.timeVectors })} ·{" "}
        {tb.column ? t("fsTimeColumn", { c: tb.column }) : tb.index || tb.clock === "index" ? t("fsTimeIndex") : t("fsTimeLog")}
      </p>
      <label className="filter">
        <Icon.Search />
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder={t("fsSearch")} aria-label={t("fsSearch")} />
      </label>
      <table className="data fv-table">
        <tbody>
          {shown.map((g) => {
            const isOpen = open === g.name || !!q;
            return [
              <tr key={`g:${g.name}`} className={`fv-group${isOpen ? " sel" : ""}`} data-group={g.name}>
                <td><button className="linklike" aria-expanded={isOpen} onClick={() => setOpen(open === g.name ? null : g.name)}>
                  {isOpen ? "▾" : lang === "he" ? "◂" : "▸"} <b>{g.name || t("fsOther")}</b></button>
                  {g.name && <span className="muted"> {t(`fsKind_${g.kind}` as "fsKind_message")}</span>}</td>
                <td className="num">{g.columns.length}</td>
                <td className="num">{rate(g.rate)}</td>
                <td className="num">{g.gaps ? <span className="fv-gap" title={t("fsGaps", { n: g.gaps, s: fmtNum(g.longestGap ?? 0, lang, 3) })}>⚠ {g.gaps}</span> : ""}</td>
              </tr>,
              ...(isOpen ? g.columns.map((c) => {
                const id = `${runId}/${c.name}`;
                const v = vals[id];
                return (
                  <tr key={id} className="fv-col" data-column={c.name}>
                    <td><button className="linklike" onClick={() => actions.addSignalLinked(id)} title={t("fsPlotHint")}>{c.field}</button>
                      {c.unit && <span className="muted"> [{c.unit}]</span>}</td>
                    <td className="num" title={t("fsSamples", { n: c.n })}>{c.n}</td>
                    <td className="num">{c.rate !== g.rate || !g.rate ? rate(c.rate) : ""}</td>
                    <td className="num" title={t("fsAtCursor")}>{cursorT !== null && v !== undefined ? (v === null ? "–" : fmtNum(v, lang, 6)) : ""}</td>
                  </tr>
                );
              }) : []),
            ];
          })}
        </tbody>
      </table>
    </div>
  );
}

/** F3 for any file that is not a flight log (a log keeps its own Parameters tab): the run's parameters
 *  with their source, and - with another file chosen - only what differs. */
export function RunParams({ runId }: { runId: string }) {
  const t = useT();
  const lang = useApp((s) => s.lang);
  const runs = useApp((s) => s.runs);
  const names = runLabels(runs);
  const others = runs.filter((r) => r.id !== runId && r.format !== "derived");
  const [rows, setRows] = useState<RunParam[] | null>(null);
  const [other, setOther] = useState("");
  const [diff, setDiff] = useState<ParamDiff | null>(null);
  useEffect(() => {
    let gone = false;
    api.runParameters(runId).then((r) => { if (!gone) setRows(r.params); }).catch(() => { if (!gone) setRows([]); });
    return () => { gone = true; };
  }, [runId]);
  useEffect(() => {
    if (!other) { setDiff(null); return; }
    let gone = false;
    api.compareParameters(runId, other).then((r) => { if (!gone) setDiff(r); }).catch(() => { if (!gone) setDiff(null); });
    return () => { gone = true; };
  }, [runId, other]);
  if (!rows) return <p className="hint" style={{ padding: "0 14px" }}>…</p>;
  const src = (s: RunParam["source"]) => <span className="muted"> · {t(`prmSource_${s}` as "prmSource_log")}</span>;
  return (
    <div className="runparams" data-params={rows.length}>
      {others.length > 0 && (
        <label className="afield log-file"><span>{t("prmCompareWith")}</span>
          <select value={other} onChange={(e) => setOther(e.target.value)} aria-label={t("prmCompareWith")}>
            <option value="">{t("prmNoCompare")}</option>
            {others.map((r) => <option key={r.id} value={r.id}>{names.get(r.id) ?? r.name}</option>)}
          </select></label>
      )}
      {!other ? (
        !rows.length ? <p className="empty-state"><span>{t("prmNone")}</span></p> : (
          <table className="data"><tbody>
            {rows.map((p) => <tr key={p.name} data-param={p.name}><td>{p.name}{src(p.source)}</td><td className="num">{fmtVal(p.value, lang)}</td></tr>)}
          </tbody></table>
        )
      ) : !diff ? <p className="hint">…</p> : (
        <>
          <p className="card-meta" data-testid="param-diff-sum">{t("prmSame", { n: diff.same })}</p>
          {!diff.differ.length && !diff.onlyA.length && !diff.onlyB.length ? <p className="empty-state"><span>{t("prmNoDiff")}</span></p> : (
            <table className="data"><tbody>
              {diff.differ.map((d) => (
                <tr key={d.name} data-diff={d.name}><td>{d.name}{src(d.source)}</td><td className="num">{fmtVal(d.a, lang)}</td><td className="num">{fmtVal(d.b, lang)}</td></tr>))}
              {diff.onlyA.map((p) => <tr key={`a:${p.name}`} data-diff={p.name}><td>{p.name}{src(p.source)}</td><td className="num">{fmtVal(p.value, lang)}</td><td className="muted">{t("prmOnlyThis")}</td></tr>)}
              {diff.onlyB.map((p) => <tr key={`b:${p.name}`} data-diff={p.name}><td>{p.name}{src(p.source)}</td><td className="muted">{t("prmOnlyOther")}</td><td className="num">{fmtVal(p.value, lang)}</td></tr>)}
            </tbody></table>
          )}
        </>
      )}
      <p className="hint log-note">{t("prmNote")}</p>
    </div>
  );
}
