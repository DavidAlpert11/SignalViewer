import { linkedExtra } from "../peers";
import { useMemo, useState } from "react";
import { useApp } from "../store";
import { useT } from "../i18n";
import { Icon } from "../icons";
import { useEscape } from "./Overlays";
import { applyTransform, describeTransform } from "../transforms";
import type { SignalTransform } from "../api";
import ExprInput from "./ExprInput";
import { FUNC_INFO, FUNC_NAMES, parenProblem, unknownNames, VAR_E, VAR_PI, VAR_T, VAR_X } from "../formulaHelp";
import { fuzzySort } from "../fuzzy";
import { substituteParams } from "../formulaRefs";

const TF_VARS = [VAR_X, VAR_T, VAR_PI, VAR_E];
const TF_ALLOWED = new Set(TF_VARS.map((v) => v.name));

type Fn = "none" | "abs" | "negate" | "deriv" | "integ" | "smooth" | "lowpass" | "highpass" | "custom";
const PRESET: Record<string, Fn> = { "abs(x)": "abs", "-x": "negate", "deriv(x)": "deriv", "integ(x)": "integ" };

/** Change many signals THEMSELVES at once (no new signals): function, scale, offset, time shift. */
export default function TransformDialog() {
  const t = useT();
  const targets = useApp((s) => s.transformTargets) ?? [];
  const runs = useApp((s) => s.runs);
  const sigs = useMemo(() => runs.flatMap((r) => r.signals).filter((s) => targets.includes(s.id)), [runs, targets]);
  // start from the current change when every target shares the same one
  const shared: SignalTransform | null = useMemo(() => {
    const keys = new Set(sigs.map((s) => JSON.stringify(s.transform ?? null)));
    return keys.size === 1 ? sigs[0]?.transform ?? null : null;
  }, [sigs]);
  const init = shared?.expr ?? "";
  const m = /^(smooth|lowpass|highpass)\(x, *([\d.]+)\)$/.exec(init);
  const [fn, setFn] = useState<Fn>(!init ? "none" : PRESET[init] ?? (m ? (m[1] as Fn) : "custom"));
  const [n, setN] = useState(m && m[1] === "smooth" ? m[2] : "10");
  const [fc, setFc] = useState(m && m[1] !== "smooth" ? m[2] : "10");
  const [custom, setCustom] = useState(init && !PRESET[init] && !m ? init : "x");
  const [scale, setScale] = useState(String(shared?.scale ?? 1));
  const [offset, setOffset] = useState(String(shared?.offset ?? 0));
  const [dt, setDt] = useState(String(shared?.dt ?? 0));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const close = () => useApp.setState({ transformTargets: null });
  useEscape(close);

  const expr = fn === "none" ? "" : fn === "abs" ? "abs(x)" : fn === "negate" ? "-x" : fn === "deriv" ? "deriv(x)"
    : fn === "integ" ? "integ(x)" : fn === "smooth" ? `smooth(x, ${n})` : fn === "lowpass" ? `lowpass(x, ${fc})`
    : fn === "highpass" ? `highpass(x, ${fc})` : custom.trim();
  const num = (v: string, d: number) => (v.trim() === "" || !Number.isFinite(Number(v)) ? d : Number(v));
  const spec: SignalTransform = { expr, scale: num(scale, 1), offset: num(offset, 0), dt: num(dt, 0) };
  const logs = useApp((s) => s.logs);
  const targetRuns = Array.from(new Set(targets.map((id) => id.slice(0, id.indexOf("/")))));
  const tfParams = useMemo(() => targetRuns.flatMap((rid) => logs[rid]?.params ?? []).map((p) => ({ name: p.name, value: p.value })),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [logs, targetRuns.join("|")]);
  const paramSub = fn === "custom" && custom.includes("param(") ? substituteParams(custom, runs, t as never, targetRuns) : null;
  // checked while typing: brackets, and names this dialog does not know (with a likely fix)
  const exprProblem = useMemo(() => {
    if (fn !== "custom" || !custom.trim()) return null;
    if (paramSub?.error) return paramSub.error;
    const p = parenProblem(custom);
    if (p) return t(p);
    const unk = unknownNames(custom, TF_ALLOWED);
    if (!unk.length) return null;
    const w = unk[0];
    if (runs.some((r) => r.signals.some((x) => x.name === w))) return t("fxOnlyX", { name: w });
    if (FUNC_INFO[w]) return t("fxNeedsParen", { name: w });
    const guess = fuzzySort([...FUNC_NAMES, ...TF_ALLOWED], (x) => x, w)[0];
    return t("fxUnknownTf", { name: w }) + (guess ? " " + t("fxDidYouMean", { name: guess }) : "");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fn, custom, runs, t, paramSub?.error]);
  const bad = [scale, offset, dt].some((v) => v.trim() !== "" && !Number.isFinite(Number(v))) || !!exprProblem;

  const run = async (tf: SignalTransform | null) => {
    setBusy(true); setError("");
    // param("NAME") becomes the value from the targets' flight log before it is sent
    if (tf?.expr && tf.expr.includes("param(")) {
      const r = substituteParams(tf.expr, runs, t as never, targetRuns);
      if (r.error) { useApp.getState().toast({ kind: "error", text: r.error }); return; }
      tf = { ...tf, expr: r.text };
    }
    try {
      await applyTransform(targets, tf);
      // the selection did its job: the next pick in the file list starts a new one
      if (targets.length > 1) useApp.setState({ listSelUsed: true });
      close();
    }
    catch (e) { setError(String((e as Error).message)); }
    finally { setBusy(false); }
  };
  const anyChanged = sigs.some((s) => s.transform);

  return (
    <div className="scrim" onMouseDown={close}>
      <div className="dialog tf-dialog" role="dialog" aria-label={t("tfTitle")} onMouseDown={(e) => e.stopPropagation()}>
        <div className="dialog-head"><h2>{t("tfTitle")} <span className="muted">· {t("nChosen", { n: targets.length })}</span></h2>
          <button className="iconbtn" onClick={close} aria-label={t("close")}><Icon.X /></button></div>
        <div className="dialog-pad">
          <p className="hint tf-note">{t("tfNote")}</p>
          {sigs.length <= 1
            ? <div className="tf-targets">{sigs.map((s) => s.name).join(", ")}</div>
            : <div className="msp-chips tf-chips">
                {/* every target, each removable: the same change is made on each of them, x being that signal */}
                {sigs.map((s) => (
                  <span key={s.id} className="msp-chip" title={s.id}>{s.name}
                    <button type="button" aria-label={`${t("remove")}: ${s.name}`}
                      onClick={() => useApp.setState({ transformTargets: targets.filter((id) => id !== s.id) })}><Icon.X width={10} height={10} /></button></span>
                ))}
              </div>}
          <label className="afield"><span>{t("tfFunction")}</span>
            <select value={fn} onChange={(e) => {
              // switching to "custom" starts from the chosen function, ready to edit
              if (e.target.value === "custom" && fn !== "custom" && expr) setCustom(expr);
              setFn(e.target.value as Fn);
            }}>
              <option value="none">{t("tfNone")}</option>
              <option value="abs">{t("opAbs")} — abs(x)</option>
              <option value="negate">{t("opNegate")} — −x</option>
              <option value="deriv">{t("opDerivative")}</option>
              <option value="integ">{t("opIntegral")}</option>
              <option value="smooth">{t("opSmooth")}</option>
              <option value="lowpass">{t("opLowpass")}</option>
              <option value="highpass">{t("opHighpass")}</option>
              <option value="custom">{t("tfCustom")}</option>
            </select></label>
          {fn === "smooth" && <label className="afield"><span>{t("windowSamples")}</span><input inputMode="numeric" value={n} onChange={(e) => setN(e.target.value)} /></label>}
          {(fn === "lowpass" || fn === "highpass") && <label className="afield" title={t("cutoffHint")}><span>{t("cutoffHz")}</span><input inputMode="decimal" value={fc} onChange={(e) => setFc(e.target.value)} /></label>}
          {fn === "custom" && <div className="afield"><span>{t("tfExpr")}</span>
            <ExprInput value={custom} onChange={setCustom} vars={TF_VARS} params={tfParams} placeholder="x * 9.81" ariaLabel={t("tfExpr")}
              invalid={!!exprProblem} onSubmit={() => { if (!bad && !busy && targets.length) run(spec); }} />
            {exprProblem ? <p className="hint err fx-err">{exprProblem}</p>
              : <p className="hint fx-help">{targets.length > 1 ? t("tfExprHintMany", { n: targets.length }) : t("tfExprHint")}</p>}</div>}
          {linkedExtra(targets) > 0 && <p className="hint tf-linked">{t("tfLinkedExtra", { n: linkedExtra(targets) })}</p>}
          <div className="arow">
            <label className="afield"><span>{t("scale")}</span><input inputMode="decimal" value={scale} onChange={(e) => setScale(e.target.value)} /></label>
            <label className="afield"><span>{t("offset")}</span><input inputMode="decimal" value={offset} onChange={(e) => setOffset(e.target.value)} /></label>
            <label className="afield"><span>{t("signalTimeOffset")}</span><input inputMode="decimal" value={dt} onChange={(e) => setDt(e.target.value)} /></label>
          </div>
          <p className="tf-result" dir="ltr">{describeTransform({ expr: expr || undefined, scale: spec.scale, offset: spec.offset, dt: spec.dt }) || "y = x"}</p>
          {error && <p className="hint err">{error}</p>}
        </div>
        <div className="dialog-foot">
          {anyChanged && <button className="btn outline" disabled={busy} onClick={() => run(null)}>{t("tfRemove")}</button>}
          <span className="spacer" />
          <button className="btn outline" onClick={close}>{t("cancel")}</button>
          <button className="btn primary" disabled={busy || bad || !targets.length} onClick={() => run(spec)}>
            {targets.length === 1 ? t("tfApply1") : t("tfApply", { n: targets.length })}</button>
        </div>
      </div>
    </div>
  );
}
