/* One frame for every tool panel, in its two places (owner, 2026-11-23: "one whole, flowing, coherent app - not
   sections cut off from each other"):
   - beside the plots: the side panel - its head (title, actions, ⤢), then its sections one under the other;
   - on the whole stage: a page like the Report - the page head in the place of the plots' bar (icon, title, actions,
     ⤡), the demo's line under it as on the plots, then an index column (what there is) beside the main column (the
     thing worked on). The Report screen uses the same page classes for its head and its library column.
   The panel gives its parts once; the frame places them. */
import { createContext, useContext, type ReactNode } from "react";
import type { PanelId } from "../store";
import { Icon } from "../icons";
import DemoGuide from "../components/DemoGuide";
import { FillButton } from "./panels";
import { panelDef } from "../components/rail";

/** where the panel being drawn is: set by App around it */
export const PlaceContext = createContext<"side" | "stage">("side");
export const usePlace = () => useContext(PlaceContext);

export default function PanelFrame({ id, title, className, bodyClass, actions, index, main, label, indexFirst }: {
  id: PanelId; title: string; label?: string;
  /** the panel's own class (on the side panel and on the page) and its side body's class */
  className: string; bodyClass: string;
  /** buttons of the panel's head, before the ⤢ */
  actions?: ReactNode;
  /** what there is to choose from (streams, conditions...): the page's index column, or the top of the side panel */
  index: ReactNode;
  /** the thing worked on (a stream's editor, What changed...): the page's main column, or under the index beside */
  main?: ReactNode;
  /** beside the plots, the index above the main part (Checks: the file and its sections, then the section) */
  indexFirst?: boolean;
}) {
  const place = usePlace();
  const I = Icon[panelDef(id).icon];
  if (place === "side") return (
    <aside className={`side ${className}`} aria-label={label ?? title}>
      <div className="side-head"><h2>{title}</h2>{actions}<FillButton id={id} /></div>
      <div className={bodyClass}>{indexFirst ? <>{index}{main}</> : <>{main}{index}</>}</div>
    </aside>
  );
  return (
    <section className={`page ${className}`} aria-label={label ?? title}>
      <div className="page-head">
        <h2 className="page-title"><I aria-hidden="true" />{title}</h2>
        {actions}
        <span className="spacer" />
        <FillButton id={id} />
      </div>
      <DemoGuide />
      <div className="page-body">
        <nav className={`page-index ${className}-index`} aria-label={title}>{index}</nav>
        <div className={`page-main ${className}-main`}>{main}</div>
      </div>
    </section>
  );
}
