"""Owner (2026-11-13): the report opens with the process in brief - the app's section of kind "process" comes
first, before the story, the verdict and the investigation, in every format."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app import report  # noqa: E402


def test_the_process_opens_the_report():
    secs = [{"title": "Findings", "items": ["a"]}, {"kind": "process", "title": "The process in brief", "items": ["Data: A", "Conclusion: ok"]}]
    assert [x["title"] for x in report._process_first(secs)] == ["The process in brief", "Findings"]
    page = report.build_html(None, {"tabs": [], "sections": secs, "lang": "en"})
    assert page.index("The process in brief") < page.index("Findings") and "Conclusion: ok" in page
