/* A draggable divider next to a side panel (its remembered width: panelWidth.ts) - one mechanism
   for every area (Recordings' side panel and Inspector, Sweeps' steps panel and set panel). */
import { MIN_PANEL } from "./panelWidth";

/** Mouse, touch or arrow keys; double-click = default width. `grow` is +1 when moving the pointer
 *  toward the middle makes the panel wider (the panel is on the start side), -1 for a panel on the
 *  end side. RTL (Hebrew) mirrors the pointer direction. `max` is the widest the panel may be now. */
export default function PanelResizer({ label, style, width, setWidth, grow, def, max }: {
  label: string; style: React.CSSProperties; width: number; setWidth: (w: number) => void; grow: 1 | -1; def: number; max: () => number;
}) {
  const clamp = (w: number) => Math.max(MIN_PANEL, Math.min(w, max()));
  const onDown = (e: React.PointerEvent) => {
    e.preventDefault();
    const x0 = e.clientX, w0 = width, rtl = document.documentElement.dir === "rtl" ? -1 : 1;
    const move = (ev: PointerEvent) => setWidth(clamp(w0 + grow * rtl * (ev.clientX - x0)));
    const up = () => { window.removeEventListener("pointermove", move); window.removeEventListener("pointerup", up); document.body.classList.remove("resizing"); };
    document.body.classList.add("resizing");
    window.addEventListener("pointermove", move); window.addEventListener("pointerup", up);
  };
  const onKey = (e: React.KeyboardEvent) => {
    const rtl = document.documentElement.dir === "rtl" ? -1 : 1;
    const step = e.shiftKey ? 64 : 16;
    if (e.key === "ArrowRight" || e.key === "ArrowLeft") {
      e.preventDefault(); e.stopPropagation();
      setWidth(clamp(width + grow * rtl * (e.key === "ArrowRight" ? step : -step)));
    }
  };
  return <div className="resizer" role="separator" aria-orientation="vertical" aria-label={label} title={label} tabIndex={0}
    style={style} onPointerDown={onDown} onKeyDown={onKey} onDoubleClick={() => setWidth(clamp(def))} />;
}
