---
name: sv-patch
description: Hand Signal Viewer work over as ONE patch file when the session cannot push - every commit since GitHub's main, authored as the owner (David Alpert <davidalpert11@gmail.com>), rebased on the latest origin/main, checked with git am on a fresh clone. Use at the end of any task in a session without push access.
---

# One patch for the owner

The owner (2026-10-19, again 2026-11-21): ONE file with ALL the commits since GitHub's main, made against the latest
main, never depending on an earlier patch. The commits carry his identity - he commits them.

## 1. The commits

```bash
git config user.name "David Alpert"
git config user.email davidalpert11@gmail.com
# commits made before the identity was set: re-author them (the messages stay)
git rebase origin/main --exec 'git commit --amend --no-edit --reset-author'
```
Small commits, one task (or one coherent part) each - `sv-flow` §3 (CHANGELOG, ROADMAP, TASKS in the same commit).

## 2. On the latest main

```bash
git fetch origin
git rebase origin/main            # conflicts: resolve, keep both sides' intent, re-run the fast checks
git log --oneline origin/main..HEAD
```

## 3. The file

```bash
git format-patch --stdout origin/main..HEAD > /tmp/signalviewer-<topic>-$(date +%Y%m%d).patch
```

## 4. Check it applies alone, on a fresh clone

```bash
rm -rf /tmp/am && git clone -q https://github.com/DavidAlpert11/SignalViewer /tmp/am && cd /tmp/am
git am /tmp/signalviewer-<topic>-*.patch && git log --format='%an <%ae> %s' origin/main..HEAD
```
Every line must show `David Alpert <davidalpert11@gmail.com>`. A binary file (picture, .npz) must survive
(`format-patch` writes binary diffs - check the file opens). Then, if time allows, the fast checks on the clone.

## 5. Send

Send the file (SendUserFile) with, in Hebrew, what is in it (one line per commit) and how to apply:

```bash
git checkout main && git pull
git am <file>.patch
git push origin main
```
If `git am` stops: `git am --abort`, then `git pull` - the patch is made again against the new main (never by hand).
