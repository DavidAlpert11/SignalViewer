/* Any two columns as points (a point per set, or per run), coloured like the lines and with the
   same filters; a click opens the point's set. */
import { useEffect, useMemo, useRef } from "react";
import { useT } from "../../i18n";
import { category, FAILS, HOLDS, ramp } from "../../sweeps/colors";
import { keptMask } from "../../sweeps/filters";
import { makeScale } from "../../sweeps/scales";
import { useSweeps, type Study } from "../../sweeps/state";
import { axisChoices, colLabel, scaleOf, scopedColumns } from "../../sweeps/view";

const W = 760, H = 460, L = 60, B = 40, T = 12, R = 16;

export default function ScatterView({ study }: { study: Study }) {
  const t = useT();
  const st = useSweeps.getState();
  const cv = useRef<HTMLCanvasElement>(null);
  const { cols, n } = useMemo(() => scopedColumns(study), [study]);
  const choices = axisChoices(study);
  const v = study.view;
  const xName = v.scatterX && cols.has(v.scatterX) ? v.scatterX : choices[0];
  const yName = v.scatterY && cols.has(v.scatterY) ? v.scatterY : (study.question.goal && cols.has("#goal") ? "#goal" : choices[1]);
  const kept = useMemo(() => keptMask(cols, v.filters, n), [cols, v.filters, n]);
  useEffect(() => {
    const c = cv.current, xc = cols.get(xName ?? ""), yc = cols.get(yName ?? "");
    if (!c || !xc || !yc) return;
    const dpr = window.devicePixelRatio || 1;
    c.width = W * dpr; c.height = H * dpr;
    const ctx = c.getContext("2d")!;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, W, H);
    const css = getComputedStyle(c), muted = css.getPropertyValue("--muted").trim() || "#888";
    const sx = makeScale(xc, scaleOf(study, xc.name, xc)), sy = makeScale(yc, scaleOf(study, yc.name, yc));
    const px = (val: number) => L + sx.norm(val) * (W - L - R), py = (val: number) => H - B - sy.norm(val) * (H - B - T);
    ctx.strokeStyle = muted; ctx.beginPath(); ctx.moveTo(L, T); ctx.lineTo(L, H - B); ctx.lineTo(W - R, H - B); ctx.stroke();
    ctx.fillStyle = muted; ctx.font = "11px 'IBM Plex Sans', sans-serif"; ctx.textAlign = "center";
    for (const tk of sx.ticks) ctx.fillText(tk.label, L + tk.t * (W - L - R), H - B + 14);
    ctx.textAlign = "right";
    for (const tk of sy.ticks) ctx.fillText(tk.label, L - 5, H - B - tk.t * (H - B - T) + 4);
    const cc = v.colorBy ? cols.get(v.colorBy) : undefined;
    const cs = cc && cc.kind === "num" ? makeScale(cc, "linear") : null;
    const colour = (r: number) => !cc ? HOLDS : (v.colorBy === "#holds" || v.colorBy === "#pareto" || v.colorBy === "#partial") ? (cc.values[r] === 1 ? HOLDS : FAILS)
      : cc.kind === "cat" ? category(cc.values[r]) : ramp(cs!.norm(cc.values[r]));
    const jitter = (s: typeof sx) => (s.places ? (Math.random() - 0.5) * 6 : 0);
    ctx.globalAlpha = n > 20000 ? 0.25 : n > 2000 ? 0.5 : 0.85;
    for (let r = 0; r < n; r++) {
      if (!kept[r]) continue;
      const X = px(xc.values[r]) + jitter(sx), Y = py(yc.values[r]) + jitter(sy);
      if (!Number.isFinite(X) || !Number.isFinite(Y)) continue;
      ctx.fillStyle = colour(r); ctx.fillRect(X - 2, Y - 2, 4, 4);
    }
    ctx.globalAlpha = 1;
  }, [cols, n, kept, xName, yName, v.colorBy, study]);
  const sel = (key: "scatterX" | "scatterY", val: string | undefined) => (
    <select value={val ?? ""} onChange={(e) => st.setView({ [key]: e.target.value })}>
      {choices.map((c) => <option key={c} value={c}>{colLabel(t, study, c)}</option>)}
    </select>
  );
  return (
    <div className="sw-scatter">
      <div className="sw-row"><label>{t("swMapX")} {sel("scatterX", xName)}</label><label>{t("swMapY")} {sel("scatterY", yName)}</label>
        <span className="hint">{t("swScatterHint")}</span></div>
      <canvas ref={cv} style={{ width: W, maxWidth: "100%", height: H }} role="img" aria-label={`${xName} / ${yName}`} />
    </div>
  );
}
