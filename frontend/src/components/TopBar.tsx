import { clearMenuItems } from "../clearing";
import { lazy, Suspense, useEffect, useRef, useState } from "react";
import { toggleLive } from "../live";
import { mavlinkConnect, mavlinkDisconnect } from "../mavlink";
import { linkListen, linkStop } from "../link";
import type { Structure } from "../store/model";
import { api, type LibraryItem } from "../api";
import { fmtNum } from "../i18n";
import { actions, pickPath, setInspectorByUser, useApp } from "../store";
import { PLOT_ID_MIME } from "../store/actions/layout";
import { shownTabName } from "../store/selectors";
import { AREAS, areaDef } from "../areas";
import { pageOnScreen } from "./rail";
import { useT } from "../i18n";
import { BrandMark, Icon } from "../icons";
import { openPaths, openSession, recentToOpen, refreshRecent, saveSession } from "../files";
import { copyErrorDetails, reportProblem } from "../errorReport";
import type { MenuItem, MoreTabs } from "../store";
import { openMenu } from "./Overlays";
import { copyForConfluence, dragOutEnd, dragOutStart, sendToConfluence } from "../clip";
import { addToReport } from "../reportDoc";
import { EXAMPLE_LABEL, openExample } from "./Welcome";
import { EXAMPLE_TASKS } from "../exampleTasks";
import { startTour } from "./Tour";
import { openTemplates, templateMenuItems } from "../templateMenu";
import { forgetMore, moreUsable, openMoreTabs, tx } from "../templates";
import { getPref, setPref } from "../prefs";
// the Sweeps area's open tables and its File ▾ / undo (its own code stays out of the main bundle, loaded with the area)
const SweepsTables = lazy(() => import("./sweeps/SweepsTables"));
const SweepsTools = lazy(() => import("./sweeps/SweepsTools"));


/** Where a menu opens under its button (left-aligned, or right-aligned in Hebrew). */
function menuAt(e: React.MouseEvent, w = 240) {
  const r = (e.currentTarget as HTMLElement).getBoundingClientRect();
  const rtl = document.documentElement.dir === "rtl";
  return { clientX: rtl ? Math.max(8, r.right - w) : r.left, clientY: r.bottom + 4, preventDefault() {}, stopPropagation() {} } as React.MouseEvent;
}

/** The app's top row (CC1, owner 2026-11-26: calm and clear): the name, the areas, search, the area's File ▾ (its
 *  files, session, export, links, Clear), its views, live, undo / redo, then ⚙ (language, theme, Settings) and Help.
 *  The Inspector's switch is about the plots: in the stage bar. */
export default function TopBar() {
  const t = useT();
  const area = useApp((s) => s.area);
  const at = menuAt;

  // F35 (owner, 2026-10-20): no File menu - its few entries are buttons again (opening files is
  // in the file panel and Ctrl+O): open / save session, Clear with its scopes, settings, day / night.
  // Help stays a menu (guide, shortcuts, examples, about).
  const helpMenu = async (e: React.MouseEvent) => {
    const pos = at(e);
    let ex: Awaited<ReturnType<typeof api.examples>> = [];
    try { ex = await api.examples(); } catch { /* no examples folder */ }
    const items: MenuItem[] = [
      { label: t("menuGuide"), keys: "F1", run: () => useApp.setState({ guideOpen: true }) },
      { label: t("shortcuts"), keys: "?", run: () => useApp.setState({ helpOpen: true }) },
      { label: t("menuTour"), run: startTour },
      // CC16: by task - verify, against a test, many runs, a look, bytes, flight logs (generic first)
      ...(ex.length ? [{ label: t("menuExamples"), run: () => {},
        items: EXAMPLE_TASKS.flatMap((g, k) => {
          const xs = g.ids.map((id) => ex.find((x) => x.id === id)).filter((x): x is (typeof ex)[number] => !!x);
          return xs.length ? [...(k ? [{ label: "", run: () => {}, sep: true }] : []), { label: t(g.label), run: () => {}, disabled: true },
            ...xs.map((x) => ({ label: "\u2003" + t(EXAMPLE_LABEL[x.id]), run: () => openExample(x) }))] : [];
        }) }] : []),
      { label: "", run: () => {}, sep: true },
      { label: t("copyErrorDetails"), run: () => copyErrorDetails(t, useApp.getState().toast) },
      { label: t("menuReportProblem"), run: () => reportProblem(t, useApp.getState().toast) },
      { label: t("menuAbout"), run: async () => {
        let v = "", mode = "";
        try { v = (await api.diagnostics()).version; } catch { /* offline server: no version */ }
        try { mode = (await api.windowNote()).mode || ""; } catch { /* (same) */ }
        // which engine draws the app, and in what (its own window, an Edge / Chrome app window,
        // a browser tab): the first question when a computer shows something odd
        const where = mode === "window" ? t("engineWindow") : mode === "app-window" ? t("engineAppWindow") : t("engineBrowser");
        useApp.getState().toast({ kind: "info", text: t("aboutText", { v }) + " · " + t("aboutEngine", { engine: engineName(), where }), ms: 12000 });
      } },
    ];
    openMenu(pos, items);
  };

  return (
    <header className="topbar">
      {/* the brand opens the start page - the examples and recent files - also with files open */}
      <button className="brand" title={t("startPageHint")} aria-label={t("startPage")}
        onClick={() => useApp.setState({ area: "recordings", startOpen: true })}><BrandMark /><span className="hide-compact">{t("appName")}</span></button>
      <AreaSwitcher />
      {/* C10: the Sweeps area's tables, as Recordings' tools below - one top row */}
      {area === "sweeps" && <Suspense fallback={null}><SweepsTables /></Suspense>}
      <div className="spacer" />
      <button className="search-trigger" data-tour="palette" onClick={() => useApp.setState({ paletteOpen: true, paletteMode: "all" })}>
        <Icon.Search width={14} height={14} /> <span>{t("commands")}</span><span className="kbd">Ctrl K</span>
      </button>
      {/* D1 (decision 5): one top row - the area's own tools sit here (CC1: File ▾, its views, live, undo / redo) */}
      {area === "recordings" && <RecordingsTools />}
      {area === "sweeps" && <Suspense fallback={null}><SweepsTools /></Suspense>}
      {/* CC1: the choices made once - language, theme - are in Settings (and the palette), not three buttons here */}
      <button className="iconbtn" onClick={() => useApp.setState({ settingsOpen: true })} title={`${t("settings")} (Ctrl+,)`} aria-label={t("settings")}>
        <Icon.Settings />
      </button>
      <button className="btn menubar-btn" aria-haspopup="menu" onClick={helpMenu}>{t("menuHelp")}</button>
    </header>
  );
}

/** The work areas (Mission Planner style): with one area only its name shows - no tabs to explain;
 *  the switch appears when a second area is registered in areas.ts. */
function AreaSwitcher() {
  const t = useT();
  const area = useApp((s) => s.area);
  if (AREAS.length < 2) return <span className="area-name" aria-current="page">{t(areaDef(area).label)}</span>;
  return (
    <nav className="areas" aria-label={t("workAreas")}>
      {AREAS.map((a) => (
        <button key={a.id} className={`area-btn${a.id === area ? " on" : ""}`} aria-current={a.id === area ? "page" : undefined}
          onClick={() => useApp.setState({ area: a.id })}>{t(a.label)}</button>
      ))}
    </nav>
  );
}

/** D1: the Recordings area has no bar of its own any more (one top row: its tools are in TopBar, its plot
 *  tabs in the stage bar). Kept so App's area table stays as it is. */
export function RecordingsBar() {
  return null;
}

/** The Recordings area's tools in the top row (CC1): File ▾ (open, recent, session, export, live links, Clear),
 *  Templates ▾, Live, undo / redo. Live follows the open files (and MAVLink): it is the Recordings area's, not the app's. */
function RecordingsTools() {
  const t = useT();
  const streaming = useApp((s) => s.streaming);
  const liveStarting = useApp((s) => s.liveStarting);
  const liveMenu = useApp((s) => s.liveMenuOpen);
  const setLiveMenu = (v: boolean) => useApp.setState({ liveMenuOpen: v });
  const mav = useApp((s) => s.mavlink);
  const link = useApp((s) => s.rawlink);
  const lang = useApp((s) => s.lang);
  const mavOn = !!mav?.running;
  const mavQuiet = mavOn && (mav!.sinceData == null || mav!.sinceData > 3);
  const past = useApp((s) => s.past.length);
  const future = useApp((s) => s.future.length);
  const hasRuns = useApp((s) => s.runs.some((r) => r.format !== "derived"));
  const at = menuAt;
  // review C3 + CC1: one labelled File ▾ - what is done with files and the session (the Files panel's + stays that
  // list's own add; Ctrl+O, Ctrl+S and the palette reach the same)
  const fileMenu = async (e: React.MouseEvent) => {
    const pos = at(e, 300);
    await refreshRecent();
    const recent = recentToOpen(8);
    const SEP = { label: "", run: () => {}, sep: true };
    openMenu(pos, [
      { label: `${t("openFiles")}…`, keys: "Ctrl+O", run: () => useApp.setState({ browserOpen: true }) },
      { label: `${t("openSession")}…`, keys: "Ctrl+Shift+O", run: () => { void openSession(); } },
      { label: t("recentFiles"), run: () => {}, disabled: !recent.length,
        items: recent.map((x) => ({ label: x.exists ? `${x.name}  ·  ${x.folder}` : `${x.name}  ·  ${t("notFound")}`,
          run: () => { void openPaths([x.path]); }, disabled: !x.exists })) },
      SEP,
      { label: t("saveSession"), keys: "Ctrl+S", run: saveSession },
      // E1: a part of a recording as a new file - a file action, beside Save
      { label: t("xrMenu"), disabled: !hasRuns, run: () => useApp.setState({ exportRecOpen: true }) },
      SEP,
      // T12 / LINK1: a MAVLink or byte link recorded to a file that opens and is followed live
      { label: `${t("liveSettings")}…`, run: () => setLiveMenu(true) },
      SEP,
      // T63 / F35: what to clear, from this tab to everything
      { label: t("clearMenu"), run: () => {}, items: clearMenuItems() },
    ]);
  };
  return (
    <span className="area-tools" role="toolbar" aria-label={t(areaDef("recordings").label)}>
      <button className="btn file-menu-btn" aria-haspopup="menu" aria-label={t("topFile")} title={t("topFileHint")} onClick={fileMenu}>
        <Icon.Folder /><span className="hide-compact">{t("topFile")}</span> <Icon.Chevron width={12} height={12} />
      </button>
      {hasRuns && <button className="btn tpl-menu-btn" aria-haspopup="menu" aria-label={t("tplMenu")} title={t("tplMenu")}
        onClick={(e) => openMenu(at(e), templateMenuItems(t))}>
        <Icon.Layout /><span className="hide-compact">{t("tplMenu")}</span> <Icon.Chevron width={12} height={12} />
      </button>}
      {/* Live re-reads the open files as they grow: with none open there is nothing to follow (the links: File ▾) */}
      {(hasRuns || streaming || mavOn || !!link?.running) && <span className="live-group">
        <button className={`btn live-btn${streaming ? " on" : ""}`} aria-pressed={streaming} disabled={liveStarting} onClick={toggleLive}
          title={streaming ? t("liveStopHint") : t("liveStartHint")} onContextMenu={(e) => { e.preventDefault(); setLiveMenu(true); }}>
          <Icon.Live /> {liveStarting ? t("liveStarting") : t("stream")}
        </button>
        {mavOn && (
          <button className={`btn mav-pill${mavQuiet ? " quiet" : ""}`} onClick={() => setLiveMenu(true)}
            title={mavQuiet ? t("mavNoData", { conn: mav!.conn ?? "" }) : t("mavReceiving", { conn: mav!.conn ?? "" })}>
            <span className="live-dot on" />MAVLink {mavQuiet ? "" : `${fmtNum(mav!.rate ?? 0, lang, 3)}/s`}
          </button>
        )}
      </span>}
      {liveMenu && <LiveSettings onClose={() => setLiveMenu(false)} />}
      <span className="sep" />
      <button className="iconbtn" disabled={!past} onClick={useApp.getState().undo} title={`${t("undo")} (Ctrl+Z)`} aria-label={t("undo")}><Icon.Undo /></button>
      <button className="iconbtn" disabled={!future} onClick={useApp.getState().redo} title={`${t("redo")} (Ctrl+Y)`} aria-label={t("redo")}><Icon.Redo /></button>
    </span>
  );
}

/** The Inspector's switch (CC1: about the plots - the stage bar's right end; off while a page is in the plots' place,
 *  UX5.1: the Inspector comes back with them). */
export function InspectorToggle() {
  const t = useT();
  const inspectorOpen = useApp((s) => s.inspectorOpen);
  const onPage = useApp(pageOnScreen);
  return (
    <button className="iconbtn insp-toggle" aria-pressed={inspectorOpen && !onPage} disabled={onPage} onClick={() => setInspectorByUser(!inspectorOpen)}
      aria-label={t("inspector")} title={onPage ? t("inspectorOnPage") : t("inspector")}><Icon.Inspector /></button>
  );
}

/** D1 (decision 5): the plot tabs - about the plots, so in the stage bar (StageBar renders this): rename,
 *  reorder, close, drop a plot on a tab, the views menu (+ ▾). */
export function PlotTabs() {
  const t = useT();
  const ws = useApp((s) => s.ws);
  const plotDrag = useApp((s) => s.plotDrag);
  const lang = useApp((s) => s.lang);
  const [editing, setEditing] = useState<string | null>(null);
  const at = menuAt;
  // F22: with many tabs the strip scrolls (its scrollbar is hidden): the wheel scrolls it, the active
  // tab is kept in view, and an "All tabs" list reaches every tab
  const strip = useRef<HTMLDivElement>(null);
  const [overflow, setOverflow] = useState(false);
  useEffect(() => {
    const el = strip.current;
    if (!el) return;
    const check = () => setOverflow(el.scrollWidth > el.clientWidth + 1);
    check();
    const ro = new ResizeObserver(check);
    ro.observe(el);
    return () => ro.disconnect();
  }, [ws.tabs.length]);
  useEffect(() => {
    strip.current?.querySelector<HTMLElement>(".tab.active")?.scrollIntoView({ block: "nearest", inline: "nearest" });
  }, [ws.activeTab, ws.tabs.length]);
  const onStripWheel = (e: React.WheelEvent) => {
    const el = strip.current;
    if (!el || Math.abs(e.deltaY) <= Math.abs(e.deltaX)) return;      // a horizontal wheel / touchpad scrolls by itself
    el.scrollLeft += document.documentElement.dir === "rtl" ? -e.deltaY : e.deltaY;
  };
  const allTabsMenu = (e: React.MouseEvent) => {
    const r = (e.currentTarget as HTMLElement).getBoundingClientRect();
    const rtl = document.documentElement.dir === "rtl";
    openMenu({ clientX: rtl ? Math.max(8, r.right - 240) : r.left, clientY: r.bottom + 4, preventDefault() {}, stopPropagation() {} } as React.MouseEvent,
      ws.tabs.map((tab, i) => ({ label: `${tab.id === ws.activeTab ? "✓ " : "\u2003"}${shownTabName(tab, i, lang)}`,
        run: () => actions.switchTab(tab.id) })));
  };
  // U1: the tabs a template left out, a click away - one button per template, its files still open
  const runs = useApp((s) => s.runs);
  const more = (ws.moreTabs ?? []).filter((m) => m.tabs.length && moreUsable(m, runs));
  // one button even for several templates (a section each), so the tab bar does not fill up
  const nameOf = (m: MoreTabs) => (m.builtin ? tx(m.name) : m.name);
  const moreItems = (m: MoreTabs, head: boolean): MenuItem[] => [
    ...(head ? [{ label: m.tabs.length === 1 ? t("moreTabsOne", { name: nameOf(m) }) : t("moreTabs", { n: m.tabs.length, name: nameOf(m) }), run: () => {}, disabled: true }] : []),
    ...m.tabs.map((n) => ({ label: (head ? "\u2003" : "") + (m.builtin ? tx(n) : n), run: () => { openMoreTabs(m, [n]); } })),
    ...(m.tabs.length > 1 ? [{ label: (head ? "\u2003" : "") + t("moreTabsAll", { n: m.tabs.length }), run: () => { openMoreTabs(m, m.tabs); } }] : []),
    { label: (head ? "\u2003" : "") + t("moreTabsDismiss"), run: () => forgetMore(m.tpl) },
  ];
  // U9 (owner, 2026-11-07): one menu for views - a new one, from a template, and the tabs templates
  // left out (U1's "+N more", a section per template)
  const viewsMenu = (e: React.MouseEvent) => openMenu(at(e, 280), [
    { label: t("addTab"), run: actions.addTab },
    { label: t("tplMenuOpen"), run: () => openTemplates() },
    ...more.flatMap((m) => [{ label: "", run: () => {}, sep: true }, ...moreItems(m, true)]),
  ]);
  const moreN = more.reduce((a, m) => a + m.tabs.length, 0);
  const moreLabel = more.length > 1 ? t("moreTabsN", { n: moreN })
    : more.length ? (moreN === 1 ? t("moreTabsOne", { name: nameOf(more[0]) }) : t("moreTabs", { n: moreN, name: nameOf(more[0]) })) : "";

  return (
    <nav className="tabs-wrap">
      <div className="tabs" role="tablist" ref={strip} onWheel={onStripWheel}>
        {ws.tabs.map((tab, i) => {
          const name = shownTabName(tab, i, lang);
          return (
            <div key={tab.id} role="tab" aria-selected={tab.id === ws.activeTab} tabIndex={0} draggable
              onDragStart={(e) => { e.dataTransfer.setData("application/x-sv-tab", tab.id); e.dataTransfer.effectAllowed = "copyMove"; dragOutStart(e, tab, undefined, name); }}
              onDragEnd={(e) => dragOutEnd(e, tab)}
              onDragOver={(e) => {
                if (e.dataTransfer.types.includes("application/x-sv-tab")) e.preventDefault();
                // L10: a plot dragged by its handle moves to this tab (Ctrl: a copy)
                if (e.dataTransfer.types.includes(PLOT_ID_MIME)) { e.preventDefault(); e.dataTransfer.dropEffect = e.ctrlKey ? "copy" : "move"; e.currentTarget.classList.add("plot-drop"); }
              }}
              onDragLeave={(e) => e.currentTarget.classList.remove("plot-drop")}
              onDrop={(e) => {
                e.currentTarget.classList.remove("plot-drop");
                const pid = e.dataTransfer.getData(PLOT_ID_MIME);
                if (pid) { e.preventDefault(); useApp.setState({ plotDrag: null }); actions.movePlotToTab(pid, tab.id, undefined, e.ctrlKey); return; }
                const id = e.dataTransfer.getData("application/x-sv-tab"); if (id) actions.moveTab(id, i);
              }}
              onContextMenu={(e) => openMenu(e, [
                { label: t("renameTab"), run: () => setEditing(tab.id) },
                { label: t("duplicateTab"), run: () => actions.duplicateTab(tab.id) },
                { label: t("saveTemplate") + "…", run: () => { actions.switchTab(tab.id); useApp.setState({ templatesOpen: true, templatesNew: "tab" }); } },
                { label: t("cfSendTab"), run: () => { void sendToConfluence(tab); } },   // CP4
                { label: t("clipTab"), run: () => { void copyForConfluence(tab); } },   // CP1
                { label: t("rdAddToReport"), run: () => addToReport(tab) },   // RE1
                { label: "", run: () => {}, sep: true },
                { label: t("closeTab"), run: () => actions.closeTab(tab.id) },
                { label: t("closeOthers"), run: () => actions.closeOtherTabs(tab.id), disabled: ws.tabs.length < 2 },
              ])}
              className={`tab${tab.id === ws.activeTab ? " active" : ""}${plotDrag ? " plot-drop-ok" : ""}`}
              onClick={() => actions.switchTab(tab.id)}
              onDoubleClick={() => setEditing(tab.id)}
              // middle click closes the tab. On mousedown/up, not auxclick: on Windows (Edge / WebView2) a
              // middle press over the scrollable tab strip starts autoscroll and no auxclick follows
              onMouseDown={(e) => { if (e.button === 1) e.preventDefault(); }}
              onMouseUp={(e) => { if (e.button === 1) { e.preventDefault(); actions.closeTab(tab.id); } }}
              onKeyDown={(e) => { if (e.key === "Enter") actions.switchTab(tab.id); if (e.key === "F2") setEditing(tab.id); }}>
              {editing === tab.id ? (
                <input autoFocus defaultValue={tab.name} placeholder={name} onClick={(e) => e.stopPropagation()}
                  onBlur={(e) => { actions.renameTab(tab.id, e.target.value.trim()); setEditing(null); }}
                  onKeyDown={(e) => { if (e.key === "Enter") (e.target as HTMLInputElement).blur(); if (e.key === "Escape") setEditing(null); }} />
              ) : <span>{name}</span>}
              <span className="x" role="button" aria-label={t("closeTab")} title={t("closeTab")}
                onClick={(e) => { e.stopPropagation(); actions.closeTab(tab.id); }}><Icon.X width={12} height={12} /></span>
            </div>
          );
        })}
      </div>
        {overflow && (
          <button className="iconbtn tabs-all" aria-haspopup="menu" onClick={allTabsMenu}
            title={t("allTabs", { n: ws.tabs.length })} aria-label={t("allTabs", { n: ws.tabs.length })}>
            <Icon.Chevron width={14} height={14} /><span className="tabs-count">{ws.tabs.length}</span>
          </button>
        )}
        <span className="add-view">
          <button className="iconbtn" onClick={actions.addTab} title={t("addTab")} aria-label={t("addTab")}
            onContextMenu={viewsMenu}><Icon.Plus /></button>
          <button className={`iconbtn more-tabs${moreN ? " has" : ""}`} aria-haspopup="menu" onClick={viewsMenu}
            title={moreN ? `${t("viewsMenu")}\n${moreLabel}` : t("viewsMenu")} aria-label={moreN ? moreLabel : t("viewsMenu")}>
            <Icon.Chevron width={12} height={12} />{moreN > 0 && <span className="more-count">{t("moreViewsBadge", { n: moreN })}</span>}
          </button>
        </span>
      </nav>
  );
}


/** Live mode settings: when to stop by itself, and what to do with new files in the same folders. */
function LiveSettings({ onClose }: { onClose: () => void }) {
  const anchor = (document.querySelector(".live-btn") ?? document.querySelector(".file-menu-btn"))?.getBoundingClientRect() ?? null;
  const t = useT();
  const box = useRef<HTMLDivElement>(null);
  const autoStop = useApp((s) => s.liveAutoStop);
  const newFiles = useApp((s) => s.liveNewFiles);
  useEffect(() => {
    const off = (e: MouseEvent) => { if (!box.current?.contains(e.target as Node)) onClose(); };
    window.addEventListener("mousedown", off);
    return () => window.removeEventListener("mousedown", off);
  }, [onClose]);
  const rtl = document.documentElement.dir === "rtl";
  const style: React.CSSProperties = anchor ? { position: "fixed", top: anchor.bottom + 6,
    ...(rtl ? { left: anchor.left } : { right: window.innerWidth - anchor.right }) } : {};
  return (
    <div className="popover live-pop" ref={box} style={style} role="dialog" aria-label={t("liveSettings")}
      onKeyDown={(e) => { if (e.key === "Escape") onClose(); }}>
      <h3>{t("liveSettings")}</h3>
      <p className="hint">{t("liveExplain")}</p>
      <label>{t("liveAutoStop")}
        <select value={autoStop ?? ""} onChange={(e) => useApp.setState({ liveAutoStop: e.target.value ? Number(e.target.value) : null })}>
          {[10, 30, 60, 300, 900].map((v) => <option key={v} value={v}>{v < 60 ? `${v} ${t("seconds")}` : `${v / 60} ${t("minutes")}`}</option>)}
          <option value="">{t("never")}</option>
        </select></label>
      <label>{t("liveNewFiles")}
        <select value={newFiles} onChange={(e) => useApp.setState({ liveNewFiles: e.target.value as "ask" | "auto" | "ignore" })}>
          <option value="ask">{t("newFilesAsk")}</option>
          <option value="auto">{t("newFilesAuto")}</option>
          <option value="ignore">{t("newFilesIgnore")}</option>
        </select></label>
      {/* "Follow" acts on the plots on screen: it lives in the StageBar while live (one place) */}
      <MavlinkSection />
      <LinkSection />
    </div>
  );
}

/** T12: receive MAVLink from a link (UDP / TCP / serial). The link is recorded to a .tlog that
 *  opens as a file and is followed by live mode. Read-only unless "ask for data" is on. */
function MavlinkSection() {
  const t = useT();
  const mav = useApp((s) => s.mavlink);
  const [conn, setConn] = useState(() => getPref("sv3.mavConn") || "udpin:127.0.0.1:14550");
  const [baud, setBaud] = useState(57600);
  const [request, setRequest] = useState(false);
  const [busy, setBusy] = useState(false);
  const [ports, setPorts] = useState<{ device: string; description: string }[]>([]);
  const [presets, setPresets] = useState<string[]>([]);
  useEffect(() => { api.mavlinkPorts().then((r) => { setPorts(r.ports); setPresets(r.presets); }).catch(() => {}); }, []);
  const serial = !/^(udp|udpin|udpout|udpbcast|tcp|tcpin):/i.test(conn.trim());
  const on = !!mav?.running;
  const connect = async () => {
    setBusy(true);
    setPref("sv3.mavConn", conn.trim());
    await mavlinkConnect(conn.trim(), { baud, request });
    setBusy(false);
  };
  return (
    <div className="mav-section">
      <h3>{t("mavTitle")}</h3>
      {!on ? <>
        <label>{t("mavConn")}
          <input list="mav-conns" value={conn} onChange={(e) => setConn(e.target.value)} spellCheck={false} dir="ltr" aria-label={t("mavConn")} />
          <datalist id="mav-conns">
            {presets.map((p) => <option key={p} value={p} />)}
            {ports.map((p) => <option key={p.device} value={p.device}>{p.description}</option>)}
          </datalist></label>
        <p className="hint">{t("mavConnHint")}</p>
        {serial && <label>{t("mavBaud")}
          <select value={baud} onChange={(e) => setBaud(Number(e.target.value))}>
            {[57600, 115200, 230400, 460800, 921600].map((b) => <option key={b} value={b}>{b}</option>)}
          </select></label>}
        <label className="acheck"><input type="checkbox" checked={request} onChange={(e) => setRequest(e.target.checked)} />{t("mavRequest")}</label>
        <p className="hint">{t("mavRequestHint")}</p>
        <button className="btn primary" disabled={busy || !conn.trim()} onClick={connect}>{t("mavConnect")}</button>
      </> : <>
        <p className="mav-status" dir="ltr">{mav!.conn}</p>
        <p className="hint">{mav!.sinceData == null ? t("mavWaiting") : t("mavStats", { n: mav!.frames ?? 0, kb: Math.round((mav!.bytes ?? 0) / 1024) })}
          {mav!.error ? ` · ${mav!.error}` : ""}</p>
        <p className="hint mav-path" dir="ltr" title={mav!.path}>{mav!.path}</p>
        <button className="btn outline" onClick={() => mavlinkDisconnect()}>{t("mavDisconnect")}</button>
      </>}
    </div>
  );
}

/** LINK1: listen to a byte link - a serial port (UART), UDP, TCP - recorded to a .svraw that opens as a file and is
 *  followed live, its messages decoded by a structure (NMEA, a .svmsg.json, one kept in the session) or kept as bytes. */
function LinkSection() {
  const t = useT();
  const link = useApp((s) => s.rawlink);
  const keptRaw = useApp((s) => s.ws.messageStreams);
  const kept = keptRaw ?? [];
  const [conn, setConn] = useState(() => getPref("sv3.linkConn") || "udp:0.0.0.0:5600");
  const [baud, setBaud] = useState(115200);
  const [busy, setBusy] = useState(false);
  const [ports, setPorts] = useState<{ device: string; description: string }[]>([]);
  const [presets, setPresets] = useState<string[]>([]);
  const [how, setHow] = useState<string>("none");          // none | lib:<key> | file | kept:<i>:<label>
  const [file, setFile] = useState<{ path: string; structure: Structure } | null>(null);
  const [lib, setLib] = useState<LibraryItem[]>([]);         // MSG3: the structure library (NMEA built in among them)
  useEffect(() => { api.linkPorts().then((r) => { setPorts(r.ports); setPresets(r.presets); }).catch(() => {}); }, []);
  useEffect(() => { api.messagesLibrary().then((r) => setLib(r.items.filter((i) => !i.error))).catch(() => {}); }, []);
  const serial = !/^(udp|udpin|tcp|tcpin):/i.test(conn.trim());
  const keptOpts = kept.flatMap((m, i) => Object.entries(m.structures ?? {}).map(([lab, s]) => ({ key: `kept:${i}:${lab}`, label: `${s.name || lab} (${lab})`, s })));
  const choose = async (v: string) => {
    if (v === "file") {
      const p = await pickPath({ mode: "open", title: t("msgStructFile"), exts: [".json"] });
      if (!p) return;
      try { setFile({ path: p, structure: (await api.messagesStructure(p)).structure }); } catch (e) {
        useApp.getState().toast({ kind: "error", text: String((e as Error).message) }); return;
      }
    }
    setHow(v);
  };
  const listen = async () => {
    setBusy(true);
    setPref("sv3.linkConn", conn.trim());
    let structure: Structure | null | undefined = null;
    try {
      structure = how.startsWith("lib:") ? (await api.messagesLibraryGet(how.slice(4))).structure : how === "file" ? file?.structure
        : keptOpts.find((o) => o.key === how)?.s ?? null;
    } catch (e) {
      useApp.getState().toast({ kind: "error", text: String((e as Error).message) });
      setBusy(false);
      return;
    }
    await linkListen(conn.trim(), { baud, structure });
    setBusy(false);
  };
  const on = !!link?.running;
  return (
    <div className="mav-section link-section">
      <h3>{t("linkTitle")}</h3>
      {!on ? <>
        <label>{t("mavConn")}
          <input list="link-conns" className="link-conn" value={conn} onChange={(e) => setConn(e.target.value)} spellCheck={false} dir="ltr" aria-label={t("linkTitle")} />
          <datalist id="link-conns">
            {presets.map((p) => <option key={p} value={p} />)}
            {ports.map((p) => <option key={p.device} value={p.device}>{p.description}</option>)}
          </datalist></label>
        <p className="hint">{t("linkConnHint")}</p>
        {serial && <label>{t("mavBaud")}
          <select value={baud} onChange={(e) => setBaud(Number(e.target.value))}>
            {[4800, 9600, 19200, 38400, 57600, 115200, 230400, 460800, 921600].map((b) => <option key={b} value={b}>{b}</option>)}
          </select></label>}
        <label>{t("linkStructure")}
          <select className="link-structure" value={how} onChange={(e) => void choose(e.target.value)}>
            <option value="none">{t("linkNone")}</option>
            {lib.map((i) => <option key={i.key} value={`lib:${i.key}`}>{i.name}</option>)}
            <option value="file">{file ? file.path.split(/[\\/]/).pop() : t("linkFile")}</option>
            {keptOpts.map((o) => <option key={o.key} value={o.key}>{o.label}</option>)}
          </select></label>
        <button className="btn primary link-listen" disabled={busy || !conn.trim()} onClick={listen}>{t("linkListen")}</button>
      </> : <>
        <p className="mav-status" dir="ltr">{link!.conn}{link!.peer ? ` ← ${link!.peer}` : ""}</p>
        <p className="hint">{link!.sinceData == null ? t("mavWaiting") : t("linkStats", { kb: Math.round((link!.bytes ?? 0) / 1024), rate: Math.round(link!.rate ?? 0) })}
          {link!.error ? ` · ${link!.error}` : ""}</p>
        <p className="hint mav-path" dir="ltr" title={link!.path}>{link!.path}</p>
        <button className="btn outline link-stop" onClick={() => linkStop()}>{t("linkStopBtn")}</button>
      </>}
    </div>
  );
}

/** The web engine from the user agent: WebView2 and Edge say Edg/, Chrome Chrome/. */
function engineName(): string {
  const ua = navigator.userAgent;
  const m = /Edg\/(\d+)/.exec(ua) || /Chrome\/(\d+)/.exec(ua) || /Firefox\/(\d+)/.exec(ua);
  if (!m) return ua;
  return (ua.includes("Edg/") ? "Edge / WebView2 " : ua.includes("Firefox/") ? "Firefox " : "Chrome ") + m[1];
}
