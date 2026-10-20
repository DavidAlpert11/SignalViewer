import { DATA_EXTS } from "../values";
import { useEffect, useMemo, useRef, useState } from "react";
import { groupByPrefix, groupDerived, memberLabel } from "../signalGroups";
import { unitOf } from "../units";
import { sparkPath, useSpark } from "../sparks";
import type { RunInfo, SignalInfo } from "../api";
import { showFileTags, actions, activeTab, fileLabel, useApp } from "../store";
import { fmtInt, fmtNum, useT } from "../i18n";
import { Icon } from "../icons";
import { openPaths, recentToOpen, refreshRecent, reloadRun, removeRun } from "../files";
import TemplateStrip from "./TemplateStrip";
import { refreshAll } from "../live";
import { applySyncOffset } from "../sync";
import { openMenu, prompt } from "./Overlays";
import { pickPath } from "../store";
import { describeTransform } from "../transforms";
import { startRetarget } from "../files";
import { SIGNAL_MIME } from "./PlotView";
import { api } from "../api";
import { createSignalItem } from "../createSignalMenu";

/* Virtualized rows: only what is on screen is in the DOM (thousands of signals). */
type Row =
  | { kind: "run"; run: RunInfo; closed: boolean; h: number }
  | { kind: "group"; runId: string; key: string; ids: string[]; closed: boolean; h: number }
  | { kind: "sig"; sig: SignalInfo; depth: number; h: number; group?: string };
const H_RUN = 30, H_GROUP = 26, H_SIG = 26, OVERSCAN = 10;

import { exactMatch, fuzzyMatch } from "../fuzzy";
/** Smart search: substrings, letters in order, or one typo (see fuzzy.ts). */
const match = (name: string, q: string) => fuzzyMatch(name, q);

function Highlight({ text, q }: { text: string; q: string }) {
  const tok = q.trim().split(/\s+/)[0];
  if (!tok) return <>{text}</>;
  const i = text.toLowerCase().indexOf(tok.toLowerCase());
  if (i < 0) return <>{text}</>;
  return <>{text.slice(0, i)}<mark>{text.slice(i, i + tok.length)}</mark>{text.slice(i + tok.length)}</>;
}

export default function DataPanel() {
  const t = useT();
  const lang = useApp((s) => s.lang);
  const runs = useApp((s) => s.runs);
  const ws = useApp((s) => s.ws);
  const [q, setQ] = useState("");
  const [closed, setClosed] = useState<Record<string, boolean>>({});
  const [renameRun, setRenaming] = useState<string | null>(null);
  const linkRuns = useApp((s) => s.linkRuns);
  const streaming = useApp((s) => s.streaming);
  const activity = useApp((s) => s.activity);
  // signals selected in the list: Ctrl / Shift + click, the checkboxes, or "select" from a search
  const picked = useApp((s) => s.listSel);
  const setPicked = (ids: string[]) => useApp.setState({ listSel: ids });
  const pickedSet = useMemo(() => new Set(picked), [picked]);
  const togglePick = (id: string) => useApp.setState({ listSel: picked.includes(id) ? picked.filter((x) => x !== id) : [...picked, id], listAnchor: id });
  const refresh = async () => { useApp.setState({ runs: await api.listRuns(), dataVersion: useApp.getState().dataVersion + 1 }); actions.dropStaleRanges(); };
  const fail = (e: unknown) => useApp.getState().toast({ kind: "error", text: String((e as Error).message) });
  const fileMenu = (e: React.MouseEvent, run: RunInfo) => {
    if (run.format === "derived") return;
    openMenu(e, [
      { label: t("rename"), run: () => setRenaming(run.id) },
      { label: t("fileTag") + "…", run: async () => {      // T46
        const v = await prompt(t("fileTag"), `${run.name} - ${t("fileTagLimit")}`, run.tag ?? "");
        if (v !== null && v.trim()) { await api.patchRun(run.id, { tag: v.trim() }); refresh(); }
      } },
      { label: t("fileDescription") + "…", run: async () => {
        const v = await prompt(t("fileDescription"), run.name, run.description ?? "", true);
        if (v !== null) { await api.patchRun(run.id, { description: v }); refresh(); }
      } },
      { label: t("fileTimeOffset") + "…", run: async () => {
        const v = await prompt(t("fileTimeOffset"), run.name, String(run.timeOffset ?? 0));
        if (v === null) return;
        const n = Number(v);
        if (!Number.isFinite(n)) return fail(new Error(t("limitsInvalid")));
        await api.patchRun(run.id, { timeOffset: n }); refresh();
      } },
      ...(runs.filter((r) => r.format !== "derived").length > 1 ? [{ label: t("syncMenu") + "…", run: () => useApp.setState({ syncFor: run.id }) }] : []),
      ...((() => {
        const c = useApp.getState().cursor;
        return c.on && c.dual && c.t1 !== null && c.t2 !== null && c.t1 !== c.t2
          ? [{ label: t("syncCursorMenu", { s: (c.t1 - c.t2).toFixed(3) }), run: () => { applySyncOffset(run.id, (run.timeOffset ?? 0) + (c.t1! - c.t2!)); } }]
          : [];
      })()),
      { label: "", run: () => {}, sep: true },
      { label: t("replaceFile"), run: async () => {
        const path = await pickPath({ mode: "open", title: t("replaceFile"), exts: DATA_EXTS });
        if (!path) return;
        try { await api.replace(run.id, path); refresh(); } catch (err) { fail(err); }
      } },
      // (Reload: the ↻ next to the file, or F5 / the panel's ↻ for every file - T49 item 4)
      { label: "", run: () => {}, sep: true },
      { label: t("remove"), run: () => removeRun(run.id), danger: true },
    ]);
  };
  const sigMenu = (e: React.MouseEvent, sig: SignalInfo) => openMenu(e, [
    ...(() => {
      const tb = activeTab(useApp.getState().ws); const p = tb.plots[tb.active];
      return p?.signals.some((s) => s.sig === sig.id)
        ? [{ label: t("removeFromActivePlot"), run: () => actions.removeSignal(p.id, sig.id) }]
        : [{ label: t("addSigToActivePlot"), run: () => actions.addSignalLinked(sig.id) }];
    })(),
    { label: t("newPlot"), run: () => actions.addSignalToNewPlot(sig.id) },
    { label: t("useAsX"), run: () => { const tb = activeTab(useApp.getState().ws); const p = tb.plots[tb.active]; if (p) actions.setAsX(p.id, sig.id); } },
    { label: "", run: () => {}, sep: true },
    // T49 item 7: one way to change a signal itself (the same as Create signals > Change this signal)
    ...(sig.id.startsWith("derived/") ? [] : [{ label: t("tfEdit"), run: () => useApp.setState({ transformTargets: [sig.id] }) }]),
    createSignalItem(sig.id),
  ]);

  // recent files that are not open now, to add one more file quickly
  const recentMenu = async (e: React.MouseEvent) => {
    const at = { clientX: e.clientX, clientY: e.clientY, preventDefault() {}, stopPropagation() {} } as React.MouseEvent;
    await refreshRecent();
    const items = recentToOpen(8);
    openMenu(at, [
      ...(items.length ? items.map((x) => ({ label: x.exists ? `${x.name}  ·  ${x.folder}` : `${x.name}  ·  ${t("notFound")}`,
        run: () => openPaths([x.path]), disabled: !x.exists }))
        : [{ label: t("recentNone"), run: () => {}, disabled: true }]),
      { label: "", run: () => {}, sep: true },
      { label: t("openFiles") + "…", run: () => useApp.setState({ browserOpen: true }) },
    ]);
  };

  const tab = activeTab(ws);
  const activePlot = tab.plots[tab.active];
  const colorOf = useMemo(() => {
    const m = new Map<string, string>();
    activePlot?.signals.forEach((s) => m.set(s.sig, s.color));
    return m;
  }, [activePlot]);

  const [groupOpen, setGroupOpen] = useState<Record<string, boolean>>({});
  const treeRef = useRef<HTMLDivElement>(null);
  const [view, setView] = useState({ top: 0, height: 600 });
  useEffect(() => {
    const el = treeRef.current;
    if (!el) return;
    const ro = new ResizeObserver(() => setView((v) => ({ ...v, height: el.clientHeight })));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  // exact matches (in any file) win; approximate ones are shown only when nothing matches exactly
  const anyExact = !!q.trim() && runs.some((r) => r.signals.some((x) => exactMatch(x.name, q)));
  const filtered = runs.map((r) => ({
    run: r,
    sigs: !q.trim() ? r.signals : r.signals.filter((x) => (anyExact ? exactMatch(x.name, q) : match(x.name, q))),
  }));
  const anyMatch = filtered.some((f) => f.sigs.length);

  const rows = useMemo(() => {
    const out: Row[] = [];
    for (const { run, sigs } of filtered) {
      if (q && !sigs.length) continue;
      const closedRun = !!closed[run.id] && !q;
      out.push({ kind: "run", run, closed: closedRun, h: H_RUN });
      if (closedRun) continue;
      // derived signals made together (a frame conversion's axes) are always nested
      const derived = run.format === "derived";
      const groups = derived ? groupDerived(sigs) : groupByPrefix(sigs, (s) => s.name);
      if (!groups) { sigs.forEach((sig) => out.push({ kind: "sig", sig, depth: 0, h: H_SIG })); continue; }
      const many = !derived && run.signals.length > 200;
      for (const g of groups) {
        const gk = `${run.id}|${g.key}`;
        // searching opens every matching group; otherwise big files start collapsed
        const open = q ? true : groupOpen[gk] ?? !many;
        if (!g.key) { g.items.forEach((sig) => out.push({ kind: "sig", sig, depth: 0, h: H_SIG })); continue; }
        out.push({ kind: "group", runId: run.id, key: g.key, ids: g.items.map((x) => x.id), closed: !open, h: H_GROUP });
        if (open) g.items.forEach((sig) => out.push({ kind: "sig", sig, depth: 1, h: H_SIG, group: derived ? g.key : undefined }));
      }
    }
    return out;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [runs, q, closed, groupOpen]);

  const offsets = useMemo(() => {
    const o = new Array(rows.length + 1);
    o[0] = 0;
    for (let i = 0; i < rows.length; i++) o[i + 1] = o[i] + rows[i].h;
    return o as number[];
  }, [rows]);
  const total = offsets[rows.length];
  let first = 0;
  { let lo = 0, hi = rows.length; while (lo < hi) { const m = (lo + hi) >> 1; if (offsets[m + 1] <= view.top) lo = m + 1; else hi = m; } first = lo; }
  first = Math.max(0, first - OVERSCAN);
  let last = first;
  while (last < rows.length && offsets[last] < view.top + view.height) last++;
  last = Math.min(rows.length, last + OVERSCAN);

  const renderRow = (row: Row) => {
    if (row.kind === "run") {
      const run = row.run;
      return (
        <div className={`run-head${row.closed ? " closed" : ""}`} onClick={() => setClosed({ ...closed, [run.id]: !closed[run.id] })}
          onContextMenu={(e) => fileMenu(e, run)}
          title={run.format === "derived" ? "" : `${run.path}\n${fmtInt(run.samples, lang)} · ${fmtNum(run.start, lang)} – ${fmtNum(run.end, lang)}${run.description ? "\n\n" + run.description : ""}`}>
          <Icon.Chevron className="chev" />
          {run.format !== "derived" && run.color && (
            // T46: the file's colour (with several files: its tag in that colour) - click to change the colour
            <label className={showFileTags(runs) && run.tag ? "file-tag run-tagpick" : "run-swatch"} style={{ ["--tag" as string]: run.color }}
              title={`${showFileTags(runs) ? t("fileTagHint") + "\n" : ""}${t("fileColor")}`} onClick={(e) => e.stopPropagation()}>
              {showFileTags(runs) && run.tag}
              <input type="color" value={run.color} aria-label={`${t("fileColor")}: ${run.name}`}
                onChange={async (e) => { await api.patchRun(run.id, { color: e.target.value }); refresh(); }} />
            </label>
          )}
          {renameRun === run.id ? (
            <input autoFocus defaultValue={run.name} className="run-name" onClick={(e) => e.stopPropagation()}
              onBlur={async (e) => {
                setRenaming(null);
                const name = e.target.value.trim();
                if (name && name !== run.name) { await api.patchRun(run.id, { name }); useApp.setState({ runs: await api.listRuns() }); }
              }}
              onKeyDown={(e) => { if (e.key === "Enter") (e.target as HTMLInputElement).blur(); if (e.key === "Escape") setRenaming(null); }} />
          ) : <span className="run-name">{run.format === "derived" ? t("derived") : fileLabel(runs, run.id)}</span>}
          {run.copy && <span className="badge-copy" title={t("copyBadgeHint")}>{t("copyBadge")}</span>}
          {!!run.timeOffset && <span className="badge-off" title={t("timeShifted", { s: fmtNum(run.timeOffset, lang) })}>{run.timeOffset > 0 ? "+" : ""}{fmtNum(run.timeOffset, lang, 4)}s</span>}
          {streaming && run.format !== "derived" && !run.copy && (() => {
            const ago = activity[run.id];
            const on = ago !== undefined && ago < 3;
            return <span className={`live-dot${on ? " on" : ""}`} role="img"
              aria-label={on ? t("liveUpdating") : t("liveIdle")}
              title={on ? t("liveUpdating") : ago === undefined ? t("liveNoData") : t("liveIdleFor", { s: fmtNum(ago, lang, 3) })} />;
          })()}
          {(run.format === "bin" || run.format === "tlog" || run.format === "ulg" || run.format === "mcap" || run.format === "hdf5" || run.format === "parquet") && (
            <span className="badge-fmt" title={t(run.format === "bin" ? "ardupilotLog" : run.format === "tlog" ? "tlogFile" : run.format === "mcap" ? "mcapFile" : run.format === "hdf5" ? "hdf5File" : run.format === "parquet" ? "parquetFile" : "ulogFile")}>
              {run.format === "ulg" ? "PX4" : run.format === "mcap" ? "ROS 2" : run.format.toUpperCase()}</span>)}
          <span className="run-meta">{fmtInt(run.signals.length, lang)}</span>
          {run.format !== "derived" && <>
            <button className="iconbtn" title={t("reload")} aria-label={t("reload")} onClick={(e) => { e.stopPropagation(); reloadRun(run.id); }}><Icon.Reload /></button>
            <button className="iconbtn" title={t("fileMenu")} aria-label={t("fileMenu")} onClick={(e) => { e.stopPropagation(); fileMenu(e, run); }}><Icon.More /></button>
          </>}
        </div>
      );
    }
    if (row.kind === "group") {
      const gk = `${row.runId}|${row.key}`;
      return (
        <div className={`grp-head${row.closed ? " closed" : ""}`} onClick={() => setGroupOpen({ ...groupOpen, [gk]: row.closed })}
          onContextMenu={(e) => openMenu(e, [
            { label: t("groupAddAll"), run: () => actions.addSignals(row.ids) },
            { label: t("groupEachNewPlot"), run: () => actions.addSignalsToNewPlots(row.ids) },
          ])}>
          <Icon.Chevron className="chev" /><span className="nm">{row.key}</span><span className="run-meta">{fmtInt(row.ids.length, lang)}</span>
        </div>
      );
    }
    const s = row.sig;
    const color = colorOf.get(s.id);
    // checkboxes only while there is a selection (Ctrl / Shift + click, or "select all shown")
    const picking = picked.length > 0;
    const button = (
      <button className={`sig${color ? " in" : ""}${row.depth ? " deep" : ""}${picking ? " pickable" : ""}`} draggable
        onDragStart={(e) => { e.dataTransfer.setData(SIGNAL_MIME, s.id); e.dataTransfer.effectAllowed = "copy"; }}
        onClick={(e) => {
          if (e.ctrlKey || e.metaKey) { togglePick(s.id); return; }
          if (e.shiftKey) {
            const order = rows.filter((r) => r.kind === "sig").map((r) => (r as { sig: SignalInfo }).sig.id);
            const anchor = useApp.getState().listAnchor;
            const a = anchor ? order.indexOf(anchor) : -1, b = order.indexOf(s.id);
            const range = a < 0 ? [s.id] : order.slice(Math.min(a, b), Math.max(a, b) + 1);
            useApp.setState({ listSel: Array.from(new Set([...(e.ctrlKey ? picked : []), ...range])), listAnchor: anchor ?? s.id });
            return;
          }
          if (e.altKey) { actions.addSignalToNewPlot(s.id); return; }
          if (colorOf.has(s.id)) actions.toggleSignal(s.id); else actions.addSignalLinked(s.id);
        }}
        onContextMenu={(e) => sigMenu(e, s)}
        title={`${s.formula ?? s.name}${rateLine(s, lang)}\n${t("listSelHint")}`} aria-label={s.name}>
        <span className="dot" style={color ? { background: color } : undefined} />
        <span className="nm"><Highlight text={nameOnly(row.group ? memberLabel(s.name, row.group) : s.name)} q={q} /></span>
        {/* T22: the unit stays visible however long the name; the rate and a small picture of the signal */}
        {unitOf(s.name) && <span className="sig-unit">{unitOf(s.name)}</span>}
        {s.rate !== undefined && <span className="sig-rate">{fmtRate(s.rate, lang)}</span>}
        {!s.labels && <SigSpark id={s.id} version={`${s.n ?? s.samples ?? 0}:${s.version ?? runs.find((r) => s.id.startsWith(`${r.id}/`))?.version ?? ""}:${s.transform ? JSON.stringify(s.transform) : ""}`} />}
        {s.transform && <span className="tf-badge" title={`${t("tfChanged")}: ${describeTransform(s.transform)}`}>ƒ</span>}
        {s.labels && <span className="txt-badge" title={t("textSignalHint", { n: Object.keys(s.labels).length, list: Object.values(s.labels).slice(0, 8).join(", ") + (Object.keys(s.labels).length > 8 ? "…" : "") })}>Aa</span>}
      </button>
    );
    if (!picking) return button;
    return (
      <div className="sig-wrap">
        <input type="checkbox" className="sig-pick" checked={pickedSet.has(s.id)} onChange={() => togglePick(s.id)}
          aria-label={s.name} onClick={(e) => e.stopPropagation()} />
        {button}
      </div>
    );
  };

  return (
    <aside className="side" aria-label={t("data")}>
      <div className="side-head">
        <h2>{t("files")}</h2>
        {runs.some((r) => r.format !== "derived") && (
          <button className="iconbtn" onClick={() => { refreshAll(); }} title={`${t("refreshAll")} (F5)`} aria-label={t("refreshAll")}><Icon.Reload /></button>
        )}
        {runs.some((r) => r.format !== "derived") && (
          <button className="iconbtn" onClick={() => startRetarget()} title={t("replaceInputFiles")} aria-label={t("replaceInputFiles")}><Icon.Replace /></button>
        )}
        {runs.filter((r) => r.format !== "derived").length > 1 && (
          // T50: an icon (pressed when on) - its label did not fit beside "Open files" with two files open
          <button className="iconbtn link-toggle" aria-pressed={linkRuns} onClick={() => useApp.setState({ linkRuns: !linkRuns })}
            title={`${t("linkFiles")} - ${t("linkFilesHint")}`} aria-label={t("linkFiles")}><Icon.Link /></button>
        )}
        <span className="split-btn">
          <button className="btn outline" onClick={() => useApp.setState({ browserOpen: true })}>
            <Icon.Plus /> {t("openFiles")}
          </button>
          <button className="btn outline split-more" aria-label={t("recentMore")} title={t("recentMore")} onClick={recentMenu}>
            <Icon.Chevron width={12} height={12} />
          </button>
        </span>
      </div>
      {linkRuns && runs.filter((r) => r.format !== "derived").length > 1 && <p className="link-note">{t("linkOnNote")}</p>}
      {q.trim() !== "" && (() => {
        const matchRuns = filtered.filter((f) => f.sigs.length);
        const allIds = matchRuns.flatMap((f) => f.sigs.map((x) => x.id));
        const shown = new Set(allIds);
        const hidden = picked.filter((id) => !shown.has(id));
        return allIds.length > 0 && (
          <div className="pick-bar">
            <span>{t("nResults", { n: allIds.length })}</span>
            <button className="linklike" onClick={() => setPicked(allIds)}>{t("selectOnlyResults", { n: allIds.length })}</button>
            {matchRuns.length > 1 && (
              <select className="mini-select" value="" aria-label={t("onlyInFile")}
                onChange={(e) => { const f = matchRuns.find((x) => x.run.id === e.target.value); if (f) setPicked(f.sigs.map((x) => x.id)); }}>
                <option value="">{t("onlyInFile")}</option>
                {matchRuns.map((f) => <option key={f.run.id} value={f.run.id}>{f.run.format === "derived" ? t("derived") : fileLabel(runs, f.run.id)} ({f.sigs.length})</option>)}
              </select>
            )}
            {hidden.length > 0 && (
              <span className="pick-warn">{t("hiddenChosen", { n: hidden.length })}{" "}
                <button className="linklike" onClick={() => setPicked(picked.filter((id) => shown.has(id)))}>{t("keepOnlyResults")}</button></span>
            )}
          </div>
        );
      })()}
      {runs.length > 0 && (
        <label className="filter">
          <Icon.Search />
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder={t("searchSignals")} aria-label={t("searchSignals")} />
          {q && <button className="iconbtn" style={{ height: 20, minWidth: 20 }} onClick={() => setQ("")} aria-label={t("close")}><Icon.X /></button>}
        </label>
      )}
      <div className="tree" ref={treeRef} onScroll={(e) => setView({ top: e.currentTarget.scrollTop, height: e.currentTarget.clientHeight })}>
        {!runs.length && <p className="empty-note">{t("noFilesHint")}</p>}
        {runs.length > 0 && !anyMatch && <p className="empty-note">{t("noMatches", { q })}</p>}
        <div className="vlist" style={{ height: total }}>
          {rows.slice(first, last).map((row, i) => {
            const idx = first + i;
            const key = row.kind === "run" ? `r:${row.run.id}` : row.kind === "group" ? `g:${row.runId}|${row.key}` : `s:${row.sig.id}`;
            return <div key={key} className="vrow" style={{ top: offsets[idx], height: row.h }}>{renderRow(row)}</div>;
          })}
        </div>
      </div>
      <TemplateStrip />
      {picked.length > 0 && (
        <div className="pick-actions" role="region" aria-label={t("nChosen", { n: picked.length })}>
          <div className="pick-top">
            <span className="pick-count">{t("nChosen", { n: picked.length })}</span>
            <button className="iconbtn" onClick={() => useApp.setState({ listSel: [], listAnchor: null })} aria-label={t("clearSelection")} title={t("clearSelection")}><Icon.X /></button>
          </div>
          <div className="pick-btns">
            {/* what a selection is for: the same thing to several signals at once */}
            <button className="btn primary" onClick={() => actions.addSignals(picked)} title={t("plotSelectedHint")}>{t("plotSelected")}</button>
            <button className="btn outline" disabled={!picked.some((id) => !id.startsWith("derived/"))}
              onClick={() => useApp.setState({ transformTargets: picked.filter((id) => !id.startsWith("derived/")) })} title={t("resultEditHint")}>{t("editSelected")}</button>
            <button className="btn outline" onClick={() => useApp.setState({ analysisSeed: picked, panel: "analysis" })} title={t("resultNewHint")}>{t("newFromSelected")}</button>
          </div>
          <p className="pick-hint">{t("listSelHint")}</p>
        </div>
      )}
    </aside>
  );
}

/* ----------------------------------------------------------------- T22: unit, rate, picture */
const nameOnly = (n: string) => { const u = unitOf(n); return u ? n.replace(/\s*[[(][^[\]()]*[\])]\s*$/, "") : n; };
function fmtRate(hz: number, lang: "en" | "he"): string {
  if (hz >= 1000) return `${fmtNum(hz / 1000, lang, 2)} kHz`;
  return `${fmtNum(hz >= 10 ? Math.round(hz) : hz, lang, hz >= 10 ? 4 : 2)} Hz`;
}
const rateLine = (s: SignalInfo, lang: "en" | "he") => (s.n ? `\n${fmtInt(s.n, lang)} · ${s.rate ? fmtRate(s.rate, lang) : "-"}` : "");
function SigSpark({ id, version }: { id: string; version: string }) {
  const sp = useSpark(id, version);
  return (
    <svg className="sig-spark" width="40" height="14" viewBox="0 0 40 14" aria-hidden="true">
      {sp && <path d={sparkPath(sp, 40, 14)} />}
    </svg>
  );
}
