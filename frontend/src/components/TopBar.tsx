import { useEffect, useRef, useState } from "react";
import { toggleLive } from "../live";
import { actions, setInspectorByUser, useApp } from "../store";
import { useT } from "../i18n";
import { BrandMark, Icon } from "../icons";
import { clearEverything, openSession, saveSession } from "../files";
import { openMenu } from "./Overlays";
import { templateMenuItems } from "../templateMenu";

export default function TopBar() {
  const t = useT();
  const ws = useApp((s) => s.ws);
  const past = useApp((s) => s.past.length);
  const future = useApp((s) => s.future.length);
  const theme = useApp((s) => s.theme);
  const streaming = useApp((s) => s.streaming);
  const inspectorOpen = useApp((s) => s.inspectorOpen);
  const [editing, setEditing] = useState<string | null>(null);
  const liveStarting = useApp((s) => s.liveStarting);
  const [liveMenu, setLiveMenu] = useState(false);
  const [liveAnchor, setLiveAnchor] = useState<DOMRect | null>(null);

  return (
    <header className="topbar">
      <div className="brand"><BrandMark />{t("appName")}</div>
      <nav className="tabs" role="tablist">
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
                { label: t("templates") + "…", run: () => useApp.setState({ templatesOpen: true }) },
                { label: "", run: () => {}, sep: true },
                { label: t("closeTab"), run: () => actions.closeTab(tab.id) },
                { label: t("closeOthers"), run: () => actions.closeOtherTabs(tab.id), disabled: ws.tabs.length < 2 },
              ])}
              className={`tab${tab.id === ws.activeTab ? " active" : ""}`}
              onClick={() => actions.switchTab(tab.id)}
              onDoubleClick={() => setEditing(tab.id)}
              onAuxClick={(e) => { if (e.button === 1) actions.closeTab(tab.id); }}
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
        <button className="iconbtn" onClick={actions.addTab} title={t("addTab")} aria-label={t("addTab")}
          onContextMenu={(e) => openMenu(e, [{ label: t("addTab"), run: actions.addTab }, { label: t("templates") + "…", run: () => useApp.setState({ templatesOpen: true }) }])}><Icon.Plus /></button>
      </nav>
      <button className="btn tpl-menu-btn" aria-haspopup="menu" aria-label={t("tplMenu")}
        onClick={(e) => { const r = (e.currentTarget as HTMLElement).getBoundingClientRect();
          openMenu({ clientX: document.documentElement.dir === "rtl" ? Math.max(8, r.right - 240) : r.left, clientY: r.bottom + 4, preventDefault() {}, stopPropagation() {} } as React.MouseEvent, templateMenuItems(t)); }}>
        <Icon.Layout /> {t("tplMenu")} <Icon.Chevron width={12} height={12} />
      </button>
      <div className="spacer" />
      <button className="search-trigger" onClick={() => useApp.setState({ paletteOpen: true })}>
        <Icon.Search width={14} height={14} /> <span>{t("commands")}</span><span className="kbd">Ctrl K</span>
      </button>
      <span className="sep" />
      <button className="iconbtn" onClick={openSession} title={`${t("openSession")} (Ctrl+Shift+O)`} aria-label={t("openSession")}><Icon.Open /></button>
      <button className="iconbtn" onClick={saveSession} title={`${t("saveSession")} (Ctrl+S)`} aria-label={t("saveSession")}><Icon.Save /></button>
      <button className="iconbtn danger-hover" onClick={clearEverything} title={t("clearEverything")} aria-label={t("clearEverything")}><Icon.Trash /></button>
      <span className="sep" />
      <button className="iconbtn" disabled={!past} onClick={useApp.getState().undo} title={`${t("undo")} (Ctrl+Z)`} aria-label={t("undo")}><Icon.Undo /></button>
      <button className="iconbtn" disabled={!future} onClick={useApp.getState().redo} title={`${t("redo")} (Ctrl+Y)`} aria-label={t("redo")}><Icon.Redo /></button>
      <span className="sep" />
      <span className="live-group">
        <button className={`btn live-btn${streaming ? " on" : ""}`} aria-pressed={streaming} disabled={liveStarting} onClick={toggleLive}
          title={streaming ? t("liveStopHint") : t("liveStartHint")}>
          <Icon.Live /> {liveStarting ? t("liveStarting") : t("stream")}
        </button>
        <button className="iconbtn live-more" aria-expanded={liveMenu} aria-label={t("liveSettings")} title={t("liveSettings")}
          onClick={(e) => { setLiveAnchor((e.currentTarget as HTMLElement).getBoundingClientRect()); setLiveMenu(!liveMenu); }}>
          <Icon.Chevron width={12} height={12} />
        </button>
        {liveMenu && <LiveSettings anchor={liveAnchor} onClose={() => setLiveMenu(false)} />}
      </span>
      <button className="iconbtn" onClick={() => useApp.setState({ theme: theme === "dark" ? "light" : "dark" })}
        title={theme === "dark" ? t("light") : t("dark")} aria-label={t("theme")}>
        {theme === "dark" ? <Icon.Sun /> : <Icon.Moon />}
      </button>
      <button className="btn" onClick={() => useApp.setState({ lang: useApp.getState().lang === "he" ? "en" : "he" })}>
        <Icon.Globe /> {t("language")}
      </button>
      <button className="iconbtn" aria-pressed={inspectorOpen} onClick={() => setInspectorByUser(!inspectorOpen)} aria-label="Inspector"><Icon.Inspector /></button>
    </header>
  );
}

/** Live mode settings: when to stop by itself, and what to do with new files in the same folders. */
function LiveSettings({ anchor, onClose }: { anchor: DOMRect | null; onClose: () => void }) {
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
    </div>
  );
}
