"""CP4: a stand-in for Confluence's REST API (Data Center / Server) - the calls Send to Confluence makes, with their
rules: the token, the space / title lookup, attachments (a new one, a new version of one), the page's storage body and
its version number (an update must give the next one). Runs in a thread on 127.0.0.1."""
import json
import re
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

TOKEN = "tok-123"


class Fake:
    def __init__(self, port: int = 0):
        self.page = {"id": "4711", "type": "page", "title": "Bench run 7", "space": "ENG", "version": 3,
                     "body": "<p>The bench run.</p><h2>Results</h2><p>The speed, as measured.</p><h2>Notes</h2><p>-</p>"}
        self.attachments = {}            # name -> {"id", "data", "versions"}
        self.calls = []
        self.srv = ThreadingHTTPServer(("127.0.0.1", port), self._handler())
        self.url = "http://127.0.0.1:%d/confluence" % self.srv.server_address[1]
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    def close(self):
        self.srv.shutdown()

    def render(self) -> str:
        """The page in a browser: its storage body with the HTML macro's lines run as they are and the Signal Viewer
        user macro drawn by its template - as Confluence does (the meta tags a Confluence page carries)."""
        import html as H
        import os
        import sys
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
        from app.report_clip import build_user_macro_template
        tpl = "\n".join(ln for ln in build_user_macro_template().splitlines() if not ln.startswith("##"))
        body = self.page["body"]
        body = re.sub(r'<ac:structured-macro ac:name="html"[^>]*><ac:plain-text-body><!\[CDATA\[(.*?)\]\]></ac:plain-text-body></ac:structured-macro>',
                      lambda m: m.group(1), body, flags=re.S)

        def user(m):
            params = dict(re.findall(r'<ac:parameter ac:name="(\w+)">(.*?)</ac:parameter>', m.group(0)))
            return (tpl.replace("$!generalUtil.htmlEncode($!paramfile)", params.get("file", ""))
                    .replace("$!generalUtil.htmlEncode($!paramheight)", params.get("height", ""))
                    .replace("$!content.id", self.page["id"]).replace("$!req.contextPath", "/confluence"))
        body = re.sub(r'<ac:structured-macro ac:name="signalviewer".*?</ac:structured-macro>', user, body, flags=re.S)
        return ('<!doctype html><html><head><meta charset="utf-8"><meta name="ajs-page-id" content="%s">'
                '<meta name="ajs-context-path" content="/confluence"><title>%s - Confluence (stand-in)</title>'
                '<style>body{font:14px sans-serif;max-width:1100px;margin:24px auto;padding:0 16px}'
                '#drop{display:none;position:fixed;inset:12px;border:3px dashed #3d8bfd;background:#f4f8ffee;padding:40px;font-size:16px;z-index:9}</style></head><body>'
                '<div id="drop"><b>This is the Confluence stand-in: a page to look at, not an editor - a drop does nothing here.</b>'
                '<p>A web page cannot take a file from a drag out of another window - on a real Confluence page a drop from Signal '
                'Viewer gives only its picture (in the editor).</p><p>To put the plot here, live: in the app, the plot\'s ⋯ menu -> '
                '<b>Send to Confluence…</b>, this page\'s link, OK - then reload this page.</p><p>(Click to close.)</p></div>'
                '<script>var d=document.getElementById("drop");addEventListener("dragover",function(e){e.preventDefault()});'
                'addEventListener("drop",function(e){e.preventDefault();d.style.display="block"});d.onclick=function(){d.style.display="none"}</script>'
                '<p style="color:#888">Confluence stand-in (Signal Viewer tools) · version %d · attachments: %s</p><h1>%s</h1>%s</body></html>'
                % (self.page["id"], H.escape(self.page["title"]), self.page["version"],
                   H.escape(", ".join(self.attachments) or "none"), H.escape(self.page["title"]), body))

    def _handler(self):
        fake = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _send(self, code, obj=None):
                data = json.dumps(obj if obj is not None else {}).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def _ok(self):
                if self.headers.get("Authorization") != "Bearer " + TOKEN:
                    self._send(401, {"message": "Unauthorized"})
                    return False
                return True

            def _body(self):
                n = int(self.headers.get("Content-Length") or 0)
                return self.rfile.read(n) if n else b""

            def _route(self, method):
                u = urllib.parse.urlparse(self.path)
                path = u.path[len("/confluence"):] if u.path.startswith("/confluence") else None
                q = urllib.parse.parse_qs(u.query)
                fake.calls.append((method, path))
                if path is None:
                    return self._send(404)
                if method == "GET" and not path.startswith("/rest/"):     # the browser's side: no token (a session)
                    return self._view(path)
                if not self._ok():
                    return
                p = fake.page
                if method == "GET" and path == "/rest/api/user/current":
                    return self._send(200, {"type": "known", "displayName": "Dana Tester"})
                if method == "GET" and path == "/rest/api/content":
                    hit = q.get("spaceKey") == [p["space"]] and q.get("title") == [p["title"]]
                    return self._send(200, {"results": [{"id": p["id"]}] if hit else []})
                m = re.fullmatch(r"/rest/api/content/(\d+)(/child/attachment(?:/(\w+)/data)?)?", path)
                if not m or m.group(1) != p["id"]:
                    return self._send(404, {"message": "No content found"})
                if m.group(2) is None:
                    if method == "GET":
                        return self._send(200, {"id": p["id"], "type": "page", "title": p["title"], "version": {"number": p["version"]},
                                                "body": {"storage": {"value": p["body"], "representation": "storage"}},
                                                "_links": {"base": fake.url, "webui": "/display/%s/Bench+run+7" % p["space"]}})
                    if method == "PUT":
                        upd = json.loads(self._body())
                        if upd["version"]["number"] != p["version"] + 1:
                            return self._send(409, {"message": "Version must be incremented"})
                        p["version"] = upd["version"]["number"]
                        p["body"] = upd["body"]["storage"]["value"]
                        return self._send(200, {"id": p["id"]})
                if method == "GET" and m.group(3) is None:
                    name = (q.get("filename") or [""])[0]
                    a = fake.attachments.get(name)
                    return self._send(200, {"results": [{"id": a["id"], "title": name}] if a else []})
                if method == "POST":
                    if self.headers.get("X-Atlassian-Token") != "no-check":
                        return self._send(403, {"message": "XSRF check failed"})
                    raw = self._body()
                    mm = re.search(rb'filename="([^"]+)"\r\nContent-Type: [^\r]+\r\n\r\n(.*?)\r\n--', raw, re.S)
                    if not mm:
                        return self._send(400, {"message": "no file"})
                    name, data = mm.group(1).decode(), mm.group(2)
                    if m.group(3) is None:
                        if name in fake.attachments:
                            return self._send(400, {"message": "Cannot add a new attachment with same file name"})
                        fake.attachments[name] = {"id": "att%d" % (len(fake.attachments) + 100), "data": data, "versions": 1}
                    else:
                        a = next(x for x in fake.attachments.values() if x["id"] == m.group(3))
                        a["data"], a["versions"] = data, a["versions"] + 1
                    return self._send(200, {"results": [{"id": fake.attachments[name]["id"]}]})
                return self._send(405)

            def _raw(self, code, data, ctype):
                self.send_response(code)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def _view(self, path):
                """The page as a reader sees it (its macros drawn as Confluence draws them) and its attachments."""
                m = re.fullmatch(r"/download/attachments/(\d+)/(.+)", path)
                if m:
                    a = fake.attachments.get(urllib.parse.unquote(m.group(2)))
                    return self._raw(200, a["data"], "text/html; charset=utf-8") if a else self._raw(404, b"not attached", "text/plain")
                if path.startswith("/display/") or path.startswith("/pages/"):
                    return self._raw(200, fake.render().encode("utf-8"), "text/html; charset=utf-8")
                return self._raw(404, b"not found", "text/plain")

            def do_GET(self):
                self._route("GET")

            def do_POST(self):
                self._route("POST")

            def do_PUT(self):
                self._route("PUT")

        return H
