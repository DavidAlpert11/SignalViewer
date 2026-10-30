/* The status line under the Sweeps area: the table on screen, its size and the answer's count. */
import { useT } from "../../i18n";
import { useStudy } from "../../sweeps/state";

export default function SweepsStatus() {
  const t = useT();
  const s = useStudy();
  return (
    <footer className="status" role="status">
      {s ? (
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
