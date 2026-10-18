import { useEffect, useMemo, useState } from "react";
import { api, type FleetFolder, type FleetKey, type FleetLog } from "../api";
import { actions, pickPath, useApp } from "../store";
import { useT, type Lang } from "../i18n";
import { followJob, openPaths } from "../files";

/** T41: the fleet - every flight log of the indexed folders: search by finding, by a number
 *  (vibration above X...), see one number's trend over the flights' dates, open a flight at a
 *  finding. The index is built on the server (app/fleet.py); scans run as jobs. */
export default function FleetPanel() {
  const t = useT();
  const lang = useApp((s) => s.lang);
  const [folders, setFolders] = useState<FleetFolder[]>([]);
  const [keys, setKeys] = useState<FleetKey[]>([]);
  const [logs, setLogs] = useState<FleetLog[] | null>(null);
  const [text, setText] = useState("");
  const [level, setLevel] = useState("");
  const [code, setCode] = useState("");
  const [key, setKey] = useState("");
  const [op, setOp] = useState<"above" | "below">("above");
  const [limit, setLimit] = useState("");
  const [trend, setTrend] = useState<{ path: string; name: string; date: number; value: number }[]>([]);
  const [open, setOpen] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const title = (c: string) => { const k = `hTitle_${c}`; const v = t(k as never); return v === k ? c : v; };
  const keyLabel = (k: string) => k === "duration" ? t("fleetDuration") : `${title(k.split(".")[0])} · ${k.split(".").slice(1).join(".")}`;
  const codes = useMemo(() => Array.from(new Set(keys.map((k) => k.key.split(".")[0]).filter((c) => c !== "duration"))).sort(), [keys]);

  const refresh = async () => {
    const st = await api.fleet();
    setFolders(st.folders);
    setKeys(st.keys);
  };
  const search = async () => {
    const q: Record<string, string | number> = {};
    if (text) q.text = text;
    if (level) q.level = level;
    if (code) q.code = code;
    if (key && limit !== "" && Number.isFinite(Number(limit))) { q.key = key; q[op] = Number(limit); }
    setLogs((await api.fleetLogs(q)).logs);
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
  const remove = async (f: string) => { setFolders((await api.fleetRemove(f)).folders); await refresh(); await search(); };

  return (
    <aside className="side fleet" aria-label={t("fleet")}>
      <div className="side-head"><h2>{t("fleet")}</h2></div>
      <div className="fleet-body">
        <p className="hint">{t("fleetIntro")}</p>
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

          {key && trend.length > 1 && <Trend points={trend} limit={limit === "" ? null : Number(limit)} lang={lang}
            label={keyLabel(key)} onPick={(p) => openAt(p, null)} />}

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
        </>}
      </div>
    </aside>
  );
}

/** Open a log of the fleet (or use it when it is open already), cursor at the finding, Log panel. */
async function openAt(path: string, at: number | null) {
  const find = () => useApp.getState().runs.find((r) => r.path === path);
  if (!find()) await openPaths([path]);
  if (!find()) return;
  if (at !== null && Number.isFinite(at)) actions.setTime(at);
  useApp.setState({ panel: "log" });
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
function Trend({ points, limit, label, lang, onPick }: {
  points: { path: string; name: string; date: number; value: number }[]; limit: number | null; label: string; lang: Lang;
  onPick: (path: string) => void;
}) {
  const W = 260, H = 110, P = 8;
  const xs = points.map((p) => p.date), ys = points.map((p) => p.value).concat(limit !== null && Number.isFinite(limit) ? [limit] : []);
  const x0 = Math.min(...xs), x1 = Math.max(...xs), y0 = Math.min(...ys), y1 = Math.max(...ys);
  const X = (v: number) => P + ((v - x0) / (x1 - x0 || 1)) * (W - 2 * P);
  const Y = (v: number) => H - P - ((v - y0) / (y1 - y0 || 1)) * (H - 2 * P);
  return (
    <figure className="fleet-trend" aria-label={label}>
      <figcaption className="muted">{label}</figcaption>
      <div dir="ltr"><svg viewBox={`0 0 ${W} ${H}`} role="img">
        {limit !== null && Number.isFinite(limit) && <line className="fleet-limitline" x1={P} x2={W - P} y1={Y(limit)} y2={Y(limit)} />}
        <polyline className="fleet-trendline" points={points.map((p) => `${X(p.date)},${Y(p.value)}`).join(" ")} />
        {points.map((p) => (
          <circle key={p.path} cx={X(p.date)} cy={Y(p.value)} r={3.5} className={limit !== null && p.value > limit ? "over" : ""}
            onClick={() => onPick(p.path)}>
            <title>{`${p.name} · ${fmtVal(p.value)} · ${fmtDate(p.date, lang)}`}</title>
          </circle>
        ))}
      </svg></div>
    </figure>
  );
}
