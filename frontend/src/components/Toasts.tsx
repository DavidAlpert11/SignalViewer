import { useState } from "react";
import { useApp } from "../store";
import { useT } from "../i18n";
import { Icon } from "../icons";

/** At most this many messages show at once; older ones still up wait behind "+N". One was too few:
 *  a file's load report and an Undo arrive together, and an Undo out of sight is an Undo lost. */
const SHOWN = 3;

/** The messages, in the notices area (App): the newest SHOWN of them, instead of an endless stack
 *  over the plots. Esc dismisses the newest. */
export default function Toasts() {
  const t = useT();
  const toasts = useApp((s) => s.toasts);
  const dismiss = useApp((s) => s.dismiss);
  const [all, setAll] = useState(false);
  const shown = all || toasts.length <= SHOWN ? toasts : toasts.slice(-SHOWN);
  const hidden = toasts.length - shown.length;
  if (!toasts.length) return null;
  return (
    <div className="toasts" aria-live="polite">
      {shown.map((m, i) => (
        <div key={m.id} className={`toast ${m.kind}`}>
          <span className="toast-text">{m.text}</span>
          {m.action && <button className="btn outline" onClick={() => { m.action!.run(); dismiss(m.id); }}>{m.action.label}</button>}
          {i === shown.length - 1 && hidden > 0 && (
            <button className="toast-more" onClick={() => setAll(true)} title={t("moreMessages", { n: hidden })}>+{hidden}</button>
          )}
          <button className="iconbtn" onClick={() => dismiss(m.id)} aria-label={t("dismiss")} title={t("dismiss")}><Icon.X /></button>
        </div>
      ))}
      {all && toasts.length > 1 && <button className="linklike toast-fold" onClick={() => setAll(false)}>{t("newestOnly")}</button>}
    </div>
  );
}
