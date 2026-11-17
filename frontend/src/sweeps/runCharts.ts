/* The Charts of All runs on every run (1.29, FT6). When the page has only some of the runs - above *most lines to
   draw*, a sample or a density picture - a chart's numbers (histogram counts, box statistics, correlations) and a
   scatter of every run (counted per cell, the sparse cells' runs one by one) come from the server
   (/api/sweep/run-charts); with every run on the page the charts work them out themselves, as before. */
import { useEffect, useRef, useState } from "react";
import { call } from "../api";
import { wireQuestion, type Study } from "./state";
import { colourSpec, describeRuns, type RunSelection } from "./selection";
import { groupColumn, maskOfKey } from "./groups";
import { modeColumns, scopeMask } from "./view";

export interface BoxNumbers { q1: number; med: number; q3: number; lo: number; hi: number; n: number; out: number[] }
export interface CellCounts { x: number[]; y: number[]; s: number[]; n: number[] }
export interface RunCharts {
  kept: number; total: number; series: number;
  hist?: { lo: number; hi: number; bins: number; counts: number[][] };
  box?: (BoxNumbers | null)[]; boxRange?: [number, number];
  corr?: { columns: string[]; coef: (number | null)[][]; hists: number[][]; ranges: [number, number][];
    cells: ((CellCounts & { k: number; px: number[]; py: number[]; ps: number[] }) | null)[][] };
  history?: { n: number; x: number[]; y: number[]; bx?: number[]; by?: number[] };
  scatter?: CellCounts & { cells: [number, number]; cx: number[]; cy: number[];
    points: { x: number[]; y: number[]; s: number[]; size: (number | null)[] | null; c: (number | null)[] | null } };
}

/** Whether a chart of this study must ask the server: All runs, and not every run is on the page. */
export const chartsPartial = (s: Study) => s.view.mode === "runs" && !!(s.answer?.runs?.sampled || s.answer?.runs?.density);

/** The brush and the sets a chart of a pane shows (the keep / exclude steps and hidden groups, its group). */
export function chartSelection(s: Study, group?: string): RunSelection {
  const a = s.answer!, n = a.sets[0]?.values.length ?? 0;
  const scope = scopeMask(s), g = group && group !== "all" ? maskOfKey(a, s.view.groups ?? [], group, s.view.rerun) : null;
  let shown: Uint8Array | null = null;
  if (scope || g) {
    shown = new Uint8Array(n);
    for (let i = 0; i < n; i++) shown[i] = (!scope || scope[i]) && (!g || g[i]) ? 1 : 0;
  }
  const setCols = new Map(a.sets.map((c) => [c.name, c]));
  if (s.view.groups?.length) setCols.set("#group", groupColumn(a, s.view.groups));
  return describeRuns(modeColumns(s).cols, s.view.filters, setCols, n, shown);
}

/** A pane's numbers from the server (null when the chart works them out itself, or while they are on their way -
 *  the previous answer is kept meanwhile, `fresh` false). */
export function useRunCharts(s: Study, group: string | undefined, ask: Record<string, unknown>): { data: RunCharts | null; fresh: boolean; partial: boolean } {
  const partial = chartsPartial(s);
  const body = partial ? { id: s.tableId, question: wireQuestion(s), ...chartSelection(s, group), colour: colourSpec(s), ...ask } : null;
  const key = body ? JSON.stringify(body) : "";
  const [got, setGot] = useState<{ key: string; data: RunCharts } | null>(null);
  const seq = useRef(0);
  useEffect(() => {
    if (!body || got?.key === key) return;
    const my = ++seq.current;
    const h = window.setTimeout(() => {
      call<RunCharts>("/api/sweep/run-charts", body).then((d) => { if (my === seq.current) setGot({ key, data: d }); }).catch(() => { /* asked again on the next change */ });
    }, 150);
    return () => window.clearTimeout(h);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);
  return { data: partial ? got?.data ?? null : null, fresh: !!got && got.key === key, partial };
}
