/* PLAN 2026-11-16 §7a, step 5 - Next runs: the one place for the next parameter sets. On the start side, the
   proposal (the re-run list, the suggestions and their settings - exported to run outside) and *Run from the app*
   (RunPanel: the round, how to run, the loop); in the middle what they propose (the maps and the sets) - or, for a
   study with no table yet, what round 1 will run. Finished rounds come back as tables in Data. */
import { useRef } from "react";
import { fmtInt, useT } from "../../i18n";
import { useApp } from "../../store";
import PanelResizer from "../PanelResizer";
import { usePanelWidth } from "../panelWidth";
import { useStudy, useSweeps } from "../../sweeps/state";
import { readiness } from "../../sweeps/setup";
import NextRunsView from "./NextRunsView";
import RunPanel from "./RunPanel";
import DemoView from "./DemoView";

const DEF = 330, GUTTER = 12;

export default function NextStep() {
  const t = useT();
  const study = useStudy();
  const demo = useSweeps((s) => s.common.open && s.common.demo);
  const [w, setW] = usePanelWidth("swNext", DEF);
  const box = useRef<HTMLDivElement>(null);
  const max = () => (box.current?.clientWidth ?? window.innerWidth) - 420;
  const side = { "--sw-next-side": `${w}px` } as React.CSSProperties;
  return (
    <div className="sw-nextstep" data-part="next" ref={box} style={side}>
      <main className="sw-center">
        {study && study.answer && !demo ? <NextRunsView study={study} extra={<RunPanel />} /> : (
          <div className="sw-next">
            <div className="sw-next-side"><RunPanel /></div>
            <div className="sw-next-main">{demo ? <DemoView /> : study ? <p className="empty-note">{study.evalError || t("swReading")}</p> : <RoundOne />}</div>
          </div>
        )}
      </main>
      <PanelResizer label={t("resizePanel")} style={{ insetInlineStart: GUTTER + w + 4 }} width={w} setWidth={setW} grow={+1} def={DEF} max={max} />
    </div>
  );
}

/** A study with no table yet (started from nothing): what round 1 will run, and where its results go. */
function RoundOne() {
  const t = useT();
  const lang = useApp((s) => s.lang);
  const study = useSweeps((s) => s.common.study);
  if (!study) return null;
  const r = readiness(study);
  if (study.history?.length) return <p className="hint nx-round1">{t("nxRound1Hint")}</p>;     // rounds ran: they are tables in Data
  return (
    <div className="card nx-round1">
      <span className="card-title">{t("nxRound1Title")}</span>
      {r.runs > 0 && <span className="card-meta">{t("rcRound1", { sets: fmtInt(r.sets, lang), combos: fmtInt(r.combos, lang), runs: fmtInt(r.runs, lang) })}</span>}
      <p className="card-meta">{t("nxRound1Hint")}</p>
    </div>
  );
}
