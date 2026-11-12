import { useEffect, useMemo, useRef } from "react";
import { useT } from "../i18n";

/* P9: the mini-map while the camera is close to an object (On the object, Chase, Cockpit) - the whole flight
   from above, north up, the object as a dot with its heading, the camera's view as a wedge; a click flies the
   camera there. A small 2D canvas over the view (not a second globe). */
export interface MiniTrack { color: string; lat: ArrayLike<number>; lon: ArrayLike<number> }
const W = 150;
export default function MiniMap({ tracks, focus, camera, onPick }: {
  tracks: MiniTrack[];
  focus: { lat: number; lon: number; hdg: number | null; color: string } | null;
  camera: { lat: number; lon: number; heading: number; fov: number } | null;
  onPick: (lat: number, lon: number) => void;
}) {
  const t = useT();
  const ref = useRef<HTMLCanvasElement>(null);
  // the box of every track (north up; east scaled by the latitude), once per data
  const box = useMemo(() => {
    let s = Infinity, n = -Infinity, w = Infinity, e = -Infinity;
    for (const tr of tracks) for (let i = 0; i < tr.lat.length; i++) {
      const a = tr.lat[i], b = tr.lon[i];
      if (!Number.isFinite(a) || !Number.isFinite(b)) continue;
      s = Math.min(s, a); n = Math.max(n, a); w = Math.min(w, b); e = Math.max(e, b);
    }
    if (!Number.isFinite(s)) return null;
    const k = Math.cos((((s + n) / 2) * Math.PI) / 180);
    const span = Math.max((n - s), (e - w) * k, 5e-4) * 1.15;
    return { cl: (s + n) / 2, co: (w + e) / 2, k, span };
  }, [tracks]);
  const xy = (lat: number, lon: number): [number, number] => !box ? [0, 0]
    : [W / 2 + ((lon - box.co) * box.k) / box.span * W, W / 2 - (lat - box.cl) / box.span * W];
  useEffect(() => {
    const cv = ref.current;
    if (!cv || !box) return;
    const r = Math.min(2, window.devicePixelRatio || 1);
    if (cv.width !== W * r || cv.height !== W * r) { cv.width = W * r; cv.height = W * r; }   // (a new canvas is 300 x 150)
    const c = cv.getContext("2d");
    if (!c) return;
    c.setTransform(r, 0, 0, r, 0, 0);
    c.clearRect(0, 0, W, W);
    for (const tr of tracks) {
      const st = Math.max(1, Math.floor(tr.lat.length / 400));
      c.strokeStyle = tr.color; c.lineWidth = 1.5; c.beginPath();
      let first = true;
      for (let i = 0; i < tr.lat.length; i += st) {
        if (!Number.isFinite(tr.lat[i]) || !Number.isFinite(tr.lon[i])) { first = true; continue; }
        const [x, y] = xy(tr.lat[i], tr.lon[i]);
        if (first) { c.moveTo(x, y); first = false; } else c.lineTo(x, y);
      }
      c.stroke();
    }
    if (camera) {
      const [x, y] = xy(camera.lat, camera.lon), a = camera.heading - Math.PI / 2, hf = camera.fov / 2;
      c.fillStyle = "rgba(242,169,59,.28)"; c.beginPath(); c.moveTo(x, y); c.arc(x, y, 40, a - hf, a + hf); c.closePath(); c.fill();
    }
    if (focus) {
      const [x, y] = xy(focus.lat, focus.lon), h = ((focus.hdg ?? 0) * Math.PI) / 180;
      c.fillStyle = focus.color; c.strokeStyle = "#fff"; c.lineWidth = 1.5;
      c.beginPath(); c.arc(x, y, 4, 0, 2 * Math.PI); c.fill(); c.stroke();
      c.beginPath(); c.moveTo(x, y); c.lineTo(x + Math.sin(h) * 11, y - Math.cos(h) * 11); c.stroke();
    }
  });
  if (!box) return null;
  return <canvas ref={ref} className="mini-map" style={{ width: W, height: W }} title={t("miniMapHint")} aria-label={t("miniMapHint")}
    onClick={(e) => {
      const b = e.currentTarget.getBoundingClientRect(), x = e.clientX - b.left, y = e.clientY - b.top;
      onPick(box.cl - (y - W / 2) / W * box.span, box.co + (x - W / 2) / W * box.span / box.k);
    }} />;
}
