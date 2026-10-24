import { flushSync } from "react-dom";
import { useMemo, useRef, useState } from "react";
import { fuzzySort } from "../fuzzy";
import { useApp } from "../store";
import { callAt, FUNC_INFO, FUNC_NAMES, PARAM_INFO, type VarInfo } from "../formulaHelp";
import { wordAt } from "../formulaRefs";

export interface SigOption { label: string; sub: string; insert: string }
type Item = { kind: "var" | "fn" | "sig"; label: string; sub: string; insert: string; caretBack?: number };

/** An expression field that suggests functions, variables and (optionally) signals while typing:
 *  ↑ ↓ to choose, Tab / Enter to insert, Esc to close, Ctrl+Space to list everything. A function is
 *  inserted with its parentheses and the caret inside; while the caret is in a call, a line under
 *  the field shows that function's arguments with the current one highlighted. */
export default function ExprInput({ value, onChange, vars, signals, params, multiline, placeholder, ariaLabel, onSubmit, invalid, inputRef }: {
  value: string; onChange: (v: string) => void; vars: VarInfo[]; signals?: SigOption[];
  params?: { name: string; value: number }[];     // flight-log parameters, for param("…")
  multiline?: boolean; placeholder?: string; ariaLabel: string; onSubmit?: () => void; invalid?: boolean;
  inputRef?: React.RefObject<(HTMLInputElement & HTMLTextAreaElement) | null>;
}) {
  const lang = useApp((s) => s.lang);
  const own = useRef<HTMLInputElement & HTMLTextAreaElement>(null);
  const ref = inputRef ?? own;
  const [caret, setCaret] = useState(value.length);
  const [sel, setSel] = useState(0);
  const [focus, setFocus] = useState(false);
  const [forced, setForced] = useState(false);            // Ctrl+Space: list even with nothing typed
  const [closed, setClosed] = useState(false);            // Esc until the next keystroke
  const at = wordAt(value, caret);
  // Ctrl+Space right after a number or a name with no match: list everything, insert at the caret
  const raw = at.word.replace(/^\{/, "").replace(/^[^:]*:/, "");
  const matches = (q: string) => !!q && (vars.some((v) => v.name.toLowerCase().startsWith(q)) || FUNC_NAMES.some((f) => f.includes(q))
    || !!signals?.some((o) => o.label.toLowerCase().includes(q)));
  const fresh = forced && (/^[\d.]/.test(raw) || !matches(raw.toLowerCase()));
  // inside param("…"): suggest parameter names
  const pm = params?.length ? /param\(\s*("?)([A-Za-z0-9_]*)$/.exec(value.slice(0, caret)) : null;
  const start = pm ? caret - pm[2].length - pm[1].length : fresh ? caret : at.start;
  // a number being typed (8, 2.5, 1e3) is not a name: nothing to suggest unless Ctrl+Space asked
  const clean = fresh ? "" : /^[\d.]/.test(raw) && !at.word.startsWith("{") ? "" : raw;

  const items: Item[] = useMemo(() => {
    if (pm && params) {
      const q = pm[2].toUpperCase();
      const list = q ? [...params.filter((p) => p.name.startsWith(q)), ...params.filter((p) => !p.name.startsWith(q) && p.name.includes(q))] : params;
      return list.slice(0, 40).map((p) => ({ kind: "var" as const, label: p.name, sub: String(p.value), insert: `"${p.name}")` }));
    }
    if (!clean && !forced) return [];
    const q = clean.toLowerCase();
    const vs = vars.filter((v) => !q || v.name.toLowerCase().startsWith(q))
      .map((v) => ({ kind: "var" as const, label: v.name, sub: lang === "he" ? v.he : v.en, insert: v.name }));
    const fnNames = !q ? FUNC_NAMES : [...FUNC_NAMES.filter((f) => f.startsWith(q)),
      ...FUNC_NAMES.filter((f) => !f.startsWith(q) && f.includes(q))];
    const fs = fnNames.map((f) => ({ kind: "fn" as const, label: `${f}(${FUNC_INFO[f].args.join(", ")})`,
      sub: lang === "he" ? FUNC_INFO[f].he : FUNC_INFO[f].en, insert: `${f}()`, caretBack: 1 }));
    if (params?.length && (!q || "param".startsWith(q))) {
      fs.unshift({ kind: "fn" as const, label: 'param("NAME")', sub: lang === "he" ? PARAM_INFO.he : PARAM_INFO.en, insert: 'param("")', caretBack: 2 });
    }
    const ss = signals && q ? fuzzySort(signals, (o) => o.label, clean).slice(0, 8)
      .map((s) => ({ kind: "sig" as const, label: s.label, sub: s.sub, insert: s.insert })) : [];
    // signals first when typing a name that matches them; functions first otherwise
    const list = ss.length && !fs.some((f) => f.label.startsWith(q + "(")) ? [...vs, ...ss, ...fs] : [...vs, ...fs, ...ss];
    return list.slice(0, forced && !q ? 40 : 10);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [clean, forced, vars, signals, lang, pm?.[2], params]);
  const exact = items.length === 1 && items[0].insert === clean;
  const show = focus && !closed && items.length > 0 && !exact;
  const call = focus ? callAt(value, caret) : null;

  const insertAt = (from: number, to: number, text: string, back = 0) => {
    const next = value.slice(0, from) + text + value.slice(to);
    const pos = from + text.length - back;
    // the new text is put in place NOW, then the caret: placed a frame later, keys typed right after
    // the completion (Tab, then "x, ") landed after the closing parenthesis
    flushSync(() => { onChange(next); setForced(false); });
    ref.current?.focus();
    ref.current?.setSelectionRange(pos, pos);
    setCaret(pos);
  };
  const accept = (i: number) => {
    const it = items[i];
    if (!it) return;
    // a function typed right before "(" already: do not add another pair
    if (pm) {
      const tail = /^"?\s*\)?/.exec(value.slice(caret))?.[0].length ?? 0;     // a closing ") already there
      insertAt(start, caret + tail, it.insert);
      return;
    }
    const hasParen = value.slice(caret).trimStart().startsWith("(");
    if (it.kind === "fn" && hasParen) insertAt(start, caret, it.insert.slice(0, -2));
    else insertAt(start, caret, it.insert, it.caretBack ?? 0);
  };
  const track = (el: HTMLInputElement | HTMLTextAreaElement) => setCaret(el.selectionStart ?? el.value.length);

  const common = {
    ref, value, spellCheck: false, dir: "ltr" as const, placeholder, "aria-label": ariaLabel,
    "aria-autocomplete": "list" as const, "aria-expanded": show, "aria-invalid": invalid || undefined,
    className: `fx-input${invalid ? " bad" : ""}`,
    onChange: (e: React.ChangeEvent<HTMLInputElement & HTMLTextAreaElement>) => { onChange(e.target.value); track(e.target); setSel(0); setClosed(false); },
    onSelect: (e: React.SyntheticEvent<HTMLInputElement & HTMLTextAreaElement>) => track(e.currentTarget),
    onClick: (e: React.MouseEvent<HTMLInputElement & HTMLTextAreaElement>) => track(e.currentTarget),
    onFocus: () => setFocus(true),
    onBlur: () => setTimeout(() => { setFocus(false); setForced(false); }, 150),
    onKeyDown: (e: React.KeyboardEvent<HTMLInputElement & HTMLTextAreaElement>) => {
      if (e.key === " " && e.ctrlKey) { e.preventDefault(); setForced(true); setClosed(false); setSel(0); return; }
      if (show) {
        if (e.key === "ArrowDown") { e.preventDefault(); setSel((s) => Math.min(items.length - 1, s + 1)); return; }
        if (e.key === "ArrowUp") { e.preventDefault(); setSel((s) => Math.max(0, s - 1)); return; }
        if (e.key === "Tab" || e.key === "Enter") { e.preventDefault(); accept(sel); return; }
        if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); setClosed(true); setForced(false); return; }
      }
      if (e.key === "Enter" && !multiline && onSubmit) { e.preventDefault(); onSubmit(); }
    },
  };

  return (
    <div className="fx-box">
      {multiline ? <textarea rows={3} {...common} /> : <input {...common} />}
      {show && (
        <div className="fx-suggest" role="listbox">
          {items.map((it, i) => (
            <button key={it.kind + it.label + it.sub} type="button" role="option" aria-selected={i === sel}
              className={`pick-item fx-item ${it.kind}${i === sel ? " on" : ""}`} onMouseDown={(e) => { e.preventDefault(); accept(i); }}>
              <span className="nm" dir="ltr">{it.label}</span>{it.sub && <span className="grp">{it.sub}</span>}
            </button>
          ))}
        </div>
      )}
      {call && !show && (() => {
        const info = FUNC_INFO[call.name] ?? PARAM_INFO;
        return (
          <div className="fx-sig" dir="ltr" aria-live="polite">
            <b>{call.name}</b>(
            {info.args.map((a, i) => (
              <span key={a}>{i > 0 && ", "}<span className={i === Math.min(call.arg, info.args.length - 1) ? "cur" : ""}>{a}</span></span>
            ))}
            ) <span className="desc" dir="auto">— {lang === "he" ? info.he : info.en}</span>
          </div>
        );
      })()}
    </div>
  );
}
