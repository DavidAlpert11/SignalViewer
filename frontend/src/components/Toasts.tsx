import { useApp } from "../store";
import { Icon } from "../icons";

export default function Toasts() {
  const toasts = useApp((s) => s.toasts);
  const dismiss = useApp((s) => s.dismiss);
  return (
    <div className="toasts" aria-live="polite">
      {toasts.map((m) => (
        <div key={m.id} className={`toast ${m.kind}`}>
          <span className="toast-text">{m.text}</span>
          {m.action && <button className="btn outline" onClick={() => { m.action!.run(); dismiss(m.id); }}>{m.action.label}</button>}
          <button className="iconbtn" onClick={() => dismiss(m.id)} aria-label="Dismiss"><Icon.X /></button>
        </div>
      ))}
    </div>
  );
}
