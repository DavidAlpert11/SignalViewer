import { useEscape } from "./Overlays";
import { useApp } from "../store";
import { useT } from "../i18n";
import { Icon } from "../icons";

/** Report preview (R-04): the interactive HTML report, shown in-app before saving. */
export default function ReportPreview() {
  const t = useT();
  const html = useApp((s) => s.reportPreviewHtml);
  useEscape(() => useApp.setState({ reportPreviewHtml: null }), !!html);
  if (!html) return null;
  const close = () => useApp.setState({ reportPreviewHtml: null });
  return (
    <div className="scrim" style={{ paddingTop: "4vh" }} onMouseDown={close}>
      <div className="dialog preview-dialog" role="dialog" aria-label={t("reportPreview")} onMouseDown={(e) => e.stopPropagation()}
        onKeyDown={(e) => { if (e.key === "Escape") close(); }}>
        <div className="dialog-head"><h2>{t("reportPreview")}</h2>
          <button className="iconbtn" autoFocus onClick={close} aria-label={t("close")}><Icon.X /></button></div>
        <iframe title={t("reportPreview")} srcDoc={html} sandbox="allow-scripts" className="preview-frame" />
      </div>
    </div>
  );
}
