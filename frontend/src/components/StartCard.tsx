import { useEffect, useState } from "react";
import { tabHasContent, useApp, fileLabel } from "../store";
import { fmtNum, useT } from "../i18n";
import { Icon } from "../icons";
import { openSuggested } from "../smartStart";
import { judgeAgainst } from "../judge";
import { openTemplates } from "../templateMenu";
import { tx } from "../templates";
import HealthRow from "./HealthRow";

/** T29: suggestions after the first file opens - the template that fits it best and, for a flight
 *  log, the findings of its health check most worth a look. Floats over the plot area (it does not
 *  take room from the plots) until closed or used. U2: once there is no template left to offer (the
 *  view is open), the findings are docked beside the timeline as "N findings" (FindingsDock) - they
 *  no longer cover the plots' data - and open over the plots only when asked. */
export default function StartCard() {
  const t = useT();
  const lang = useApp((s) => s.lang);
  const card = useApp((s) => s.startCard);
  const runs = useApp((s) => s.runs);
  const open = useApp((s) => s.findingsOpen);
  // a suggested view is for the start: with two tabs of the user's own (a comparison's tabs, a plot
  // moved to a new tab) it was still floating over them, on every tab
  const underWay = useApp((s) => s.ws.tabs.filter(tabHasContent).length >= 2);
  useEffect(() => {
    if (card?.template && !card.files && underWay) useApp.setState({ startCard: card.health?.length || card.golden ? { ...card, template: null } : null });
  }, [card, underWay]);
  if (!card || !runs.some((r) => r.id === card.runId)) return null;
  if (!card.template && !card.golden && !open) return null;   // docked: FindingsDock
  // findings only: X folds them back into the dock; with a suggestion it closes the card, as before
  const close = () => useApp.setState(card.template || card.golden ? { startCard: null } : { findingsOpen: false });
  const judge = async () => {
    const g = card.golden!;
    useApp.setState({ startCard: { ...card, golden: null }, findingsOpen: false });
    await judgeAgainst(card.runId, g);
  };
  return (
    <section className="start-card" role="dialog" aria-label={t("startTitle")}>
      <div className="start-head">
        <h3>{t("startTitle")} <span className="muted">{card.files ? t("startFiles", { n: card.files }) : fileLabel(runs, card.runId)}</span></h3>
        <button className="iconbtn" onClick={close} aria-label={t("close")} title={t("close")}><Icon.X /></button>
      </div>
      <NextStep card={card} />
      {card.golden && (
        <div className="start-tpl start-judge">
          <p>★ <b>{t("startJudge", { name: card.golden.name })}</b>
            <span className="muted"> · {t("startJudgeWhy", { p: fmtNum(Math.round(card.golden.share * 100), lang) })}</span></p>
          <div className="arow"><button className="btn primary" onClick={judge}>{t("startJudgeBtn")}</button></div>
        </div>
      )}
      {card.template && (
        <div className="start-tpl">
          <p>{t("startSuggest")} <b>{tx(card.template.name, lang)}</b>
            <span className="muted"> · {card.files ? t("startCompare") : t("startFits", { p: fmtNum(Math.round(card.template.fit * 100), lang) })}</span></p>
          <div className="arow">
            <button className={`btn ${card.golden ? "outline" : "primary"}`} onClick={() => openSuggested(card)}>{t("startOpen")}</button>
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

/** U2: the health check's findings docked beside the timeline - "! 3 findings" opens them (the start
 *  card's list), × puts them away (the Log panel has them all, the timeline keeps their marks). */
export function FindingsDock() {
  const t = useT();
  const card = useApp((s) => s.startCard);
  const runs = useApp((s) => s.runs);
  const open = useApp((s) => s.findingsOpen);
  if (!card || card.template || !card.health?.length || !runs.some((r) => r.id === card.runId)) return null;
  const n = card.health.length;
  const level = card.health.some((f) => f.level === "error") ? "error" : "warning";
  return (
    <span className={`findings-dock ${level}`}>
      <button className="findings-btn" aria-expanded={open} onClick={() => useApp.setState({ findingsOpen: !open })}
        title={t("findingsShow")}>
        <span className={`hicon ${level}`} aria-hidden="true">{level === "error" ? "✕" : "!"}</span>
        {n === 1 ? t("findingsOne") : t("findingsN", { n })}
      </button>
      <button className="iconbtn sm" onClick={() => useApp.setState({ startCard: null, findingsOpen: false })}
        title={t("findingsHide")} aria-label={t("findingsHide")}><Icon.X width={12} height={12} /></button>
    </span>
  );
}

/* W4: the start card's second line names the next step for this file - several files: Compare; a flight log
   with findings: its N findings; a golden run fits: Judge it; otherwise nothing. One sentence, a link to the
   place; each reason is said once per session. */
const said = new Set<string>();
type Next = { reason: string; text: string; link: string; go: () => void };
export function nextStepOf(t: ReturnType<typeof useT>, card: NonNullable<ReturnType<typeof useApp.getState>["startCard"]>): Next | null {
  if (card.files && card.files >= 2) return { reason: "compare", text: t("nextCompare", { n: card.files }), link: t("nextCompareLink"), go: () => useApp.setState({ panel: "compare" }) };
  if (card.health?.length) return { reason: "findings", text: card.health.length === 1 ? t("nextFindingsOne") : t("nextFindings", { n: card.health.length }),
    link: t("nextFindingsLink"), go: () => useApp.setState({ panel: "log" }) };
  if (card.golden) return { reason: "judge", text: t("nextJudge", { name: card.golden.name }), link: t("nextJudgeLink"), go: () => { const g = card.golden!; useApp.setState({ startCard: { ...card, golden: null } }); void judgeAgainst(card.runId, g); } };
  return null;
}

function NextStep({ card }: { card: NonNullable<ReturnType<typeof useApp.getState>["startCard"]> }) {
  const t = useT();
  const next = nextStepOf(t, card);
  // once per session per reason: the first card that has it keeps it while it is open
  const [mine] = useState(() => (next && !said.has(next.reason) ? (said.add(next.reason), next.reason) : null));
  if (!next || next.reason !== mine) return null;
  return <p className="start-next" data-reason={next.reason}>{next.text} · <button className="linklike" onClick={next.go}>{next.link}</button></p>;
}
