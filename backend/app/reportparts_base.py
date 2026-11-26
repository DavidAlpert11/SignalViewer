"""The report's ready-made parts (app/reportparts.py): what every part shares - the words (en / he), the options each
part takes, the numbers' format, a Markdown table, and Part, the context a part writes into. Split out of
app/reportparts.py (UX5.5).
"""
import re
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

from svcore.docfields import format_value

PALETTE = ["#3D8BFD", "#E8590C", "#2F9E44", "#AE3EC9", "#F08C00", "#0CA678", "#E64980", "#1C7ED6"]
PARTS = ("toc", "requirements", "overview", "tracking", "navigation", "states", "trajectory", "moments", "differences", "messages", "summary")
UNITS = {"position": "m", "velocity": "m/s", "attitude": "deg"}

S: Dict[str, Dict[str, Any]] = {
    "en": {
        "none_req": "No checks file with the open files - a `<name>.checks.json` beside a recording, or a `checks.json` in its folder (what Checks and signalviewer-cli check read).",
        "req_intro": "**{n} requirements** from {file}, judged on every sample of {runs} run(s): {ok} passed, {bad} failed.",
        "req_verdict_pass": "**Verdict: ✔ every requirement is met.**", "req_verdict_fail": "**Verdict: ✖ {n} requirement(s) not met.**",
        "req_runs": "**{ok} of {n} runs meet every requirement.**", "req_runs_bad": "Not met: {list}.",
        "req_head": ["Requirement", "Verdict", "Measured", "First failed at (s)"], "req_req": "Requirement",
        "req_skipped": "– not judged", "req_error": "⚠ error", "req_limit": "limit", "req_outside": "outside {n} times, first at {t} s",
        "req_hl": "{r} not met - {m}", "req_plot": "{r} - where it failed",
        "none_trk": "No commanded / measured pairs in the open files (a pair is found by its names: Des…, …_cmd, …_setpoint, target…, …_ref).",
        "trk_intro": "**{n} commanded / measured pairs**, found by their names; each compared on all its samples (error = measured − commanded).",
        "trk_head": ["Commanded", "Measured", "RMS error", "Max error", "at (s)", "Bias", "Delay (s)", "Steps", "Overshoot", "Settling (s)"],
        "trk_tol": ["Outside ±{tol}", "Pass"], "file": "File", "pass": "✔ pass", "fail": "✖ fail",
        "trk_plot": "{m} vs its command", "error": "error (right axis)", "not_settled": "not settled ({n})",
        "trk_cap": "Largest error {max} at {t} s; RMS {rms}.", "trk_cap_steps": " {n} steps, overshoot up to {o} % (at {to} s).",
        "trk_hl": "{m} followed {s} with RMS error {rms} (max {max} at {t} s)", "trk_hl_fail": "{m} outside ±{tol} for {out} % of the time",
        "none_nav": "Fewer than two map objects with a position in the open files - nothing to compare.",
        "nav_intro": "**Navigation errors against {ref}** ({why}); {n} objects compared on every sample, in north / east / down.",
        "nav_guess": "the reference was guessed: {cls} - choose another with | ref NAME", "nav_chosen": "the chosen reference",
        "qty": {"position": "Position", "velocity": "Velocity", "attitude": "Attitude"},
        "nav_head": ["Object", "Error", "RMS", "Mean", "95 %", "Max", "at (s)"],
        "nav_plot": "{q} error of {o} against {ref}", "nav_axis": "{c} - {q} error [{u}] against {ref}", "nav_hl": "{o}: {q} error up to {max} {u} (at {t} s), 95 % within {p95} {u}",
        "nav_left": "Left out: {list}.",
        "none_st": "No state signals in the open files (a mode, phase or state - text values or a few whole-number levels).",
        "st_intro": "**{name}** - {n} stretches, {c} changes{dropped}.", "st_dropped": " ({n} shorter than {min} s not listed)",
        "st_head": ["#", "State", "From (s)", "To (s)", "Duration (s)", "Where"], "st_where": "alt {alt} m, {d} from start",
        "st_steady": "The same all the time: {list}.",
        "st_most": "Most time in **{s}** ({p} %). Changes: {list}.", "st_hl": "{name}: {n} changes, most time in {s} ({p} %)",
        "none_tr": "No map object with a latitude and a longitude in the open files.",
        "tr_head": ["", "Value", "at (s)"], "tr_dur": "Duration", "tr_trav": "Distance travelled", "tr_far": "Farthest from the start",
        "tr_high": "Highest", "tr_low": "Lowest", "tr_speed": "Fastest (ground speed)", "tr_plot": "Track of {o}", "tr_map": "The tracks on the map",
        "tr_intro": "**{o}** in {f}, from {t0} s to {t1} s.",
        "tr_hl": "{o}: {d} travelled, {far} from the start at most",
        "none_diff": "One file is open - open two or more to compare them.",
        "diff_intro": "Compared **{others}** with **{base}** (the baseline), on the baseline's samples in their common time: "
                      "**{n} signals** in both - {same} the same (under 2 %), {small} with small differences, **{large} with large ones**.",
        "diff_only": "Only in one file: {list}.", "diff_skip": "Not compared: {n} time / counter signals.",
        "diff_region": "**The central region of the change: {a} – {b} s.**", "diff_first": " First to diverge: **{name}** at {t} s.",
        "diff_how": "*How it is measured:* the difference on every sample as a share of how much the signal moves "
                    "(its 1st–99th percentile span); *overall* over the whole common time, *in its region* in the 1 % slices "
                    "where it is largest - a signal the same everywhere but in one place has a small overall and a large peak.",
        "diff_head": ["Signal", "File", "Overall", "In its region", "Region (s)", "First diverged (s)", "Shape"],
        "diff_plot": "{name} - {a} – {b} s", "diff_cap": "{others} against {base}: {o} overall, {p} in this region.",
        "diff_where": "Where the files differ", "diff_where_cap": "Each signal's difference over time, as % of how much it moves.",
        "diff_states": "**States that differ:**", "diff_params": "**Parameters that differ** ({n})",
        "diff_rest": "**All differences** ({n})", "diff_hl": "{name} differs from {base} mostly in {a} – {b} s ({p} in its region)",
        "diff_hl_region": "The files differ most in {a} – {b} s; first to diverge: {name} at {t} s",
        "diff_same": "The files are the same in every compared signal.", "param": "Parameter",
        "mo_head": ["Time (s)", "Moment", "Detail"], "mo_intro": "**{f}** - {n} moments worth a look, in time order.",
        "mo_none": "Nothing special found in the open files.",
        "mo": {"phase": "{s} begins", "state": "{name}: {a} → {b}", "takeoff": "Leaves the ground", "landing": "Back on the ground",
               "highest": "Highest", "farthest": "Farthest from the start", "stuck": "{sig} stuck", "saturated": "{sig} at its {edge}",
               "gap": "No samples", "spike": "{sig} spike", "error": "Largest {m} error"},
        "mo_det": {"stuck": "at {v} for {d} s", "saturated": "{v} for {d} s", "gap": "{d} s without samples", "spike": "{v}",
                   "highest": "{v} m", "farthest": "{v}", "error": "{v} (command {c})", "takeoff": "{v} m above the start", "landing": ""},
        "edge": {"max": "maximum", "min": "minimum"},
        "mo_hl": "{f}: {what} at {t} s",
        "ov_intro": "**{f}** - {n} signals, {d} s (from {t0} to {t1} s){r}.", "ov_rate": "about {r} samples a second",
        "ov_quality": "Data quality: {n} signals need a look - {kinds}: {list}.", "ov_clean": "Data quality: nothing to say - no missing values, gaps, repeated or backward time stamps, or rate changes.",
        "ov_kind": {"missing": "missing values", "gaps": "gaps", "duplicates": "repeated time stamps", "backwards": "time going back", "rateChanges": "rate changes"},
        "ov_head": ["Signal", "Min", "Max", "Mean", "Std", "Max at (s)"], "ov_more": "The first {n} of {m} signals (| top N for more).",
        "ov_states": "State signals (distinct values): {list}.", "ov_hl": "{f}: {n} signals with data-quality problems ({kinds})",
        "none_msg": "No byte stream with repeating messages in the open files (a signal of whole numbers 0..255 byte by byte, or columns byte_0..byte_N one message per row).",
        "msg_intro": "**{name}**{file} - **{n} messages** in {d} s ({bytes} bytes); header **{h}**; {cs}.",
        "msg_cs": "checksum {s}: **{e} errors**", "msg_nocs": "no checksum found",
        "msg_lost": " {r} broken frames resynced, {o} bytes outside messages.",
        "msg_head": ["Type", "Count", "Share", "Length (bytes)", "Rate (Hz)", "Period (s)", "Jitter (ms)", "Longest interval (s)", "First (s)", "Last (s)", "Checksum errors"],
        "msg_order": "**The order** repeats every {p} messages: {seq} ({f} of the messages follow it).",
        "msg_trans": "**The commonest transitions:** {list}.",
        "msg_gaps": "**No messages for:** {list}.", "msg_gap": "{dt} s from {a} s",
        "msg_rate": "Messages per second, by type", "msg_rate_cap": "Counted in 1-second bins - a dropout falls to zero.",
        "msg_int": "Interval between messages of a type (s)", "msg_int_cap": "Each type's period over time: jitter, missed messages and dropouts stand out.",
        "msg_err": "Checksum errors (running count)",
        "msg_hl_err": "{name}: {e} checksum errors in {n} messages", "msg_hl_gap": "{name}: no messages for {dt} s from {a} s",
        "msg_hl_resync": "{name}: {r} broken frames resynced", "msg_hl": "{name}: {n} messages, {k} types, header {h}",
        "msg_struct": "**The packet** - what every message of this stream is made of:",
        "msg_struct_head": ["Part", "Bytes (from 0)", "What"],
        "msg_f": {"header": "Header", "length": "Length", "type": "Message type", "payload": "Payload", "checksum": "Checksum"},
        "msg_w": {"header": "fixed {h}", "length": "the message's length: frame = this byte + {a}", "type": "{n} kinds: {list}",
                  "type_len": "{n} kinds: {list} - each kind its own length", "payload": "{list}",
                  "payload_fixed": "{n} bytes", "checksum": "{s} over the bytes from {a} up to it", "none": "no checksum found", "fixed": "every message {n} bytes"},
        "msg_last": ["the last byte", "the last 2 bytes"], "msg_per": "{t}: {n} bytes",
        "msg_seq": "**The messages in order** (the first {n}, from {t} s): {list}",
        "msg_seq_plot": "Message type in order - the first {s} s", "msg_seq_cap": "Each message a step: which kind came after which.",
        "msg_link": "**{a} ↔ {b} - requests and replies** (a reply is the answer in the other direction within {to} s):",
        "msg_link_head": ["Request", "Reply", "Paired by", "Requests", "Answered", "Unanswered", "Retries", "Latency mean (ms)", "95 % (ms)", "Max (ms)", "at (s)", "Replies without a request"],
        "msg_by_id": "byte {j} echoed", "msg_by_next": "the next answer",
        "msg_link_none": "**{a} ↔ {b}:** no message answers another - streaming both ways.",
        "msg_unans": "**Unanswered** ({req}): {n} - at {list} s.", "msg_retry": "**Sent again** ({req}) before an answer: at {list} s.",
        "msg_hs": "**The handshake** at {t} s: {seq}.", "msg_hs_again": "**Again** at {t} s - a reconnect: {seq}.",
        "msg_lat": "Reply latency (s)", "msg_lat_cap": "Each answered request at its time; the gaps are the unanswered ones.",
        "msg_hl_unans": "{a} ↔ {b}: {n} of {m} {req} unanswered", "msg_hl_reconnect": "{a} ↔ {b}: the handshake again at {t} s (a reconnect)",
        "msg_hl_retry": "{a} ↔ {b}: {req} sent again {n} times", "msg_hl_lat": "{a} ↔ {b}: {req} answered in {mean} ms on average, {max} ms at most (at {t} s)",
        "ov_streams": "Byte streams (decoded by [[messages]], their bytes are not measurements): {list}.",
        "toc": "Contents", "toc_none": "No headings yet (## a heading).",
        "sum_none": "Nothing to point out: the report's automatic parts found nothing unusual.",
        "sum_intro": "**What to look at** - the most important things the parts below found:",
        "bad_opt": "{part}: the option \"{o}\" is not known (known: {known}).",
        "no_ref": "No object named \"{r}\" (objects: {list}).", "no_base": "No open file named like \"{b}\" (files: {list}).",
    },
    "he": {
        "none_req": "אין קובץ בדיקות לקבצים הפתוחים - `<name>.checks.json` ליד הקלטה, או `checks.json` בתיקייה שלה (מה שהבדיקות ו-signalviewer-cli check קוראים).",
        "req_intro": "**{n} דרישות** מתוך {file}, נבדקו על כל דגימה של {runs} ריצות: {ok} עברו, {bad} נכשלו.",
        "req_verdict_pass": "**פסק דין: ✔ כל הדרישות מתקיימות.**", "req_verdict_fail": "**פסק דין: ✖ {n} דרישות לא מתקיימות.**",
        "req_runs": "**{ok} מתוך {n} ריצות עומדות בכל הדרישות.**", "req_runs_bad": "לא עומדות: {list}.",
        "req_head": ["דרישה", "פסק דין", "נמדד", "נכשלה לראשונה ב- (s)"], "req_req": "דרישה",
        "req_skipped": "– לא נבדקה", "req_error": "⚠ שגיאה", "req_limit": "גבול", "req_outside": "מחוץ לגבול {n} פעמים, לראשונה ב-{t} s",
        "req_hl": "{r} לא מתקיימת - {m}", "req_plot": "{r} - היכן נכשלה",
        "none_trk": "אין בקבצים הפתוחים זוגות פקודה / ביצוע (זוג נמצא לפי השמות: Des…, …_cmd, …_setpoint, target…, …_ref).",
        "trk_intro": "**{n} זוגות פקודה / ביצוע**, שנמצאו לפי השמות; כל זוג מושווה על כל הדגימות (שגיאה = ביצוע − פקודה).",
        "trk_head": ["פקודה", "ביצוע", "שגיאת RMS", "שגיאה מרבית", "בזמן (ש')", "הטיה", "השהיה (ש')", "צעדים", "Overshoot", "התייצבות (ש')"],
        "trk_tol": ["מחוץ ל-±{tol}", "תקין"], "file": "קובץ", "pass": "✔ תקין", "fail": "✖ נכשל",
        "trk_plot": "{m} מול הפקודה", "error": "שגיאה (ציר ימני)", "not_settled": "לא התייצב ({n})",
        "trk_cap": "השגיאה הגדולה ביותר {max} בזמן {t} ש'; RMS {rms}.", "trk_cap_steps": " {n} צעדים, overshoot עד {o} % (בזמן {to} ש').",
        "trk_hl": "{m} עקב אחרי {s} בשגיאת RMS {rms} (מרבית {max} בזמן {t} ש')", "trk_hl_fail": "{m} מחוץ ל-±{tol} ב-{out} % מהזמן",
        "none_nav": "פחות משני אובייקטים עם מיקום בקבצים הפתוחים - אין מה להשוות.",
        "nav_intro": "**שגיאות ניווט מול {ref}** ({why}); {n} אובייקטים מושווים על כל הדגימות, בצפון / מזרח / מטה.",
        "nav_guess": "הייחוס נוחש: {cls} - לבחירת אחר | ref שם", "nav_chosen": "הייחוס שנבחר",
        "qty": {"position": "מיקום", "velocity": "מהירות", "attitude": "זוויות"},
        "nav_head": ["אובייקט", "שגיאה", "RMS", "ממוצע", "95 %", "מרבית", "בזמן (ש')"],
        "nav_plot": "שגיאת {q} של {o} מול {ref}", "nav_axis": "{c} - שגיאת {q} [{u}] מול {ref}", "nav_hl": "{o}: שגיאת {q} עד {max} {u} (בזמן {t} ש'), 95 % בתוך {p95} {u}",
        "nav_left": "לא הושוו: {list}.",
        "none_st": "אין בקבצים הפתוחים סיגנלי מצב (מוד, שלב או מצב - ערכי טקסט או כמה רמות שלמות).",
        "st_intro": "**{name}** - {n} קטעים, {c} מעברים{dropped}.", "st_dropped": " ({n} קצרים מ-{min} ש' לא ברשימה)",
        "st_head": ["#", "מצב", "מ- (ש')", "עד (ש')", "משך (ש')", "איפה"], "st_where": "גובה {alt} מ', {d} מנקודת ההתחלה",
        "st_steady": "ללא שינוי כל הזמן: {list}.",
        "st_most": "רוב הזמן ב-**{s}** ({p} %). מעברים: {list}.", "st_hl": "{name}: {n} מעברים, רוב הזמן ב-{s} ({p} %)",
        "none_tr": "אין בקבצים הפתוחים אובייקט עם קו רוחב וקו אורך.",
        "tr_head": ["", "ערך", "בזמן (ש')"], "tr_dur": "משך", "tr_trav": "מרחק שעבר", "tr_far": "הכי רחוק מההתחלה",
        "tr_high": "הגובה הרב ביותר", "tr_low": "הגובה הנמוך ביותר", "tr_speed": "המהירות הגבוהה ביותר (קרקע)", "tr_plot": "המסלול של {o}", "tr_map": "המסלולים על המפה",
        "tr_intro": "**{o}** ב-{f}, מ-{t0} ש' עד {t1} ש'.",
        "tr_hl": "{o}: עבר {d}, התרחק עד {far} מההתחלה",
        "none_diff": "פתוח קובץ אחד - פתח שניים או יותר כדי להשוות.",
        "diff_intro": "**{others}** הושוו מול **{base}** (הבסיס), על הדגימות של הבסיס בזמן המשותף: "
                      "**{n} סיגנלים** בשני הקבצים - {same} זהים (פחות מ-2 %), {small} בהבדל קטן, **{large} בהבדל גדול**.",
        "diff_only": "רק בקובץ אחד: {list}.", "diff_skip": "לא הושוו: {n} סיגנלי זמן / מונה.",
        "diff_region": "**האזור המרכזי של השינוי: {a} – {b} ש'.**", "diff_first": " הראשון שסטה: **{name}** בזמן {t} ש'.",
        "diff_how": "*איך זה נמדד:* ההפרש על כל דגימה ביחס לכמה שהסיגנל זז (טווח האחוזונים 1–99); *כולל* על כל הזמן המשותף, "
                    "*באזור שלו* בפרוסות של 1 % שבהן הוא הגדול ביותר - סיגנל זהה בכל מקום חוץ ממקום אחד מקבל כולל קטן ושיא גדול.",
        "diff_head": ["סיגנל", "קובץ", "כולל", "באזור שלו", "אזור (ש')", "סטה לראשונה (ש')", "צורה"],
        "diff_plot": "{name} - {a} – {b} ש'", "diff_cap": "{others} מול {base}: {o} כולל, {p} באזור הזה.",
        "diff_where": "איפה הקבצים שונים", "diff_where_cap": "ההפרש של כל סיגנל לאורך הזמן, באחוזים מכמה שהוא זז.",
        "diff_states": "**מצבים שונים:**", "diff_params": "**פרמטרים שונים** ({n})",
        "diff_rest": "**כל ההבדלים** ({n})", "diff_hl": "{name} שונה מ-{base} בעיקר ב-{a} – {b} ש' ({p} באזור שלו)",
        "diff_hl_region": "הקבצים שונים בעיקר ב-{a} – {b} ש'; הראשון שסטה: {name} בזמן {t} ש'",
        "diff_same": "הקבצים זהים בכל הסיגנלים שהושוו.", "param": "פרמטר",
        "mo_head": ["זמן (ש')", "רגע", "פירוט"], "mo_intro": "**{f}** - {n} רגעים ששווה להסתכל עליהם, לפי סדר הזמן.",
        "mo_none": "לא נמצא שום דבר מיוחד בקבצים הפתוחים.",
        "mo": {"phase": "{s} מתחיל", "state": "{name}: {a} → {b}", "takeoff": "עוזב את הקרקע", "landing": "חוזר לקרקע",
               "highest": "הגובה הרב ביותר", "farthest": "הכי רחוק מההתחלה", "stuck": "{sig} תקוע", "saturated": "{sig} ב{edge} שלו",
               "gap": "אין דגימות", "spike": "קפיצה ב-{sig}", "error": "השגיאה הגדולה ביותר של {m}"},
        "mo_det": {"stuck": "על {v} במשך {d} ש'", "saturated": "{v} במשך {d} ש'", "gap": "{d} ש' בלי דגימות", "spike": "{v}",
                   "highest": "{v} מ'", "farthest": "{v}", "error": "{v} (פקודה {c})", "takeoff": "{v} מ' מעל ההתחלה", "landing": ""},
        "edge": {"max": "מקסימום", "min": "מינימום"},
        "mo_hl": "{f}: {what} בזמן {t} ש'",
        "ov_intro": "**{f}** - {n} סיגנלים, {d} ש' (מ-{t0} עד {t1} ש'){r}.", "ov_rate": "בערך {r} דגימות בשנייה",
        "ov_quality": "איכות הנתונים: {n} סיגנלים דורשים בדיקה - {kinds}: {list}.", "ov_clean": "איכות הנתונים: אין מה לציין - אין ערכים חסרים, חורים, חותמות זמן כפולות או אחורה, או שינויי קצב.",
        "ov_kind": {"missing": "ערכים חסרים", "gaps": "חורים", "duplicates": "חותמות זמן כפולות", "backwards": "זמן שחוזר אחורה", "rateChanges": "שינויי קצב"},
        "ov_head": ["סיגנל", "מינימום", "מקסימום", "ממוצע", "סטיית תקן", "מקסימום בזמן (ש')"], "ov_more": "{n} הראשונים מתוך {m} סיגנלים (| top N ליותר).",
        "ov_states": "סיגנלי מצב (מספר ערכים): {list}.", "ov_hl": "{f}: {n} סיגנלים עם בעיות איכות נתונים ({kinds})",
        "none_msg": "אין בקבצים הפתוחים זרם בתים עם הודעות חוזרות (סיגנל של מספרים שלמים 0..255 בית אחר בית, או עמודות byte_0..byte_N הודעה בשורה).",
        "msg_intro": "**{name}**{file} - **{n} הודעות** ב-{d} ש' ({bytes} בתים); כותרת **{h}**; {cs}.",
        "msg_cs": "checksum {s}: **{e} שגיאות**", "msg_nocs": "לא נמצא checksum",
        "msg_lost": " {r} מסגרות שבורות - סונכרן מחדש, {o} בתים מחוץ להודעות.",
        "msg_head": ["סוג", "כמות", "חלק", "אורך (בתים)", "קצב (Hz)", "מחזור (ש')", "ריצוד (ms)", "המרווח הארוך ביותר (ש')", "ראשונה (ש')", "אחרונה (ש')", "שגיאות checksum"],
        "msg_order": "**הסדר** חוזר כל {p} הודעות: {seq} ({f} מההודעות לפיו).",
        "msg_trans": "**המעברים הנפוצים:** {list}.",
        "msg_gaps": "**אין הודעות במשך:** {list}.", "msg_gap": "{dt} ש' מ-{a} ש'",
        "msg_rate": "הודעות בשנייה, לפי סוג", "msg_rate_cap": "נספר בחלונות של שנייה - נפילה של הקשר יורדת לאפס.",
        "msg_int": "המרווח בין הודעות מאותו סוג (ש')", "msg_int_cap": "המחזור של כל סוג לאורך הזמן: ריצוד, הודעות חסרות ונפילות בולטים.",
        "msg_err": "שגיאות checksum (ספירה מצטברת)",
        "msg_hl_err": "{name}: {e} שגיאות checksum ב-{n} הודעות", "msg_hl_gap": "{name}: אין הודעות במשך {dt} ש' מ-{a} ש'",
        "msg_hl_resync": "{name}: {r} מסגרות שבורות - סונכרן מחדש", "msg_hl": "{name}: {n} הודעות, {k} סוגים, כותרת {h}",
        "msg_struct": "**הפקטה** - ממה בנויה כל הודעה בזרם הזה:",
        "msg_struct_head": ["חלק", "בתים (מ-0)", "מה"],
        "msg_f": {"header": "כותרת", "length": "אורך", "type": "סוג ההודעה", "payload": "תוכן", "checksum": "Checksum"},
        "msg_w": {"header": "קבועה {h}", "length": "אורך ההודעה: המסגרת = הבית הזה + {a}", "type": "{n} סוגים: {list}",
                  "type_len": "{n} סוגים: {list} - לכל סוג אורך משלו", "payload": "{list}",
                  "payload_fixed": "{n} בתים", "checksum": "{s} על הבתים מ-{a} ועד לפניו", "none": "לא נמצא checksum", "fixed": "כל הודעה {n} בתים"},
        "msg_last": ["הבית האחרון", "2 הבתים האחרונים"], "msg_per": "{t}: {n} בתים",
        "msg_seq": "**ההודעות לפי הסדר** ({n} הראשונות, מ-{t} ש'): {list}",
        "msg_seq_plot": "סוג ההודעה לפי הסדר - {s} השניות הראשונות", "msg_seq_cap": "כל הודעה מדרגה: איזה סוג בא אחרי איזה.",
        "msg_link": "**{a} ↔ {b} - בקשות ותשובות** (תשובה היא ההודעה בכיוון השני בתוך {to} ש'):",
        "msg_link_head": ["בקשה", "תשובה", "הותאמו לפי", "בקשות", "נענו", "לא נענו", "שליחות חוזרות", "השהיה ממוצעת (ms)", "95 % (ms)", "מרבית (ms)", "בזמן (ש')", "תשובות בלי בקשה"],
        "msg_by_id": "בית {j} חוזר בתשובה", "msg_by_next": "התשובה הבאה",
        "msg_link_none": "**{a} ↔ {b}:** אף הודעה לא עונה לאחרת - זרימה בשני הכיוונים.",
        "msg_unans": "**לא נענו** ({req}): {n} - בזמנים {list} ש'.", "msg_retry": "**נשלחו שוב** ({req}) לפני תשובה: בזמנים {list} ש'.",
        "msg_hs": "**לחיצת היד** בזמן {t} ש': {seq}.", "msg_hs_again": "**שוב** בזמן {t} ש' - התחברות מחדש: {seq}.",
        "msg_lat": "השהיית התשובה (ש')", "msg_lat_cap": "כל בקשה שנענתה בזמן שלה; החורים הם הבקשות שלא נענו.",
        "msg_hl_unans": "{a} ↔ {b}: {n} מתוך {m} {req} לא נענו", "msg_hl_reconnect": "{a} ↔ {b}: לחיצת היד שוב בזמן {t} ש' (התחברות מחדש)",
        "msg_hl_retry": "{a} ↔ {b}: {req} נשלחה שוב {n} פעמים", "msg_hl_lat": "{a} ↔ {b}: {req} נענתה בממוצע תוך {mean} ms, לכל היותר {max} ms (בזמן {t} ש')",
        "ov_streams": "זרמי בתים (מפוענחים ב-[[messages]], הבתים שלהם אינם מדידות): {list}.",
        "toc": "תוכן העניינים", "toc_none": "אין עדיין כותרות (## כותרת).",
        "sum_none": "אין מה להדגיש: החלקים האוטומטיים של הדוח לא מצאו דבר חריג.",
        "sum_intro": "**על מה להסתכל** - הדברים החשובים ביותר שהחלקים שלהלן מצאו:",
        "bad_opt": "{part}: האפשרות \"{o}\" אינה מוכרת (מוכרות: {known}).",
        "no_ref": "אין אובייקט בשם \"{r}\" (אובייקטים: {list}).", "no_base": "אין קובץ פתוח בשם כמו \"{b}\" (קבצים: {list}).",
    },
}
KNOWN = {"requirements": "top N, table", "tracking": "top N, table, tol X, outside X%, skip NAME", "navigation": "ref NAME, position, velocity, attitude, top N, table",
         "states": "min Xs, table", "trajectory": "table", "moments": "top N", "differences": "base NAME, top N, table, small X%, large X%", "summary": "top N", "toc": "", "overview": "top N, plots N, table",
         "messages": "header AA55, length N, type N, checksum NAME, table"}


class PartError(Exception):
    pass


def fmt(v, digits: str = "") -> str:
    if v is None:
        return "—"
    return format_value(float(v), digits) if not isinstance(v, str) else v


def pct(v: Optional[float]) -> str:
    return "—" if v is None else ("%.3g %%" % (v * 100) if v * 100 < 10 else "%.0f %%" % (v * 100))


def secs(v: Optional[float]) -> str:
    return "—" if v is None else ("%.3g" % v if abs(v) < 10 else "%.1f" % v)


def dist(m: Optional[float], lang: str) -> str:
    if m is None:
        return "—"
    if m >= 1000:
        return ("%.2f km" if lang == "en" else "%.2f ק\"מ") % (m / 1000)
    return ("%.0f m" if lang == "en" else "%.0f מ'") % m


def table(head: Sequence[str], rows: Sequence[Sequence[str]]) -> str:
    def cell(x) -> str:
        return str(x).replace("|", "\\|").replace("\n", " ")
    return "\n".join(["| " + " | ".join(cell(h) for h in head) + " |", "|" + "---|" * len(head)]
                     + ["| " + " | ".join(cell(c) for c in r) + " |" for r in rows])


def options(part: str, opts: Sequence[str]) -> Dict:
    """`| top 5, table, tol 2` -> {"top": 5, "table": True, "tol": 2.0}; anything else is an error said in place."""
    out: Dict = {}
    for o in opts:
        o = o.strip()
        if not o:
            continue
        m = re.fullmatch(r"(top|tol|min|outside|small|large)\s*[= ]?\s*(-?[\d.]+)\s*(%|s)?", o, re.I)
        if m:
            v = float(m.group(2))
            out[m.group(1).lower()] = int(v) if m.group(1).lower() == "top" else (v / 100 if m.group(3) == "%" or m.group(1).lower() in ("small", "large") else v)
            continue
        m = re.fullmatch(r"(header|length|type|checksum)\s*[= ]\s*(\S+)", o, re.I)
        if m and part == "messages":
            out[m.group(1).lower()] = m.group(2)
            continue
        m = re.fullmatch(r"(ref|base|skip)\s*[= ]\s*(.+)", o, re.I)
        if m:
            k = m.group(1).lower()
            if k == "skip":
                out.setdefault("skip", []).append(m.group(2).strip().strip('"'))
            else:
                out[k] = m.group(2).strip().strip('"')
            continue
        lo = o.lower()
        if lo in ("table", "table only"):
            out["table"] = True
        elif lo in ("position", "velocity", "attitude"):
            out.setdefault("what", []).append(lo)
        else:
            raise PartError(o)
    return out


class Part:
    """What one part writes: Markdown with ⟦k⟧ markers for its plots, the plot items (appended to the document's),
    the inline series its plots draw (an error is not a recorded signal) and its highlights for [[summary]]."""

    def __init__(self, store, items: List[dict], extra: Dict[str, Tuple[np.ndarray, np.ndarray]], lang: str):
        self.store, self.items, self.extra, self.lang = store, items, extra, lang
        self.S = S.get(lang, S["en"])
        self.md: List[str] = []
        self.highlights: List[Dict] = []
        self.base = ""                                   # the app's map layer (the part item's "mapBase")

    def say(self, text: str):
        self.md.append(text)

    def plot(self, title: str, signals: List[dict], rng=None, caption: str = "", mode: str = "time", x: Optional[str] = None,
             table: str = "none"):
        sp = {"title": title, "caption": caption, "mode": mode, "range": rng, "signals": signals}
        if x:
            sp["xSignal"], sp["xLabel"] = x, x.split("/", 1)[-1]
        self.items.append({"kind": "plots", "plots": [sp], "table": table, "tab": "", "auto": True})
        self.md.append("\u27e6%d\u27e7" % (len(self.items) - 1))

    def map(self, title: str, objects: List[dict], caption: str = ""):
        """A map of tracks (app/mapimage.py: the picture in PDF / Word, the interactive offline map in the page), on
        the map layer the app shows (only the tiles it has kept are used; else the offline world map)."""
        sp = {"title": title, "caption": caption, "mode": "geo", "signals": [],
              "geo": {"objects": objects, "base": self.base or "offline", "cursor": None, "places": [], "names": True, "trackWidth": 2.5}}
        self.items.append({"kind": "plots", "plots": [sp], "table": "none", "tab": "", "auto": True})
        self.md.append("\u27e6%d\u27e7" % (len(self.items) - 1))

    def series(self, label: str, t, y) -> str:
        sid = "auto/%d/%s" % (len(self.extra), label)
        self.extra[sid] = (np.asarray(t, dtype=np.float64), np.asarray(y, dtype=np.float64))
        return sid

    def hl(self, level: str, score: float, text: str):
        self.highlights.append({"level": level, "score": float(score), "text": text})


def sig_line(sid: str, label: str, k: int, **kw) -> dict:
    return {"id": sid, "label": label, "color": PALETTE[k % len(PALETTE)], "width": 1.5, "scale": 1, "offset": 0,
            "state": False, "tOffset": 0, **kw}


def _runs(store, ids: Optional[Sequence[str]]) -> List[str]:
    rids = [r for r in (ids or list(store.runs)) if r in store.runs and r != "derived"]
    return rids


def _name(store, rid: str) -> str:
    return store.get(rid).name


def _sig(store, sid: str):
    t, y = store.signal(sid)
    return np.asarray(t, dtype=np.float64), np.asarray(y, dtype=np.float64)


def _label(store, sid: str, rids: Sequence[str]) -> str:
    rid, _, name = sid.partition("/")
    return name if len(rids) < 2 else "%s: %s" % (_name(store, rid), name)
