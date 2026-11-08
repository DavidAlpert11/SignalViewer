# Security

Signal Viewer runs a local server for its own window: it listens only on 127.0.0.1 and answers
only requests whose `Host` and `Origin` are this computer, so a web page in your browser cannot use
it. It needs no network at all, and nothing is sent from the app - with one exception you choose:
an **online map layer** (OpenStreetMap, Esri, OpenTopoMap in the map's layer menu) makes the app
request the map tiles of the area on screen from that provider (the request carries the tile's
coordinates, i.e. roughly where you are looking, and the app's name as its User-Agent). The default
map (*Automatic*) is the offline one, and an *Online map* sign shows while online tiles are used.
*Settings ▸ Never use the network*, or the environment variable `SV_OFFLINE=1` (for a whole
installation), stops every request; tiles already cached on the disk are still shown.

**A security problem** - for example a way for a web page, a file or another user on the computer
to read your files or run code through Signal Viewer: please report it privately through
[*Report a vulnerability*](https://github.com/DavidAlpert11/SignalViewer/security/advisories/new),
not as a public issue. You will get an answer within a week; the fix goes into the next release
with credit to you, if you wish.

Opening a file you do not trust: the readers only read data; a *reader* or a *Python operation* in
your `~/.signalviewer` folder is Python code and runs as you - install only ones you trust.

Supported: the latest release.
