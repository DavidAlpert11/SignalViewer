import { useEffect, useRef } from "react";
import { useApp } from "../store";
import { useT } from "../i18n";

/* P9: the flight display of the object the camera is on - the same look as the offline 3D page's
   (report_assets/scene3d.html adi/tape): the attitude indicator, a ground-speed tape on its left, an altitude
   tape with the height above the ground on its right, the name and heading under it. Numbers in the units
   of Settings > Map and objects (m/s and m, or kt and ft). Its colours are an instrument's, the same in both
   themes (sky, ground, amber marks). */
export interface FdState { name: string; roll: number | null; pitch: number | null; hdg: number | null; gs: number | null; alt: number; agl: number | null }

const W = 236, H = 136;
export default function FlightDisplay({ s }: { s: FdState }) {
  const t = useT();
  const units = useApp((st) => st.mapPrefs.units);
  const ref = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const cv = ref.current;
    if (!cv) return;
    const r = Math.min(2, window.devicePixelRatio || 1);
    if (cv.width !== W * r || cv.height !== H * r) { cv.width = W * r; cv.height = H * r; }
    const c = cv.getContext("2d");
    if (!c) return;
    c.setTransform(r, 0, 0, r, 0, 0);
    c.clearRect(0, 0, W, H);
    const imp = units === "imperial", R = Math.PI / 180;
    const cx = 118, cy = 59, R0 = 54, roll = s.roll ?? 0, pitch = s.pitch ?? 0;
    // the attitude indicator
    c.save(); c.beginPath(); c.arc(cx, cy, R0, 0, 2 * Math.PI); c.clip();
    c.translate(cx, cy); c.rotate(-roll * R); c.translate(0, pitch * 1.6);
    c.fillStyle = "#3a7bc8"; c.fillRect(-120, -240, 240, 240);
    c.fillStyle = "#8a5a2b"; c.fillRect(-120, 0, 240, 240);
    c.strokeStyle = "#fff"; c.lineWidth = 1.5; c.beginPath(); c.moveTo(-120, 0); c.lineTo(120, 0); c.stroke();
    c.lineWidth = 1; c.font = "9px system-ui"; c.fillStyle = "#fff"; c.textAlign = "left";
    for (const p of [-20, -10, 10, 20]) { const y = -p * 1.6, w = p % 20 ? 10 : 18; c.beginPath(); c.moveTo(-w, y); c.lineTo(w, y); c.stroke(); c.fillText(String(Math.abs(p)), w + 3, y + 3); }
    c.restore();
    c.strokeStyle = "#f2a93b"; c.lineWidth = 3; c.beginPath(); c.moveTo(cx - 30, cy); c.lineTo(cx - 10, cy); c.lineTo(cx, cy + 7); c.lineTo(cx + 10, cy); c.lineTo(cx + 30, cy); c.stroke();
    c.lineWidth = 1.5; c.strokeStyle = "rgba(255,255,255,.7)"; c.beginPath(); c.arc(cx, cy, R0, 0, 2 * Math.PI); c.stroke();
    // the tapes
    const tape = (x: number, v: number | null, step: number, unit: string, label: string, sub: string) => {
      const w = 52;
      c.fillStyle = "rgba(11,17,24,.72)"; c.fillRect(x, 5, w, 108);
      if (v !== null && Number.isFinite(v)) {
        c.save(); c.beginPath(); c.rect(x, 5, w, 108); c.clip();
        c.strokeStyle = "rgba(255,255,255,.75)"; c.fillStyle = "#fff"; c.font = "9px system-ui"; c.textAlign = "center"; c.lineWidth = 1;
        const k = 18 / step;
        for (let m = Math.floor((v - 60 / k) / step) * step; m <= v + 60 / k; m += step) {
          const y = cy - (m - v) * k;
          c.beginPath(); c.moveTo(x, y); c.lineTo(x + 5, y); c.stroke(); c.fillText(String(Math.round(m)), x + w / 2 + 2, y + 3);
        }
        c.restore();
      }
      c.fillStyle = "#0b1118"; c.fillRect(x - 1, cy - 9, w + 2, 18); c.strokeStyle = "#f2a93b"; c.lineWidth = 1.5; c.strokeRect(x - 1, cy - 9, w + 2, 18);
      c.fillStyle = "#fff"; c.textAlign = "center"; c.font = "600 11px system-ui"; c.fillText(v === null || !Number.isFinite(v) ? "—" : String(Math.round(v)), x + w / 2, cy + 4);
      c.font = "9px system-ui"; c.fillText(`${label} ${unit}`, x + w / 2, 124);
      if (sub) c.fillText(sub, x + w / 2, H - 2);
    };
    tape(4, s.gs === null ? null : imp ? s.gs * 1.943844 : s.gs, imp ? 10 : 5, imp ? "kt" : "m/s", t("fdGs"), "");
    const aglTxt = s.agl === null ? "" : `${t("fdAgl")}: ${Math.round(imp ? s.agl / 0.3048 : s.agl)} ${imp ? "ft" : "m"}`;
    tape(180, imp ? s.alt / 0.3048 : s.alt, imp ? 100 : 20, imp ? "ft" : "m", t("fdAlt"), aglTxt);
    const hdg = (((s.hdg ?? 0) % 360) + 360) % 360;
    c.font = "600 12px system-ui"; c.textAlign = "center"; c.fillStyle = "#fff"; c.strokeStyle = "#0b1118"; c.lineWidth = 3;
    const txt = `${s.name} · ${hdg.toFixed(0)}°`;
    c.strokeText(txt, cx, H - 4); c.fillText(txt, cx, H - 4);
  });
  return <canvas ref={ref} className="flight-display" style={{ width: W, height: H }} aria-label={t("g3Display")} role="img" />;
}
