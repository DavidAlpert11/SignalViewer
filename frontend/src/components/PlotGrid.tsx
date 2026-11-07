/* The plot grid of the active tab (A3: moved out of App.tsx). */
import { useRef } from "react";
import { actions, activeTab, useApp } from "../store";
import PlotView from "./PlotView";

/** Plot grid; drag the gaps between plots to resize rows and columns (V-02). */
export default function PlotGrid() {
  const tab = useApp((s) => activeTab(s.ws));
  const ref = useRef<HTMLDivElement>(null);
  const rows = tab.rowSizes && tab.rowSizes.length === tab.rows ? tab.rowSizes : Array(tab.rows).fill(1);
  const cols = tab.colSizes && tab.colSizes.length === tab.cols ? tab.colSizes : Array(tab.cols).fill(1);
  const startDrag = (axis: "row" | "col", i: number) => (e: React.MouseEvent) => {
    e.preventDefault();
    const el = ref.current;
    if (!el) return;
    const sizes = (axis === "row" ? rows : cols).slice();
    const total = sizes.reduce((a, b) => a + b, 0);
    const px = axis === "row" ? el.clientHeight : el.clientWidth;
    const rtl = document.documentElement.dir === "rtl" && axis === "col";
    const start = axis === "row" ? e.clientY : e.clientX;
    const a0 = sizes[i], b0 = sizes[i + 1];
    const move = (ev: MouseEvent) => {
      let d = ((axis === "row" ? ev.clientY : ev.clientX) - start) / px * total;
      if (rtl) d = -d;
      const min = total * 0.08;
      const a = Math.max(min, Math.min(a0 + b0 - min, a0 + d));
      sizes[i] = a; sizes[i + 1] = a0 + b0 - a;
      if (axis === "row") actions.setSizes(sizes.slice(), tab.colSizes); else actions.setSizes(tab.rowSizes, sizes.slice());
    };
    const up = () => { window.removeEventListener("mousemove", move); window.removeEventListener("mouseup", up); };
    window.addEventListener("mousemove", move); window.addEventListener("mouseup", up);
  };
  const frac = (arr: number[]) => arr.map((v) => `minmax(0, ${v}fr)`).join(" ");
  const sum = (arr: number[], n: number) => arr.slice(0, n).reduce((a, b) => a + b, 0) / arr.reduce((a, b) => a + b, 0);
  return (
    <div className="grid" ref={ref} style={{ gridTemplateRows: frac(rows), gridTemplateColumns: frac(cols) }}>
      {tab.plots.map((p, i) => <PlotView key={p.id} tab={tab} plot={p} index={i} active={i === tab.active} />)}
      {rows.slice(0, -1).map((_, i) => (
        <div key={`r${i}`} className="gutter-h" style={{ top: `calc(${sum(rows, i + 1) * 100}% - 4px)` }} onMouseDown={startDrag("row", i)}
          onDoubleClick={() => actions.setSizes(undefined, tab.colSizes)} role="separator" aria-orientation="horizontal" />
      ))}
      {cols.slice(0, -1).map((_, i) => (
        <div key={`c${i}`} className="gutter-v" style={{ insetInlineStart: `calc(${sum(cols, i + 1) * 100}% - 4px)` }} onMouseDown={startDrag("col", i)}
          onDoubleClick={() => actions.setSizes(tab.rowSizes, undefined)} role="separator" aria-orientation="vertical" />
      ))}
    </div>
  );
}
