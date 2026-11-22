"""CP4 (owner, 2026-11-22: "the most important now - a good way to throw an interactive plot from the app straight to
Confluence, the easiest way"): *Send to Confluence…* - the plot or tab's page (every sample, as Copy for Confluence
saves it) uploaded as an attachment of a page and the macro that shows it added at the page's end, through
Confluence's REST API (Data Center / Server 7.9+ with a personal access token; Cloud with an e-mail and an API token).
Nothing to save, drag or paste. Sent again: the attachment gets a new version and the page is left as it is (its macro
shows the newest).

The address and the token are the user's, kept in ~/.signalviewer/confluence.json (readable by the user only); the
token is never sent back to the page. The app talks to that address only, only when the user sends - allowed with
"Never use the network" (a company's own server), not with SV_OFFLINE=1 (an administrator's no)."""
import base64
import html
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
import uuid
from typing import Any, Dict, List, Optional, Tuple

from app import prefs

FILE = "confluence.json"
RECENT_MAX = 8
TIMEOUT = 30


class ConfluenceError(Exception):
    """Said to the user as it is: what happened and what to do."""


def config() -> Dict[str, Any]:
    c = prefs._read(FILE, {})
    return c if isinstance(c, dict) else {}


def public() -> Dict[str, Any]:
    """What the page may see: the address, the user, whether a token is kept, the recent pages - never the token."""
    c = config()
    return {"url": c.get("url") or "", "user": c.get("user") or "", "hasToken": bool(c.get("token")),
            "recent": c.get("recent") or []}


def save(url: Optional[str] = None, user: Optional[str] = None, token: Optional[str] = None) -> Dict[str, Any]:
    """The settings changed (a value left None is kept; an empty token removes it)."""
    c = config()
    if url is not None:
        u = url.strip().rstrip("/")
        if u and not re.match(r"^https?://[^/\s]+", u):
            raise ConfluenceError("The Confluence address starts with https:// - e.g. https://confluence.example.com")
        c["url"] = re.sub(r"/(pages|display|spaces|wiki/spaces)/.*$", "", u)      # a page's link pasted: its server
    if user is not None:
        c["user"] = user.strip()
    if token is not None:
        if token.strip():
            c["token"] = token.strip()
        else:
            c.pop("token", None)
    prefs._write(FILE, c)
    try:
        os.chmod(prefs._path(FILE), 0o600)
    except OSError:
        pass
    return public()


def _remember(page_url: str, title: str) -> None:
    c = config()
    rec = [r for r in c.get("recent") or [] if r.get("url") != page_url]
    c["recent"] = [{"url": page_url, "title": title}] + rec[:RECENT_MAX - 1]
    prefs._write(FILE, c)


# ------------------------------------------------------------------------------------------------ the HTTP calls

def _base(c: Dict[str, Any]) -> str:
    url = (c.get("url") or "").rstrip("/")
    if not url or not c.get("token"):
        raise ConfluenceError("Confluence is not set up yet: Settings -> Confluence - its address and a personal access "
                              "token (in Confluence: your picture -> Settings -> Personal Access Tokens -> Create token).")
    from app.tiles import offline_forced
    if offline_forced():
        raise ConfluenceError("The network is off for this app (SV_OFFLINE=1, set by an administrator): nothing is sent.")
    return url


def _auth(c: Dict[str, Any]) -> str:
    if c.get("user"):                                   # Cloud: the e-mail and an API token
        return "Basic " + base64.b64encode(("%s:%s" % (c["user"], c["token"])).encode()).decode()
    return "Bearer " + str(c["token"])                 # Data Center / Server: a personal access token


def _call(c: Dict[str, Any], method: str, path: str, body: Optional[bytes] = None,
          ctype: Optional[str] = None, what: str = "") -> Any:
    url = _base(c) + path
    head = {"Authorization": _auth(c), "Accept": "application/json", "X-Atlassian-Token": "no-check",
            "User-Agent": "SignalViewer"}
    if ctype:
        head["Content-Type"] = ctype
    req = urllib.request.Request(url, data=body, method=method, headers=head)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            raw = r.read()
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = json.loads(e.read().decode("utf-8", "replace")).get("message", "")
        except Exception:
            pass
        if e.code == 401:
            raise ConfluenceError("Confluence refused the token (401): make a new personal access token and put it in "
                                  "Settings -> Confluence.") from None
        if e.code == 403:
            raise ConfluenceError("You may not %s on Confluence (403): ask the page's owner for edit rights." % (what or "do that")) from None
        if e.code == 404:
            raise ConfluenceError("Confluence has no such page (404) - or you may not see it: check the link.") from None
        if e.code == 413:
            raise ConfluenceError("The page is larger than Confluence takes as an attachment (413): send a shorter "
                                  "range or fewer lines - or ask the administrator to raise the attachment limit.") from None
        raise ConfluenceError("Confluence answered %d%s." % (e.code, (": " + detail) if detail else "")) from None
    except (urllib.error.URLError, OSError) as e:
        reason = getattr(e, "reason", e)
        raise ConfluenceError("Confluence at %s could not be reached (%s): check the address in Settings, the "
                              "network or the VPN." % (_base(c), reason)) from None
    if not raw:
        return {}
    try:
        return json.loads(raw.decode("utf-8"))
    except ValueError:
        raise ConfluenceError("Confluence's answer was not what its REST API gives - is %s the address of "
                              "Confluence itself (not a login page)?" % _base(c)) from None


def test() -> Dict[str, Any]:
    """Settings -> Test: who Confluence says we are."""
    c = config()
    me = _call(c, "GET", "/rest/api/user/current", what="read your profile")
    name = me.get("displayName") or me.get("username") or me.get("publicName") or ""
    if me.get("type") == "anonymous" or not name:
        raise ConfluenceError("Confluence answered as an anonymous visitor: the token was not taken - check it.")
    return {"user": name}


# ------------------------------------------------------------------------------------------------ the page

def page_id(c: Dict[str, Any], link: str) -> str:
    """A page's id from its link: .../pages/viewpage.action?pageId=123, .../spaces/KEY/pages/123/Title,
    .../display/KEY/Title (looked up by its title), or the id itself."""
    s = link.strip()
    if re.fullmatch(r"\d+", s):
        return s
    u = urllib.parse.urlparse(s)
    q = urllib.parse.parse_qs(u.query)
    if q.get("pageId"):
        return q["pageId"][0]
    m = re.search(r"/pages/(\d+)(/|$)", u.path)
    if m:
        return m.group(1)
    m = re.search(r"/display/([^/]+)/([^/?#]+)", u.path)
    if m:
        key, title = urllib.parse.unquote(m.group(1)), urllib.parse.unquote_plus(m.group(2))
        r = _call(c, "GET", "/rest/api/content?" + urllib.parse.urlencode({"spaceKey": key, "title": title, "type": "page"}),
                  what="find the page")
        res = r.get("results") or []
        if res:
            return str(res[0]["id"])
        raise ConfluenceError("Confluence has no page \"%s\" in the space %s." % (title, key))
    raise ConfluenceError("That is not a link to a Confluence page: open the page in the browser and copy its address "
                          "(or Page -> ... -> Page information and its page id).")


def _multipart(name: str, data: bytes, ctype: str) -> Tuple[bytes, str]:
    b = "----sv" + uuid.uuid4().hex
    head = ('--%s\r\nContent-Disposition: form-data; name="file"; filename="%s"\r\nContent-Type: %s\r\n\r\n'
            % (b, name.replace('"', "_"), ctype)).encode("utf-8")
    tail = ('\r\n--%s\r\nContent-Disposition: form-data; name="minorEdit"\r\n\r\ntrue\r\n--%s--\r\n' % (b, b)).encode()
    return head + data + tail, "multipart/form-data; boundary=" + b


def macro_storage(kind: str, name: str, height: int, html_macro: str) -> str:
    """The macro in Confluence's storage format: the Signal Viewer user macro, or the HTML macro with its lines."""
    if kind == "user":
        return ('<ac:structured-macro ac:name="signalviewer" ac:schema-version="1">'
                '<ac:parameter ac:name="file">%s</ac:parameter><ac:parameter ac:name="height">%d</ac:parameter>'
                '</ac:structured-macro>' % (html.escape(name), height))
    return ('<ac:structured-macro ac:name="html" ac:schema-version="1"><ac:plain-text-body><![CDATA[%s]]>'
            '</ac:plain-text-body></ac:structured-macro>' % html_macro.replace("]]>", "]]]]><![CDATA[>"))


def _shows(body: str, name: str) -> bool:
    """The page shows this attachment already (either macro)."""
    esc = html.escape(name)
    return ('<ac:parameter ac:name="file">%s</ac:parameter>' % esc) in body or ('data-name="%s"' % esc) in body


def send(link: str, page_html: str, name: str, kind: str, height: int, html_macro: str) -> Dict[str, Any]:
    """The page attached to the Confluence page `link` (a new version when it is there) and its macro added at the
    page's end unless the page shows it already. Returns the page's title, its address and what was done."""
    c = config()
    pid = page_id(c, link)
    data = page_html.encode("utf-8")
    had = _call(c, "GET", "/rest/api/content/%s/child/attachment?%s" % (pid, urllib.parse.urlencode({"filename": name})),
                what="see the page's attachments")
    body, ctype = _multipart(name, data, "text/html")
    existing = (had.get("results") or [])
    if existing:
        _call(c, "POST", "/rest/api/content/%s/child/attachment/%s/data" % (pid, existing[0]["id"]), body, ctype,
              what="attach a file to this page")
    else:
        _call(c, "POST", "/rest/api/content/%s/child/attachment" % pid, body, ctype, what="attach a file to this page")
    page = _call(c, "GET", "/rest/api/content/%s?expand=body.storage,version" % pid, what="read the page")
    storage = ((page.get("body") or {}).get("storage") or {}).get("value") or ""
    added = False
    if not _shows(storage, name):
        new = storage + macro_storage(kind, name, height, html_macro)
        upd = {"id": pid, "type": page.get("type") or "page", "title": page.get("title") or "",
               "version": {"number": int((page.get("version") or {}).get("number") or 1) + 1,
                           "message": "Signal Viewer: %s" % name},
               "body": {"storage": {"value": new, "representation": "storage"}}}
        _call(c, "PUT", "/rest/api/content/%s" % pid, json.dumps(upd).encode("utf-8"), "application/json",
              what="edit this page")
        added = True
    links = page.get("_links") or {}
    web = (links.get("base") or _base(c)) + (links.get("webui") or "/pages/viewpage.action?pageId=%s" % pid)
    title = page.get("title") or pid
    _remember(link.strip(), title)
    return {"page": title, "url": web, "added": added, "updated": bool(existing), "name": name, "size": len(data)}


def safe_name(title: str) -> str:
    """The attachment's name from the plot's or tab's title."""
    s = re.sub(r'[\\/:*?"<>|{}#\[\]^~]+', "_", title or "").strip(" ._") or "signalviewer"
    return s[:60] + ".html"


def recent() -> List[Dict[str, str]]:
    return list(config().get("recent") or [])
