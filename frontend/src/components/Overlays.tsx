import { useEffect, useRef, useState } from "react";
import { actions, activeTab, useApp, type MenuItem } from "../store";
import { useT } from "../i18n";
import { Icon } from "../icons";

/** Escape closes a dialog wherever the keyboard focus is (not only inside the dialog). */
export function useEscape(close: () => void, active = true) {
  useEffect(() => {
    if (!active) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") { e.stopPropagation(); close(); } };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [close, active]);
}

/* ------------------------------------------------------------ dialog focus (F18) */
const FOCUSABLE = 'button:not(:disabled), input:not(:disabled), select:not(:disabled), textarea:not(:disabled), [tabindex]:not([tabindex="-1"])';

/** Every modal dialog (a .dialog on a .scrim) takes the keyboard while it is open: the focus moves
 *  into it (it stayed on the button behind the scrim, so Esc and type-to-filter did nothing until a
 *  click), Tab cycles inside it, and when it closes the focus goes back where it was. One watcher
 *  for all the dialogs, mounted once in App, so a new dialog gets it without doing anything. */
export function ModalFocus() {
  useEffect(() => {
    const stack: { dlg: HTMLElement; before: HTMLElement | null }[] = [];
    const top = () => {
      const all = Array.from(document.querySelectorAll<HTMLElement>(".scrim > .dialog"));
      return all.find((d) => d.closest(".scrim-top")) ?? all[all.length - 1] ?? null;
    };
    const sync = () => {
      while (stack.length && !document.contains(stack[stack.length - 1].dlg)) {      // closed: focus back
        const { before } = stack.pop()!;
        const now = top();
        if (before && document.contains(before) && (!now || now.contains(before))) before.focus({ preventScroll: true });
      }
      const d = top();
      if (!d || stack.some((x) => x.dlg === d)) return;
      stack.push({ dlg: d, before: document.activeElement as HTMLElement | null });
      if (!d.contains(document.activeElement)) {             // an autoFocus field inside keeps its focus
        if (!d.hasAttribute("tabindex")) d.setAttribute("tabindex", "-1");
        d.focus({ preventScroll: true });
      }
    };
    const obs = new MutationObserver(sync);
    obs.observe(document.body, { childList: true, subtree: true });
    const onKey = (e: KeyboardEvent) => {
      const d = top();
      if (e.key !== "Tab" || !d) return;
      const items = Array.from(d.querySelectorAll<HTMLElement>(FOCUSABLE)).filter((x) => x.offsetParent !== null);
      if (!items.length) { e.preventDefault(); d.focus(); return; }
      const first = items[0], last = items[items.length - 1], at = document.activeElement as HTMLElement | null;
      const inside = !!at && d.contains(at);
      if (e.shiftKey && (!inside || at === first || at === d)) { e.preventDefault(); last.focus(); }
      else if (!e.shiftKey && (!inside || at === last)) { e.preventDefault(); first.focus(); }
    };
    window.addEventListener("keydown", onKey, true);
    return () => { obs.disconnect(); window.removeEventListener("keydown", onKey, true); };
  }, []);
  return null;
}

/* ------------------------------------------------------------ context menu */
export function openMenu(e: React.MouseEvent, items: MenuItem[]) {
  e.preventDefault();
  e.stopPropagation();
  useApp.setState({ menu: { x: e.clientX, y: e.clientY, items } });
}

export function ContextMenu() {
  const menu = useApp((s) => s.menu);
  const ref = useRef<HTMLDivElement>(null);
  const subRef = useRef<HTMLDivElement>(null);
  const [pos, setPos] = useState({ x: 0, y: 0 });
  const [sub, setSub] = useState<number | null>(null);       // the open submenu (T21b)
  const [subFlip, setSubFlip] = useState({ side: false, up: 0 });
  useEffect(() => { setSub(null); }, [menu]);
  // a submenu that would leave the window opens on the other side / higher
  useEffect(() => {
    const el = subRef.current;
    if (sub === null || !el) { setSubFlip({ side: false, up: 0 }); return; }
    const r = el.getBoundingClientRect();
    setSubFlip({ side: r.right > window.innerWidth - 4 || r.left < 4, up: Math.max(0, r.bottom - window.innerHeight + 8) });
  }, [sub]);
  useEffect(() => {
    if (!menu) return;
    const close = () => useApp.setState({ menu: null });
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") close(); };
    // capture phase: dialogs stop mousedown from bubbling, so a menu opened inside a dialog
    // (the template library's "New") must still close when clicking anywhere outside it
    const outside = (e: MouseEvent) => { if (!ref.current?.contains(e.target as Node)) close(); };
    window.addEventListener("mousedown", outside, true);
    window.addEventListener("keydown", onKey);
    window.addEventListener("blur", close);
    // keep inside the window
    const el = ref.current;
    const w = el?.offsetWidth ?? 220, h = el?.offsetHeight ?? 200;
    setPos({ x: Math.min(menu.x, window.innerWidth - w - 8), y: Math.min(menu.y, window.innerHeight - h - 8) });
    return () => { window.removeEventListener("mousedown", outside, true); window.removeEventListener("keydown", onKey); window.removeEventListener("blur", close); };
  }, [menu]);
  if (!menu) return null;
  const leaf = (it: MenuItem, i: number) => it.sep ? <div key={i} className="menu-sep" /> : (
    <button key={i} role="menuitem" disabled={it.disabled} className={it.danger ? "danger" : ""}
      onClick={() => { useApp.setState({ menu: null }); it.run(); }}>
      {it.label}
    </button>
  );
  const rtl = document.documentElement.dir === "rtl";
  return (
    <div className={`menu ctx${menu.items.length > 14 && !menu.items.some((it) => it.items) ? " long" : ""}`} ref={ref} role="menu" style={{ left: pos.x, top: pos.y }} onMouseDown={(e) => e.stopPropagation()}>
      {menu.items.map((it, i) => !it.items ? leaf(it, i) : (
        <div key={i} className="menu-subwrap" onMouseEnter={() => setSub(i)} onMouseLeave={() => setSub(null)}>
          <button role="menuitem" aria-haspopup="menu" aria-expanded={sub === i} disabled={it.disabled}
            className={sub === i ? "open" : ""} onClick={() => setSub(sub === i ? null : i)}
            onKeyDown={(e) => { if (e.key === (rtl ? "ArrowLeft" : "ArrowRight")) { e.preventDefault(); setSub(i); } }}>
            {it.label}<span className="menu-more" aria-hidden="true">›</span>
          </button>
          {sub === i && (
            <div ref={subRef} role="menu" className={"menu ctx sub" + (subFlip.side ? " flip" : "")}
              style={subFlip.up ? { top: -5 - subFlip.up } : undefined}>
              {it.items.map(leaf)}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

/* ------------------------------------------------------------ confirm (uses the prompt dialog without a field) */
export function confirmAsk(title: string, text: string): Promise<boolean> {
  return new Promise((resolve) => useApp.setState({
    promptDialog: { title, label: text, value: "", confirmOnly: true, resolve: (v: string | null) => resolve(v !== null) } as never,
  }));
}

/* ------------------------------------------------------------ prompt dialog */
export function prompt(title: string, label: string, value: string, multiline = false): Promise<string | null> {
  return new Promise((resolve) => useApp.setState({ promptDialog: { title, label, value, multiline, resolve } }));
}

export function PromptDialog() {
  const t = useT();
  const d = useApp((s) => s.promptDialog);
  const [v, setV] = useState("");
  useEffect(() => { if (d) setV(d.value); }, [d]);
  useEscape(() => { if (d) { d.resolve(null); useApp.setState({ promptDialog: null }); } }, !!d);
  if (!d) return null;
  const done = (val: string | null) => { d.resolve(val); useApp.setState({ promptDialog: null }); };
  return (
    <div className="scrim" onMouseDown={() => done(null)}>
      <div className="dialog small" role="dialog" aria-label={d.title} onMouseDown={(e) => e.stopPropagation()}
        onKeyDown={(e) => { if (e.key === "Escape") done(null); if (e.key === "Enter" && !d.multiline) done(v); }}>
        <div className="dialog-head"><h2>{d.title}</h2><button className="iconbtn" onClick={() => done(null)} aria-label={t("close")}><Icon.X /></button></div>
        <div className="dialog-pad">
          {(d as { confirmOnly?: boolean }).confirmOnly ? <p className="confirm-text">{d.label}</p> : <label className="afield"><span>{d.label}</span>
            {d.multiline ? <textarea autoFocus rows={4} value={v} onChange={(e) => setV(e.target.value)} />
              : <input autoFocus value={v} onChange={(e) => setV(e.target.value)} onFocus={(e) => e.target.select()} />}
          </label>}
        </div>
        <div className="dialog-foot"><span className="spacer" />
          <button className="btn outline" onClick={() => done(null)}>{t("cancel")}</button>
          <button className="btn primary" onClick={() => done(v)}>{t("ok")}</button></div>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------ axis limits (V-07) */
export function AxisDialog() {
  const t = useT();
  const plotId = useApp((s) => s.axisDialog);
  const ws = useApp((s) => s.ws);
  const tab = activeTab(ws);
  const plot = tab.plots.find((p) => p.id === plotId);
  const [f, setF] = useState({ x0: "", x1: "", y0: "", y1: "", all: false });
  useEffect(() => {
    if (!plot) return;
    setF({ x0: plot.xlim?.[0]?.toString() ?? "", x1: plot.xlim?.[1]?.toString() ?? "",
      y0: plot.ylim?.[0]?.toString() ?? "", y1: plot.ylim?.[1]?.toString() ?? "", all: false });
  }, [plotId]); // eslint-disable-line react-hooks/exhaustive-deps
  useEscape(() => useApp.setState({ axisDialog: null }), !!plot);
  if (!plot) return null;
  const close = () => useApp.setState({ axisDialog: null });
  const pair = (a: string, b: string): [number, number] | null => {
    if (a.trim() === "" || b.trim() === "") return null;
    const x = Number(a), y = Number(b);
    return Number.isFinite(x) && Number.isFinite(y) && x !== y ? [Math.min(x, y), Math.max(x, y)] : null;
  };
  const bad = (a: string, b: string) => (a.trim() !== "" || b.trim() !== "") && !pair(a, b);
  const apply = () => { actions.setAxisLimits(plot.id, pair(f.x0, f.x1), pair(f.y0, f.y1), f.all); close(); };
  const num = (k: "x0" | "x1" | "y0" | "y1", label: string) => (
    <label className="afield"><span>{label}</span>
      <input className="num" inputMode="decimal" value={f[k]} placeholder={t("auto")} onChange={(e) => setF({ ...f, [k]: e.target.value })} /></label>
  );
  return (
    <div className="scrim" onMouseDown={close}>
      <div className="dialog small" role="dialog" aria-label={t("axisLimits")} onMouseDown={(e) => e.stopPropagation()}
        onKeyDown={(e) => { if (e.key === "Escape") close(); if (e.key === "Enter") apply(); }}>
        <div className="dialog-head"><h2>{t("axisLimits")}</h2><button className="iconbtn" onClick={close} aria-label={t("close")}><Icon.X /></button></div>
        <div className="dialog-pad">
          <div className="arow">{num("x0", `X ${t("from")}`)}{num("x1", `X ${t("to")}`)}</div>
          {bad(f.x0, f.x1) && <p className="hint err">{t("limitsInvalid")}</p>}
          <div className="arow">{num("y0", `Y ${t("from")}`)}{num("y1", `Y ${t("to")}`)}</div>
          {bad(f.y0, f.y1) && <p className="hint err">{t("limitsInvalid")}</p>}
          <label className="acheck"><input type="checkbox" checked={f.all} onChange={(e) => setF({ ...f, all: e.target.checked })} />{t("applyAllPlots")}</label>
          <p className="hint" style={{ fontSize: "0.923rem" }}>{t("limitsHint")}</p>
        </div>
        <div className="dialog-foot">
          <button className="btn outline" onClick={() => { actions.setAxisLimits(plot.id, null, null, f.all); close(); }}>{t("clearLimits")}</button>
          <span className="spacer" />
          <button className="btn outline" onClick={close}>{t("cancel")}</button>
          <button className="btn primary" disabled={bad(f.x0, f.x1) || bad(f.y0, f.y1)} onClick={apply}>{t("apply")}</button>
        </div>
      </div>
    </div>
  );
}
