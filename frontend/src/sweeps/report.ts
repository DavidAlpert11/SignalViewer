/* A study as a page to keep or send: the question, the answer, the best sets and the plot, in one
   self-contained HTML file (no app needed to read it). */
import type { TFn } from "../i18n";
import { labelOf } from "./scales";
import type { Study } from "./state";
import { colLabel, setColumns } from "./view";

const esc = (s: string) => s.replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]!);

export function studyReport(t: TFn, s: Study, plotPng: string | null, lang: string): string {
  const a = s.answer;
  const q = s.question;
  const cols = setColumns(s);
  const params = s.columns.filter((c) => c.role === "param").map((c) => c.name);
  const holds = s.columns.filter((c) => c.role === "hold");
  const show = ["#rank", ...params, ...(cols.has("#goal") ? ["#goal"] : []),
    ...(a?.sets.filter((c) => c.group === "condition" && c.part === "margin").map((c) => c.name) ?? [])];
  const rank = cols.get("#rank")?.values;
  const order = rank ? [...rank.keys()].filter((i) => Number.isFinite(rank[i])).sort((x, y) => rank[x] - rank[y]).slice(0, 25) : [];
  const li = (x: string) => `<li>${esc(x)}</li>`;
  const holdTxt = holds.map((h) => `${h.name}: ${(q.holdValues[h.name]?.length ? q.holdValues[h.name] : h.values ?? []).join(", ")}`);
  const condTxt = q.conditions.map((c) => `${c.column} ${c.op} ${c.value} - ${c.mode === "all" ? t("swInAll") : c.mode === "atLeast" ? `${t("swAtLeast")} ${c.k}` : `${t("swOnlyIn")} ${Object.entries(c.where ?? {}).map(([k, v]) => `${k} ${v.join(", ")}`).join("; ")}`}`);
  return `<!doctype html><html lang="${lang}" dir="${lang === "he" ? "rtl" : "ltr"}"><head><meta charset="utf-8"><title>${esc(s.name)}</title>
<style>body{font-family:system-ui,sans-serif;margin:32px;color:#1f2328;max-width:1100px}h1{margin:0 0 4px}h2{margin-top:28px}
.big{font-size:2.2rem;font-weight:700}table{border-collapse:collapse;font-size:13px}th,td{border-bottom:1px solid #ddd;padding:5px 9px;text-align:start}
td.n{text-align:end;font-variant-numeric:tabular-nums}.muted{color:#667}img{max-width:100%;border:1px solid #ddd;border-radius:8px}</style></head><body>
<h1>${esc(s.name)}</h1><p class="muted">${esc(s.path)} · ${new Date().toLocaleString(lang === "he" ? "he-IL" : "en-US")}</p>
<p><span class="big">${a?.counts.holding ?? "–"}</span> ${esc(t("swOfSetsHold", { n: a?.counts.sets ?? 0 }))} · ${esc(t("swCombosEach", { n: a?.counts.combos ?? 0 }))}</p>
<h2>${esc(t("swQuestion"))}</h2><ul>
${li(`${t("swRoleParam")}: ${params.join(", ")}`)}${holdTxt.map((x) => li(`${t("swRoleHold")} - ${x}`)).join("")}
${q.goal ? li(`${t("swGoal")}: ${q.goal.direction === "max" ? t("swMaximize") : t("swMinimize")} ${q.goal.column} (${t("swWorst")})`) : ""}
${condTxt.map(li).join("")}${q.derived.map((d) => li(`ƒ ${d.name} = ${d.kind === "row" ? d.expr : `${d.op}(${d.column})`}`)).join("")}
${q.exclude.length ? li(t("swLeftOutN", { n: q.exclude.length })) : ""}</ul>
${plotPng ? `<h2>${esc(t("swCenterLines"))}</h2><img src="${plotPng}" alt="">` : ""}
<h2>${esc(t("swBestSets"))}</h2><table><thead><tr>${show.map((c) => `<th>${esc(colLabel(t, s, c))}</th>`).join("")}</tr></thead><tbody>
${order.map((i) => `<tr>${show.map((c) => { const col = cols.get(c)!; return `<td class="${col.kind === "num" ? "n" : ""}">${esc(labelOf(col, col.values[i]))}</td>`; }).join("")}</tr>`).join("\n")}
</tbody></table></body></html>`;
}
