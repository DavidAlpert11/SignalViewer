/* The status line under the Sweeps area: the table on screen, its size and the answer's count; with a study file
   open (C10), one sentence for the study and the part shown. */
import { useT } from "../../i18n";
import { useStudy, useSweeps } from "../../sweeps/state";
import { useStudyPanel } from "../../sweeps/studyStore";

export default function SweepsStatus() {
  const t = useT();
  const s = useStudy();
  // review R10: with Common parameters open the line spoke of the (absent) single table
  const st = useStudyPanel((x) => (x.open ? x.study : null));
  const res = useStudyPanel((x) => x.result);
  const part = useSweeps((x) => x.part);
  const demo = useStudyPanel((x) => x.demo);
  const shown = part === "setup" ? t("suTitle") : part === "about" ? t("nvAbout") : part === "run" ? t("swCenterNext") : part === "together" || part === "" ? (demo ? t("dmTitle") : t("nvTogether"))
    : part === "table" && s ? s.name : "";
  return (
    <footer className="status" role="status">
      {st ? (
        <>
          <span>{t("swStatusStudy", { name: st.name || "–", n: st.tables.length })}</span>
          {shown && <span>{t("swStatusShown", { part: shown })}</span>}
          {res && <span>{t("swStatusStudyHold", { n: res.counts.feasible.toLocaleString(), of: res.counts.values.toLocaleString() })}</span>}
        </>
      ) : s ? (
        <>
          <span>{s.name}</span>
          <span>{t(s.recordings ? "swStatusRecordings" : "swStatusRows", { n: s.rows.toLocaleString() })}</span>
          {s.recordings ? s.answer && s.question.conditions.length > 0 && <span>{t("swStatusRecHold", { n: s.answer.counts.holding.toLocaleString(), of: s.answer.counts.sets.toLocaleString() })}</span>
            : s.answer && <span>{t("swStatusAnswer", { n: s.answer.counts.holding.toLocaleString(), of: s.answer.counts.sets.toLocaleString(), s: s.answer.seconds.toFixed(2) })}</span>}
          {s.evaluating && <span>{t("swReading")}</span>}
        </>
      ) : <span>{t("swStatusNone")}</span>}
    </footer>
  );
}
