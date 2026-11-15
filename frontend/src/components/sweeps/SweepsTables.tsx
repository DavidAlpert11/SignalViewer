/* The Sweeps area's open tables as pills in the top row (D1: one top row - TopBar mounts the area's own part there,
   as Recordings' tools; loaded lazily with the area). A click shows a table, its × closes it. They were tabs in the
   Sweeps bar: one control, one place. */
import { useT } from "../../i18n";
import { Icon } from "../../icons";
import { useSweeps } from "../../sweeps/state";
import "./sweeps.css";

export default function SweepsTables() {
  const t = useT();
  const studies = useSweeps((s) => s.studies);
  const active = useSweeps((s) => s.active);
  if (!studies.length) return null;
  const show = (i: number) => useSweeps.setState({ active: i, part: "table" });
  return (
    <div className="sw-pills" role="tablist" aria-label={t("swTablesOpen")}>
      {studies.map((s, i) => (
        <div key={s.tableId} role="tab" tabIndex={0} aria-selected={i === active} className={`pill sw-tbl-pill${i === active ? " on" : ""}`}
          title={s.path || s.name} onClick={() => show(i)} onKeyDown={(e) => { if (e.key === "Enter") show(i); }}>
          <bdi className="sw-ellipsis">{s.name}</bdi>
          <span className="x" role="button" aria-label={t("swCloseStudy")} title={t("swCloseStudy")}
            onClick={(e) => { e.stopPropagation(); useSweeps.getState().close(i); }}><Icon.X width={11} height={11} /></span>
        </div>
      ))}
    </div>
  );
}
