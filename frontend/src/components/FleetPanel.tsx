import { useEffect, useMemo, useState } from "react";
import { api, type FleetFolder, type FleetKey, type FleetLog } from "../api";
import { actions, pickPath, useApp } from "../store";
import { fmtNum, useT, type Lang } from "../i18n";
import { followJob, openPaths } from "../files";
import Toasts from "./Toasts";

/** T41: the fleet - every flight log of the indexed folders: search by finding, by a number
 *  (vibration above X...), see one number's trend over the flights' dates, open a flight at a
 *  finding. The index is built on the server (app/fleet.py); scans run as jobs. */
export default function FleetPanel() {
  const t = useT();
  const lang = useApp((s) => s.lang);
  const [folders, setFolders] = useState<FleetFolder[]>([]);
  const [keys, setKeys] = useState<FleetKey[]>([]);
  const [logs, setLogs] = useState<FleetLog[] | null>(null);
  const [all, setAll] = useState<FleetLog[] | null>(null);
  // the search is kept while another panel is shown (Open here opens the Log panel; back to the
  // Fleet, the search, the trend and the open flight are as they were)
  const [text, setText] = useKept("text", "");
  const [level, setLevel] = useKept("level", "");
  const [code, setCode] = useKept("code", "");
  const [key, setKey] = useKept("key", "");
  const [op, setOp] = useKept<"above" | "below">("op", "above");
  const [limit, setLimit] = useKept("limit", "");
  const [trend, setTrend] = useState<{ path: string; name: string; date: number; value: number }[]>([]);
  const [open, setOpen] = useKept<string | null>("open", null);
  const [busy, setBusy] = useState(false);
  const [example, setExample] = useState<string | null>(null);

  const title = (c: string) => { const k = `hTitle_${c}`; const v = t(k as never); return v === k ? c : v; };
  const keyLabel = (k: string) => k === "duration" ? t("fleetDuration") : `${title(k.split(".")[0])} · ${k.split(".").slice(1).join(".")}`;
  const codes = useMemo(() => Array.from(new Set(keys.map((k) => k.key.split(".")[0]).filter((c) => c !== "duration"))).sort(), [keys]);

  const refresh = async () => {
    const st = await api.fleet();
    setFolders(st.folders);
    setKeys(st.keys);
    setExample(st.example ?? null);
  };
  const search = async () => {
    const q: Record<string, string | number> = {};
    if (text) q.text = text;
    if (level) q.level = level;
    if (code) q.code = code;
    if (key && limit !== "" && Number.isFinite(Number(limit))) { q.key = key; q[op] = Number(limit); }
    setLogs((await api.fleetLogs(q)).logs);
    // the summary is of the whole fleet, whatever the question
    setAll(Object.keys(q).length ? (await api.fleetLogs({})).logs : null);
  };
  useEffect(() => { refresh().then(search).catch(() => setLogs([])); }, []);   // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    const h = window.setTimeout(() => { search().catch(() => {}); }, 250);    // as you type / choose
    return () => window.clearTimeout(h);
  }, [text, level, code, key, op, limit]);                                    // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (!key) { setTrend([]); return; }
    api.fleetTrend(key).then((r) => setTrend(r.points)).catch(() => setTrend([]));
  }, [key, folders]);

  // the trend follows the typed search (not the number's limit - that is the line on it): type a
  // vehicle's name and the line is that vehicle's flights only
  const shownTrend = useMemo(() => {
    const q = text.trim().toLowerCase();
    return q ? trend.filter((p) => p.name.toLowerCase().includes(q) || p.path.toLowerCase().includes(q)) : trend;
  }, [trend, text]);
  const scan = async (start: () => Promise<Parameters<typeof followJob>[0]>, label: string) => {
    setBusy(true);
    try {
      const res = await followJob<{ read?: number; failed?: number; folders?: unknown[] }>(await start(), label);
      if (res) useApp.getState().toast({ kind: "info", text: t("fleetScanned") });
      await refresh();
      await search();
    } catch (e) {
      useApp.getState().toast({ kind: "error", text: String((e as Error).message) });
    } finally { setBusy(false); }
  };
  const addFolder = async () => {
    const path = await pickPath({ mode: "folder", title: t("fleetChooseFolder") });
    if (path) scan(() => api.fleetAdd(path), t("fleetIndexing"));
  };
  /* the example (owner, 2026-11-03: what the fleet is for): two copters, ten flights; it opens on the
     vibration trend, where the worn motor shows */
  const tryExample = async () => {
    if (!example) return;
    if (!folders.some((f) => f.folder === example)) await scan(() => api.fleetAdd(example), t("fleetIndexing"));
    setText(""); setLevel(""); setCode(""); setKey("vibration.max"); setOp("above"); setLimit("30");
  };
  const remove = async (f: string) => { setFolders((await api.fleetRemove(f)).folders); await refresh(); await search(); };

  return (
    // U9 (owner, 2026-11-07): an area of its own (was a panel of the Recordings rail) - the whole width
    // for the folders, the search and the trend on one side, the flights on the other
    <>
    <div className="areabar fleet-bar" role="toolbar" aria-label={t("areaFleet")}>
      <h2>{t("fleet")}</h2><span className="hint">{t("fleetIntro")}</span>
    </div>
    <main className="fleet-area" aria-label={t("fleet")}>
      <div className="fleet-body">
        <div className="fleet-side">
        {example && !folders.some((f) => f.folder === example) && (
          <div className="fleet-example">
            <p>{t("fleetWhat")}</p>
            <button className="btn sm primary" disabled={busy} onClick={() => { void tryExample(); }}>{t("fleetTryExample")}</button>
          </div>
        )}
        <div className="fleet-folders">
          {folders.map((f) => (
            <div key={f.folder} className="fleet-folder">
              <bdi dir="ltr" title={f.folder}>{f.folder}</bdi>
              <span className="muted">{t("fleetLogsN", { n: f.logs })}</span>
              <button className="icon-btn" aria-label={t("fleetRemoveFolder")} title={t("fleetRemoveFolder")} onClick={() => remove(f.folder)}>×</button>
            </div>
          ))}
          <div className="fleet-btns">
            <button className="btn sm" disabled={busy} onClick={addFolder}>{t("fleetAddFolder")}</button>
            {folders.length > 0 && <button className="btn sm" disabled={busy} onClick={() => scan(api.fleetRescan, t("fleetUpdating"))}>{t("fleetUpdate")}</button>}
          </div>
        </div>

        {folders.length > 0 && <>
          <div className="fleet-search">
            <input type="search" placeholder={t("fleetSearch")} aria-label={t("fleetSearch")} value={text} onChange={(e) => setText(e.target.value)} />
            <div className="fleet-row">
              <select aria-label={t("fleetLevel")} value={level} onChange={(e) => setLevel(e.target.value)}>
                <option value="">{t("fleetAnyLevel")}</option>
                <option value="warning">{t("fleetWarnOrError")}</option>
                <option value="error">{t("fleetErrorOnly")}</option>
              </select>
              <select aria-label={t("fleetFinding")} value={code} onChange={(e) => setCode(e.target.value)}>
                <option value="">{t("fleetAnyFinding")}</option>
                {codes.map((c) => <option key={c} value={c}>{title(c)}</option>)}
              </select>
            </div>
            <div className="fleet-row">
              <select aria-label={t("fleetNumber")} value={key} onChange={(e) => setKey(e.target.value)}>
                <option value="">{t("fleetNoNumber")}</option>
                {keys.map((k) => <option key={k.key} value={k.key}>{keyLabel(k.key)}</option>)}
              </select>
              {key && <>
                <select aria-label={t("fleetOp")} value={op} onChange={(e) => setOp(e.target.value as "above" | "below")}>
                  <option value="above">{t("fleetAbove")}</option>
                  <option value="below">{t("fleetBelow")}</option>
                </select>
                <input type="number" step="any" className="fleet-limit" aria-label={t("fleetLimit")} value={limit} onChange={(e) => setLimit(e.target.value)} />
              </>}
            </div>
          </div>

          {key && shownTrend.length > 1 && <Trend points={shownTrend} limit={limit === "" ? null : Number(limit)} lang={lang} op={op}
            label={keyLabel(key)} onPick={(p) => openAt(p, null)} />}
        </>}
        </div>
        {folders.length > 0 && <div className="fleet-main">
          {/* owner (2026-11-13): what the Fleet is for, as the questions it answers - one click each */}
          <div className="fleet-questions" role="group" aria-label={t("fleetQuestions")}>
            <span className="muted">{t("fleetQuestions")}</span>
            <button className={`chipbtn${level === "error" && !key ? " on" : ""}`} onClick={() => { setText(""); setCode(""); setKey(""); setLevel("error"); }}>{t("fleetQErrors")}</button>
            {keys.some((k) => k.key === "vibration.max") && <button className={`chipbtn${key === "vibration.max" ? " on" : ""}`}
              onClick={() => { setText(""); setLevel(""); setCode(""); setKey("vibration.max"); setOp("above"); setLimit(limit || "30"); }}>{t("fleetQTrend")}</button>}
            {keys.some((k) => k.key.startsWith("battery")) && <button className={`chipbtn${key.startsWith("battery") ? " on" : ""}`}
              onClick={() => { const k = keys.find((x) => x.key.startsWith("battery"))!.key; setText(""); setLevel(""); setCode(""); setKey(k); setOp("below"); setLimit(""); }}>{t("fleetQBattery")}</button>}
            <button className="chipbtn" onClick={() => { setText(""); setLevel(""); setCode(""); setKey(""); setLimit(""); }}>{t("fleetQAll")}</button>
          </div>
          {(all ?? logs) && (all ?? logs)!.length > 0 && <FleetSummary logs={(all ?? logs)!} shown={logs ?? []} lang={lang} onPick={(p) => setOpen(p)} />}

          <div className="fleet-count muted">{logs ? (logs.length === 1 ? t("fleetFoundOne") : t("fleetFound", { n: logs.length })) : t("loading")}</div>
          <ul className="fleet-list">
            {(logs ?? []).map((l) => (
              <li key={l.path} className={`fleet-log${l.error ? " bad" : ""}`}>
                <button className="fleet-line" aria-expanded={open === l.path} onClick={() => setOpen(open === l.path ? null : l.path)}>
                  <span className="fleet-date" title={l.date_source === "file" ? t("fleetDateFromFile") : t("fleetDateFromGps")}>
                    {fmtDate(l.date, lang)}{l.date_source === "file" ? "*" : ""}</span>
                  <bdi className="fleet-name" dir="ltr">{l.name}</bdi>
                  {l.errors > 0 && <span className="fleet-badge err">{l.errors}</span>}
                  {l.warnings > 0 && <span className="fleet-badge warn">{l.warnings}</span>}
                  {key && l.metrics[key] !== undefined && <span className="fleet-val">{fmtVal(l.metrics[key])}</span>}
                </button>
                {open === l.path && (
                  <div className="fleet-detail">
                    {l.error ? <p className="muted">{t("fleetUnreadable")}: {l.error}</p> : <>
                      <p className="muted">{[l.vehicle, l.firmware, l.duration != null ? fmtDur(l.duration) : null].filter(Boolean).join(" · ")}</p>
                      {Object.keys(l.modes).length > 0 && <p className="muted">{Object.entries(l.modes).sort((a, b) => b[1] - a[1]).slice(0, 5)
                        .map(([m, s]) => `${m} ${fmtDur(s)}`).join(" · ")}</p>}
                      <ul className="fleet-findings">
                        {l.findings.filter((f) => f.level !== "ok").map((f, i) => (
                          <li key={i} className={f.level}>
                            <span>{findingText(t, f.code, f.level, f.vals)}</span>
                            <button className="btn sm" onClick={() => openAt(l.path, f.t)}>{t("fleetOpenAt")}</button>
                          </li>
                        ))}
                      </ul>
                      <button className="btn sm" onClick={() => openAt(l.path, null)}>{t("fleetOpen")}</button>
                    </>}
                  </div>
                )}
              </li>
            ))}
          </ul>
        </div>}
      </div>
      {/* the area's messages (Recordings has its own place for them, over its timeline) */}
      <div className="notices fleet-notices"><Toasts /></div>
    </main>
    </>
  );
}

/** Open a log of the fleet (or use it when it is open already), cursor at the finding, Log panel. */
async function openAt(path: string, at: number | null) {
  const find = () => useApp.getState().runs.find((r) => r.path === path);
  if (!find()) await openPaths([path]);
  if (!find()) return;
  if (at !== null && Number.isFinite(at)) actions.setTime(at);
  useApp.setState({ area: "recordings", panel: "log" });     // U9: the log opens in Recordings
}

function findingText(t: ReturnType<typeof useT>, code: string, level: string, vals: Record<string, number | string>) {
  const k = `h_${code}_${level}`;
  const v = t(k as never, vals as never);
  return v === k ? `${code} (${level})` : v;
}

const fmtVal = (v: number) => (Math.abs(v) >= 100 ? v.toFixed(0) : Math.abs(v) >= 1 ? v.toFixed(1) : v.toPrecision(2));
const fmtDur = (s: number) => `${Math.floor(s / 60)}:${String(Math.round(s % 60)).padStart(2, "0")}`;
const fmtDate = (unix: number, lang: Lang) =>
  new Date(unix * 1000).toLocaleDateString(lang === "he" ? "he-IL" : "en-GB", { year: "2-digit", month: "2-digit", day: "2-digit" });

/** One number over the flights' dates: points, the search limit as a line, click a point -> that log. */
function Trend({ points, limit, label, lang, onPick, op }: {
  points: { path: string; name: string; date: number; value: number }[]; limit: number | null; label: string; lang: Lang;
  onPick: (path: string) => void; op: "above" | "below";
}) {
  const t = useT();
  const over = (v: number) => limit !== null && Number.isFinite(limit) && (op === "above" ? v > limit : v < limit);
  const firstOver = [...points].sort((a, b) => a.date - b.date).find((p) => over(p.value));
  const W = 260, H = 110, P = 8, L = 30;      // review R11: L = room for the values (the chart had no y axis)
  const xs = points.map((p) => p.date), ys = points.map((p) => p.value).concat(limit !== null && Number.isFinite(limit) ? [limit] : []);
  const x0 = Math.min(...xs), x1 = Math.max(...xs), y0 = Math.min(...ys), y1 = Math.max(...ys);
  const X = (v: number) => L + ((v - x0) / (x1 - x0 || 1)) * (W - L - P);
  const Y = (v: number) => H - P - ((v - y0) / (y1 - y0 || 1)) * (H - 2 * P);
  return (
    <figure className="fleet-trend" aria-label={label}>
      <figcaption className="muted">{label}</figcaption>
      <div dir="ltr"><svg viewBox={`0 0 ${W} ${H}`} role="img" fontSize={8}>
        {[y0, y1].filter((v, i, a) => a.indexOf(v) === i && (limit === null || Math.abs(Y(v) - Y(limit)) > 9)).map((v) => (
          <text key={v} className="fleet-ytick" x={L - 5} y={Y(v) + 3} textAnchor="end">{fmtVal(v)}</text>))}
        {limit !== null && Number.isFinite(limit) && <>
          <line className="fleet-limitline" x1={L} x2={W - P} y1={Y(limit)} y2={Y(limit)} />
          <text className="fleet-ytick limit" x={L - 5} y={Y(limit) + 3} textAnchor="end">{fmtVal(limit)}</text>
        </>}
        <polyline className="fleet-trendline" points={points.map((p) => `${X(p.date)},${Y(p.value)}`).join(" ")} />
        {points.map((p) => (
          <circle key={p.path} cx={X(p.date)} cy={Y(p.value)} r={3.5} className={over(p.value) ? "over" : ""}
            onClick={() => onPick(p.path)}>
            <title>{`${p.name} · ${fmtVal(p.value)} · ${fmtDate(p.date, lang)}`}</title>
          </circle>
        ))}
      </svg></div>
      <div className="fleet-trend-axis muted" dir="ltr"><span>{fmtDate(Math.min(...xs), lang)}</span><span>{fmtDate(Math.max(...xs), lang)}</span></div>
      {firstOver ? <p className="fleet-first">{t("fleetFirstOver", { name: firstOver.name, date: fmtDate(firstOver.date, lang), v: fmtVal(firstOver.value) })}
        {" "}<button className="linklike" onClick={() => onPick(firstOver.path)}>{t("fleetOpen")}</button></p>
        : limit !== null && Number.isFinite(limit) ? <p className="muted">{t("fleetNoneOver")}</p> : null}
    </figure>
  );
}

/** Owner (2026-11-13): the fleet at a glance - how many flights, vehicles, hours, how many with errors or
 *  warnings, and every flight on its date, coloured by its worst finding (a click opens it in the list). */
function FleetSummary({ logs, shown, lang, onPick }: { logs: FleetLog[]; shown: FleetLog[]; lang: Lang; onPick: (path: string) => void }) {
  const inQ = new Set(shown.map((l) => l.path));
  const t = useT();
  const ok = logs.filter((l) => !l.error);
  const vehicles = new Set(ok.map((l) => l.vehicle).filter(Boolean)).size;
  const hours = ok.reduce((a, l) => a + (l.duration ?? 0), 0) / 3600;
  const withErr = ok.filter((l) => l.errors > 0).length, withWarn = ok.filter((l) => !l.errors && l.warnings > 0).length;
  const d0 = Math.min(...ok.map((l) => l.date)), d1 = Math.max(...ok.map((l) => l.date));
  const pct = (d: number) => `${(100 * (d - d0)) / (d1 - d0 || 1)}%`;
  return (
    <section className="fleet-summary" aria-label={t("fleetSummary")}>
      <div className="fleet-tiles">
        <span><b>{ok.length}</b>{ok.length === 1 ? t("fleetTileFlight") : t("fleetTileFlights")}</span>
        {vehicles > 0 && <span><b>{vehicles}</b>{vehicles === 1 ? t("fleetTileVehicle") : t("fleetTileVehicles")}</span>}
        {hours >= 1 ? <span><b>{fmtNum(hours, lang, 3)}</b>{t("fleetTileHours")}</span>
          : <span><b>{fmtNum(Math.round(hours * 60), lang)}</b>{t("fleetTileMinutes")}</span>}
        <span className="err"><b>{withErr}</b>{t("fleetTileErrors")}</span>
        <span className="warn"><b>{withWarn}</b>{t("fleetTileWarnings")}</span>
      </div>
      {ok.length > 1 && <div className="fleet-strip" dir="ltr" aria-label={t("fleetStrip")}>
        {ok.map((l) => <button key={l.path} className={`fleet-dot ${l.errors ? "err" : l.warnings ? "warn" : "ok"}${inQ.size < logs.length && !inQ.has(l.path) ? " out" : ""}`} style={{ left: pct(l.date) }}
          title={`${l.name} · ${fmtDate(l.date, lang)}${l.errors ? ` · ${l.errors} ✕` : ""}${l.warnings ? ` · ${l.warnings} !` : ""}`}
          aria-label={l.name} onClick={() => onPick(l.path)} />)}
      </div>}
      {ok.length > 1 && <div className="fleet-trend-axis muted" dir="ltr"><span>{fmtDate(d0, lang)}</span><span>{fmtDate(d1, lang)}</span></div>}
    </section>
  );
}

/* the panel's search, kept for the session (not saved) across the panel being closed and opened */
const KEPT: Record<string, unknown> = {};
function useKept<T>(name: string, initial: T): [T, (v: T) => void] {
  const [v, setV] = useState<T>(name in KEPT ? (KEPT[name] as T) : initial);
  return [v, (x: T) => { KEPT[name] = x; setV(x); }];
}
