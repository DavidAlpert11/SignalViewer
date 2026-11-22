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
    def __init__(self):
        self.page = {"id": "4711", "type": "page", "title": "Bench run 7", "space": "ENG", "version": 3,
                     "body": "<p>The bench run.</p>"}
        self.attachments = {}            # name -> {"id", "data", "versions"}
        self.calls = []
        self.srv = ThreadingHTTPServer(("127.0.0.1", 0), self._handler())
        self.url = "http://127.0.0.1:%d/confluence" % self.srv.server_address[1]
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    def close(self):
        self.srv.shutdown()

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

            def do_GET(self):
                self._route("GET")

            def do_POST(self):
                self._route("POST")

            def do_PUT(self):
                self._route("PUT")

        return H
