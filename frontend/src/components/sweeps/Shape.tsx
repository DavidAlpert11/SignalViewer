/* A number with its label - the stat tiles several steps share. */

export function Stat({ label, value, warn }: { label: string; value: number | string; warn?: boolean }) {
  return (
    <div className={`sw-stat${warn ? " warn" : ""}`}>
      <div className="sw-stat-value">{typeof value === "number" ? value.toLocaleString() : value}</div>
      <div className="sw-stat-label">{label}</div>
    </div>
  );
}
