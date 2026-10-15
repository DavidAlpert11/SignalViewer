import { useApp, fileLabel } from "../store";
import { fmtNum, useT } from "../i18n";
import { Icon } from "../icons";
import { openSuggested } from "../smartStart";
import { openTemplates } from "../templateMenu";
import { tx } from "../templates";
import HealthRow from "./HealthRow";

/** T29: suggestions after the first file opens - the template that fits it best and, for a flight
 *  log, the findings of its health check most worth a look. Floats over the plot area (it does not
 *  take room from the plots) until closed or used. */
export default function StartCard() {
  const t = useT();
  const lang = useApp((s) => s.lang);
  const card = useApp((s) => s.startCard);
  const runs = useApp((s) => s.runs);
  if (!card || !runs.some((r) => r.id === card.runId)) return null;
  const close = () => useApp.setState({ startCard: null });
  return (
    <section className="start-card" role="dialog" aria-label={t("startTitle")}>
      <div className="start-head">
        <h3>{t("startTitle")} <span className="muted">{fileLabel(runs, card.runId)}</span></h3>
        <button className="iconbtn" onClick={close} aria-label={t("close")} title={t("close")}><Icon.X /></button>
      </div>
      {card.template && (
        <div className="start-tpl">
          <p>{t("startSuggest")} <b>{tx(card.template.name, lang)}</b>
            <span className="muted"> · {t("startFits", { p: fmtNum(Math.round(card.template.fit * 100), lang) })}</span></p>
          <div className="arow">
            <button className="btn primary" onClick={() => openSuggested(card)}>{t("startOpen")}</button>
            <button className="btn outline" onClick={() => { openTemplates(card.template!.id); close(); }}>{t("startOther")}</button>
          </div>
        </div>
      )}
      {card.health && (
        <div className="start-health health">
          <h4>{card.health.length ? t("startWorthALook") : t("startHealthOk")}</h4>
          {card.health.length > 0 && <ol className="health-list">
            {card.health.map((f, i) => <HealthRow key={i} f={f} runId={card.runId} maxSpans={2} />)}
          </ol>}
          <button className="linklike" onClick={() => useApp.setState({ panel: "log" })}>{t("startLogPanel")}</button>
        </div>
      )}
    </section>
  );
}
