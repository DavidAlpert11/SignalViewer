"""B9: MkDocs hooks for the documentation site (mkdocs.yml -> hooks).

The Hebrew user guide (docs/GUIDE.he.md) is written right to left. The same file is shown inside the
app (Help -> User guide, F1) by the app's own renderer, so it stays plain Markdown; the site gets its
direction here instead: the page's content is wrapped in dir="rtl" lang="he" (code, paths and
shortcuts inside it stay left to right - stylesheets/extra.css)."""

RTL_PAGES = {"GUIDE.he.md"}


def on_page_content(html, page, config, files):
    if page.file.src_uri in RTL_PAGES:
        return f'<div class="sv-rtl" dir="rtl" lang="he">{html}</div>'
    return html
