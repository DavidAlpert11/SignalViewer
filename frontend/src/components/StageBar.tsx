import { useEffect, useRef, useState } from "react";
import { actions, activeTab, MAX_PLOTS, rangeKey, useApp } from "../store";
import { useT } from "../i18n";
import { Icon } from "../icons";

const QUICK: [number, number][] = [[1, 1], [2, 1], [3, 1], [1, 2], [2, 2], [3, 2], [3, 3]];

function LayoutIcon({ r, c }: { r: number; c: number }) {
  const cells = [];
  for (let i = 0; i < r; i++) for (let j = 0; j < c; j++)
    cells.push(<rect key={`${i}${j}`} x={2 + j * (16 / c) + 0.6} y={3 + i * (14 / r) + 0.6} width={16 / c - 1.2} height={14 / r - 1.2} rx="1" />);
  return <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.3" aria-hidden="true">{cells}</svg>;
}

/** Any rows x columns with at most MAX_PLOTS plots (V-02): hover the grid or type. */
/** The layout popover (T20): the common layouts, then any rows × columns. */
function GridPicker({ rows, cols, anchor, onPick, onClose }: { rows: number; cols: number; anchor: DOMRect | null; onPick: (r: number, c: number) => void; onClose: () => void }) {
  const t = useT();
  const box = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const off = (e: MouseEvent) => { if (!box.current?.contains(e.target as Node)) onClose(); };
    // F18: Esc closes it wherever the focus is (it worked only with the focus inside)
    const esc = (e: KeyboardEvent) => { if (e.key === "Escape") { e.stopPropagation(); onClose(); } };
    window.addEventListener("mousedown", off);
    window.addEventListener("keydown", esc, true);
    return () => { window.removeEventListener("mousedown", off); window.removeEventListener("keydown", esc, true); };
  }, [onClose]);
  // fixed, so the toolbar (which scrolls horizontally) does not clip it
  const rtl = document.documentElement.dir === "rtl";
  const style: React.CSSProperties = anchor ? { position: "fixed", top: anchor.bottom + 4,
    ...(rtl ? { right: window.innerWidth - anchor.right } : { left: anchor.left }) } : {};
  const [hover, setHover] = useState<[number, number]>([rows, cols]);
  const [r, setR] = useState(String(rows)), [c, setC] = useState(String(cols));
  const ok = (a: number, b: number) => a >= 1 && b >= 1 && a * b <= MAX_PLOTS;
  const nr = Number(r), nc = Number(c);
  return (
    <div className="gridpick" ref={box} style={style} role="dialog" aria-label={t("layout")}
      onKeyDown={(e) => { if (e.key === "Escape") onClose(); }}>
      <div className="gridpick-quick">
        {QUICK.map(([qr, qc]) => (
          <button key={`${qr}x${qc}`} className="iconbtn" aria-pressed={rows === qr && cols === qc}
            onClick={() => onPick(qr, qc)} title={`${qr} × ${qc}`} aria-label={`${t("layout")} ${qr} × ${qc}`}>
            <LayoutIcon r={qr} c={qc} />
          </button>
        ))}
      </div>
      <div className="gridpick-cells">
        {Array.from({ length: MAX_PLOTS * MAX_PLOTS }, (_, k) => {
          const rr = Math.floor(k / MAX_PLOTS) + 1, cc = (k % MAX_PLOTS) + 1;
          const allowed = rr * cc <= MAX_PLOTS;
          return <button key={k} disabled={!allowed} className={allowed && rr <= hover[0] && cc <= hover[1] ? "on" : ""}
            aria-label={`${rr} × ${cc}`} onMouseEnter={() => allowed && setHover([rr, cc])}
            onFocus={() => allowed && setHover([rr, cc])} onClick={() => onPick(rr, cc)} />;
        })}
      </div>
      <div className="gridpick-label">{hover[0]} × {hover[1]}</div>
      <div className="gridpick-type">
        <input aria-label={t("rows")} inputMode="numeric" value={r} onChange={(e) => setR(e.target.value)} />
        <span>×</span>
        <input aria-label={t("columns")} inputMode="numeric" value={c} onChange={(e) => setC(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter" && ok(nr, nc)) onPick(nr, nc); }} />
        <button className="btn outline" disabled={!ok(nr, nc)} onClick={() => onPick(nr, nc)}>{t("apply")}</button>
      </div>
      <div className="gridpick-hint">{t("maxPlots", { n: MAX_PLOTS })}</div>
    </div>
  );
}

/** A small popover under its button, closed by a click outside or Escape. */
function Popover({ anchor, onClose, label, children }: { anchor: DOMRect | null; onClose: () => void; label: string; children: React.ReactNode }) {
  const box = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const off = (e: MouseEvent) => { if (!box.current?.contains(e.target as Node) && !(e.target as HTMLElement).closest?.(".zoom-btn")) onClose(); };
    // F18: Esc closes it wherever the focus is (it worked only with the focus inside)
    const esc = (e: KeyboardEvent) => { if (e.key === "Escape") { e.stopPropagation(); onClose(); } };
    window.addEventListener("mousedown", off);
    window.addEventListener("keydown", esc, true);
    return () => { window.removeEventListener("mousedown", off); window.removeEventListener("keydown", esc, true); };
  }, [onClose]);
  const rtl = document.documentElement.dir === "rtl";
  const style: React.CSSProperties = anchor ? { position: "fixed", top: anchor.bottom + 4,
    ...(rtl ? { right: window.innerWidth - anchor.right } : { left: anchor.left }) } : {};
  return <div className="gridpick bar-pop" ref={box} style={style} role="dialog" aria-label={label}
    onKeyDown={(e) => { if (e.key === "Escape") onClose(); }}>{children}</div>;
}

export default function StageBar() {
  const t = useT();
  const tab = useApp((s) => activeTab(s.ws));
  const cursor = useApp((s) => s.cursor);
  const streaming = useApp((s) => s.streaming);
  const follow = useApp((s) => s.follow);
  const plot = tab.plots[tab.active];
  const canBack = useApp((s) => !!plot && (s.zoomHistory[rangeKey(tab, plot)]?.length ?? 0) > 0);
  const [picker, setPicker] = useState(false);
  const [anchor, setAnchor] = useState<DOMRect | null>(null);
  const zoomMode = useApp((s) => s.zoomMode);
  const [zoomMenu, setZoomMenu] = useState(false);
  const [zoomAnchor, setZoomAnchor] = useState<DOMRect | null>(null);

  return (
    <div className="stage-bar">
      {/* T20: one layout button: the current layout; the popover has the common ones and any size */}
      <span className="pick-wrap">
        <button className="btn layout-btn" aria-expanded={picker} aria-haspopup="dialog" title={t("layoutHint")} aria-label={t("layout")}
          onClick={(e) => { setAnchor((e.currentTarget as HTMLElement).getBoundingClientRect()); setPicker(!picker); }}>
          <LayoutIcon r={Math.min(tab.rows, 3)} c={Math.min(tab.cols, 3)} /><span>{tab.rows} × {tab.cols}</span>
        </button>
        {picker && <GridPicker rows={tab.rows} cols={tab.cols} anchor={anchor} onPick={(r, c) => { actions.setLayout(r, c); setPicker(false); }} onClose={() => setPicker(false)} />}
      </span>
      <span className="sep" />
      <button className="btn" aria-pressed={tab.linkX} onClick={actions.toggleLinkX} title={t("linkX")}><Icon.Link /> X</button>
      <button className="btn" aria-pressed={!!tab.linkY} onClick={actions.toggleLinkY} title={t("linkY")}><Icon.Link /> Y</button>
      <span className="sep" />
      {/* T19: the zoom mode in a menu; for one drag Shift = values, Ctrl = a box */}
      <span className="pick-wrap">
        <button className="btn zoom-btn" aria-expanded={zoomMenu} aria-haspopup="menu" title={t("zoomModeHint")}
          onClick={(e) => { setZoomAnchor((e.currentTarget as HTMLElement).getBoundingClientRect()); setZoomMenu(!zoomMenu); }}>
          <Icon.Search /><span>{t("zoom")}:</span> {zoomMode === "x" ? "X" : zoomMode === "y" ? "Y" : "XY"}
        </button>
        {zoomMenu && <Popover anchor={zoomAnchor} onClose={() => setZoomMenu(false)} label={t("zoomMode")}>
          <span className="seg zoom-seg" role="group" aria-label={t("zoomMode")}>
            {(["x", "y", "xy"] as const).map((m) => (
              <button key={m} className={zoomMode === m ? "on" : ""} aria-pressed={zoomMode === m}
                title={`${t(m === "x" ? "zoomX" : m === "y" ? "zoomY" : "zoomXY")} (Z)`} onClick={() => { actions.setZoomMode(m); setZoomMenu(false); }}>
                {m === "x" ? "X" : m === "y" ? "Y" : "XY"}
              </button>
            ))}
          </span>
          <p className="hint">{t("zoomKeysHint")}</p>
        </Popover>}
      </span>
      <button className="iconbtn" disabled={!canBack} onClick={actions.zoomBack} title={`${t("zoomBack")} (Backspace)`} aria-label={t("zoomBack")}><Icon.Undo /></button>
      <button className="btn" onClick={actions.resetZoom} title={`${t("resetZoom")} (R)`}><Icon.Reset /><span className="hide-narrow">{t("resetZoom")}</span></button>
      <button className="iconbtn" onClick={actions.clearAllPlots} title={t("clearAllHint")} aria-label={t("clearAll")}><Icon.Eraser /></button>
      {streaming && <>
        <span className="sep" />
        <span className="bar-label">{t("follow")}</span>
        <select className="mini-select" value={follow ?? ""} onChange={(e) => useApp.setState({ follow: e.target.value ? Number(e.target.value) : null })} aria-label={t("follow")}>
          <option value="">{t("followOff")}</option>
          {[10, 30, 60, 300].map((v) => <option key={v} value={v}>{v} {t("seconds")}</option>)}
        </select>
      </>}
      <div className="spacer" />
      <button className="btn cursor-btn" aria-pressed={cursor.on} onClick={actions.toggleCursor} title={`${t("cursor")} (Space)`}><Icon.Cursor /><span className="hide-narrow">{t("cursor")}</span></button>
      <button className="btn cursor-btn" aria-pressed={cursor.on && cursor.dual} onClick={actions.toggleDual} title={`${t("dualCursor")} (D)`}><Icon.Dual /><span className="hide-narrow">{t("dualCursor")}</span></button>
    </div>
  );
}
