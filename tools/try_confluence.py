"""Try *Send to Confluence* with no Confluence (CP4): a stand-in of its REST API on this computer, with one page.

    python tools/try_confluence.py            (Ctrl+C stops it)

It prints the address, the token and the page's link. In the app: Settings -> Confluence -> the address and the token,
Save and test ("Connected as Dana Tester"); then a plot's ⋯ -> Send to Confluence…, the page's link, OK. Open the page's
link in the browser: the plot is there, live - as on a Confluence page. Send again: the attachment's version goes up,
the page stays as it is. The stand-in keeps everything in memory only."""
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend", "tests"))
from fake_confluence import TOKEN, Fake  # noqa: E402


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8090
    f = Fake(port)
    print("Confluence stand-in running.\n")
    print("  Settings -> Confluence -> address : %s" % f.url)
    print("                           token   : %s" % TOKEN)
    print("  Send to Confluence -> page's link: %s/display/ENG/Bench+run+7" % f.url)
    print("  Open in the browser              : %s/display/ENG/Bench+run+7\n" % f.url)
    print("Ctrl+C stops it.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        f.close()


if __name__ == "__main__":
    main()
