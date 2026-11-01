/* MF04: a model of one result (a response surface) - trained on the active group's sets, each kind
   validated by cross-validation (errors and R², the best marked, ★ the one used), predicted against
   real, explored (a surface, its contour bands, two cuts through the base values typed), and
   optimised virtually: the best sets the model predicts, meeting the goal's conditions (each its own
   model), saved as a group of virtual sets and exported to be run for real. */
import { useEffect, useMemo, useState } from "react";
import { pickPath } from "../../store";
import { useT, type TKey } from "../../i18n";
import { sweepApi, type SurrogateGrid, type SurrogateReport, type VirtualSet } from "../../sweeps/api";
import { FAILS, HOLDS, rampOf } from "../../sweeps/colors";
import { idOfParams, maskOfKey } from "../../sweeps/groups";
import { fmtValue } from "../../sweeps/scales";
import { notify, notifyError } from "../../sweeps/notify";
import { useSweeps, wireQuestion, type Study } from "../../sweeps/state";
import { colLabel } from "../../sweeps/view";
import NumField from "./NumField";

const MODEL_KEY: Record<string, TKey> = { poly: "swModelPoly", rbf: "swModelRbf", knn: "swModelKnn", kriging: "swModelKriging" };
const f3 = (x: number | null | undefined) => (x === null || x === undefined || !Number.isFinite(x) ? "–" : fmtValue(x));
const pc = (x: number | null | undefined) => (x === null || x === undefined || !Number.isFinite(x) ? "–" : `${(x * 100).toFixed(1)}%`);

export default function SurrogateView({ study }: { study: Study }) {
  const t = useT();
  const a = study.answer!;
  const v = study.view;
  const [column, setColumn] = useState("");
  const [rep, setRep] = useState<SurrogateReport | null>(null);
  const [fav, setFav] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const group = v.activeGroup ?? "all";
  const sets = useMemo(() => {
    if (group === "all") return null;
    const m = maskOfKey(a, v.groups ?? [], group, v.rerun);
    return m ? [...m.keys()].filter((i) => m[i]) : null;
  }, [a, v.groups, v.rerun, group]);
  const choices = a.sets.filter((c) => c.kind === "num" && (c.group === "goal" || c.group === "output" || c.group === "derived" || (c.group === "condition" && c.part === "worst")));
  const train = async () => {
    setBusy(true);
    try { const r = await sweepApi.surrogateTrain(study.tableId, wireQuestion(study), column || null, sets); setRep(r); setFav(r.best); }
    catch (e) { notifyError(e); } finally { setBusy(false); }
  };
  const model = fav ?? rep?.best ?? null;
  const yName = column ? colLabel(t, study, column) : study.question.goal ? colLabel(t, study, "#goal") : t("swRepItHolding");
  return (
    <div className="sw-model">
      <div className="sw-row sw-model-head">
        <label>{t("swModelOf")} <select aria-label={t("swModelOf")} value={column} onChange={(e) => { setColumn(e.target.value); setRep(null); }}>
          <option value="">{study.question.goal ? t("swSensGoal") : t("swRepItHolding")}</option>
          {choices.map((c) => <option key={c.name} value={c.name}>{colLabel(t, study, c.name)}</option>)}
        </select></label>
        <span className="hint">{t("swSensGroup", { g: group })}</span>
        <button className="btn primary" disabled={busy} onClick={train}>{busy ? t("swReading") : t("swModelTrain")}</button>
      </div>
      <p className="hint">{t("swModelHint")}</p>
      {rep && <>
        <div className="sw-table-wrap">
          <table className="sw-table sw-model-table">
            <thead><tr><th>★</th><th>{t("swModelKind")}</th><th className="num">{t("swModelMae")}</th><th className="num">{t("swModelRel")}</th>
              <th className="num">{t("swModelNorm")}</th><th className="num">R²</th></tr></thead>
            <tbody>
              {rep.table.map((r) => (
                <tr key={r.model} data-model={r.model} className={`${r.model === rep.best ? "best" : ""}${r.available ? "" : " off"}`}>
                  <td><input type="radio" name="sw-fav" aria-label={t("swModelFav", { m: t(MODEL_KEY[r.model] ?? "swModelPoly") })} disabled={!r.available}
                    checked={model === r.model} onChange={() => setFav(r.model)} /></td>
                  <td>{t(MODEL_KEY[r.model] ?? "swModelPoly")}{r.model === rep.best && <span className="sw-best-tag"> {t("swModelBest")}</span>}</td>
                  {r.available ? <><td className="num">{f3(r.mae)}</td><td className="num">{pc(r.rel)}</td><td className="num">{pc(r.norm)}</td><td className="num">{f3(r.r2)}</td></>
                    : <td colSpan={4} className="hint">{r.error}</td>}
                </tr>
              ))}
            </tbody>
          </table>
          <p className="hint">{t("swModelCv", { n: rep.n, k: rep.folds })}</p>
        </div>
        {model && <div className="sw-model-grid">
          <PredVsReal pts={rep.predicted[model] ?? []} t={t} yName={yName} />
          <Explore rep={rep} model={model} />
        </div>}
        {model && <Virtual study={study} rep={rep} model={model} column={column} sets={sets} />}
      </>}
    </div>
  );
}

function PredVsReal({ pts, t, yName }: { pts: [number, number][]; t: (k: TKey, p?: Record<string, string | number>) => string; yName: string }) {
  const W = 300, H = 260, L = 44, B = 36, T = 10, R = 10;
  if (!pts.length) return null;
  const all = pts.flat();
  let lo = Math.min(...all), hi = Math.max(...all);
  if (lo === hi) { lo -= 1; hi += 1; }
  const X = (v: number) => L + ((v - lo) / (hi - lo)) * (W - L - R), Y = (v: number) => H - B - ((v - lo) / (hi - lo)) * (H - B - T);
  return (
    <figure className="sw-model-fig">
      <svg viewBox={`0 0 ${W} ${H}`} className="sw-chart" role="img" aria-label={t("swModelPvR")}>
        <line x1={X(lo)} y1={Y(lo)} x2={X(hi)} y2={Y(hi)} className="sw-ax-line" strokeDasharray="4 3" />
        <line x1={L} y1={H - B} x2={W - R} y2={H - B} className="sw-ax-line" /><line x1={L} y1={T} x2={L} y2={H - B} className="sw-ax-line" />
        {pts.map(([r, p], i) => Number.isFinite(p) && <circle key={i} cx={X(r)} cy={Y(p)} r={2.2} fill={HOLDS} />)}
        <text x={L} y={H - B + 13} className="sw-ax">{fmtValue(lo)}</text><text x={W - R} y={H - B + 13} textAnchor="end" className="sw-ax">{fmtValue(hi)}</text>
        <text x={(L + W - R) / 2} y={H - 4} textAnchor="middle" className="sw-ax">{t("swModelReal", { c: yName })}</text>
        <text x={12} y={(T + H - B) / 2} transform={`rotate(-90 12 ${(T + H - B) / 2})`} textAnchor="middle" className="sw-ax">{t("swModelPred")}</text>
      </svg>
      <figcaption className="hint">{t("swModelPvR")}</figcaption>
    </figure>
  );
}

/** The model over two parameters (colour, and its bands as a contour) and along each of them, the
 *  others at the base values (typed; a level for a text parameter). */
function Explore({ rep, model }: { rep: SurrogateReport; model: string }) {
  const t = useT();
  const ps = rep.params;
  const [x, setX] = useState(ps[0]?.name ?? "");
  const [y, setY] = useState(ps[1]?.name ?? ps[0]?.name ?? "");
  const [base, setBase] = useState<Record<string, string | number>>(() =>
    Object.fromEntries(ps.map((p) => [p.name, p.kind === "number" ? +((p.lo + p.hi) / 2).toPrecision(6) : p.levels[0]])));
  const [surf, setSurf] = useState<SurrogateGrid | null>(null);
  const [cx, setCx] = useState<SurrogateGrid | null>(null);
  const [cy, setCy] = useState<SurrogateGrid | null>(null);
  const bk = JSON.stringify(base);
  useEffect(() => {
    let live = true;
    const go = async () => {
      try {
        const [s, a, b] = await Promise.all([
          x !== y ? sweepApi.surrogateGrid(rep.key, model, base, x, y, 30) : Promise.resolve(null),
          sweepApi.surrogateGrid(rep.key, model, base, x, null, 60),
          x !== y ? sweepApi.surrogateGrid(rep.key, model, base, y, null, 60) : Promise.resolve(null)]);
        if (live) { setSurf(s); setCx(a); setCy(b); }
      } catch (e) { if (live) notifyError(e); }
    };
    void go();
    return () => { live = false; };
  }, [rep.key, model, x, y, bk]); // eslint-disable-line react-hooks/exhaustive-deps
  const sel = (val: string, set: (s: string) => void, label: TKey) => (
    <label>{t(label)} <select aria-label={t(label)} value={val} onChange={(e) => set(e.target.value)}>{ps.map((p) => <option key={p.name} value={p.name}>{p.name}</option>)}</select></label>
  );
  return (
    <div className="sw-model-explore">
      <div className="sw-row sw-model-base">
        {sel(x, setX, "swMapX")}{sel(y, setY, "swMapY")}
        <span className="hint">{t("swModelBase")}</span>
        {ps.map((p) => p.kind === "number"
          ? <label key={p.name} className="mono">{p.name} <NumField value={Number(base[p.name])} lo={p.lo} hi={p.hi} label={t("swModelBaseOf", { c: p.name })}
              onChange={(v) => setBase({ ...base, [p.name]: v })} /></label>
          : <label key={p.name} className="mono">{p.name} <select value={String(base[p.name])} onChange={(e) => setBase({ ...base, [p.name]: e.target.value })}>
              {p.levels.map((l) => <option key={l}>{l}</option>)}</select></label>)}
      </div>
      <div className="sw-model-2x2">
        {surf && <Surface g={surf} bands={0} t={t} label={t("swModelSurface")} />}
        {surf && <Surface g={surf} bands={8} t={t} label={t("swModelContour")} />}
        {cx && <Cut g={cx} t={t} />}
        {cy && <Cut g={cy} t={t} />}
      </div>
    </div>
  );
}

function Surface({ g, bands, t, label }: { g: SurrogateGrid; bands: number; t: (k: TKey) => string; label: string }) {
  void t;
  const z = g.z as (number | null)[][];
  const vals = z.flat().filter((v): v is number => v !== null);
  const lo = Math.min(...vals), hi = Math.max(...vals);
  const ramp = rampOf("viridis");
  const nx = g.xs.length, ny = g.ys!.length, W = 260, H = 220, L = 6, B = 6;
  const cw = (W - 2 * L) / nx, ch = (H - 2 * B) / ny;
  const tone = (v: number | null) => { if (v === null || hi === lo) return FAILS; let f = (v - lo) / (hi - lo); if (bands) f = Math.min(bands - 1, Math.floor(f * bands)) / (bands - 1); return ramp(f); };
  return (
    <figure className="sw-model-fig">
      <svg viewBox={`0 0 ${W} ${H}`} className="sw-chart" role="img" aria-label={label}>
        {z.map((row, j) => row.map((v, i) => <rect key={`${i}:${j}`} x={L + i * cw} y={H - B - (j + 1) * ch} width={cw + 0.5} height={ch + 0.5} fill={tone(v)} />))}
      </svg>
      <figcaption className="hint">{label}: {g.x} × {g.y} · {fmtValue(lo)} – {fmtValue(hi)}</figcaption>
    </figure>
  );
}

function Cut({ g, t }: { g: SurrogateGrid; t: (k: TKey, p?: Record<string, string | number>) => string }) {
  const z = g.z as (number | null)[];
  const W = 260, H = 220, L = 40, B = 28, T = 8, R = 8;
  const vals = z.filter((v): v is number => v !== null);
  if (!vals.length) return null;
  let lo = Math.min(...vals), hi = Math.max(...vals);
  if (lo === hi) { lo -= 1; hi += 1; }
  const n = g.xs.length;
  const X = (i: number) => L + (n > 1 ? i / (n - 1) : 0.5) * (W - L - R), Y = (v: number) => H - B - ((v - lo) / (hi - lo)) * (H - B - T);
  const pts = z.map((v, i) => (v === null ? null : `${X(i)},${Y(v)}`)).filter(Boolean).join(" ");
  return (
    <figure className="sw-model-fig">
      <svg viewBox={`0 0 ${W} ${H}`} className="sw-chart" role="img" aria-label={t("swModelCut", { c: g.x })}>
        <line x1={L} y1={H - B} x2={W - R} y2={H - B} className="sw-ax-line" /><line x1={L} y1={T} x2={L} y2={H - B} className="sw-ax-line" />
        <polyline points={pts} fill="none" stroke={HOLDS} strokeWidth={2} />
        <text x={L - 3} y={T + 8} textAnchor="end" className="sw-ax">{fmtValue(hi)}</text><text x={L - 3} y={H - B} textAnchor="end" className="sw-ax">{fmtValue(lo)}</text>
        <text x={L} y={H - B + 13} className="sw-ax">{String(g.xs[0])}</text><text x={W - R} y={H - B + 13} textAnchor="end" className="sw-ax">{String(g.xs[n - 1])}</text>
      </svg>
      <figcaption className="hint">{t("swModelCut", { c: g.x })}</figcaption>
    </figure>
  );
}

function Virtual({ study, rep, model, column, sets }: { study: Study; rep: SurrogateReport; model: string; column: string; sets: number[] | null }) {
  const t = useT();
  const goalDir = study.question.goal?.direction ?? "max";
  const [dir, setDir] = useState<"max" | "min">(goalDir);
  const [n, setN] = useState(10);
  const [conds, setConds] = useState(true);
  const [res, setRes] = useState<VirtualSet[] | null>(null);
  const [busy, setBusy] = useState(false);
  const order = study.answer!.sets.filter((c) => c.group === "param").map((c) => c.name);
  const run = async () => {
    setBusy(true);
    try { setRes((await sweepApi.surrogateOptimise(study.tableId, wireQuestion(study), column || null, sets, model, dir, n, conds)).sets); }
    catch (e) { notifyError(e); } finally { setBusy(false); }
  };
  const save = () => {
    if (!res) return;
    const gs = study.view.groups ?? [];
    let color = 0;
    while (gs.some((g) => g.color === color)) color++;
    const k = gs.filter((g) => g.source === "virtual").length + 1;
    useSweeps.getState().setView({ groups: [...gs, { id: `g${Date.now().toString(36)}v`, name: t("swVirtualGroup", { n: k }), color, source: "virtual", frozen: true,
      ids: res.map((s) => idOfParams(s.params, order)) }], colorBy: "#group" });
    notify(t("swVirtualSaved", { n: res.length }));
  };
  const exportList = async () => {
    if (!res) return;
    const p = await pickPath({ mode: "save", title: t("swVirtualExport"), exts: [".csv", ".tsv", ".json", ".m", ".py"], defaultName: `${study.name.replace(/\.[^.]+$/, "")}_virtual.csv` });
    if (!p) return;
    try {
      const r = await sweepApi.suggestExport(study.tableId, wireQuestion(study), res.map((s) => s.params), p, true);
      notify(t("swExported", { n: r.rows, path: r.path }));
      useSweeps.getState().journal("export", { path: r.path, n: r.rows });
    } catch (e) { notifyError(e); }
  };
  void rep;
  return (
    <section className="sw-virtual">
      <h3>{t("swVirtualTitle")}</h3>
      <div className="sw-row">
        <select aria-label={t("swPDirection")} value={dir} onChange={(e) => setDir(e.target.value as "max" | "min")}>
          <option value="max">↑ {t("swMax")}</option><option value="min">↓ {t("swMin")}</option></select>
        <label>{t("swDoeN")} <NumField value={n} lo={1} hi={50} label={t("swDoeN")} onChange={(x) => setN(Math.max(1, Math.min(50, Math.round(x))))} /></label>
        <label className="acheck"><input type="checkbox" checked={conds} onChange={(e) => setConds(e.target.checked)} />{t("swVirtualConds")}</label>
        <button className="btn primary" disabled={busy} onClick={run}>{t("swVirtualRun")}</button>
      </div>
      {res && <>
        <div className="sw-table-wrap">
          <table className="sw-table sw-virtual-table">
            <thead><tr><th />{order.map((p) => <th key={p} className="num">{p}</th>)}<th className="num">{t("swModelPred")}</th><th>{t("swVirtualMeets")}</th></tr></thead>
            <tbody>{res.map((s, i) => (
              <tr key={i} className="status-virtual"><td>≈</td>{order.map((p) => <td key={p} className="num">{typeof s.params[p] === "number" ? fmtValue(s.params[p] as number) : String(s.params[p])}</td>)}
                <td className="num">{f3(s.predicted)}</td><td className={s.meets ? "ok" : "bad"}>{s.meets ? "✓" : "✗"}</td></tr>))}</tbody>
          </table>
        </div>
        <div className="sw-row">
          <button className="btn outline" onClick={save}>{t("swVirtualSave")}</button>
          <button className="btn outline" onClick={exportList}>{t("swVirtualExport")}</button>
          <span className="hint">{t("swVirtualHint")}</span>
        </div>
      </>}
    </section>
  );
}
