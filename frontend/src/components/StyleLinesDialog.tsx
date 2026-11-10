import { useMemo, useState } from "react";
import { actions, LINE_STYLES, TRACE_COLORS, useApp, type LineStyle } from "../store";
import { fmtInt, useT } from "../i18n";
import { Icon } from "../icons";
import { useEscape } from "./Overlays";
import { defaultScope, linesInScope, type LineLook, type StyleScope } from "../styleLines";

/** N4: one look for a whole group of lines - colour (one, or the palette in turn), width, line style -
 *  on this plot / this tab / every tab (a group from the signal list) or on the legend selection.
 *  A field left on "keep" stays as each line has it; the change is one Undo step. */
export default function StyleLinesDialog() {
  const t = useT();
  const lang = useApp((s) => s.lang);
  const ws = useApp((s) => s.ws);
  const d = useApp((s) => s.styleDialog)!;
  const close = () => useApp.setState({ styleDialog: null });
  useEscape(close);
  const [scope, setScope] = useState<StyleScope>(() => defaultScope(useApp.getState().ws, d.sigs));
  const [color, setColor] = useState<"keep" | "palette" | string>("keep");
  const [widthText, setWidthText] = useState("");                     // "" = keep
  const [style, setStyle] = useState<"keep" | "auto" | LineStyle>("keep");

  const targets = useMemo(() => d.lines ?? linesInScope(ws, d.sigs, scope), [ws, d, scope]);
  const counts = useMemo(() => (d.lines ? null : {
    plot: linesInScope(ws, d.sigs, "plot").length, tab: linesInScope(ws, d.sigs, "tab").length, all: linesInScope(ws, d.sigs, "all").length,
  }), [ws, d]);
  const width = widthText.trim() === "" ? undefined : Number(widthText);
  const badWidth = width !== undefined && !(width >= 0.5 && width <= 6);
  const look: LineLook = {
    ...(color !== "keep" ? { color } : {}),
    ...(width !== undefined ? { width } : {}),
    ...(style !== "keep" ? { lineStyle: style } : {}),
  };
  const nothing = !Object.keys(look).length;

  const apply = () => { actions.styleLines(targets, look); close(); };

  return (
    <div className="scrim" onMouseDown={close}>
      <div className="dialog rt-dialog sl-dialog" role="dialog" aria-label={t("styleTitle")} onMouseDown={(e) => e.stopPropagation()}>
        <div className="dialog-head">
          <h2>{t("styleTitle")} <span className="muted">· {d.name}</span></h2>
          <button className="iconbtn" onClick={close} aria-label={t("close")}><Icon.X /></button>
        </div>
        <p className="hint rt-lead">{t("styleLead")}</p>
        <div className="dialog-body rt-rows">
          {counts && (
            <fieldset className="sw-mode sl-scope">
              <legend>{t("styleScope")}</legend>
              {(["plot", "tab", "all"] as StyleScope[]).map((k) => (
                <label key={k}><input type="radio" name="sl-scope" value={k} checked={scope === k} onChange={() => setScope(k)} />
                  {" "}{t(`styleScope_${k}` as "styleScope_plot")} <span className="muted">({fmtInt(counts[k], lang)})</span></label>
              ))}
            </fieldset>
          )}
          <fieldset className="sw-mode sl-color">
            <legend>{t("color")}</legend>
            <div className="swatches">
              <button className={`sl-keep${color === "keep" ? " on" : ""}`} onClick={() => setColor("keep")}>{t("styleKeep")}</button>
              <button className={`sl-palette${color === "palette" ? " on" : ""}`} title={t("stylePaletteHint")} onClick={() => setColor("palette")}>{t("stylePalette")}</button>
              {TRACE_COLORS.slice(0, 8).map((c) => (
                <button key={c} className={c === color ? "on" : ""} style={{ background: c }} aria-label={c} onClick={() => setColor(c)} />
              ))}
            </div>
          </fieldset>
          <fieldset className="sw-mode">
            <legend>{t("width")}</legend>
            <label className="ta-field">
              <input className="sl-width" type="number" min={0.5} max={6} step={0.5} placeholder={t("styleKeep")} value={widthText}
                onChange={(e) => setWidthText(e.target.value)} aria-label={t("width")} />
            </label>
          </fieldset>
          <fieldset className="sw-mode">
            <legend>{t("lineStyle")}</legend>
            <select className="sl-style" value={style} onChange={(e) => setStyle(e.target.value as typeof style)} aria-label={t("lineStyle")}>
              <option value="keep">{t("styleKeep")}</option>
              <option value="auto">{t("lineAuto")}</option>
              {LINE_STYLES.map((k) => <option key={k} value={k}>{t(`lineStyle_${k}` as "lineStyle_solid")}</option>)}
            </select>
          </fieldset>
          {badWidth && <p className="hint err">{t("styleBadWidth")}</p>}
        </div>
        <div className="dialog-foot">
          <span className="hint sl-count">{t("styleCount", { n: targets.length })}</span>
          <span className="spacer" />
          <button className="btn outline" onClick={close}>{t("cancel")}</button>
          <button className="btn primary sl-apply" disabled={nothing || badWidth || !targets.length} onClick={apply}>{t("styleApply")}</button>
        </div>
      </div>
    </div>
  );
}
