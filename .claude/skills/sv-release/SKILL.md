---
name: sv-release
description: Prepare a Signal Viewer release (the owner tags) - the version in five files, CHANGELOG with highlights, the README / docs review against the CHANGELOG, the validation page, pictures, the whole e2e suite, ci, and the commands the owner runs to tag and to delete old branches. Use when the owner asks for a release or a new version.
---

# Preparing a release

The owner tags; an agent prepares. Never change the version unless the owner asks for a release. Rules: `/CLAUDE.md`
"Releasing". Steps:

1. **Checks** - the whole e2e suite one file at a time (skill `sv-checks` §4) and `tools/quick_check.py`, green.
2. **The version** (X.Y.Z) in: `build.bat` (`set VERSION=`), `backend/app/version.py`, `CITATION.cff` (`version`,
   `date-released`), `installer/SignalViewer.iss` (`AppVersion`), `installer/version_info.txt` (four places: the two
   tuples `(X, Y, Z, 0)` and two strings), `docs/install.md` (the installer's file name).
   `grep -rn "<old version>" build.bat backend/app/version.py CITATION.cff installer docs/install.md` must find nothing.
3. **CHANGELOG.md** - rename `## Next – unreleased` to `## X.Y.Z – <date>` (keep an empty `## Next – unreleased`
   above), a `**Highlights:**` line, user-facing wording.
4. **README review (the owner's rule, every release)** - each CHANGELOG item against: README (why / tour / send the
   answer / formats / the Hebrew section - short, in line with the English, no `~` outside code), `docs/features.md`,
   `docs/limitations.md` (remove what was fixed, add what is new), `docs/install.md`, `docs/command-line.md`, and
   the user page of the feature.
5. **The validation page** - `python tools/make_validation_doc.py` (a test checks the page names this version).
6. **Pictures** when the interface changed - skill `sv-media`.
7. **TASKS.md / ROADMAP.md** - the release row, the log line (which e2e ran), tasks ticked.
8. **Commit** small ("Release X.Y.Z prepared: …"), the last message with `[ci]` so ci runs on the push; push to main
   only when the owner says so (CLAUDE.md "Publishing").
9. **Give the owner the commands** (a cloud session cannot tag a release or delete remote branches for him):

```bash
git checkout main && git pull origin main
git tag vX.Y.Z && git push origin vX.Y.Z           # the build workflow makes every package; then publish the Release on GitHub
git push origin --delete <each old branch>          # first check: git rev-list --count origin/main..origin/<branch> is 0
```

If the tag's build fails (Windows / macOS only, typically), fix on main and tell the owner to move the tag.
