import { useState } from "react";
import { activeTab, useApp, type Plot } from "../store";
import { useT } from "../i18n";
import { Icon } from "../icons";
import TimeChart from "./TimeChart";

/** Create signals > Preview > "A plot per axis": each preview line in a plot of its own, in a row
 *  under the plot grid - ordinary time plots (same time axis and zoom as the tab), but not part of
 *  the workspace: nothing is saved or undone, and Create / Clear removes them. */
export default function PreviewPlots() {
  const t = useT();
  const pv = useApp((s) => (s.preview?.separate ? s.preview : null));
  const tab = useApp((s) => activeTab(s.ws));
  const [, setLoading] = useState(false);
  if (!pv) return null;
  return (
    <section className="pv-strip" aria-label={t("previewPlots")}>
      <div className="pv-strip-head">
        <span>{t("previewPlots")}</span>
        <button className="iconbtn" onClick={() => useApp.setState({ preview: null })} title={t("clearPreview")} aria-label={t("clearPreview")}><Icon.X /></button>
      </div>
      <div className="pv-strip-plots" style={{ gridTemplateColumns: `repeat(${pv.lines.length}, minmax(0, 1fr))` }}>
        {pv.lines.map((l, k) => {
          const plot: Plot = { id: `preview:${k}`, title: l.label, signals: [] };
          return (
            <div key={`${k}:${l.label}`} className="plot pv-plot">
              <div className="plot-head"><span className="plot-title">{l.label}</span></div>
              <div className="plot-body"><TimeChart tab={tab} plot={plot} index={-1} onLoading={setLoading} previewOnly={[l]} /></div>
            </div>
          );
        })}
      </div>
    </section>
  );
}
