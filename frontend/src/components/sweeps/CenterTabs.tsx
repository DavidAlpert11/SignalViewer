/* The middle of the area: the lines (plot and table), which parameter matters, two parameters as a
   map, any two columns as points, what to run next, the data's health, and two studies compared. */
import { useT, type TKey } from "../../i18n";
import { CENTERS, type Center } from "../../sweeps/model";
import { useSweeps, type Study } from "../../sweeps/state";

const KEY: Record<Center, TKey> = { lines: "swCenterLines", effects: "swCenterEffects", map: "swCenterMap", scatter: "swCenterScatter",
  next: "swCenterNext", health: "swCenterHealth", compare: "swCenterCompare" };

export default function CenterTabs({ study, studies }: { study: Study; studies: number }) {
  const t = useT();
  const shown = CENTERS.filter((c) => c !== "compare" || studies > 1);
  return (
    <div className="sw-center-tabs" role="tablist">
      {shown.map((c) => (
        <button key={c} role="tab" aria-selected={study.view.center === c} className={study.view.center === c ? "on" : ""}
          onClick={() => useSweeps.getState().setView({ center: c })}>{t(KEY[c])}</button>
      ))}
    </div>
  );
}
