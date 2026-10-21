<!-- Thank you! The checks below are also in CONTRIBUTING.md; CI runs most of them on this pull request. -->

**What and why**

**How it was checked**

- [ ] `cd backend && python -m pytest -q` and `mypy --config-file ../pyproject.toml app svcore signalviewer`
- [ ] `cd frontend && npx tsc -b && npm run build` (UI changes; no need to commit `frontend/dist`)
- [ ] A test for the changed behaviour (backend `backend/tests`, UI flows `tests/e2e`)
- [ ] New text in the UI in English and Hebrew (`frontend/src/i18n.ts`), and checked right to left
- [ ] A line in `CHANGELOG.md` for what users will notice
