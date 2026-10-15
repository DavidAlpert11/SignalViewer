import { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import { useApp, type Plot } from "../store";
import { useT } from "../i18n";
import { XYZCanvas, type Shown } from "./XYZChart";

/* The 3D view on a computer without WebGL (an old or virtual machine, remote desktop, a graphics
   driver the browser blocks - and since Chrome / Edge 139 no software fallback either): the plot's
   objects as tracks in metres east / north / up from the first object's first position, drawn by
   the XYZ plot's canvas (2D only, no WebGL). No terrain, map or models - but the flight in 3D,
   with the timeline's time. */

const A = 6378137.0, E2 = (1 / 298.257223563) * (2 - 1 / 298.257223563);
function ecef(lat: number, lon: number, h: number): [number, number, number] {
  const la = (lat * Math.PI) / 180, lo = (lon * Math.PI) / 180, s = Math.sin(la);
  const n = A / Math.sqrt(1 - E2 * s * s);
  return [(n + h) * Math.cos(la) * Math.cos(lo), (n + h) * Math.cos(la) * Math.sin(lo), (n * (1 - E2) + h) * s];
}

interface Props { plot: Plot; index: number; onLoading: (b: boolean) => void; reason: string }

export default function Globe3DFallback({ plot, index, onLoading, reason }: Props) {
  const t = useT();
  const dataVersion = useApp((s) => s.dataVersion);
  const objects = useMemo(() => plot.objects ?? [], [plot.objects]);
  const key = objects.map((o) => [o.id, o.lat, o.lon, o.alt].join(":")).join("|");
  const [raw, setRaw] = useState<{ t: Float64Array; lat: Float64Array; lon: Float64Array; alt: Float32Array | null }[]>([]);

  useEffect(() => {
    if (!objects.length) { setRaw([]); return; }
    let cancelled = false;
    onLoading(true);
    Promise.all(objects.map((o) => api.objectTrack(o).catch(() => null)))
      .then((rs) => { if (!cancelled) setRaw(rs.map((r) => r ?? { t: new Float64Array(), lat: new Float64Array(), lon: new Float64Array(), alt: null })); })
      .finally(() => { if (!cancelled) onLoading(false); });
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, dataVersion]);

  /* east / north / up (m) from the first valid position of the first object */
  const shown = useMemo((): Shown[] => {
    let origin: [number, number, number] | null = null;
    for (const r of raw) {
      for (let i = 0; i < r.t.length && !origin; i++) {
        const h = r.alt ? r.alt[i] : 0;
        if (Number.isFinite(r.lat[i]) && Number.isFinite(r.lon[i]) && Number.isFinite(h)) origin = [r.lat[i], r.lon[i], h];
      }
      if (origin) break;
    }
    if (!origin) return [];
    const o = ecef(...origin), la = (origin[0] * Math.PI) / 180, lo = (origin[1] * Math.PI) / 180;
    const sla = Math.sin(la), cla = Math.cos(la), slo = Math.sin(lo), clo = Math.cos(lo);
    const names = [t("g3East"), t("g3North"), t("g3Up")];
    return raw.map((r, k) => {
      const n = r.t.length, e = new Float64Array(n), no = new Float64Array(n), u = new Float64Array(n);
      for (let i = 0; i < n; i++) {
        const p = ecef(r.lat[i], r.lon[i], r.alt ? r.alt[i] : 0), dx = p[0] - o[0], dy = p[1] - o[1], dz = p[2] - o[2];
        e[i] = -slo * dx + clo * dy;
        no[i] = -sla * clo * dx - sla * slo * dy + cla * dz;
        u[i] = cla * clo * dx + cla * slo * dy + sla * dz;
      }
      return { t: r.t, v: [e, no, u], color: objects[k]?.color ?? "#3D8BFD", width: 2, names, label: objects[k]?.name ?? "" };
    });
  }, [raw, objects, t]);

  return (
    <XYZCanvas shown={shown} equal flipZ={false} index={index} hint={t("xyzControls")} letters={["E", "N", "U"]} legendTop={44}>
      <div className="globe3d-light g3-nowebgl" dir="auto" title={reason}>{t("globeNoWebgl")}</div>
      {!objects.length && <div className="plot-empty">{t("globeNeedsObject")}</div>}
    </XYZCanvas>
  );
}
