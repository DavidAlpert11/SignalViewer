import { clearMenuItems } from "../clearing";
import { useEffect, useRef, useState } from "react";
import { toggleLive } from "../live";
import { mavlinkConnect, mavlinkDisconnect } from "../mavlink";
import { api } from "../api";
import { fmtNum } from "../i18n";
import { actions, setInspectorByUser, useApp } from "../store";
import { useT } from "../i18n";
import { BrandMark, Icon } from "../icons";
import { openPaths, openSession, saveSession } from "../files";
import { copyErrorDetails } from "../errorReport";
import type { MenuItem } from "../store";
import { openMenu } from "./Overlays";
import { templateMenuItems } from "../templateMenu";
import { getPref, setPref } from "../prefs";

export default function TopBar() {
  const t = useT();
  const ws = useApp((s) => s.ws);
  const past = useApp((s) => s.past.length);
  const future = useApp((s) => s.future.length);
  const streaming = useApp((s) => s.streaming);
  const inspectorOpen = useApp((s) => s.inspectorOpen);
  const [editing, setEditing] = useState<string | null>(null);
  const liveStarting = useApp((s) => s.liveStarting);
  const liveMenu = useApp((s) => s.liveMenuOpen);
  const setLiveMenu = (v: boolean) => useApp.setState({ liveMenuOpen: v });
  const mav = useApp((s) => s.mavlink);
  const lang = useApp((s) => s.lang);
  const theme = useApp((s) => s.theme);
  const mavOn = !!mav?.running;
  const mavQuiet = mavOn && (mav!.sinceData == null || mav!.sinceData > 3);
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
      ws.tabs.map((tab, i) => ({ label: `${tab.id === ws.activeTab ? "✓ " : "\u2003"}${tab.name || `${t("tab")} ${i + 1}`}`,
        run: () => actions.switchTab(tab.id) })));
  };

  // F35 (owner, 2026-10-20): no File menu - its few entries are buttons again (opening files is
  // in the file panel and Ctrl+O): open / save session, Clear with its scopes, settings, day / night.
  // Help stays a menu (guide, shortcuts, examples, about).
  const at = (e: React.MouseEvent, w = 240) => {
    const r = (e.currentTarget as HTMLElement).getBoundingClientRect();
    const rtl = document.documentElement.dir === "rtl";
    return { clientX: rtl ? Math.max(8, r.right - w) : r.left, clientY: r.bottom + 4, preventDefault() {}, stopPropagation() {} } as React.MouseEvent;
  };
  const helpMenu = async (e: React.MouseEvent) => {
    const pos = at(e);
    let ex: Awaited<ReturnType<typeof api.examples>> = [];
    try { ex = await api.examples(); } catch { /* no examples folder */ }
    const EX = { flight: "exampleFlight", twoFlights: "exampleTwoFlights", car: "exampleCar", ardupilot: "exampleArdupilot" } as const;
    const items: MenuItem[] = [
      { label: t("menuGuide"), keys: "F1", run: () => useApp.setState({ guideOpen: true }) },
      { label: t("shortcuts"), keys: "?", run: () => useApp.setState({ helpOpen: true }) },
      ...(ex.length ? [{ label: t("menuExamples"), run: () => {},
        items: ex.map((x) => ({ label: t(EX[x.id]), run: () => openPaths(x.paths, undefined, { autoView: true }) })) }] : []),
      { label: "", run: () => {}, sep: true },
      { label: t("copyErrorDetails"), run: () => copyErrorDetails(t, useApp.getState().toast) },
      { label: t("menuAbout"), run: async () => {
        let v = "";
        try { v = (await api.diagnostics()).version; } catch { /* offline server: no version */ }
        useApp.getState().toast({ kind: "info", text: t("aboutText", { v }), ms: 12000 });
      } },
    ];
    openMenu(pos, items);
  };

  return (
    <header className="topbar">
      <div className="brand" title={t("appName")}><BrandMark /><span className="hide-compact">{t("appName")}</span></div>
      <button className="iconbtn" onClick={() => openSession()} title={`${t("openSession")}… (Ctrl+Shift+O)`} aria-label={t("openSession")}><Icon.Open /></button>
      <button className="iconbtn" onClick={saveSession} title={`${t("saveSession")} (Ctrl+S)`} aria-label={t("saveSession")}><Icon.Save /></button>
      <nav className="tabs-wrap">
      <div className="tabs" role="tablist" ref={strip} onWheel={onStripWheel}>
        {ws.tabs.map((tab, i) => {
          const name = tab.name || `${t("tab")} ${i + 1}`;
          return (
            <div key={tab.id} role="tab" aria-selected={tab.id === ws.activeTab} tabIndex={0} draggable
              onDragStart={(e) => e.dataTransfer.setData("application/x-sv-tab", tab.id)}
              onDragOver={(e) => { if (e.dataTransfer.types.includes("application/x-sv-tab")) e.preventDefault(); }}
              onDrop={(e) => { const id = e.dataTransfer.getData("application/x-sv-tab"); if (id) actions.moveTab(id, i); }}
              onContextMenu={(e) => openMenu(e, [
                { label: t("renameTab"), run: () => setEditing(tab.id) },
                { label: t("duplicateTab"), run: () => actions.duplicateTab(tab.id) },
                { label: t("saveTemplate") + "…", run: () => { actions.switchTab(tab.id); useApp.setState({ templatesOpen: true, templatesNew: "tab" }); } },
                { label: "", run: () => {}, sep: true },
                { label: t("closeTab"), run: () => actions.closeTab(tab.id) },
                { label: t("closeOthers"), run: () => actions.closeOtherTabs(tab.id), disabled: ws.tabs.length < 2 },
              ])}
              className={`tab${tab.id === ws.activeTab ? " active" : ""}`}
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
        <button className="iconbtn" onClick={actions.addTab} title={t("addTab")} aria-label={t("addTab")}
          onContextMenu={(e) => openMenu(e, [{ label: t("addTab"), run: actions.addTab }])}><Icon.Plus /></button>
      </nav>
      <button className="btn tpl-menu-btn" aria-haspopup="menu" aria-label={t("tplMenu")}
        onClick={(e) => { const r = (e.currentTarget as HTMLElement).getBoundingClientRect();
          openMenu({ clientX: document.documentElement.dir === "rtl" ? Math.max(8, r.right - 240) : r.left, clientY: r.bottom + 4, preventDefault() {}, stopPropagation() {} } as React.MouseEvent, templateMenuItems(t)); }}>
        <Icon.Layout /> {t("tplMenu")} <Icon.Chevron width={12} height={12} />
      </button>
      <div className="spacer" />
      <button className="search-trigger" onClick={() => useApp.setState({ paletteOpen: true, paletteMode: "all" })}>
        <Icon.Search width={14} height={14} /> <span>{t("commands")}</span><span className="kbd">Ctrl K</span>
      </button>
      <span className="sep" />
      <button className="iconbtn" disabled={!past} onClick={useApp.getState().undo} title={`${t("undo")} (Ctrl+Z)`} aria-label={t("undo")}><Icon.Undo /></button>
      <button className="iconbtn" disabled={!future} onClick={useApp.getState().redo} title={`${t("redo")} (Ctrl+Y)`} aria-label={t("redo")}><Icon.Redo /></button>
      {/* T63 / F35: one Clear button, what to clear in its menu (this tab ... everything) */}
      <button className="btn clear-btn" aria-haspopup="menu" title={t("clearMenuHint")} aria-label={t("clearMenu")}
        onClick={(e) => openMenu(at(e, 320), clearMenuItems())}>
        <Icon.Eraser /><span className="hide-narrow">{t("clearMenu")}</span><Icon.Chevron width={12} height={12} />
      </button>
      <span className="sep" />
      <span className="live-group">
        <button className={`btn live-btn${streaming ? " on" : ""}`} aria-pressed={streaming} disabled={liveStarting} onClick={toggleLive}
          title={streaming ? t("liveStopHint") : t("liveStartHint")}>
          <Icon.Live /> {liveStarting ? t("liveStarting") : t("stream")}
        </button>
        <button className="iconbtn live-more" aria-expanded={liveMenu} aria-label={t("liveSettings")} title={t("liveSettings")}
          onClick={() => setLiveMenu(!liveMenu)}>
          <Icon.Chevron width={12} height={12} />
        </button>
        {mavOn && (
          <button className={`btn mav-pill${mavQuiet ? " quiet" : ""}`} onClick={() => setLiveMenu(true)}
            title={mavQuiet ? t("mavNoData", { conn: mav!.conn ?? "" }) : t("mavReceiving", { conn: mav!.conn ?? "" })}>
            <span className="live-dot on" />MAVLink {mavQuiet ? "" : `${fmtNum(mav!.rate ?? 0, lang, 3)}/s`}
          </button>
        )}
        {liveMenu && <LiveSettings onClose={() => setLiveMenu(false)} />}
      </span>
      <button className="iconbtn" onClick={() => useApp.setState({ settingsOpen: true })} title={`${t("settings")} (Ctrl+,)`} aria-label={t("settings")}>
        <Icon.Settings />
      </button>
      <button className="iconbtn theme-btn" aria-pressed={theme === "dark"} onClick={() => useApp.setState({ theme: theme === "dark" ? "light" : "dark" })}
        title={`${t("theme")}: ${theme === "dark" ? t("dark") : t("light")}`} aria-label={t("theme")}>
        {theme === "dark" ? <Icon.Moon /> : <Icon.Sun />}
      </button>
      <button className="btn" onClick={() => useApp.setState({ lang: useApp.getState().lang === "he" ? "en" : "he" })}
        title={t("language")} aria-label={t("language")}>
        <Icon.Globe /><span className="hide-compact">{t("language")}</span>
      </button>
      <button className="btn menubar-btn" aria-haspopup="menu" onClick={helpMenu}>{t("menuHelp")}</button>
      <button className="iconbtn" aria-pressed={inspectorOpen} onClick={() => setInspectorByUser(!inspectorOpen)} aria-label={t("inspector")} title={t("inspector")}><Icon.Inspector /></button>
    </header>
  );
}

/** Live mode settings: when to stop by itself, and what to do with new files in the same folders. */
function LiveSettings({ onClose }: { onClose: () => void }) {
  const anchor = document.querySelector(".live-more")?.getBoundingClientRect() ?? null;
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
