---
name: sv-messages
description: Work on Signal Viewer's messages - byte streams (TX / RX / both with a direction column), the framing found by itself, structures (binary and NMEA-like text), the guided Messages panel from raw bytes to a recording, live links, the [[messages]] report part. A map of the files, the data flow and the tests. Use for any change to messages, structures or links.
---

# Messages: from bytes to a recording

User docs: `docs/messages.md`. Decisions: `docs/dev/TASKS.md` (MSG1, MSG2, MSG3, MSG4, LINK1).

## The flow (what the user does, in the Messages panel - 4 steps)

1. **What the signal carries** - only TX, only RX, both with a direction column (which value is TX), or two signals
   (TX and RX). `ws.messageStreams[]` (`MessageStream`, `store/model.ts`) keeps it; `messages.ts streamsOf` turns it
   into one stream per direction (`params.dir` = the direction column's value).
2. **The messages in the bytes** - `POST /api/messages/inspect` (`svcore/msginspect.py`): the recurring byte
   patterns (header / footer candidates), the structure proposed (`protocol.suggest`) or the user's, and the first
   frames as hex with each byte's role (header, length, type, field, checksum, footer). A click on a byte sets its
   role (`components/ByteView.tsx`).
3. **The variables** - `components/StructureEditor.tsx` (form or JSON) with the first frames' decoded values beside
   each field (the same inspect call, `values`).
4. **The recording** - `POST /api/messages/parse` -> a pushed run `python:messages/<name>` (`protocol.to_run`),
   re-made when a session opens (`remakeRecordings`); Save as CSV / Parquet / MAT / HDF5 (`/api/export/recording`),
   Plot the messages (derived op `messages`), Add to the report (`[[messages <signal>]]`).

## The code

| Piece | Where |
|---|---|
| framing found by itself (2-byte header, length / type / fixed, checksum schemes), per-type numbers, request / reply | `backend/svcore/bytestream.py` |
| structures: check, parse binary (`frames_binary`) and text, suggest, NMEA, ICD layouts | `backend/svcore/protocol.py` |
| the guided view: patterns, frames with roles, values | `backend/svcore/msginspect.py` |
| routes: suggest, parse, inspect, library, streams | `backend/app/routes/messages.py` |
| live links (serial / UDP / TCP) -> `.svraw` | `backend/svcore/rawlink.py`, `app/routes/live.py` |
| report part | `backend/app/reportparts.py` (`messages`), `find_streams` |
| panel, steps, byte view, structure form | `frontend/src/components/MessagesPanel.tsx`, `StreamEditor.tsx`, `ByteView.tsx`, `StructureEditor.tsx` |
| actions (decode, make the recording, report, library) | `frontend/src/messages.ts` |
| strings | `frontend/src/i18n/live.ts` (msg*, msgp*, msgStep*) |
| examples | `examples/report_demo` (serial link), `examples/serial_link`, `backend/svcore/example_data/make_serial_link.py` |

## Tests

`backend/tests/test_bytestream.py`, `test_protocol.py`, `test_msginspect.py`, `test_messages_library.py`,
`test_rawlink.py`; e2e `tests/e2e/test_messages.py` (the panel, the steps, make the recording). Every message
counts: a frame with a bad checksum is left out **and counted**, never sampled (CLAUDE.md).
