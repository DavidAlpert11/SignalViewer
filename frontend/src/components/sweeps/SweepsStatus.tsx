/* The status line under the Sweeps area: the table on screen, its size and the answer's count. */
import { useT } from "../../i18n";
import { useStudy } from "../../sweeps/state";
import { useStudyPanel } from "../../sweeps/studyStore";

export default function SweepsStatus() {
  const t = useT();
  const s = useStudy();
  // review R10: with Common parameters open the line spoke of the (absent) single table
  const st = useStudyPanel((x) => (x.open ? x.study : null));
  const res = useStudyPanel((x) => x.result);
  return (
    <footer className="status" role="status">
      {st ? (
        <>
          <span>{t("swStatusStudy", { name: st.name || "–", n: st.tables.length })}</span>
          {res && <span>{t("swStatusStudyHold", { n: res.counts.feasible.toLocaleString(), of: res.counts.values.toLocaleString() })}</span>}
        </>
      ) : s ? (
        <>
          <span>{s.name}</span>
          <span>{t("swStatusRows", { n: s.rows.toLocaleString() })}</span>
          {s.answer && <span>{t("swStatusAnswer", { n: s.answer.counts.holding.toLocaleString(), of: s.answer.counts.sets.toLocaleString(), s: s.answer.seconds.toFixed(2) })}</span>}
          {s.evaluating && <span>{t("swReading")}</span>}
        </>
      ) : <span>{t("swStatusNone")}</span>}
    </footer>
  );
}
