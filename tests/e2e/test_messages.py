"""MSG1 / MSG3: messages in a byte stream - the serial link demo from Help -> Examples opens the Link review; *Decode as
messages…* on a signal with a direction column (both ways) makes the tab with the reply latency; the definition kept.

    python -m pytest tests/e2e/test_messages.py -q
"""
import os
import shutil

import pytest

pw = pytest.importorskip("playwright.sync_api")
from test_features import S, env, open_files, pg, save_as, sig  # noqa: E402,F401
from test_report_doc import preview_has  # noqa: E402

DEMO = os.path.join(os.path.dirname(__file__), "..", "..", "examples", "serial_link")
SHOT = os.environ.get("SV_SHOTS")             # a folder: pictures of the screen for the owner (not needed by the test)


def shot(pg, name):
    if SHOT:
        os.makedirs(SHOT, exist_ok=True)
        pg.screenshot(path=os.path.join(SHOT, name))


def test_the_serial_link_example_opens_the_link_review(pg):
    pg.locator(".topbar .menubar-btn", has_text="Help").click()
    pg.locator(".menu.ctx button", has_text="Examples").click()
    pg.locator(".menu.ctx.sub button", has_text="a serial link").click()
    pg.wait_for_selector(".rd .rd-text", timeout=30000)
    pg.wait_for_function("(window.__sv.state().ws.report?.doc?.text || '').includes('[[messages]]')", timeout=30000)
    # the packet's make-up, requests and replies, the handshake and its reconnect - in the preview
    preview_has(pg, "fixed AA 55", "fixed EB 90", "requests and replies", "The handshake", "a reconnect", "Unanswered")
    shot(pg, "msg_report.png")
    if SHOT:                                                         # further down: the link's part and its plots
        pg.frame_locator(".rd-preview iframe, .rd iframe").first.locator("text=requests and replies").first.scroll_into_view_if_needed()
        pg.wait_for_timeout(800)
        shot(pg, "msg_report_link.png")


def test_decode_as_messages_both_ways_with_a_direction_column(pg):
    shutil.copy(os.path.join(DEMO, "link_mixed.csv"), os.path.join(pg.env["data"], "link_mixed.csv"))
    open_files(pg, "link_mixed.csv")
    sig(pg, "byte").click(button="right")
    pg.locator(".menu.ctx button", has_text="Decode as messages").click()
    pg.wait_for_selector(".messages .msgp-stream.open .msgp-edit")
    shot(pg, "msg_dialog.png")
    # a direction column is there: "both" is guessed, with dir and TX
    assert pg.locator(".msgp-stream.open input[value=both]").is_checked()
    assert pg.locator(".msgp-stream.open .msg-dir").input_value().endswith("/dir")
    assert pg.locator(".msgp-stream.open .msg-txv option:checked").inner_text() == "TX"
    pg.locator(".msgp-stream.open .msg-go").click()
    pg.wait_for_function("window.__sv.state().ws.tabs.some(t => t.name.startsWith('Messages: byte'))", timeout=30000)
    pg.wait_for_timeout(1500)
    shot(pg, "msg_tab.png")
    n = S(pg, "s.ws.tabs.find(t => t.name.startsWith('Messages: byte')).plots.length")
    assert n == 6                                                    # bytes, type, length, interval, ok, latency
    # TX and RX: two lines in each quantity's plot; the latency of the answered requests
    assert S(pg, "s.ws.tabs.find(t => t.name.startsWith('Messages: byte')).plots[1].signals.length") == 2
    assert S(pg, "s.runs.find(r => r.format === 'derived').signals.some(x => x.params?.what === 'latency' && x.samples === 284)")
    ms = S(pg, "s.ws.messageStreams")
    assert len(ms) == 1 and ms[0]["carries"] == "both"               # the definition kept in the session


def example(pg, text):
    pg.locator(".topbar .menubar-btn", has_text="Help").click()
    pg.locator(".menu.ctx button", has_text="Examples").click()
    pg.locator(".menu.ctx.sub button", has_text=text).click()


def test_messages_to_signals_example_makes_two_recordings(pg):
    """MSG2: the serial link with its two structure files -> two recordings of their own, plotted."""
    example(pg, "messages to signals")
    pg.wait_for_function("['tx_byte - messages', 'rx_byte - messages'].every(n => window.__sv.state().runs.some(r => r.name === n))", timeout=60000)
    sigs = S(pg, "s.runs.find(r => r.name === 'rx_byte - messages').signals.map(x => x.name)")
    assert "ATTITUDE.roll [deg]" in sigs and "ATTITUDE.alt [m]" in sigs and "STATUS.mode" in sigs
    pg.wait_for_function("window.__sv.state().ws.tabs.some(t => t.name === 'rx_byte - messages')", timeout=30000)
    pg.wait_for_timeout(1500)
    shot(pg, "msg2_link_recording.png")
    ms = S(pg, "s.ws.messageStreams")
    assert len(ms) == 1 and sorted(m["label"] for m in ms[0]["made"]) == ["RX", "TX"]


def test_propose_a_binary_structure_rename_and_make(pg):
    shutil.copy(os.path.join(DEMO, "link_tx_rx.csv"), os.path.join(pg.env["data"], "link_tx_rx.csv"))
    open_files(pg, "link_tx_rx.csv")
    sig(pg, "rx_byte").click(button="right")
    pg.locator(".menu.ctx button", has_text="Decode as messages").click()
    pg.wait_for_selector(".messages .msgp-stream.open .msgp-edit")
    assert pg.locator(".msgp-stream.open input[value=rx]").is_checked()                  # named rx: guessed RX
    pg.locator(".msgp-stream.open .msg-propose").click()
    pg.wait_for_selector(".msgp-stream.open .msg-struct .msg-msg")
    assert pg.locator(".msgp-stream.open .msg-hdr").input_value() == "EB90"
    att = pg.locator(".msgp-stream.open .msg-msg", has=pg.locator(".msg-name[value=MSG_A0]"))
    att.locator(".msg-f-name").first.fill("roll")
    att.locator("input[size='5']").nth(0).fill("0.01")                           # x scale
    shot(pg, "msg2_propose_binary.png")
    pg.locator(".msgp-stream.open .msg-make").click()
    pg.wait_for_function("window.__sv.state().runs.some(r => r.name === 'rx_byte - messages')", timeout=30000)
    roll = S(pg, "s.runs.find(r => r.name === 'rx_byte - messages').signals.find(x => x.name === 'MSG_A0.roll')")
    assert roll is not None


def test_gps_nmea_example_and_uart_proposes_nmea(pg):
    example(pg, "raw NMEA")
    pg.wait_for_function("window.__sv.state().runs.some(r => r.name.endsWith('receiver.nmea'))", timeout=60000)
    sigs = S(pg, "s.runs.find(r => r.name.endsWith('receiver.nmea')).signals.map(x => x.name)")
    assert "GGA.lat [deg]" in sigs and "RMC.speed [kn]" in sigs
    # the track on a map at once, speed / satellites / altitude beside it
    pg.wait_for_function("window.__sv.state().ws.tabs.some(t => t.plots.some(p => (p.mode === 'geo' || p.mode === '3d') && (p.objects || []).length))", timeout=30000)
    pg.wait_for_function("window.__sv.state().ws.tabs.some(t => t.name.endsWith('receiver.nmea'))", timeout=30000)
    if SHOT:
        pg.evaluate("() => { const st = window.__sv.state(); const tb = st.ws.tabs.find(t => t.plots.some(p => p.mode === 'geo' || p.mode === '3d')); window.__sv.setState({ ws: { ...st.ws, activeTab: tb.id } }); }")
        pg.wait_for_timeout(3000)
        shot(pg, "msg2_gps_map.png")
    pg.wait_for_function("window.__sv.state().runs.some(r => r.name.endsWith('receiver_uart.csv'))", timeout=60000)
    sig(pg, "rx_byte").click(button="right")
    pg.locator(".menu.ctx button", has_text="Decode as messages").click()
    pg.wait_for_selector(".messages .msgp-stream.open .msgp-edit")
    pg.locator(".msgp-stream.open .msg-propose").click()
    pg.wait_for_selector(".msgp-stream.open .msg-struct .msg-msg")
    assert pg.locator(".msgp-stream.open .msg-kind").input_value() == "text"
    names = pg.locator(".msgp-stream.open .msg-name").evaluate_all("els => els.map(e => e.value)")
    assert {"GGA", "RMC", "PDEMO"} <= set(names)
    shot(pg, "msg2_propose_nmea.png")
    pg.locator(".msgp-stream.open .msg-make").click()
    pg.wait_for_function("window.__sv.state().runs.some(r => r.name === 'rx_byte - messages')", timeout=30000)
    assert S(pg, "s.runs.find(r => r.name === 'rx_byte - messages').signals.some(x => x.name === 'PDEMO.f1')")


def test_listen_to_a_udp_link_decoded_live(pg):
    """LINK1: Live -> Listen to a link: UDP with NMEA - the recording opens and grows live; Stop keeps the file."""
    import socket
    import time
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    pg.click(".live-more")
    pg.locator(".link-conn").fill(f"udp:127.0.0.1:{port}")
    pg.locator(".link-structure").select_option(label="NMEA 0183")      # MSG3: from the structure library
    pg.locator(".link-listen").click()
    pg.wait_for_selector(".link-stop")
    lines = open(os.path.join(os.path.dirname(__file__), "..", "..", "examples", "gps_nmea", "receiver.nmea"), "rb").read().splitlines(keepends=True)
    tx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def send(a, b):
        for ln in lines[a:b]:
            tx.sendto(ln, ("127.0.0.1", port))
            time.sleep(0.002)
    send(0, 100)
    pg.wait_for_function("window.__sv.state().runs.some(r => r.name.endsWith('.svraw') && r.signals.some(x => x.name.startsWith('GGA.lat')))", timeout=30000)
    n0 = S(pg, "s.runs.find(r => r.name.endsWith('.svraw')).signals.find(x => x.name.startsWith('GGA.lat')).n")
    send(100, 400)                                              # more comes in: the plots' data grows (live)
    pg.wait_for_function(f"window.__sv.state().runs.find(r => r.name.endsWith('.svraw')).signals.find(x => x.name.startsWith('GGA.lat')).n > {n0}", timeout=30000)
    shot(pg, "link_live.png")
    # MSG3: the running link shows in the Messages panel too (started and stopped in Live)
    pg.keyboard.press("Escape")
    pg.mouse.click(5, 300)
    pg.locator(".rail button[aria-label='Messages']").click()
    pg.wait_for_selector(".msgp-running .msgp-link")
    shot(pg, "msg3_running.png")
    pg.click(".live-more")
    pg.locator(".link-stop").click()
    pg.wait_for_selector(".link-listen")
    path = S(pg, "s.runs.find(r => r.name.endsWith('.svraw')).path")
    assert os.path.isfile(path) and os.path.isfile(path[:-6] + ".svmsg.json")    # the recording and its structure stay


def test_messages_panel_is_the_one_home(pg):
    """MSG3: the Messages panel - the byte streams of the open files found with their types, a log's message types
    (a click plots them), the structure library; a structure saved to the library, a stream added to the report."""
    shutil.copy(os.path.join(DEMO, "link_tx_rx.csv"), os.path.join(pg.env["data"], "link_tx_rx.csv"))
    shutil.copy(os.path.join(DEMO, "..", "copter_flight.bin"), os.path.join(pg.env["data"], "copter_flight.bin"))
    open_files(pg, "link_tx_rx.csv", "copter_flight.bin")
    pg.locator(".rail button[aria-label='Messages']").click()
    pg.wait_for_selector(".msgp-stream[data-key$='/tx_byte'] .msgp-types .chip-s", timeout=30000)
    assert pg.locator(".msgp-stream[data-key$='/rx_byte']").count() == 1
    assert "AA 55" in pg.locator(".msgp-stream[data-key$='/tx_byte'] .msgp-dir").inner_text()
    assert pg.locator(".msgp-lib-list li", has_text="NMEA 0183").count() == 1
    # the flight log's message types: a click plots that message's fields in a new tab
    pg.wait_for_selector(".msgp-log tbody tr")
    pg.locator(".msgp-log summary", has_text="copter_flight").click() if not pg.locator(".msgp-log[open]").count() else None
    pg.locator(".msgp-log tbody tr", has=pg.locator("td", has_text="ATT")).first.click()
    pg.wait_for_function("window.__sv.state().ws.tabs.some(t => t.name === 'ATT' && t.plots[0].signals.length > 0)", timeout=30000)
    # a stream opened: proposed, saved to the library (listed), added to the report
    pg.locator(".msgp-stream[data-key$='/tx_byte'] .msgp-stream-head").click()
    ed = pg.locator(".msgp-stream.open")
    ed.locator(".msg-propose").click()
    ed.locator(".msg-struct .msg-msg").first.wait_for()
    ed.locator(".msg-save").click()
    pg.locator(".dialog.small input").first.fill("ground link TX")                 # its name in the library
    pg.keyboard.press("Enter")
    pg.wait_for_selector(".msgp-lib-list li:has-text('ground link TX')", timeout=15000)
    shot(pg, "msg3_panel.png")
    ed.locator(".msg-report").click()
    pg.wait_for_function("(window.__sv.state().ws.report?.doc?.text || '').includes('[[messages tx_byte]]')", timeout=15000)
    assert S(pg, "s.ws.messageStreams.length") == 1
    # the saved structure is offered when listening to a link
    pg.click(".live-more")
    pg.wait_for_function("[...document.querySelectorAll('.link-structure option')].some(o => o.textContent === 'NMEA 0183')", timeout=15000)
    opts = pg.locator(".link-structure option").evaluate_all("els => els.map(e => e.textContent)")
    assert "NMEA 0183" in opts and len(opts) >= 4


def test_guided_steps_from_raw_bytes_to_a_csv(pg):
    """MSG4: the four steps - the patterns found (the header first), the first messages byte by byte coloured by role,
    a click on a byte makes it a value (its first values shown at once), the recording made and saved as CSV."""
    shutil.copy(os.path.join(DEMO, "link_tx_rx.csv"), os.path.join(pg.env["data"], "link_tx_rx.csv"))
    open_files(pg, "link_tx_rx.csv")
    sig(pg, "rx_byte").click(button="right")
    pg.locator(".menu.ctx button", has_text="Decode as messages").click()
    ed = pg.locator(".msgp-stream.open")
    for n in (1, 2, 3, 4):
        ed.locator(".msg-step-%d h4" % n).wait_for()
    # step 2: proposed by itself - the header is the first pattern, the messages byte by byte
    ed.locator(".msg-step-2 .msg-pat.role-header", has_text="EB 90").first.wait_for(timeout=30000)
    ed.locator(".bv-frame .bv-b.role-header").first.wait_for()
    att = ed.locator(".bv-frame", has=pg.locator(".bv-meta b", has_text="MSG_A0")).first
    assert att.locator(".bv-b").nth(2).get_attribute("class").count("role-type") == 1
    assert att.locator(".bv-b").nth(3).get_attribute("class").count("role-length") == 1
    shot(pg, "msg4_steps.png")
    # step 2 -> 3: byte 12 is not a value any more, then a 16-bit signed MSB-first value starts there
    att.locator(".bv-b").nth(12).click()
    pg.locator(".menu.ctx button", has_text="Not a value").click()
    att.locator(".bv-b").nth(12).click()
    pg.locator(".menu.ctx button", has_text="A value starts here").click()
    pg.locator(".menu.ctx.sub button", has_text="16-bit signed, MSB first").click()
    table = ed.locator(".msg-values-t", has=pg.locator("caption", has_text="MSG_A0"))
    table.locator("th", has_text="value_12").wait_for(timeout=15000)
    assert table.locator("tbody tr").count() >= 1
    assert "×" in table.locator("caption").inner_text()                     # counted on the whole stream
    # step 4: the recording, then a CSV of it
    ed.locator(".msg-make").click()
    pg.wait_for_function("window.__sv.state().runs.some(r => r.name === 'rx_byte - messages' && r.signals.some(x => x.name === 'MSG_A0.value_12'))", timeout=30000)
    ed.locator(".msg-made").wait_for()
    ed.locator(".msg-savefile").click()
    save_as(pg, "rx_values.csv")
    path = os.path.join(pg.env["out"], "rx_values.csv")
    pg.wait_for_function("document.body.innerText.includes('rx_values.csv')", timeout=30000)
    head = open(path, encoding="utf-8").readline()
    assert "MSG_A0.value_12" in head
