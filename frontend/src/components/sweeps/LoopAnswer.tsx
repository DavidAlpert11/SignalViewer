/* FR6 (owner, 2026-11-16): the loop's answer in words - the best set as "Kp = 0.12, Ki = 0.03, Kd = 0.004" and its
   value; once converged, a sentence that says it is the answer. One place for the demo's loop and a study's own. */
import { fmtNum, useT } from "../../i18n";
import { useApp } from "../../store";
import type { LoopProgress } from "../../sweeps/studyTypes";

export default function LoopAnswer({ p }: { p: LoopProgress }) {
  const t = useT();
  const lang = useApp((s) => s.lang);
  if (!p.best) return null;
  const set = Object.entries(p.best.values).map(([k, v]) => `${k} = ${typeof v === "number" ? fmtNum(v, "en", 5) : v}`).join(", ");
  const score = fmtNum(p.best.score, lang, 5);
  return p.converged
    ? <p className="lp-answer" role="status">{t("lpAnswer")} <bdi dir="ltr" className="lp-answer-set">{set}</bdi> · {t("lpAnswerValue", { v: score })}</p>
    : <span className="lp-best">{t("lpBest")}: <b>{score}</b> <bdi dir="ltr" className="hint">{set}</bdi></span>;
}
