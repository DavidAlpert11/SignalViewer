/* C6: *New study* - the one way in for both flows (plan §4.3): *I have results* (a table of runs: it opens with its
   results at once and fills the study's Set up from its columns) and *Start from nothing* (the Set up is typed,
   the app runs round 1). Both land in the same study. */
import { useT } from "../../i18n";
import { pickPath } from "../../store";
import { useSweeps } from "../../sweeps/state";
import { haveResults, startFromNothing } from "../../sweeps/studyStore";
import { notifyError } from "../../sweeps/notify";
import { TABLE_EXTS } from "../../sweeps/studyFile";
import Toasts from "../Toasts";

export default function NewStudy() {
  const t = useT();
  const busy = useSweeps((s) => s.busy);
  const have = async () => {
    const p = await pickPath({ mode: "open", title: t("nsHaveTitle"), exts: TABLE_EXTS });
    if (p) await haveResults(p).catch(notifyError);
  };
  return (
    <div className="sw-welcome ns-wrap" data-part="new">
      <div className="notices sw-notices"><Toasts /></div>
      <div className="ns" role="group" aria-label={t("nsTitle")}>
        <h1 className="ns-title">{t("nsTitle")}</h1>
        <div className="ns-ways">
          <section className="card ns-way" data-way="results">
            <span className="eyebrow">{t("nsHave")}</span>
            <h2 className="card-title">{t("nsHaveTitle")}</h2>
            <p className="card-meta">{t("nsHaveHint")}</p>
            <div className="card-next"><button className="btn primary ns-have" disabled={busy} onClick={() => { void have(); }}>{t("nsHaveTitle")}…</button></div>
          </section>
          <section className="card ns-way" data-way="nothing">
            <span className="eyebrow">{t("nsNothing")}</span>
            <h2 className="card-title">{t("nsNothingTitle")}</h2>
            <p className="card-meta">{t("nsNothingHint")}</p>
            <div className="card-next"><button className="btn primary ns-nothing" onClick={startFromNothing}>{t("nsStart")}</button></div>
          </section>
        </div>
        <button className="btn ghost ns-back" onClick={() => useSweeps.setState({ part: "" })}>{t("nsCancel")}</button>
      </div>
    </div>
  );
}
