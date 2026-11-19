---
name: sv-example
description: Add an example dataset to Signal Viewer - a deterministic generator in svcore/example_data, its files in examples/, the entry in Help -> Examples or the welcome screen, labels, tests. Use when a feature needs demo data the user can open from the app.
---

# A new example

The packages carry no heavy recordings: the app writes an example's files on first use from a generator
(`backend/svcore/example_data/__init__.py`); the repository keeps the files.

1. **Generator** - `backend/svcore/example_data/make_<name>.py` with `main(folder)`: deterministic (a fixed seed,
   fixed number formats - CSV byte for byte), generic names unless the example is about one format. A thin wrapper
   `tools/make_<name>.py`. Register the files in `GENERATORS` (`example_data/__init__.py`). Run it, commit the files.
2. **In the app** - `EXAMPLE_SETS` in `backend/app/routes/fs.py` (`id`, `files`, optional `open`: `study` / `sweep` /
   `summary` / `report`); the id in `ExampleId` (`frontend/src/api.ts`); `EXAMPLE_LABEL`, `EXAMPLE_DESC`,
   `EXAMPLE_ICON` (`components/Welcome.tsx`) and a new `open` kind in `openPrepared`; labels `example<Name>`,
   `example<Name>Desc` in `i18n/templates.ts` (en + he). A welcome card only if the owner wants it (`FEATURED`, six).
3. **Tests** - `backend/tests/test_backend.py::test_examples_listed_with_existing_files_only` (the list, in order),
   `test_example_data` (the generator writes what git has), e2e `test_welcome_cards` (the Help count).
4. **Docs** - the feature's page says how to open it; CHANGELOG.
