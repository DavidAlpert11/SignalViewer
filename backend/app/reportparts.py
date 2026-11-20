"""RE2 (owner, 2026-11-19): the report's ready-made parts - `[[tracking]]`, `[[navigation]]`, `[[states]]`,
`[[trajectory]]`, `[[differences]]`, `[[summary]]`. Each looks at the open files, finds what it needs by the
signals' names (commanded / measured pairs, map objects, state signals, the same signal in several files),
computes on every sample (svcore/reportparts.py, svcore/objcompare.py) and writes ordinary Markdown - a sentence,
tables, plots - that replaces the part's marker before the document is parsed. So the page, the PDF and Word
draw it with the code that draws everything else, and *Expand to text* hands the same Markdown to the user.

Generic on purpose: nothing here knows a log format; the names' rules are the app's (desired.ts, objectDetect.ts)
and a part that finds nothing says so in one line.
"""
import math
import os
import re
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

from svcore import reportparts as rp
from svcore.docfields import format_value

PALETTE = ["#3D8BFD", "#E8590C", "#2F9E44", "#AE3EC9", "#F08C00", "#0CA678", "#E64980", "#1C7ED6"]
PARTS = ("toc", "overview", "tracking", "navigation", "states", "trajectory", "moments", "differences", "messages", "summary")
UNITS = {"position": "m", "velocity": "m/s", "attitude": "deg"}

S: Dict[str, Dict[str, Any]] = {
    "en": {
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
KNOWN = {"tracking": "top N, table, tol X, outside X%, skip NAME", "navigation": "ref NAME, position, velocity, attitude, top N, table",
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


# ------------------------------------------------------------------------------------------------ tracking

def tracking(p: Part, rids: List[str], arg: str, o: Dict):
    st, S_ = p.store, p.S
    ids = [f"{rid}/{n}" for rid in rids for n in st.get(rid).run.signals]
    pairs = rp.setpoint_pairs(ids)
    flt = arg.strip().lower()
    if flt:
        pairs = [q for q in pairs if flt in q["setpoint"].lower() or flt in q["measured"].lower()]
    for sk in o.get("skip", []):
        pairs = [q for q in pairs if sk.lower() not in q["setpoint"].lower() and sk.lower() not in q["measured"].lower()]
    if not pairs:
        p.say("*%s*" % S_["none_trk"])
        return
    tol, outside = o.get("tol"), o.get("outside", 0.0)
    rows = []
    for q in pairs:
        r = rp.tracking(_sig(st, q["setpoint"]), _sig(st, q["measured"]), q["measured"].split("/", 1)[1], tol, st.is_state(q["setpoint"]))
        rows.append((q, r))
    rows.sort(key=lambda x: -(x[1].get("score") or 0))
    p.say(S_["trk_intro"].format(n=len(pairs)))
    head = ([S_["file"]] if len(rids) > 1 else []) + S_["trk_head"] + ([h.format(tol=fmt(tol)) for h in S_["trk_tol"]] if tol else [])
    body = []
    for q, r in rows:
        if r.get("error"):
            continue
        fails = tol is not None and (r.get("outside") or 0) > outside * 100
        sett = r.get("settling")
        settle = S_["not_settled"].format(n=r["unsettled"]) if r.get("steps") and sett is None else secs(sett) if r.get("steps") else "—"
        row = ([_name(st, q["measured"].split("/")[0])] if len(rids) > 1 else []) + [
            rp.bare(q["setpoint"].split("/", 1)[1]), rp.bare(q["measured"].split("/", 1)[1]), fmt(r["rms"]), fmt(r["max"]), secs(r["tmax"]),
            fmt(r["bias"]), secs(r.get("delay")), str(r.get("steps") or 0),
            ("%.0f %%" % r["overshoot"]) if r.get("steps") else "—", settle]
        if tol:
            row += ["%.2g %%" % r["outside"], S_["fail"] if fails else S_["pass"]]
        body.append(row)
        m, s = rp.bare(q["measured"].split("/", 1)[1]), rp.bare(q["setpoint"].split("/", 1)[1])
        if len(rids) > 1:
            m = "%s: %s" % (_name(st, q["measured"].split("/")[0]), m)
        if fails:
            p.hl("fail", 10 + (r.get("outside") or 0), S_["trk_hl_fail"].format(m=m, tol=fmt(tol), out="%.2g" % r["outside"]))
        else:
            p.hl("warn" if r["score"] > 0.1 else "info", r["score"], S_["trk_hl"].format(m=m, s=s, rms=fmt(r["rms"]), max=fmt(r["max"]), t=secs(r["tmax"])))
    p.say(table(head, body))
    if o.get("table"):
        return
    for k, (q, r) in enumerate([x for x in rows if not x[1].get("error")][:o.get("top", 4)]):
        m = q["measured"].split("/", 1)[1]
        cap = S_["trk_cap"].format(max=fmt(r["max"]), t=secs(r["tmax"]), rms=fmt(r["rms"]))
        if r.get("steps"):
            cap += S_["trk_cap_steps"].format(n=r["steps"], o="%.0f" % r["overshoot"], to=secs(r["tOvershoot"]))
        e = p.series(S_["error"], *r["e"])
        p.plot(S_["trk_plot"].format(m=_label(st, q["measured"], rids)),
               [sig_line(q["measured"], _label(st, q["measured"], rids), 0),
                sig_line(q["setpoint"], _label(st, q["setpoint"], rids), 1, style="dash"),
                sig_line(e, S_["error"], 3, axis="right", width=1)], caption=cap)
        del r["e"]


# ------------------------------------------------------------------------------------------------ objects

def detect_objects(store, rids: Sequence[str]) -> List[dict]:
    """The addable map objects of these files, best first ("file:name" where two files share a name)."""
    from svcore.objects import addable, detect
    cands = []
    for rid in rids:
        lr = store.get(rid)
        d = detect([(f"{rid}/{n}", n) for n in lr.run.signals], rid, lr.name)
        cands += [dict(c) for c in d["candidates"] if addable(c)]
    names = [c["name"] for c in cands]
    for c in cands:
        if len(rids) > 1 and names.count(c["name"]) > 1:
            c["name"] = "%s:%s" % (store.get(c["runId"]).name, c["name"])
    return cands


GUESS = {"truth": 0, "receiver": 1, "navigation": 2, "other": 3}


def guess_reference(objs: Sequence[dict]) -> Optional[dict]:
    """The reference an engineer would take: the truth (simulation / model), else a receiver (GPS), else the first."""
    return min(objs, key=lambda c: GUESS.get(c.get("cls", "other"), 3)) if objs else None


def navigation(p: Part, rids: List[str], arg: str, o: Dict):
    """Each object against the reference. Several files and no reference chosen: inside each file, against its own
    guessed reference (a truth in run A is not the reference of run B's estimate)."""
    st, S_ = p.store, p.S
    want = o.get("ref") or arg.strip()
    groups = [rids] if want or len(rids) < 2 else [[r] for r in rids]
    done = False
    acc: Dict[Tuple[str, str], List] = {}
    refs: List[str] = []
    for g in groups:
        objs = detect_objects(st, g)
        if len(objs) < 2:
            continue
        if want:
            ref = next((c for c in objs if c["name"].lower() == want.lower()), None) or next((c for c in objs if want.lower() in c["name"].lower()), None)
            if ref is None:
                raise PartError(S_["no_ref"].format(r=want, list=", ".join(c["name"] for c in objs)))
            why = S_["nav_chosen"]
        else:
            ref = guess_reference(objs)
            assert ref is not None                       # two objects or more
            why = S_["nav_guess"].format(cls=ref["cls"])
        _navigation(p, objs, ref, why, o, st.get(g[0]).name if len(groups) > 1 else "", acc)
        refs.append(ref["name"])
        done = True
    if not done:
        p.say("*%s*" % S_["none_nav"])
        return
    if not o.get("table"):
        # one plot per axis (owner: every component on one plot cannot be read): in it every compared object - of
        # every file, so two runs' errors are seen together; horizontal / vertical are left to the tables
        for (q, c), lines in acc.items():
            # the noisiest underneath, the smooth ones on top - a receiver's noise must not hide an estimate's error
            lines = sorted(lines, key=lambda x: -float(np.nanstd(np.diff(np.asarray(x[1][1], dtype=np.float64)))) if len(x[1][1]) > 2 else 0.0)
            p.plot(S_["nav_axis"].format(c=c, q=S_["qty"][q], u=UNITS[q], ref=" / ".join(dict.fromkeys(refs))),
                   [sig_line(p.series("%s %s" % (lab, c), *ts), lab, k) for k, (lab, ts) in enumerate(lines)])


def _navigation(p: Part, objs: List[dict], ref: dict, why: str, o: Dict, file: str, acc: Dict[Tuple[str, str], List]):
    from svcore.objcompare import compare
    st, S_ = p.store, p.S
    what = o.get("what") or ["position", "velocity", "attitude"]
    res = compare(lambda sid: _sig(st, sid), objs, ref["name"], None, what, "ned")
    named = (lambda n: "%s: %s" % (file, n)) if file else (lambda n: n)
    p.say(S_["nav_intro"].format(ref=named(ref["name"]), why=why, n=len(objs) - 1))
    for q in what:
        rows = [r for r in res["stats"] if r["qty"] == q]
        if not rows:
            continue
        u = UNITS[q]
        p.say("**%s** [%s]" % (S_["qty"][q], u))
        p.say(table(S_["nav_head"], [[named(r["object"]), r["comp"], fmt(r["rms"]), fmt(r["mean"]), fmt(r["p95_abs"]), fmt(r["max_abs"]), secs(r["t_max_abs"])] for r in rows]))
        # a highlight per object (its largest component); the worst object of this quantity plotted
        by: Dict[str, List[dict]] = {}
        for r in rows:
            by.setdefault(r["object"], []).append(r)
        for obj, rs in by.items():
            w = max(rs, key=lambda r: r["max_abs"] or 0)
            p.hl("info", 0.5 + (w["p95_abs"] or 0) / (1 + abs(w["p95_abs"] or 0)) * 0.1,
                 S_["nav_hl"].format(o=named(obj), q=S_["qty"][q], max=fmt(w["max_abs"]), u=u, t=secs(w["t_max_abs"]), p95=fmt(w["p95_abs"])))
        # the plots come after every file's tables (navigation): one plot per axis, each object a line
        obs = sorted(by, key=lambda ob: -max(r["rms"] or 0 for r in by[ob]))[:o.get("top", 4)]
        for c in [c for c in res["errors"][q][obs[0]] if c not in ("horizontal error", "vertical error")]:
            for ob in obs:
                if c in res["errors"][q][ob]:
                    acc.setdefault((q, c), []).append((named(ob), res["errors"][q][ob][c]))
    left = ["%s (%s)" % (x.get("object"), x.get("why") or x.get("reason") or "") for q in res.get("left_out", {}).values() for x in q]
    reasons = ["%s: %s" % (S_["qty"].get(q, q), r) for q, r in res.get("reasons", {}).items()]
    if left or reasons:
        p.say(S_["nav_left"].format(list="; ".join(reasons + left)))


# ------------------------------------------------------------------------------------------------ states

def state_signals(store, rids: Sequence[str]) -> List[str]:
    """The state signals worth a timeline: the run's mode / phase signal first (overview.phase_signal), then any
    signal with text values (a status, a mode by another name), then the numeric states named like a mode / phase."""
    from svcore.overview import PHASE_NAMES, phase_signal
    out: List[str] = []
    for rid in rids:
        names = list(store.get(rid).run.signals)
        lab = [(n, bool(store.labels(f"{rid}/{n}"))) for n in names]
        first = phase_signal(lab)
        # then any text-valued signal (a status, a mode by another name) and the numeric states named like a mode
        texts = [n for n, has in lab if has and n != first and len(store.labels(f"{rid}/{n}") or {}) <= 50]
        named = [n for n in names if n != first and n not in texts and PHASE_NAMES.search(n) and store.is_state(f"{rid}/{n}")]
        cands = ([first] if first else []) + texts + named
        out += [f"{rid}/{n}" for n in cands]
    return out


def states(p: Part, rids: List[str], arg: str, o: Dict):
    st, S_ = p.store, p.S
    cands = state_signals(st, rids)
    flt = arg.strip().lower()
    if flt:
        cands = [c for c in cands if flt in c.split("/", 1)[1].lower()] or \
            [f"{rid}/{n}" for rid in rids for n in st.get(rid).run.signals if flt in n.lower()]
    if not cands:
        p.say("*%s*" % S_["none_st"])
        return
    mn = o.get("min", 0.0)
    steady: List[str] = []
    for sid in cands[:8]:
        rid = sid.split("/")[0]
        t, y = _sig(st, sid)
        run = st.get(rid).run
        end = max(float(t[-1]) if len(t) else 0.0, float(run.end_time or 0.0) + float(run.time_offset or 0.0))
        tl = rp.timeline(t, y, st.labels(sid), end)
        if not tl:
            continue
        if len(tl) == 1 and not flt:                    # never changes: one line, no table and no plot
            steady.append("%s: %s" % (_label(st, sid, rids), tl[0]["label"]))
            continue
        shown = [s for s in tl if s["b"] - s["a"] >= mn]
        dropped = len(tl) - len(shown)
        name = _label(st, sid, rids)
        p.say(S_["st_intro"].format(name=name, n=len(tl), c=max(0, len(tl) - 1),
                                    dropped=S_["st_dropped"].format(n=dropped, min=secs(mn)) if dropped else ""))
        track = _track_of(st, rid)
        rows = []
        for k, s in enumerate(shown[:200]):
            where = "—"
            if track:
                lat = rp.at(track["t"], track["lat"], s["a"]); lon = rp.at(track["t"], track["lon"], s["a"])
                alt = rp.at(track["t"], track["alt"], s["a"]) if track.get("alt") is not None else None
                if lat is not None and lon is not None:
                    d = float(rp.distance_m(track["lat0"], track["lon0"], np.array([lat]), np.array([lon]))[0])
                    where = S_["st_where"].format(alt=fmt(alt) if alt is not None else "—", d=dist(d, p.lang))
            rows.append([str(k + 1), s["label"], secs(s["a"]), secs(s["b"]), secs(s["b"] - s["a"]), where])
        p.say(table(S_["st_head"], rows))
        tot: Dict[str, float] = {}
        for s in tl:
            tot[s["label"]] = tot.get(s["label"], 0.0) + (s["b"] - s["a"])
        whole = sum(tot.values()) or 1.0
        most = max(tot, key=lambda k: tot[k])
        ch: Dict[str, int] = {}
        for a, b in zip(tl, tl[1:]):
            key = "%s → %s" % (a["label"], b["label"])
            ch[key] = ch.get(key, 0) + 1
        top = sorted(ch.items(), key=lambda kv: -kv[1])[:6]
        p.say(S_["st_most"].format(s=most, p="%.0f" % (tot[most] / whole * 100),
                                   list=", ".join("%s ×%d" % kv for kv in top) if top else "—"))
        p.hl("info", 0.3, S_["st_hl"].format(name=name, n=max(0, len(tl) - 1), s=most, p="%.0f" % (tot[most] / whole * 100)))
        if not o.get("table"):
            p.plot(name, [sig_line(sid, name, 0, state=True)])
    if steady:
        p.say(S_["st_steady"].format(list=", ".join(steady)))


def _track_of(store, rid: str) -> Optional[dict]:
    objs = [c for c in detect_objects(store, [rid]) if c.get("pos") == "lla"]
    if not objs:
        return None
    c = guess_reference(objs)
    if c is None:
        return None
    pk = c["picks"]
    t, lat = _sig(store, pk["lat"]["id"])
    _, lon = _sig(store, pk["lon"]["id"])
    alt = None
    if "alt" in pk:
        ta, a = _sig(store, pk["alt"]["id"])
        alt = np.interp(t, ta, a) if len(ta) > 1 else None
    if len(lon) != len(lat):
        tl, lon0 = _sig(store, pk["lon"]["id"])
        lon = np.interp(t, tl, lon0)
    ok = np.flatnonzero(np.isfinite(lat) & np.isfinite(lon) & ~((np.abs(lat) < 1e-9) & (np.abs(lon) < 1e-9)))
    if not len(ok):
        return None
    return {"name": c["name"], "t": t, "lat": lat, "lon": lon, "alt": alt, "lat0": float(lat[ok[0]]), "lon0": float(lon[ok[0]]),
            "latId": pk["lat"]["id"], "lonId": pk["lon"]["id"]}


def trajectory(p: Part, rids: List[str], arg: str, o: Dict):
    """Each file's track (its reference object: the truth, else the receiver...) - its facts - and one map with every
    file's track, so two runs of one route are seen together."""
    st, S_ = p.store, p.S
    tracks: List[dict] = []
    for rid in rids:
        objs = [c for c in detect_objects(st, [rid]) if c.get("pos") == "lla"]
        if arg.strip():
            objs = [c for c in objs if arg.strip().lower() in c["name"].lower()]
        if not objs:
            continue
        c = (guess_reference(objs) if not arg.strip() else None) or objs[0]
        tr = _track_of_obj(st, c)
        f = rp.path_facts(tr["t"], tr["lat"], tr["lon"], tr["alt"]) if tr else {}
        if not f:
            continue
        name = c["name"] if len(rids) < 2 or ":" in c["name"] else "%s: %s" % (_name(st, rid), c["name"])
        p.say(S_["tr_intro"].format(o=c["name"], f=_name(st, rid), t0=secs(f["t0"]), t1=secs(f["t1"])))
        rows = [[S_["tr_dur"], secs(f["t1"] - f["t0"]) + (" s" if p.lang == "en" else " ש'"), ""],
                [S_["tr_trav"], dist(f["travelled"], p.lang), ""],
                [S_["tr_far"], dist(f["farthest"], p.lang), secs(f["tFarthest"])]]
        if "highest" in f:
            rows += [[S_["tr_high"], fmt(f["highest"]) + " m", secs(f["tHighest"])], [S_["tr_low"], fmt(f["lowest"]) + " m", ""]]
        if "speed" in f:
            rows.append([S_["tr_speed"], fmt(f["speed"]) + " m/s", ""])
        p.say(table(S_["tr_head"], rows))
        p.hl("info", 0.2, S_["tr_hl"].format(o=name, d=dist(f["travelled"], p.lang), far=dist(f["farthest"], p.lang)))
        pk = c["picks"]
        tracks.append({"name": name, "color": PALETTE[len(tracks) % len(PALETTE)], "lat": pk["lat"]["id"], "lon": pk["lon"]["id"],
                       "alt": pk["alt"]["id"] if "alt" in pk else None, "track": None})
    if not tracks:
        p.say("*%s*" % S_["none_tr"])
        return
    if not o.get("table"):
        p.map(S_["tr_map"] if len(tracks) > 1 else S_["tr_plot"].format(o=tracks[0]["name"]), tracks)


def _track_of_obj(store, c: dict) -> Optional[dict]:
    pk = c["picks"]
    t, lat = _sig(store, pk["lat"]["id"])
    tl, lon = _sig(store, pk["lon"]["id"])
    if len(tl) != len(t):
        lon = np.interp(t, tl, lon)
    alt = None
    if "alt" in pk:
        ta, a = _sig(store, pk["alt"]["id"])
        alt = np.interp(t, ta, a) if len(ta) > 1 else None
    return {"t": t, "lat": lat, "lon": lon, "alt": alt, "latId": pk["lat"]["id"], "lonId": pk["lon"]["id"]}


# ------------------------------------------------------------------------------------------------ overview

def overview(p: Part, rids: List[str], arg: str, o: Dict):
    """Any recording, whatever it holds (owner, 2026-11-19: not only flight logs): each file's size and rate, its data
    quality (svcore/quality.py, the Quality dialog's checks), every numeric signal's statistics on all its samples,
    its state signals, and its first signals plotted - one plot each."""
    from svcore.ops import compute_signal_stats
    from svcore.quality import run_quality
    st, S_ = p.store, p.S
    shown: Dict[str, List[str]] = {}
    for rid in rids:
        lr = st.get(rid)
        run = lr.run
        names = list(run.signals)
        flt = arg.strip().lower()
        if flt:
            names = [n for n in names if flt in n.lower()]
        nums: List[str] = []
        states_: List[str] = []
        streams = set(byte_streams(st, rid))
        for n in names:
            if n not in streams:
                (states_ if st.is_state(f"{rid}/{n}") else nums).append(n)
        t0, t1 = float(run.start_time + (run.time_offset or 0)), float(run.end_time + (run.time_offset or 0))
        rate = (len(run.time) - 1) / (run.end_time - run.start_time) if run.end_time > run.start_time and len(run.time) > 1 else None
        p.say(S_["ov_intro"].format(f=lr.name, n=len(names), d=secs(t1 - t0), t0=secs(t0), t1=secs(t1),
                                    r=(", " + S_["ov_rate"].format(r=fmt(rate))) if rate else ""))
        q = run_quality((n, sg.time if sg.time is not None else run.time, sg.data, st.is_state(f"{rid}/{n}"))
                        for n, sg in ((n, run.signals[n]) for n in names))
        bad = [r for r in q["signals"] if r["issues"]]
        if bad:
            kinds = ", ".join("%s %d" % (S_["ov_kind"].get(k, k), c) for k, c in q["count"].items() if c)
            p.say(S_["ov_quality"].format(n=len(bad), kinds=kinds, list=", ".join(
                "%s (%s)" % (r["name"], ", ".join(S_["ov_kind"].get(k, k) for k in r["issues"])) for r in bad[:8]) + (" …" if len(bad) > 8 else "")))
            p.hl("warn", 2.0, S_["ov_hl"].format(f=lr.name, n=len(bad), kinds=kinds))
        else:
            p.say(S_["ov_clean"])
        rows = []
        for n in nums[:o.get("top", 60)]:
            t, y = _sig(st, f"{rid}/{n}")
            ss = compute_signal_stats(t, y) or {}
            tmax = None
            if len(y) and np.isfinite(y).any():
                tmax = float(t[int(np.nanargmax(y))])
            rows.append([n, fmt(ss.get("min")), fmt(ss.get("max")), fmt(ss.get("mean")), fmt(ss.get("std")), secs(tmax)])
        if rows:
            p.say(table(S_["ov_head"], rows))
            if len(nums) > len(rows):
                p.say(S_["ov_more"].format(n=len(rows), m=len(nums)))
        if streams:
            p.say(S_["ov_streams"].format(list=", ".join(n for n in names if n in streams)))
        if states_:
            p.say(S_["ov_states"].format(list=", ".join("%s (%d)" % (n, len(st.labels(f"{rid}/{n}") or {}) or
                                                                     len(np.unique(_sig(st, f"{rid}/{n}")[1][np.isfinite(_sig(st, f"{rid}/{n}")[1])])))
                                                         for n in states_[:20])))
        for n in nums[:o.get("plots", 4)]:
            shown.setdefault(n, []).append(f"{rid}/{n}")
    # the first signals plotted, one plot each - a signal several files have: every file's line in one plot
    if not o.get("table"):
        for n, ids in shown.items():
            p.plot(n, [sig_line(i, _label(st, i, rids), k) for k, i in enumerate(ids)])


# ------------------------------------------------------------------------------------------------ moments

def moments(p: Part, rids: List[str], arg: str, o: Dict):
    """The moments of each file worth a look, as one time line: the scenario's phases, every change of another
    state (a receiver LOST and back), leaving and returning to the ground, the highest and the farthest points, the
    largest tracking errors, and the recording's own flags (a stuck or saturated signal, a gap, a spike -
    svcore/overview.py, the overview strip's)."""
    st, S_ = p.store, p.S
    M, D = S_["mo"], S_["mo_det"]
    any_found = False
    for rid in rids:
        rows: List[Tuple[float, str, str, str]] = []           # (t, moment, detail, level)
        ov = st.overview(rid)
        ph = ov.get("phaseSignal")
        for s_ in (ov.get("phases") or [])[1:]:
            rows.append((s_["a"], M["phase"].format(s=s_["label"]), "", "info"))
        for sid in state_signals(st, [rid]):
            name = sid.split("/", 1)[1]
            if name == ph:
                continue
            t, y = _sig(st, sid)
            tl = rp.timeline(t, y, st.labels(sid))
            for a, b in list(zip(tl, tl[1:]))[:40]:
                rows.append((b["a"], M["state"].format(name=name, a=a["label"], b=b["label"]), "", "warn"))
        tr = _track_of(st, rid)
        if tr is not None and tr.get("alt") is not None:
            alt = np.asarray(tr["alt"], dtype=np.float64)
            t = tr["t"]
            ok = np.isfinite(alt)
            if ok.sum() > 10:
                base = float(alt[ok][0])
                up = (alt - base > 5.0) & ok
                runs = [(a, b) for a, b in rp._stretches(up) if t[min(b, len(t) - 1)] - t[a] >= 3.0]
                if runs:
                    a0, b0 = runs[0][0], runs[-1][1]
                    rows.append((float(t[a0]), M["takeoff"], D["takeoff"].format(v="5"), "info"))
                    if b0 < len(t):
                        rows.append((float(t[min(b0, len(t) - 1)]), M["landing"], "", "info"))
            f = rp.path_facts(t, tr["lat"], tr["lon"], tr["alt"])
            if "tHighest" in f:
                rows.append((f["tHighest"], M["highest"], D["highest"].format(v=fmt(f["highest"])), "info"))
            if "tFarthest" in f:
                rows.append((f["tFarthest"], M["farthest"], D["farthest"].format(v=dist(f["farthest"], p.lang)), "info"))
        ids = [f"{rid}/{n}" for n in st.get(rid).run.signals]
        errs = []
        for q in rp.setpoint_pairs(ids):
            tk = rp.tracking(_sig(st, q["setpoint"]), _sig(st, q["measured"]), q["measured"].split("/", 1)[1], None, st.is_state(q["setpoint"]))
            if tk.get("tmax") is not None:
                ts_, ys_ = _sig(st, q["setpoint"])
                errs.append((tk["score"], tk["tmax"], rp.bare(q["measured"].split("/", 1)[1]), tk["max"], rp.at(ts_, ys_, tk["tmax"])))
        for sc, tm, m, mx, c in sorted(errs, reverse=True)[:3]:
            rows.append((tm, M["error"].format(m=m), D["error"].format(v=fmt(mx), c=fmt(c)), "warn" if sc > 0.1 else "info"))
        for fl in ov.get("flags") or []:
            k = fl["kind"]
            dur = secs(fl["b"] - fl["a"])
            title = M[k].format(sig=fl.get("signal", ""), edge=S_["edge"].get(fl.get("edge", ""), ""))
            det = D[k].format(v=fmt(fl.get("value")), d=dur)
            rows.append((fl["a"], title, det, "warn"))
        if arg.strip():
            rows = [r for r in rows if arg.strip().lower() in (r[1] + " " + r[2]).lower()]
        if not rows:
            continue
        any_found = True
        rows.sort(key=lambda r: r[0])
        f_name = _name(st, rid)
        p.say(S_["mo_intro"].format(f=f_name, n=len(rows)))
        p.say(table(S_["mo_head"], [[secs(r[0]), r[1], r[2]] for r in rows[:o.get("top", 60)]]))
        for r in rows:
            if r[3] == "warn":
                p.hl("warn", 1.0, S_["mo_hl"].format(f=f_name, what=r[1], t=secs(r[0])))
    if not any_found:
        p.say("*%s*" % S_["mo_none"])


# ------------------------------------------------------------------------------------------------ differences

_COUNTER = re.compile(r"(^|[._ \[])(time|timestamp|timeus|time_us|timems|time_boot_ms|t|tow|gms|gwk|lineno|seq|counter|index|sample)($|[._ \]])", re.I)


_BASE_WORDS = re.compile(r"(^|[^a-z])(ref|reference|base|baseline|golden|gold|nominal|master|expected)([^a-z]|$)", re.I)


def guess_base(store, rids: Sequence[str]) -> str:
    """The baseline an engineer would take: the file whose name says so (ref, baseline, golden, nominal...), else
    the first opened."""
    return next((r for r in rids if _BASE_WORDS.search(os.path.splitext(store.get(r).name)[0])), rids[0])


def pick_base(store, rids: Sequence[str], want: str) -> str:
    if not want:
        return guess_base(store, rids)
    w = want.lower()
    hit = next((r for r in rids if store.get(r).name.lower() == w), None) or next((r for r in rids if w in store.get(r).name.lower()), None)
    if hit is None:
        raise PartError(S["en"]["no_base"].format(b=want, list=", ".join(store.get(r).name for r in rids)))
    return hit


def differences(p: Part, rids: List[str], arg: str, o: Dict):
    st, S_ = p.store, p.S
    if len(rids) < 2:
        p.say("*%s*" % S_["none_diff"])
        return
    base = pick_base(st, rids, o.get("base") or arg.strip())
    others = [r for r in rids if r != base]
    key = lambda n: rp.bare(n).strip().lower()           # the same signal whatever its unit's spelling (Compare's C13)
    bnames = {key(n): n for n in st.get(base).run.signals}
    onames = {r: {key(n): n for n in st.get(r).run.signals} for r in others}
    common = [k for k in bnames if all(k in onames[r] for r in others)]
    only = sorted({st.get(base).name + ": " + bnames[k] for k in bnames if k not in common}
                  | {st.get(r).name + ": " + n for r in others for k, n in onames[r].items() if k not in bnames})
    small, large = o.get("small", 0.02), o.get("large", 0.10)
    rows, skipped = [], 0
    for k in common:
        name = bnames[k]
        bid = f"{base}/{name}"
        if _COUNTER.search(name):
            skipped += 1
            continue
        tb, yb = _sig(st, bid)
        state = st.is_state(bid)
        blab = st.labels(bid)
        worst = None
        for r in others:
            oid = f"{r}/{onames[r][k]}"
            to, yo = _sig(st, oid)
            olab = st.labels(oid)
            if blab or olab:                             # text states: each file numbers its texts its own way
                yb, yo, common_lab = _same_codes(yb, blab or {}, yo, olab or {})
            d: Optional[Dict] = {"overall": 0.0, "peak": 0.0, "same": True}
            if not (len(tb) == len(to) and np.array_equal(tb, to) and np.allclose(yb, yo, equal_nan=True, rtol=0, atol=0)):
                d = rp.difference((tb, yb), (to, yo), name, state)
            if d is None:
                continue
            d.update({"name": name, "rid": r, "oid": oid, "bid": bid, "state": state})
            if blab or olab:
                d["labels"] = common_lab
            if worst is None or max(d["peak"], d["overall"]) > max(worst["peak"], worst["overall"]):
                worst = d
        if worst is not None:
            rows.append(worst)
    if not rows:
        p.say("*%s*" % S_["diff_same"])
        return
    lv = {"same": 0, "small": 0, "large": 0}
    for d in rows:
        d["level"] = "same" if d.get("same") else rp.level(d, small, large)
        lv[d["level"]] += 1
    rows.sort(key=lambda d: -max(d["peak"], d["overall"]))
    base_name = st.get(base).name
    others_name = ", ".join(st.get(r).name for r in others)
    p.say(S_["diff_intro"].format(others=others_name, base=base_name, n=len(rows), same=lv["same"], small=lv["small"], large=lv["large"]))
    notes = []
    if only:
        notes.append(S_["diff_only"].format(list=", ".join(only[:12]) + (" …" if len(only) > 12 else "")))
    if skipped:
        notes.append(S_["diff_skip"].format(n=skipped))
    if notes:
        p.say(" ".join(notes))
    differ = [d for d in rows if d["level"] != "same"]
    if not differ:
        p.say("*%s*" % S_["diff_same"])
        return
    # the top: one per family (IMU.AccX / AccY / AccZ is one row on top; all are in the table at the end)
    top, fams = [], set()
    for d in differ:
        fam = d["name"].rsplit(".", 1)[0] if "." in d["name"] else d["name"]
        if fam in fams:
            continue
        fams.add(fam)
        top.append(d)
        if len(top) >= o.get("top", 6):
            break
    reg = rp.region([d for d in top if d["level"] == "large"] or top)
    if reg:
        line = S_["diff_region"].format(a=secs(reg["a"]), b=secs(reg["b"]))
        if reg.get("first") is not None:
            line += S_["diff_first"].format(name=reg["firstName"], t=secs(reg["first"]))
            p.hl("warn", 5.0, S_["diff_hl_region"].format(a=secs(reg["a"]), b=secs(reg["b"]), name=reg["firstName"], t=secs(reg["first"])))
        p.say(line)
    p.say(S_["diff_how"])

    def row(d):
        return [d["name"], st.get(d["rid"]).name, pct(d["overall"]), pct(d["peak"]),
                "%s – %s" % (secs(d["region"][0]), secs(d["region"][1])) if d.get("region") else "—",
                secs(d.get("first")), "—" if d.get("shape") is None else "%.2f" % d["shape"]]
    p.say(table(S_["diff_head"], [row(d) for d in top]))
    for d in top:
        if d["level"] == "large":
            p.hl("warn", d["peak"], S_["diff_hl"].format(name=d["name"], base=base_name, a=secs(d["region"][0]), b=secs(d["region"][1]), p=pct(d["peak"])))
    if not o.get("table"):
        # where the files differ, over the whole time: each top signal's difference as % of how much it moves
        lines = []
        for j, d in enumerate(top):
            tb, yb = _sig(st, d["bid"])
            to, yo = _sig(st, d["oid"])
            if d.get("labels") is not None:              # text states on one numbering, as compared
                yb, yo, _ = _same_codes(yb, st.labels(d["bid"]) or {}, yo, st.labels(d["oid"]) or {})
            a, b = max(tb[0], to[0]), min(tb[-1], to[-1])
            m = (tb >= a) & (tb <= b)
            t = tb[m]
            y1 = rp.on_grid(to, yo, t, d["state"])
            per = rp.angle_period(d["name"], [yb, yo])
            dd = y1 - yb[m]
            if per:
                dd = (dd + per / 2) % per - per / 2
            lines.append(sig_line(p.series(d["name"], t, np.abs(dd) / d["span"] * 100.0), d["name"], j))
        p.plot(S_["diff_where"], lines, rng=None, caption=S_["diff_where_cap"])
        # each top signal zoomed on its own region (with a margin), every file's line
        for d in top:
            a, b = d["region"]
            w = max(b - a, 1.0)
            rng = [max(d["t0"], a - 0.5 * w), min(d["t1"], b + 0.5 * w)]
            ids = [d["bid"]] + [f"{r}/{onames[r][key(d['name'])]}" for r in others]
            p.plot(S_["diff_plot"].format(name=d["name"], a=secs(a), b=secs(b)),
                   [sig_line(i, _label(st, i, rids), k, state=d["state"]) for k, i in enumerate(ids)], rng=rng,
                   caption=S_["diff_cap"].format(others=others_name, base=base_name, o=pct(d["overall"]), p=pct(d["peak"])))
    # states whose sequence differs
    seqs = []
    for d in differ:
        if d.get("state") and d.get("sequences") and d["sequences"][0] != d["sequences"][1]:
            lab = d.get("labels") or st.labels(d["bid"]) or {}
            nm = lambda v: lab.get(int(v), fmt(v)) if float(v).is_integer() else fmt(v)
            seqs.append("- %s - %s: %s; %s: %s" % (d["name"], base_name, " → ".join(nm(v) for v in d["sequences"][0][:12]),
                                                   st.get(d["rid"]).name, " → ".join(nm(v) for v in d["sequences"][1][:12])))
    if seqs:
        p.say(S_["diff_states"] + "\n\n" + "\n".join(seqs[:8]))
    # parameters that differ (a log's parameters, the file's settings, numbers in its name) - often the cause
    try:
        from svcore.investigate import run_params
        pb = run_params(st.get(base).run)
        po = {r: run_params(st.get(r).run) for r in others}
        diffp = [k for k in sorted(pb) if any(k in po[r] and not _same(pb[k], po[r][k]) for r in others)]
        if diffp:
            p.say(S_["diff_params"].format(n=len(diffp)))
            p.say(table([S_["param"], base_name] + [st.get(r).name for r in others],
                        [[k, fmt(pb[k])] + [fmt(po[r].get(k)) for r in others] for k in diffp[:25]]))
    except Exception:                                    # parameters are a help, never a reason to fail the part
        pass
    rest = [d for d in differ if d not in top]
    if rest:
        p.say(S_["diff_rest"].format(n=len(rest)))
        p.say(table(S_["diff_head"], [row(d) for d in rest[:300]]))


def _same_codes(yb, lb: Dict[int, str], yo, lo: Dict[int, str]):
    """Two text-valued signals on one numbering: the base file's codes kept, the other's texts mapped onto them
    (a text only the other file has gets a new code)."""
    by_text = {v: k for k, v in lb.items()}
    common = dict(lb)
    nxt = max(list(lb) + [-1]) + 1
    remap = {}
    for code, text in lo.items():
        if text not in by_text:
            by_text[text] = nxt
            common[nxt] = text
            nxt += 1
        remap[code] = by_text[text]
    yo = np.asarray(yo, dtype=np.float64).copy()
    src = yo.copy()
    for code, new in remap.items():
        yo[src == code] = new
    return yb, yo, common


def _same(a, b) -> bool:
    try:
        return abs(float(a) - float(b)) <= 1e-9 * max(1.0, abs(float(a)))
    except (TypeError, ValueError):
        return a == b


# ------------------------------------------------------------------------------------------------ summary

# ------------------------------------------------------------------------------------------------ messages

_COLS = re.compile(r"^(.*?)(?:byte|b|data)[_\[]?(\d+)\]?$", re.I)
_DIR = re.compile(r"^(.*[._ ])?(dir|direction|rxtx|tx_rx|rx_tx|txrx|port|channel|src|source)$", re.I)


def hexb(v: int) -> str:
    return "0x%02X" % int(v)


def defined_streams(store, rids: Sequence[str], defs: Sequence[Dict]) -> List[Tuple[str, str, List[str], Dict]]:
    """The streams the user defined (ws.messageStreams, owner 2026-11-19): only TX, only RX, or both with a direction
    column (txValue = its code for TX; the other values are RX). (rid, name, ids, params) each."""
    out: List[Tuple[str, str, List[str], Dict]] = []
    for d in defs or []:
        src = [str(x) for x in d.get("sources") or []]
        if not src or any(x.split("/")[0] not in rids or not _has(store, x) for x in src):
            continue
        rid = src[0].split("/")[0]
        name = src[0].split("/", 1)[1] if len(src) == 1 else "%s…%s" % (src[0].split("/", 1)[1], src[-1].split("/", 1)[1])
        prm = {k: d[k] for k in ("header", "checksum") if d.get(k)}
        carries = d.get("carries") or "tx"
        dir_ = d.get("dir")
        if carries == "pair" and len(src) == 2:         # two signals: the first TX, the second RX
            out.append((rid, "%s TX" % src[0].split("/", 1)[1], src[:1], prm))
            out.append((rid, "%s RX" % src[1].split("/", 1)[1], src[1:], prm))
        elif carries == "both" and dir_ and _has(store, dir_) and len(src) == 1:
            from svcore import bytestream as bs
            vals = bs.directions(_sig(store, dir_)[1])
            tx = d.get("txValue")
            tx = float(tx) if tx is not None else (vals[0] if vals else 0.0)
            out.append((rid, "%s TX" % name, src + [dir_], {**prm, "dir": tx}))
            for v in vals:
                if abs(v - tx) > 1e-9:
                    out.append((rid, "%s RX" % name if len(vals) == 2 else "%s RX %g" % (name, v), src + [dir_], {**prm, "dir": v}))
        else:
            out.append((rid, "%s %s" % (name, "RX" if carries == "rx" else "TX"), src, prm))
    return out


def _has(store, sid: str) -> bool:
    try:
        store.signal(sid)
        return True
    except KeyError:
        return False


def find_streams(store, rids: Sequence[str], defs: Optional[Sequence[Dict]] = None) -> List[Dict]:
    """The byte streams of these files, decoded: the ones the user defined (TX / RX / both with a direction column),
    and in the other signals the ones found by themselves - a byte-by-byte signal (split by a direction column beside
    it), or columns byte_0..byte_N (one message per row). Each: name, rid, ids, params, the decode."""
    from svcore import bytestream as bs
    out: List[Dict] = []
    mine = defined_streams(store, rids, defs or [])
    taken = {i for _r, _n, ids, _p in mine for i in ids}
    for rid, name, ids, prm in mine:
        try:
            out.append({"name": name, "rid": rid, "ids": ids, "params": prm, "r": bs.decode([_sig(store, i) for i in ids], prm)})
        except bs.StreamError as e:
            out.append({"name": name, "rid": rid, "ids": ids, "params": prm, "error": str(e)})
    for rid in rids:
        run = store.get(rid).run
        names = list(run.signals)
        dirs = [n for n in names if _DIR.match(n)]
        groups: Dict[str, List[Tuple[int, str]]] = {}
        for n in names:
            m = _COLS.match(n)
            if m:
                groups.setdefault(m.group(1), []).append((int(m.group(2)), n))
        in_cols: set = set()
        tried: List[Tuple[str, List[str], Dict]] = []
        for pre, cols in groups.items():
            if len(cols) >= 4 and not any(f"{rid}/{n}" in taken for _i, n in cols):
                cols.sort()
                in_cols.update(n for _i, n in cols)
                tried.append(("%s%s…%s" % (pre, cols[0][1][len(pre):], cols[-1][1][len(pre):]), [f"{rid}/{n}" for _i, n in cols], {}))
        for n in names:
            sid = f"{rid}/{n}"
            if n in in_cols or n in dirs or sid in taken or store.is_state(sid):
                continue
            if not bs.is_byte_like(_sig(store, sid)[1]):
                continue
            split = False
            for dn in dirs:
                yd = _sig(store, f"{rid}/{dn}")[1]
                vals = bs.directions(yd)
                if vals:
                    lab = store.labels(f"{rid}/{dn}") or {}
                    for v in vals:
                        tried.append(("%s %s" % (n, lab.get(int(v), lab.get(str(int(v)), "%s=%g" % (dn, v)))), [sid, f"{rid}/{dn}"], {"dir": v}))
                    split = True
                    break
            if not split:
                tried.append((n, [sid], {}))
        for name, ids, prm in tried:
            try:
                r = bs.decode([_sig(store, i) for i in ids], prm)
            except bs.StreamError:
                continue
            out.append({"name": name, "rid": rid, "ids": ids, "params": prm, "r": r})
    return out


def messages(p: Part, rids: List[str], arg: str, o: Dict, defs: Optional[Sequence[Dict]] = None):
    """MSG1: each byte stream's messages - the framing found, a table per type, the order, the gaps; one plot per
    quantity (messages per second by type, the interval by type, the checksum errors) with every stream's lines."""
    from svcore import bytestream as bs
    st, S_ = p.store, p.S
    force = {k: o[k] for k in ("header", "length", "type", "checksum") if k in o}
    streams = find_streams(st, rids, defs)
    for s_ in [x for x in streams if x.get("error")]:
        p.say("⚠ **%s**: %s" % (s_["name"], s_["error"]))
    streams = [x for x in streams if not x.get("error")]
    if force:                                            # forced framing: decode the byte-like signals again with it
        again = []
        for s_ in streams:
            try:
                again.append({**s_, "r": bs.decode([_sig(st, i) for i in s_["ids"]], {**s_["params"], **force})})
            except bs.StreamError as e:
                raise PartError("%s: %s" % (s_["name"], e))
        streams = again
    flt = arg.strip().lower()
    if flt:
        streams = [s_ for s_ in streams if flt in s_["name"].lower()]
    if not streams:
        p.say("*%s*" % S_["none_msg"])
        return
    rate_lines: List[dict] = []
    int_lines: List[dict] = []
    err_lines: List[dict] = []
    seq_lines: List[Tuple[dict, float, float]] = []
    k = 0
    for s_ in streams:
        r, name = s_["r"], s_["name"]
        file = " (%s)" % _name(st, s_["rid"]) if len(rids) > 1 else ""
        cs = r["checksum"]
        cst = S_["msg_cs"].format(s=cs["scheme"], e=r["errors"]) if cs else S_["msg_nocs"]
        lost = S_["msg_lost"].format(r=r["resyncs"], o=r["outside"]) if r["resyncs"] or r["outside"] else ""
        p.say(S_["msg_intro"].format(name=name, file=file, n=r["count"], d=secs(r["duration"]), bytes=r["bytes"], h=r["header"], cs=cst) + lost)
        p.say(S_["msg_struct"])
        p.say(table(S_["msg_struct_head"], structure(r, S_)))
        rows = [[hexb(x["type"]) if r["typeOffset"] is not None else "—", str(x["count"]), pct(x["share"]),
                 ", ".join(str(v) for v in x["lengths"]), fmt(x["rate"]), secs(x["period"]),
                 "—" if x["jitter"] is None else "0" if x["jitter"] < 1e-9 else "%.3g" % (x["jitter"] * 1000), secs(x["maxInterval"]), secs(x["first"]), secs(x["last"]),
                 str(x["errors"]) if cs else "—"] for x in r["types"]]
        p.say(table(S_["msg_head"], rows))
        od = r["order"]
        if od["period"]:
            seq = " ".join(hexb(v) for v in od["sequence"][:24]) + (" …" if len(od["sequence"]) > 24 else "")
            p.say(S_["msg_order"].format(p=od["period"], seq=seq, f=pct(od["fit"])))
        elif od["transitions"]:
            p.say(S_["msg_trans"].format(list=", ".join("%s → %s (%d)" % (hexb(x["from"]), hexb(x["to"]), x["count"]) for x in od["transitions"][:6])))
        if r["typeOffset"] is not None and r["count"] > 1:
            ty = r["messages"]["type"]
            k_ = min(40, len(ty))
            p.say(S_["msg_seq"].format(n=k_, t=secs(float(r["messages"]["t"][0])), list=" ".join(hexb(v) for v in ty[:k_])))
        if r["gaps"]:
            p.say(S_["msg_gaps"].format(list=", ".join(S_["msg_gap"].format(dt=secs(g["dt"]), a=secs(g["from"])) for g in r["gaps"])))
        label = name + file
        if r["errors"]:
            p.hl("warn", 5 + r["errors"], S_["msg_hl_err"].format(name=label, e=r["errors"], n=r["count"]))
        for g in r["gaps"][:2]:
            p.hl("warn", 3 + g["dt"], S_["msg_hl_gap"].format(name=label, dt=secs(g["dt"]), a=secs(g["from"])))
        if r["resyncs"]:
            p.hl("info", 1 + r["resyncs"], S_["msg_hl_resync"].format(name=label, r=r["resyncs"]))
        p.hl("info", 0.5, S_["msg_hl"].format(name=label, n=r["count"], k=len(r["types"]), h=r["header"]))
        m = r["messages"]
        t = np.asarray(m["t"], dtype=np.float64)
        if len(t) < 2:
            continue
        edges = np.arange(math.floor(t[0]), math.ceil(t[-1]) + 1.0, 1.0)
        if len(edges) < 2:
            edges = np.array([t[0], t[0] + 1.0])
        for x in r["types"][:8]:
            sel = m["type"] == x["type"] if r["typeOffset"] is not None else np.ones(len(t), dtype=bool)
            tt = t[sel]
            lab = "%s %s" % (name, hexb(x["type"])) if r["typeOffset"] is not None else name
            cnt, _e = np.histogram(tt, edges)
            rate_lines.append(sig_line(p.series(lab, edges[:-1] + 0.5, cnt.astype(np.float64)), lab, k))
            if len(tt) > 1:
                int_lines.append(sig_line(p.series(lab + " Δt", tt[1:], np.diff(tt)), lab, k))
            k += 1
        if r["typeOffset"] is not None:
            span = min(2.0, float(t[-1] - t[0]))
            seq_lines.append((sig_line(p.series(name + " type", t, m["type"].astype(np.float64)), name, len(seq_lines), state=True), t[0], span))
        if cs and r["errors"]:
            err_lines.append(sig_line(p.series(name + " errors", t, np.cumsum(~m["ok"]).astype(np.float64)), name, len(err_lines)))
    lat_lines = links(p, streams, rids)
    if o.get("table"):
        return
    if lat_lines:
        p.plot(S_["msg_lat"], lat_lines, caption=S_["msg_lat_cap"])
    if seq_lines:
        t0 = min(x[1] for x in seq_lines)
        span = max(x[2] for x in seq_lines)
        p.plot(S_["msg_seq_plot"].format(s="%g" % span), [x[0] for x in seq_lines], rng=[float(t0), float(t0 + span)], caption=S_["msg_seq_cap"])
    if rate_lines:
        p.plot(S_["msg_rate"], rate_lines, caption=S_["msg_rate_cap"])
    if int_lines:
        p.plot(S_["msg_int"], int_lines, caption=S_["msg_int_cap"])
    if err_lines:
        p.plot(S_["msg_err"], err_lines)


def _times(ts: Sequence[float], n: int = 12) -> str:
    return ", ".join(secs(x) for x in list(ts)[:n]) + (" …" if len(ts) > n else "")


def links(p: Part, streams: List[Dict], rids: Sequence[str]) -> List[dict]:
    """Both directions of a link (two streams of one file: TX and RX, or one signal split by its direction): which
    message answers which, the latency, what went unanswered or was sent again, the handshake and reconnects."""
    from svcore import bytestream as bs
    S_ = p.S
    lines: List[dict] = []
    by: Dict[str, List[Dict]] = {}
    for s_ in streams:
        by.setdefault(s_["rid"], []).append(s_)
    for rid, ss in by.items():
        if len(ss) != 2:
            continue
        # the side that sends (TX) first
        ss = sorted(ss, key=lambda x: (0 if re.search(r"tx|send|out|up", x["name"], re.I) else 1, x["name"]))
        a, b = ss[0]["name"], ss[1]["name"]
        e = bs.exchange(ss[0]["r"], ss[1]["r"], (a, b))
        hs = e["handshake"]
        if hs:
            seq = lambda h: " → ".join("%s %s" % (x["dir"], hexb(x["type"])) for x in h["steps"])
            p.say(S_["msg_hs"].format(t=secs(hs[0]["t"]), seq=seq(hs[0])))
            for h in hs[1:]:
                p.say(S_["msg_hs_again"].format(t=secs(h["t"]), seq=seq(h)))
                p.hl("warn", 4, S_["msg_hl_reconnect"].format(a=a, b=b, t=secs(h["t"])))
        if not e["pairs"]:
            p.say(S_["msg_link_none"].format(a=a, b=b))
            continue
        p.say(S_["msg_link"].format(a=a, b=b, to=secs(e["timeout"])))
        rows = []
        for q in e["pairs"]:
            lt = q["latency"] or {}
            ms = lambda v: "—" if v is None else "%.3g" % (v * 1000)
            rows.append(["%s %s" % (q["from"], hexb(q["request"])), "%s %s" % (q["to"], hexb(q["reply"])),
                         S_["msg_by_id"].format(j=q["echo"]["request"]) if q["echo"] else S_["msg_by_next"],
                         str(q["requests"]), str(q["replies"]), str(len(q["unanswered"])), str(len(q["retries"])),
                         ms(lt.get("mean")), ms(lt.get("p95")), ms(lt.get("max")), secs(lt.get("tmax")), str(len(q["orphans"]))])
        p.say(table(S_["msg_link_head"], rows))
        for k, q in enumerate(e["pairs"]):
            req = hexb(q["request"])
            if q["unanswered"]:
                p.say(S_["msg_unans"].format(req=req, n=len(q["unanswered"]), list=_times(q["unanswered"])))
                p.hl("warn", 4 + len(q["unanswered"]), S_["msg_hl_unans"].format(a=a, b=b, n=len(q["unanswered"]), m=q["requests"] - len(q["retries"]), req=req))
            if q["retries"]:
                p.say(S_["msg_retry"].format(req=req, list=_times(q["retries"])))
                p.hl("info", 2 + len(q["retries"]), S_["msg_hl_retry"].format(a=a, b=b, req=req, n=len(q["retries"])))
            lt = q["latency"]
            if lt and q["replies"] >= 5:
                p.hl("info", 1, S_["msg_hl_lat"].format(a=a, b=b, req=req, mean="%.3g" % (lt["mean"] * 1000), max="%.3g" % (lt["max"] * 1000), t=secs(lt["tmax"])))
                lab = "%s → %s" % (req, hexb(q["reply"]))
                if len(rids) > 1:
                    lab = "%s: %s" % (_name(p.store, rid), lab)
                lines.append(sig_line(p.series(lab + " latency", q["t"], q["lat"]), lab, len(lines)))
    return lines


def structure(r: Dict, S_: Dict[str, Any]) -> List[List[str]]:
    """The packet's parts: the fixed header, the length / type bytes, the payload (per type), the checksum."""
    from svcore.bytestream import SCHEMES_1
    F, W = S_["msg_f"], S_["msg_w"]
    rule, toff, cs = r["rule"], r["typeOffset"], r["checksum"]
    k = (1 if cs["scheme"] in SCHEMES_1 else 2) if cs else 0
    rows = [[F["header"], "0–1", W["header"].format(h=r["header"])]]
    fields = []
    if rule["how"] == "length":
        fields.append((rule["off"], [F["length"], str(rule["off"]), W["length"].format(a=rule["add"])]))
    if toff is not None:
        kinds = ", ".join(hexb(x["type"]) for x in sorted(r["types"], key=lambda x: x["type"]))
        fields.append((toff, [F["type"], str(toff), W["type_len" if rule["how"] == "type" else "type"].format(n=len(r["types"]), list=kinds)]))
    fields.sort()
    rows += [f for _o, f in fields]
    start = max([1] + [o for o, _f in fields]) + 1
    lens = sorted({L for x in r["types"] for L in x["lengths"]})
    if len(lens) == 1:
        rows.append([F["payload"], "%d–%d" % (start, lens[0] - k - 1), W["payload_fixed"].format(n=lens[0] - k - start)])
    else:
        per = ", ".join(S_["msg_per"].format(t=hexb(x["type"]) if toff is not None else "?", n=x["lengths"][0] - k - start)
                        for x in sorted(r["types"], key=lambda x: x["type"]))
        rows.append([F["payload"], "%d…" % start, W["payload"].format(list=per)])
    if cs:
        a = 2 if cs["over"].startswith("without") else 0
        rows.append([F["checksum"], S_["msg_last"][k - 1], W["checksum"].format(s=cs["scheme"], a=a)])
    else:
        rows.append([F["checksum"], "—", W["none"]])
    if rule["how"] == "fixed":
        rows.append(["", "", W["fixed"].format(n=rule["len"])])
    return rows


def byte_streams(store, rid: str, defs: Optional[Sequence[Dict]] = None) -> List[str]:
    """The names of a file's signals that are byte streams (the overview leaves their statistics out)."""
    out: List[str] = []
    for s_ in find_streams(store, [rid], defs):
        out += [i.split("/", 1)[1] for i in s_["ids"]]
    return out



def summary(p: Part, highlights: List[Dict], o: Dict):
    S_ = p.S
    if not highlights:
        p.say("*%s*" % S_["sum_none"])
        return
    order = {"fail": 0, "warn": 1, "info": 2}
    hs = sorted(highlights, key=lambda h: (order.get(h["level"], 3), -h["score"]))[:o.get("top", 7)]
    mark = {"fail": "✖", "warn": "⚠", "info": "•"}
    p.say(S_["sum_intro"])
    p.say("\n".join("- %s %s" % (mark.get(h["level"], "•"), h["text"]) for h in hs))


RUN = {"overview": overview, "moments": moments, "messages": messages, "tracking": tracking, "navigation": navigation, "states": states, "trajectory": trajectory, "differences": differences}


def expand_all(store, text: str, items: List[dict], lang: str) -> Tuple[str, Dict[str, Tuple[np.ndarray, np.ndarray]]]:
    """Every part item of the document -> its Markdown in place of its marker (the summary last, from the others'
    highlights). Returns the new text and the inline series the parts' plots draw."""
    extra: Dict[str, Tuple[np.ndarray, np.ndarray]] = {}
    highlights: List[Dict] = []
    later: List[int] = []
    out = text
    for k, it in enumerate(list(items)):
        if it.get("kind") != "part":
            continue
        if it.get("part") in ("summary", "toc"):
            later.append(k)
            continue
        out = out.replace("\u27e6%d\u27e7" % k, _one(store, k, it, items, extra, lang, highlights))
    for k in later:
        if items[k].get("part") == "toc":
            continue
        out = out.replace("\u27e6%d\u27e7" % k, _one(store, k, items[k], items, extra, lang, highlights))
    for k in later:                                      # the table of contents last: the parts' headings are in
        if items[k].get("part") == "toc":
            out = out.replace("\u27e6%d\u27e7" % k, toc_markdown(out, S.get(lang, S["en"])))
            items[k] = {"kind": "done"}
    return out, extra


def heading_id(text: str) -> str:
    """The anchor of a heading in the page (app/reportdoc.py gives each h2 / h3 this id; [[toc]] links to it)."""
    return "h-" + (re.sub(r"[^\w\u0590-\u05FF]+", "-", text.strip().lower()).strip("-") or "x")


def toc_markdown(text: str, S_: Dict[str, Any]) -> str:
    """[[toc]]: the document's headings (## and ###, after the title) as a list of links - the page's links jump."""
    from app.reportdoc import parse, MARK
    lines = []
    for b in parse(text):
        if b["t"] == "heading" and b["level"] in (2, 3):
            t = MARK.sub("", b["text"]).strip()
            if t:
                lines.append("%s- [%s](#%s)" % ("  " * (b["level"] - 2), t.replace("[", "(").replace("]", ")"), heading_id(t)))
    if not lines:
        return "\n\n*%s*\n\n" % S_["toc_none"]
    return "\n\n**%s**\n\n%s\n\n" % (S_["toc"], "\n".join(lines))


def _one(store, k: int, it: dict, items: List[dict], extra, lang: str, highlights: List[Dict]) -> str:
    part = str(it.get("part") or "")
    p = Part(store, items, extra, lang)
    p.base = str(it.get("mapBase") or "")
    try:
        o = options(part, it.get("opts") or [])
        rids = _runs(store, it.get("runs"))
        if part == "summary":
            summary(p, highlights, o)
        elif part == "messages":
            messages(p, rids, str(it.get("arg") or ""), o, it.get("streams"))
        else:
            RUN[part](p, rids, str(it.get("arg") or ""), o)
    except PartError as e:
        msg = str(e)
        if " " not in msg.strip():                       # an option word
            msg = p.S["bad_opt"].format(part=part, o=msg, known=KNOWN.get(part, ""))
        items[k] = {"kind": "error", "error": msg}
        return "\u27e6%d\u27e7" % k
    except KeyError as e:                                 # a file closed meanwhile
        items[k] = {"kind": "error", "error": "%s: %s" % (part, e)}
        return "\u27e6%d\u27e7" % k
    highlights += p.highlights
    items[k] = {"kind": "done"}
    return "\n\n" + "\n\n".join(p.md) + "\n\n"


class WithExtra:
    """The Store, plus the parts' inline series ("auto/<n>/<label>") for plot_data - nothing added to the Store."""

    def __init__(self, store, extra: Dict[str, Tuple[np.ndarray, np.ndarray]]):
        self._s, self._x = store, extra

    def signal(self, sid: str):
        if sid in self._x:
            return self._x[sid]
        return self._s.signal(sid)

    def labels(self, sid: str):
        return None if sid in self._x else self._s.labels(sid)

    def __getattr__(self, name):
        return getattr(self._s, name)


# ------------------------------------------------------------------------------------------------ the library

def scan(store, rids: Optional[Sequence[str]] = None, defs: Optional[Sequence[Dict]] = None) -> Dict:
    """What the parts would find - for the Report screen's library: the files, the pairs, the objects with the
    guessed reference, the state signals, the tracks."""
    rids = _runs(store, rids)
    ids = [f"{rid}/{n}" for rid in rids for n in store.get(rid).run.signals]
    pairs = rp.setpoint_pairs(ids)
    objs = detect_objects(store, rids) if rids else []
    ref = guess_reference(objs)
    return {"files": [{"id": r, "name": store.get(r).name} for r in rids],
            "pairs": [{"setpoint": q["setpoint"].split("/", 1)[1], "measured": q["measured"].split("/", 1)[1],
                       "file": store.get(q["measured"].split("/")[0]).name} for q in pairs],
            "objects": [{"name": c["name"], "cls": c["cls"], "pos": c["pos"]} for c in objs],
            "reference": ref["name"] if ref else None,
            "base": store.get(guess_base(store, rids)).name if rids else None,
            "states": [{"name": s.split("/", 1)[1], "file": store.get(s.split("/")[0]).name} for s in state_signals(store, rids)],
            "tracks": sum(1 for c in objs if c.get("pos") == "lla"),
            "streams": [{"name": s_["name"], "file": store.get(s_["rid"]).name, "count": s_["r"]["count"]} for s_ in find_streams(store, rids, defs) if not s_.get("error")]}
