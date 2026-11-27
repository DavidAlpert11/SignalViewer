"""CH (owner, 2026-11-26): a communication channel - separate TX and RX made one channel of requests and replies in one
click, its anomalies counted and shown over time, the counts compared with a similar file.

    python -m pytest tests/e2e/test_channel.py -q
"""
import os
import shutil

import pytest

pw = pytest.importorskip("playwright.sync_api")
from test_features import S, env, live_settings, open_files, pg  # noqa: E402,F401

SHOT = os.environ.get("SV_SHOTS")             # a folder: pictures of the screen for the owner (not needed by the test)
DEMO = os.path.join(os.path.dirname(__file__), "..", "..", "examples", "serial_link")


def messages_page(pg):
    pg.keyboard.press("Control+k")
    pg.keyboard.type("Messages")
    pg.keyboard.press("Enter")
    pg.wait_for_selector(".page.messages, .side.messages")


def test_separate_tx_and_rx_become_one_channel_in_one_click(pg):
    shutil.copy(os.path.join(DEMO, "link_tx_rx.csv"), os.path.join(pg.env["data"], "link_tx_rx.csv"))
    open_files(pg, "link_tx_rx.csv")
    messages_page(pg)
    offer = pg.locator(".ch-offer")
    offer.wait_for(timeout=30000)
    assert "tx_byte" in offer.inner_text() and "rx_byte" in offer.inner_text()
    offer.locator(".ch-make").click()
    # kept in the session at once (one Undo), TX first; the stream opens as the pair
    pg.wait_for_function("(window.__sv.state().ws.messageStreams || []).some(m => m.carries === 'pair' && m.sources[0].endsWith('/tx_byte') && m.sources[1].endsWith('/rx_byte'))")
    pg.wait_for_selector(".msgp-current input[value=pair]:checked, .msgp-stream.open input[value=pair]:checked", timeout=30000)
    assert pg.locator(".ch-offer").count() == 0
    pg.keyboard.press("Control+z")
    pg.wait_for_function("!(window.__sv.state().ws.messageStreams || []).length")


def test_the_channel_block_counts_and_shows_the_anomalies(pg):
    shutil.copy(os.path.join(DEMO, "link_tx_rx.csv"), os.path.join(pg.env["data"], "link_tx_rx.csv"))
    open_files(pg, "link_tx_rx.csv")
    messages_page(pg)
    pg.locator(".ch-offer .ch-make").click()
    view = pg.locator(".ch-view[data-total]")
    view.wait_for(timeout=30000)
    # the patterns beyond the content: both framings, the command answered by its ACK, the handshake
    txt = view.inner_text()
    assert "AA 55" in txt and "EB 90" in txt and "0x10 → RX 0x90" in txt and "Handshake" in txt
    # every anomaly of the demo counted (svcore/channel.py, test_channel): one chip per kind
    chip = lambda k: int(pg.locator(f".ch-chip[data-kind={k}] b").inner_text().replace(",", ""))
    assert chip("unanswered") == 18 and chip("checksum") == 4 and chip("retry") == 1 and chip("reconnect") == 1
    assert int(view.get_attribute("data-total")) == sum(chip(k) for k in pg.locator(".ch-chip").evaluate_all("es => es.map(e => e.dataset.kind)"))
    # the strip: a lane per kind; a click on the reconnect's mark puts the cursor there (19.5 s)
    assert pg.locator(".ch-lane[data-kind]").count() == pg.locator(".ch-chip").count()
    pg.locator(".ch-lane[data-kind=reconnect] .ch-mark").first.click()
    pg.wait_for_function("Math.abs(window.__sv.state().cursor.t1 - 19.5) < 0.05")
    # a chip shows only its kind in the list
    pg.locator(".ch-chip[data-kind=retry]").click()
    pg.locator(".ch-list summary").click()
    assert pg.locator(".ch-table tbody tr").count() == 1
    # Plot the messages: the anomalies so far, one step each, beside the data
    total = int(view.get_attribute("data-total"))
    if SHOT:
        view.screenshot(path=os.path.join(SHOT, "channel.png"))
    pg.locator(".msg-go").click()
    pg.wait_for_function("window.__sv.state().ws.tabs.some(t => t.plots.some(p => p.signals.some(s => s.sig.endsWith('.anomalies'))))", timeout=30000)
    n = S(pg, "s.runs.find(r => r.format === 'derived').signals.find(x => x.name.endsWith('.anomalies')).samples")
    assert n == total + 2                                  # from 0 at the first message to the last one


def test_the_channel_example_compares_two_recordings(pg):
    """CH4 / CH5: Help -> Examples -> one link recorded twice: one channel in a step, its anomalies, the second
    recording beside it (each count against the first's), then the report with the files' table."""
    pg.locator(".topbar .menubar-btn", has_text="Help").click()
    pg.locator(".menu.ctx button", has_text="Examples").click()
    pg.locator(".menu.ctx.sub button", has_text="one link recorded twice").click()
    pg.wait_for_selector(".demo-guide[data-demo=channel][data-step='1'] .demo-next", timeout=30000)
    pg.locator(".demo-guide .demo-next").click()
    view = pg.locator(".ch-view[data-total]")
    view.wait_for(timeout=30000)
    assert view.get_attribute("data-total") == "23"                     # make_channel.py: run1's anomalies
    # CH12: whose - 5 the link's, 8 likely the capture's (a sniffer's glitch the link shows), 10 no effect seen
    cause = lambda c: pg.locator(f".ch-cause[data-cause={c}] b").inner_text()
    assert (cause("link"), cause("capture"), cause("none")) == ("5", "8", "10")
    pg.locator(".ch-cause[data-cause=capture]").click()
    pg.locator(".ch-list summary").click()
    assert pg.locator(".ch-table tbody tr").count() == 8 and pg.locator(".ch-table tbody td.ch-c-capture").count() == 8
    assert pg.locator(".ch-mark.ch-c-capture").count() >= 1 and pg.locator(".ch-mark.ch-c-link").count() == 0
    if SHOT:
        view.screenshot(path=os.path.join(SHOT, "channel_causes.png"))
    pg.locator(".ch-cause[data-cause=capture]").click()
    # CH10: by itself - the second recording beside it, nothing to click
    row = pg.locator(".ch-compare-t tr[data-file='link_run2.csv']")
    row.wait_for(timeout=30000)
    assert pg.locator(".ch-compare-go").count() == 0 and pg.locator(".ch-compare-t .ch-mini").count() == 2
    assert "ch-out" in row.locator("td[data-kind=checksum]").get_attribute("class")          # 7 against 2: stands out
    assert "stands out: 7 × Bad checksum" in pg.locator(".ch-diffs").inner_text()
    assert pg.locator(".ch-compare-t tr.ch-this td[data-kind=all]").inner_text() == "23"
    assert row.locator("td[data-kind=all] .ch-more").inner_text().startswith("42")          # more: marked, +19
    assert "+19" in row.locator("td[data-kind=all]").inner_text()
    assert row.locator("td[data-kind=broken] .ch-less").count() == 1                     # 0 against 1: fewer
    assert row.locator("td[data-kind=handshake] .ch-more").count() == 1
    if SHOT:
        view.screenshot(path=os.path.join(SHOT, "channel_compare.png"))
    pg.locator(".demo-guide[data-step='2'] .demo-next").click()
    pg.wait_for_function("(window.__sv.state().ws.report?.doc?.text || '').includes('[[messages]]')", timeout=30000)
    from test_report_doc import preview_has
    preview_has(pg, "the same channel in 2 files", "link_run2.csv")


def _two_loggers(folder, shift=0.0):
    """The serial link's TX and RX in two files whose names say nothing (two loggers; the second's clock `shift` s off)."""
    import csv
    rows = list(csv.reader(open(os.path.join(DEMO, "link_tx_rx.csv"))))[1:]
    with open(os.path.join(folder, "logger_a.csv"), "w", newline="\n") as f:
        f.write("time,port1\n" + "".join("%s,%s\n" % (r[0], r[1]) for r in rows if r[1]))
    with open(os.path.join(folder, "logger_b.csv"), "w", newline="\n") as f:
        f.write("time,port2\n" + "".join("%.6f,%s\n" % (float(r[0]) + shift, r[2]) for r in rows if r[2]))


def test_tx_in_one_file_rx_in_another_answering_each_other(pg):
    """CH7 / CH8 (owner, 2026-11-27): each stream's anomalies in the list at once; a TX in one file and an RX in
    another are offered as one channel because one answers the other - its requests, replies and anomalies."""
    _two_loggers(pg.env["data"])
    open_files(pg, "logger_a.csv", "logger_b.csv")
    messages_page(pg)
    badge = pg.locator(".msgp-stream", has_text="port1").locator(".msgp-anom")
    badge.wait_for(timeout=30000)
    assert "anomalies" in badge.inner_text()
    offer = pg.locator(".ch-offer")
    offer.wait_for(timeout=30000)
    assert "logger_a.csv" in offer.inner_text() and "logger_b.csv" in offer.inner_text()
    offer.locator(".ch-make").click()
    pg.wait_for_function("(window.__sv.state().ws.messageStreams || []).some(m => m.carries === 'pair' && m.sources[0].endsWith('/port1') && m.sources[1].endsWith('/port2'))")
    pg.locator(".ch-chip[data-kind=unanswered]").wait_for(timeout=30000)
    assert pg.locator(".ch-chip[data-kind=unanswered] b").inner_text() == "18"
    assert "0x10 → RX 0x90" in pg.locator(".ch-view").inner_text()


def test_two_loggers_two_clocks_aligned_in_one_click(pg):
    """CH9: the RX logger's clock 7 s ahead - offered as one link with the shift; its channel says so and one click moves
    the RX file (its time offset, Undo): the requests are answered again."""
    _two_loggers(pg.env["data"], shift=7.0)
    open_files(pg, "logger_a.csv", "logger_b.csv")
    messages_page(pg)
    offer = pg.locator(".ch-offer")
    offer.wait_for(timeout=30000)
    assert "7.00" in offer.inner_text()
    offer.locator(".ch-make").click()
    clock = pg.locator(".ch-clock")
    clock.wait_for(timeout=30000)
    assert abs(float(clock.get_attribute("data-shift")) - 7.0) < 0.01
    clock.locator(".ch-clock-go").click()
    pg.wait_for_function("Math.abs(window.__sv.state().runs.find(r => r.name === 'logger_b.csv').timeOffset + 7.0) < 0.01", timeout=30000)
    pg.wait_for_function("document.querySelector('.ch-chip[data-kind=unanswered] b')?.textContent === '18' && !document.querySelector('.ch-clock')", timeout=30000)
