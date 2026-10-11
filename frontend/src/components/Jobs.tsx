import { useApp } from "../store";
import { useT } from "../i18n";
import { cancelJob } from "../files";

/** Progress for background jobs, with cancel (N-04). */
export default function Jobs() {
  const t = useT();
  const jobs = useApp((s) => s.jobs);
  if (!jobs.length) return null;
  return (
    <div className="jobs" role="status" aria-live="polite">
      {jobs.map((j) => (
        <div key={j.id} className="job">
          <div className="job-top">
            <span className="job-label">{j.label}</span>
            <span className="job-pct">{Math.round(j.progress * 100)}%</span>
            <button className="btn outline" onClick={() => cancelJob(j.id)}>{t("cancel")}</button>
          </div>
          <div className="bar" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(j.progress * 100)} aria-label={j.label}>
            <span style={{ width: `${Math.max(2, j.progress * 100)}%` }} />
          </div>
        </div>
      ))}
    </div>
  );
}
