/* What the formula language offers, for suggestions and help while typing. The list must match
   the server (backend/svcore/formula.py, FUNCTION_NAMES) - a backend test checks that. */

export interface FuncInfo { args: string[]; en: string; he: string }

export const FUNC_INFO: Record<string, FuncInfo> = {
  abs: { args: ["x"], en: "absolute value", he: "ערך מוחלט" },
  sqrt: { args: ["x"], en: "square root", he: "שורש ריבועי" },
  exp: { args: ["x"], en: "e to the power x", he: "e בחזקת x" },
  log: { args: ["x"], en: "natural logarithm", he: "לוגריתם טבעי" },
  log10: { args: ["x"], en: "base-10 logarithm", he: "לוגריתם בבסיס 10" },
  sin: { args: ["x"], en: "sine (radians)", he: "סינוס (רדיאנים)" },
  cos: { args: ["x"], en: "cosine (radians)", he: "קוסינוס (רדיאנים)" },
  tan: { args: ["x"], en: "tangent (radians)", he: "טנגנס (רדיאנים)" },
  asin: { args: ["x"], en: "arc sine, in radians", he: "ארקסינוס, ברדיאנים" },
  acos: { args: ["x"], en: "arc cosine, in radians", he: "ארקקוסינוס, ברדיאנים" },
  atan: { args: ["x"], en: "arc tangent, in radians", he: "ארקטנגנס, ברדיאנים" },
  atan2: { args: ["y", "x"], en: "angle of the point (x, y), in radians", he: "הזווית של הנקודה (x, y), ברדיאנים" },
  sign: { args: ["x"], en: "−1, 0 or 1", he: "‎−1, 0 או 1" },
  floor: { args: ["x"], en: "round down", he: "עיגול כלפי מטה" },
  ceil: { args: ["x"], en: "round up", he: "עיגול כלפי מעלה" },
  round: { args: ["x"], en: "round to the nearest whole number", he: "עיגול למספר השלם הקרוב" },
  min: { args: ["a", "b"], en: "the smaller of the two, sample by sample", he: "הקטן מבין השניים, דגימה אחר דגימה" },
  max: { args: ["a", "b"], en: "the larger of the two, sample by sample", he: "הגדול מבין השניים, דגימה אחר דגימה" },
  clip: { args: ["x", "lo", "hi"], en: "limit x to the range lo … hi", he: "הגבלת x לטווח lo … hi" },
  where: { args: ["condition", "a", "b"], en: "a where the condition holds, else b  (e.g. where(x > 0, x, 0))", he: "a כשהתנאי מתקיים, אחרת b  (למשל where(x > 0, x, 0))" },
  deriv: { args: ["x"], en: "derivative over time (per second)", he: "נגזרת לפי הזמן (לשנייה)" },
  integ: { args: ["x"], en: "integral over time", he: "אינטגרל לפי הזמן" },
  smooth: { args: ["x", "n=10"], en: "moving average over n samples", he: "ממוצע נע על n דגימות" },
  lowpass: { args: ["x", "fc"], en: "low-pass filter, cut-off fc in Hz", he: "מסנן מעביר נמוכים, תדר קטעון fc ב־Hz" },
  highpass: { args: ["x", "fc"], en: "high-pass filter, cut-off fc in Hz", he: "מסנן מעביר גבוהים, תדר קטעון fc ב־Hz" },
  deg: { args: ["x"], en: "radians to degrees", he: "רדיאנים למעלות" },
  rad: { args: ["x"], en: "degrees to radians", he: "מעלות לרדיאנים" },
  wrap180: { args: ["deg"], en: "angle wrapped to −180 … 180", he: "זווית מגולגלת לטווח ‎−180 … 180" },
  wrap360: { args: ["deg"], en: "angle wrapped to 0 … 360 (heading)", he: "זווית מגולגלת לטווח 0 … 360 (כיוון)" },
  q2roll: { args: ["qw", "qx", "qy", "qz"], en: "roll from a quaternion, in degrees", he: "גלגול מקווטרניון, במעלות" },
  q2pitch: { args: ["qw", "qx", "qy", "qz"], en: "pitch from a quaternion, in degrees", he: "עלרוד מקווטרניון, במעלות" },
  q2yaw: { args: ["qw", "qx", "qy", "qz"], en: "yaw (heading) from a quaternion, in degrees, −180 … 180", he: "סבסוב (כיוון) מקווטרניון, במעלות, ‎−180 … 180" },
  norm01: { args: ["x"], en: "scaled to 0 … 1 (min → 0, max → 1)", he: "מנורמל ל־0 … 1 (מינימום ← 0, מקסימום ← 1)" },
};
export const FUNC_NAMES = Object.keys(FUNC_INFO);
/** Not a server function: replaced by the value before the formula is sent (flight logs only). */
export const PARAM_INFO: FuncInfo = { args: ['"NAME"'], en: "a parameter's value from the flight log", he: "ערך של פרמטר מלוג הטיסה" };

export interface VarInfo { name: string; en: string; he: string }
export const VAR_T: VarInfo = { name: "t", en: "time [s]", he: "זמן [s]" };
export const VAR_PI: VarInfo = { name: "pi", en: "π = 3.14159…", he: "π = 3.14159…" };
export const VAR_E: VarInfo = { name: "e", en: "e = 2.71828…", he: "e = 2.71828…" };
export const VAR_X: VarInfo = { name: "x", en: "the signal itself", he: "הסיגנל עצמו" };

/** The function call the caret is in, and which argument: "smooth(x, |" -> { smooth, 1 }. */
export function callAt(text: string, caret: number): { name: string; arg: number } | null {
  let depth = 0, arg = 0, braces = 0;
  for (let i = caret - 1; i >= 0; i--) {
    const c = text[i];
    if (c === "}") braces++;
    else if (c === "{") braces = Math.max(0, braces - 1);
    if (braces) continue;
    if (c === ")") depth++;
    else if (c === "(") {
      if (depth === 0) {
        const m = /([A-Za-z_]\w*)\s*$/.exec(text.slice(0, i));
        return m && (FUNC_INFO[m[1]] || m[1] === "param") ? { name: m[1], arg } : null;
      }
      depth--;
    } else if (c === "," && depth === 0) arg++;
  }
  return null;
}

/** Names in an expression that are neither functions (followed by "(") nor allowed variables.
 *  Text inside {…} is skipped (signal references); "1e5" is a number, not the name e5. */
export function unknownNames(text: string, allowed: Set<string>): string[] {
  const out: string[] = [];
  const re = /\{[^}]*\}|"[^"]*"|[A-Za-z_\u0590-\u05FF][\w.\u0590-\u05FF[\]]*/g;
  let m: RegExpExecArray | null;
  while ((m = re.exec(text))) {
    const w = m[0];
    if (w.startsWith("{") || w.startsWith('"')) continue;
    const before = text[m.index - 1];
    if (before && /[\d.]/.test(before)) continue;                 // exponent of a number: 1e5, 2.5e-3
    const after = text.slice(m.index + w.length).trimStart();
    if (after.startsWith("(") && (FUNC_INFO[w] || w === "param")) continue;
    if (allowed.has(w)) continue;
    if (!out.includes(w)) out.push(w);
  }
  return out;
}

/** Unbalanced parentheses: a message key, or null when fine. */
export function parenProblem(text: string): "fxParenOpen" | "fxParenClose" | null {
  let d = 0;
  for (const c of text) {
    if (c === "(") d++;
    else if (c === ")" && --d < 0) return "fxParenClose";
  }
  return d > 0 ? "fxParenOpen" : null;
}
