---
name: sv-media
description: Make Signal Viewer's pictures and films for the README, the docs and the welcome cards from the app itself (tools/make_readme_media.py and friends) - which scene makes what, what needs the internet, how to add a scene. Use when the interface changed before a release, or to show the owner a result.
---

# Pictures and films

All pictures come from the real app (CLAUDE.md "How to work here").

```bash
python tools/make_readme_media.py --only 48 49        # scenes whose number / name starts with these
python tools/make_readme_media.py --only examples     # the welcome cards' pictures
```

- Each scene is a function `img_<NN>_<name>(b, app)` in `tools/make_readme_media.py`; scenes are found by that name.
  It starts with `ctx, pg = page(b, app)` (a clean app, dark theme), opens files with `open_api(pg, app, "<file
  under examples/>")`, waits for the END state (`pg.wait_for_function(...)` on `window.__sv.state()`), then
  `shot(pg, "<NN>_<name>")` -> `docs/images/<NN>_<name>.png`. Reports: `_report_parts`, `_preview_to(pg, text)`.
- `57_report_latex` needs a LaTeX installed and a Chromium with its PDF view (`SV_CHROMIUM=/opt/pw-browsers/chromium`;
  the default headless shell draws no PDF). Map / satellite scenes (05 28 31 44 46) need the internet; films need ffmpeg; `06_3d_terrain.png` is not made here.
- Long films: `tools/make_demo_video.py`, `tools/make_training_video.py`; after scene 31: `tools/make_social_preview.py`.
- The training film is **narrated** (`tools/narration.py`): `pip install piper-tts`; the voice (en_US-lessac-medium) is
  fetched once into `~/.cache/signalviewer/voices` (or `SV_VOICE=<.onnx>`); `--silent` for none. A chapter's words are
  `f.say(...)` / `f.cap(..., say=...)` - the next step waits until the line is said. In a cloud sandbox Playwright's
  video needs `ln -sf /usr/bin/ffmpeg /opt/pw-browsers/ffmpeg-1013/ffmpeg-linux` (its own ffmpeg is not installed).
  Examples without a welcome card open through Help -> Examples (`help_example`: sideways into the submenu, then down).
- Look at every picture you made (Read it) before committing; show the owner with the file-sending tool.
- A picture used in the README or docs is referenced as `docs/images/…` / `images/…`; `mkdocs build --strict` checks.
