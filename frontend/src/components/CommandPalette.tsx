import { useEffect, useMemo, useRef, useState } from "react";
import { refreshAll, toggleLive } from "../live";
import { mavlinkDisconnect } from "../mavlink";
import { actions, activeTab, useApp } from "../store";
import { useT } from "../i18n";
import { newCollection, openTemplates, saveAsTemplate } from "../templateMenu";
import { Icon } from "../icons";
import { clearEverything, openPaths, openSession, pickSessionForRetarget, recentToOpen, refreshRecent, saveSession, startRetarget } from "../files";
import { api, type FsPlaces } from "../api";
import { fuzzySort } from "../fuzzy";

interface Cmd { id: string; label: string; group: string; icon?: React.ReactNode; run: () => void; keys?: string }

export default function CommandPalette() {
  const t = useT();
  const open = useApp((s) => s.paletteOpen);
  const mode = useApp((s) => s.paletteMode);
  const [places, setPlaces] = useState<FsPlaces | null>(null);
  useApp((s) => s.recent);
  useEffect(() => {
    if (!open || mode !== "open") return;
    refreshRecent();
    api.places().then(setPlaces).catch(() => setPlaces(null));
  }, [open, mode]);
  const runs = useApp((s) => s.runs);
  const [q, setQ] = useState("");
  const [sel, setSel] = useState(0);
  const listRef = useRef<HTMLDivElement>(null);

  const close = () => { useApp.setState({ paletteOpen: false, paletteMode: "all" }); setQ(""); setSel(0); };

  const cmds = useMemo<Cmd[]>(() => {
    const st = () => useApp.getState();
    const base: Cmd[] = [
      { id: "open", label: t("openFiles"), group: t("files"), icon: <Icon.Folder />, run: () => useApp.setState({ browserOpen: true }), keys: "Ctrl O" },
      { id: "quickopen", label: t("quickOpen"), group: t("files"), icon: <Icon.Folder />, run: () => window.setTimeout(() => useApp.setState({ paletteOpen: true, paletteMode: "open" }), 0), keys: "Ctrl P" },
      { id: "savesession", label: t("saveSession"), group: t("files"), icon: <Icon.Save />, run: saveSession, keys: "Ctrl S" },
      { id: "opensession", label: t("openSession"), group: t("files"), icon: <Icon.Open />, run: () => openSession(), keys: "Ctrl ⇧ O" },
      { id: "retarget-current", label: t("replaceInputFiles"), group: t("files"), icon: <Icon.Replace />, run: () => startRetarget() },
      { id: "retarget-session", label: t("openSessionNewFiles"), group: t("files"), icon: <Icon.Replace />, run: pickSessionForRetarget },
      { id: "templates", label: t("tplMenuOpen"), group: t("templates"), icon: <Icon.Layout />, run: () => openTemplates() },
      { id: "tplSave", label: t("tplMenuSave"), group: t("templates"), icon: <Icon.Save />, run: saveAsTemplate },
      { id: "tplCollection", label: t("tplMenuCollection"), group: t("templates"), icon: <Icon.Layout />, run: newCollection },
      { id: "clearall", label: t("clearEverything"), group: t("files"), icon: <Icon.Trash />, run: clearEverything },
      { id: "compare", label: t("compare"), group: t("compare"), icon: <Icon.Compare />, run: () => useApp.setState({ panel: "compare" }) },
      { id: "report", label: t("report"), group: t("report"), icon: <Icon.Report />, run: () => useApp.setState({ panel: "report" }) },
      { id: "fleet", label: t("fleet"), group: t("fleet"), icon: <Icon.Fleet />, run: () => useApp.setState({ panel: "fleet" }) },
      { id: "analysis", label: t("analysis"), group: t("analysis"), icon: <Icon.Analysis />, run: () => useApp.setState({ panel: "analysis" }) },
      { id: "guide", label: t("menuGuide"), group: t("hHelp"), icon: <Icon.Keyboard />, run: () => useApp.setState({ guideOpen: true }), keys: "F1" },
      { id: "help", label: t("shortcuts"), group: t("hHelp"), icon: <Icon.Keyboard />, run: () => useApp.setState({ helpOpen: true }), keys: "?" },
      { id: "text1", label: `${t("hTextSize")}: 100%`, group: t("hHelp"), icon: <Icon.Globe />, run: () => useApp.setState({ uiScale: 1 }) },
      { id: "text2", label: `${t("hTextSize")}: 112%`, group: t("hHelp"), icon: <Icon.Globe />, run: () => useApp.setState({ uiScale: 1.12 }) },
      { id: "text3", label: `${t("hTextSize")}: 125%`, group: t("hHelp"), icon: <Icon.Globe />, run: () => useApp.setState({ uiScale: 1.25 }) },
      { id: "tab", label: t("addTab"), group: t("tab"), icon: <Icon.Plus />, run: actions.addTab },
      { id: "duptab", label: t("duplicateTab"), group: t("tab"), icon: <Icon.Copy />, run: () => actions.duplicateTab(st().ws.activeTab) },
      { id: "clearplots", label: t("clearAll"), group: t("tab"), icon: <Icon.Eraser />, run: actions.clearAllPlots },
      { id: "closetab", label: t("closeTab"), group: t("tab"), icon: <Icon.X />, run: () => actions.closeTab(st().ws.activeTab) },
      // F22: every tab is reachable by name, however many there are
      ...st().ws.tabs.map((tb, i) => ({ id: `goto-${tb.id}`, label: t("goToTab", { name: tb.name || `${t("tab")} ${i + 1}` }), group: t("tab"),
        icon: <Icon.Layout />, run: () => actions.switchTab(tb.id) })),
      { id: "cursor", label: t("cursor"), group: t("cursor"), icon: <Icon.Cursor />, run: actions.toggleCursor, keys: "Space" },
      { id: "dual", label: t("dualCursor"), group: t("cursor"), icon: <Icon.Dual />, run: actions.toggleDual, keys: "D" },
      { id: "reset", label: t("resetZoom"), group: t("plot"), icon: <Icon.Reset />, run: actions.resetZoom, keys: "R" },
      { id: "link", label: t("linkX"), group: t("plot"), icon: <Icon.Link />, run: actions.toggleLinkX },
      { id: "undo", label: t("undo"), group: t("undo"), icon: <Icon.Undo />, run: () => st().undo(), keys: "Ctrl Z" },
      { id: "redo", label: t("redo"), group: t("undo"), icon: <Icon.Redo />, run: () => st().redo(), keys: "Ctrl Y" },
      { id: "theme", label: `${t("theme")}: ${st().theme === "dark" ? t("light") : t("dark")}`, group: t("theme"), icon: <Icon.Sun />, run: () => useApp.setState({ theme: st().theme === "dark" ? "light" : "dark" }) },
      { id: "lang", label: t("language"), group: t("theme"), icon: <Icon.Globe />, run: () => useApp.setState({ lang: st().lang === "he" ? "en" : "he" }) },
      { id: "live", label: t("stream"), group: t("files"), icon: <Icon.Live />, run: toggleLive },
      useApp.getState().mavlink?.running
        ? { id: "mav-off", label: t("mavCmdDisconnect"), group: t("files"), icon: <Icon.Live />, run: () => { mavlinkDisconnect(); } }
        : { id: "mav-on", label: t("mavCmdConnect"), group: t("files"), icon: <Icon.Live />, run: () => useApp.setState({ liveMenuOpen: true }) },
      { id: "refreshall", label: t("refreshAll"), group: t("files"), icon: <Icon.Reload />, run: () => { refreshAll(); }, keys: "F5" },
      { id: "zoomx", label: t("zoomX"), group: t("plot"), icon: <Icon.Reset />, run: () => actions.setZoomMode("x"), keys: "Z" },
      { id: "zoomy", label: t("zoomY"), group: t("plot"), icon: <Icon.Reset />, run: () => actions.setZoomMode("y"), keys: "Z" },
      { id: "zoomxy", label: t("zoomXY"), group: t("plot"), icon: <Icon.Reset />, run: () => actions.setZoomMode("xy"), keys: "Z" },
    ];
    for (const [r, c] of [[1, 1], [2, 1], [3, 1], [4, 1], [2, 2]] as const)
      base.push({ id: `layout${r}${c}`, label: `${t("layout")} ${r} × ${c}`, group: t("layout"), icon: <Icon.Layout />, run: () => actions.setLayout(r, c) });
    for (const run of runs)
      for (const s of run.signals)
        base.push({ id: s.id, label: s.name, group: run.name, icon: <Icon.Analysis />, run: () => actions.addSignal(s.id) });
    return base;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [runs, open, t]);

  // T24: quick open (Ctrl+P) - favourites, recent folders (open in the file dialog), recent files
  const quick: Cmd[] = [];
  if (mode === "open") {
    const folder = (p: string) => () => useApp.setState({ browserOpen: true, browserStart: p });
    const seen = new Set<string>();
    const once = (p: string) => { const k = p.toLowerCase(); if (seen.has(k)) return false; seen.add(k); return true; };
    for (const f of places?.favourites ?? []) if (f.exists && once(f.path)) quick.push({ id: `fav:${f.path}`, label: f.path, group: t("placesFav"), icon: <Icon.Folder />, run: folder(f.path) });
    for (const r of recentToOpen(12)) if (r.exists) quick.push({ id: `file:${r.path}`, label: r.name, group: r.folder, icon: <Icon.File />, run: () => { openPaths([r.path]); } });
    for (const f of places?.recent ?? []) if (f.exists && once(f.path)) quick.push({ id: `dir:${f.path}`, label: f.path, group: t("placesRecent"), icon: <Icon.Folder />, run: folder(f.path) });
  }
  const items = fuzzySort(mode === "open" ? quick : cmds, (c) => `${c.label} ${c.group}`, q).slice(0, 60);

  useEffect(() => { setSel(0); }, [q]);
  useEffect(() => { listRef.current?.querySelector(".pal-item.on")?.scrollIntoView({ block: "nearest" }); }, [sel]);

  if (!open) return null;
  const tab = activeTab(useApp.getState().ws);
  return (
    <div className="scrim" onMouseDown={close}>
      <div className="dialog" role="dialog" aria-label={t("commands")} onMouseDown={(e) => e.stopPropagation()}>
        <input className="palette-input" autoFocus value={q} placeholder={mode === "open" ? t("quickOpen") : t("commands")} aria-label={mode === "open" ? t("quickOpen") : t("commands")}
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Escape") close();
            else if (e.key === "ArrowDown") { e.preventDefault(); setSel((s) => Math.min(items.length - 1, s + 1)); }
            else if (e.key === "ArrowUp") { e.preventDefault(); setSel((s) => Math.max(0, s - 1)); }
            else if (e.key === "Enter" && items[sel]) { items[sel].run(); close(); }
          }} />
        <div className="dialog-body" ref={listRef} role="listbox">
          {!items.length && <p className="empty-note">{mode === "open" ? t("quickOpenNone") : t("noCommands")}</p>}
          {items.map((c, i) => (
            <button key={c.id} role="option" aria-selected={i === sel} className={`pal-item${i === sel ? " on" : ""}`}
              onMouseEnter={() => setSel(i)} onClick={() => { c.run(); close(); }}>
              {c.icon}<span>{c.label}</span>
              <span className="grp">{c.keys ? <span className="kbd">{c.keys}</span> : c.group}
                {runs.some((r) => r.name === c.group) && ` → ${tab.plots[tab.active] ? t("plotTitle", { n: tab.active + 1 }) : ""}`}</span>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
