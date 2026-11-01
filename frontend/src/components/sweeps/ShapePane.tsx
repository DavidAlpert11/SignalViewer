/* MF09: the sets' shape, as two Charts pane kinds. *Principal components* - the group's sets on the
   plane of their first two principal components (or a 2-D map that keeps their distances), coloured by
   cluster (k-means or hierarchical, k chosen) or by group; the clusters kept as groups in one click.
   *Self-organising map* - a grid of nodes, each with how many sets it holds, shaded by the U-matrix
   (dark = a border between clusters); a click keeps a node's sets as a group. The maths:
   svcore/sweep/clusters.py, on the columns chosen (standardised). */
import { useEffect, useMemo, useState } from "react";
import { useT } from "../../i18n";
import { sweepApi, type ClustersResult } from "../../sweeps/api";
import { category } from "../../sweeps/colors";
import { maskOfKey, setIds } from "../../sweeps/groups";
import type { DeskPane } from "../../sweeps/model";
import { notify } from "../../sweeps/notify";
import { fmtValue } from "../../sweeps/scales";
import { useSweeps, wireQuestion, type Study } from "../../sweeps/state";

export function ShapePane({ study, pane, group, onChange }: { study: Study; pane: DeskPane; group: string | undefined; onChange: (p: Partial<DeskPane>) => void }) {
  const t = useT();
  const a = study.answer!;
  const v = study.view;
  const som = pane.kind === "som";
  const method = som ? "som" : pane.method ?? "kmeans";
  const k = pane.k ?? 3;
  const columns = pane.columns ?? [];
  const sets = useMemo(() => {
    const m = group ? maskOfKey(a, v.groups ?? [], group, v.rerun) : null;
    return m ? [...m.keys()].filter((i) => m[i]) : null;
  }, [a, v.groups, v.rerun, group]);
  const [res, setRes] = useState<ClustersResult | null>(null);
  const [err, setErr] = useState("");
  const key = JSON.stringify([study.tableId, wireQuestion(study), columns, sets, method, k]);
  useEffect(() => {
    if (!columns.length) { setRes(null); return; }
    let live = true;
    sweepApi.clusters(study.tableId, wireQuestion(study), columns, sets, method, k)
      .then((r) => { if (live) { setRes(r); setErr(""); } }).catch((e) => live && setErr((e as Error).message));
    return () => { live = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  const ids = useMemo(() => setIds(a), [a]);
  const keepGroups = (labels: number[], name: (j: number) => string, only?: number) => {
    if (!res) return;
    const st = useSweeps.getState();
    const gs = [...(v.groups ?? [])];
    const by = new Map<number, string[]>();
    labels.forEach((l, i) => { if (only === undefined || l === only) by.set(l, [...(by.get(l) ?? []), ids[res.sets[i]]]); });
    const stamp = Date.now().toString(36);
    for (const [j, list] of [...by.entries()].sort((x, y) => x[0] - y[0])) {
      let color = 0;
      while (gs.some((g) => g.color === color)) color++;
      gs.push({ id: `g${stamp}c${j}`, name: name(j), color, source: "cluster", frozen: true, ids: list });
    }
    st.setView({ groups: gs, colorBy: "#group" });
    notify(t("swShapeSaved", { n: by.size }));
  };

  return (
    <div className="sw-shape">
      <div className="sw-row sw-shape-bar">
        {!som && <select aria-label={t("swShapeMethod")} value={method} onChange={(e) => onChange({ method: e.target.value as DeskPane["method"] })}>
          <option value="kmeans">{t("swShapeKmeans")}</option><option value="hierarchical">{t("swShapeHier")}</option><option value="mds">{t("swShapeMds")}</option>
        </select>}
        {!som && method !== "mds" && <label>k <input type="number" min={2} max={10} value={k} aria-label={t("swShapeK")} style={{ width: 48 }}
          onChange={(e) => onChange({ k: Math.max(2, Math.min(10, Number(e.target.value) || 3)) })} /></label>}
        {res?.clusters && <button className="btn outline" onClick={() => keepGroups(res.clusters!.labels, (j) => t("swShapeCluster", { n: j + 1 }))}>
          {t("swShapeKeep", { n: res.clusters.sizes.length })}</button>}
      </div>
      {!columns.length && <p className="empty-note">{t("swShapePick")}</p>}
      {err && <p className="sw-error">{err}</p>}
      {res && !som && <Plane t={t} res={res} mds={method === "mds"} />}
      {res?.som && <SomGrid t={t} res={res} onNode={(n) => keepGroups(res.som!.node, () => t("swShapeNode", { n: n + 1 }), n)} />}
    </div>
  );
}

function Plane({ t, res, mds }: { t: ReturnType<typeof useT>; res: ClustersResult; mds: boolean }) {
  const pts = (mds ? res.mds?.coords : res.pca.coords) ?? [];
  if (!pts.length) return null;
  const W = 360, H = 240, L = 40, B = 30, T = 8, R = 10;
  const ext = (i: number) => { const xs = pts.map((p) => p[i] ?? 0); const lo = Math.min(...xs), hi = Math.max(...xs); const pad = (hi - lo || 1) * 0.06; return [lo - pad, hi + pad]; };
  const [x0, x1] = ext(0), [y0, y1] = ext(1);
  const px = (v: number) => L + ((v - x0) / (x1 - x0)) * (W - L - R), py = (v: number) => H - B - ((v - y0) / (y1 - y0)) * (H - B - T);
  const ex = res.pca.explained;
  const xl = mds ? t("swShapeDim", { n: 1 }) : `PC1 (${Math.round((ex[0] ?? 0) * 100)}%)`;
  const yl = mds ? t("swShapeDim", { n: 2 }) : `PC2 (${Math.round((ex[1] ?? 0) * 100)}%)`;
  const lab = res.clusters?.labels;
  return (
    <figure className="sw-shape-plane">
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={mds ? t("swShapeMds") : t("swPanePca")} data-points={pts.length}>
        <line x1={L} y1={H - B} x2={W - R} y2={H - B} className="sw-axis-line" /><line x1={L} y1={T} x2={L} y2={H - B} className="sw-axis-line" />
        <text x={(L + W - R) / 2} y={H - 6} textAnchor="middle" className="sw-ax">{xl}</text>
        <text x={12} y={(T + H - B) / 2} textAnchor="middle" className="sw-ax" transform={`rotate(-90 12 ${(T + H - B) / 2})`}>{yl}</text>
        {pts.map((p, i) => <circle key={i} cx={px(p[0])} cy={py(p[1] ?? 0)} r={3} fill={lab ? category(lab[i]) : category(0)} fillOpacity={0.8} />)}
      </svg>
      <figcaption className="hint">
        {mds ? t("swShapeStress", { s: fmtValue(res.mds?.stress ?? NaN) })
          : t("swShapeLoadings", { list: res.columns.map((c, j) => `${c} ${fmtValue(res.pca.loadings[0]?.[j] ?? NaN)}`).join(", ") })}
        {res.clusters && ` · ${res.clusters.sizes.map((n, j) => `${j + 1}: ${n}`).join(" · ")}`}
      </figcaption>
    </figure>
  );
}

function SomGrid({ t, res, onNode }: { t: ReturnType<typeof useT>; res: ClustersResult; onNode: (n: number) => void }) {
  const s = res.som!;
  const top = Math.max(...s.umatrix, 1e-12);
  return (
    <figure className="sw-som">
      <div className="sw-som-grid" style={{ gridTemplateColumns: `repeat(${s.w}, 1fr)` }} role="grid" aria-label={t("swPaneSom")}>
        {s.hits.map((h, n) => (
          <button key={n} className="sw-som-node" data-node={n} disabled={!h} title={t("swShapeNodeHint", { n: h })}
            style={{ ["--u" as string]: String(s.umatrix[n] / top) }} onClick={() => onNode(n)}>{h || ""}</button>
        ))}
      </div>
      <figcaption className="hint">{t("swShapeSomHint", { q: fmtValue(s.qerror) })}</figcaption>
    </figure>
  );
}
