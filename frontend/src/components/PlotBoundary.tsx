import { Component, type ReactNode } from "react";
import { reportError } from "../errorReport";

/** A plot that fails to draw shows a message here; the rest of the app keeps working. */
export default class PlotBoundary extends Component<{ children: ReactNode; label: string; retry: string; resetKey: string }, { error: string | null; key: string }> {
  state = { error: null as string | null, key: "" };
  static getDerivedStateFromError(e: Error) { return { error: e.message || String(e) }; }
  static getDerivedStateFromProps(p: { resetKey: string }, s: { error: string | null; key: string }) {
    // a different signal set or mode clears the error automatically
    return p.resetKey !== s.key ? { error: null, key: p.resetKey } : null;
  }
  componentDidCatch(e: Error) { console.error("Plot failed to draw:", e); reportError(e.message || String(e), e.stack, "plot"); }
  render() {
    if (!this.state.error) return this.props.children;
    return (
      <div className="plot-error" role="alert">
        <p>{this.props.label}</p>
        <code>{this.state.error}</code>
        <button className="btn outline" onClick={() => this.setState({ error: null })}>{this.props.retry}</button>
      </div>
    );
  }
}
