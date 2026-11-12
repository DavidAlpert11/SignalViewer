import { useApp } from "./store";

/** P2: record which objects turned out to have no position (a saved session's EAHR): their chips say
 *  "no position"; the views draw nothing for them and leave them out of Fit. */
export function markNoPosition(ids: string[], empty: string[]): void {
  const st = useApp.getState();
  const keep = st.objNoPosition.filter((x) => !ids.includes(x));
  const next = [...keep, ...empty];
  if (next.length !== st.objNoPosition.length || next.some((x, i) => x !== st.objNoPosition[i])) useApp.setState({ objNoPosition: next });
}
