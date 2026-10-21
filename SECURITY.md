# Security

Signal Viewer runs a local server for its own window: it listens only on 127.0.0.1 and answers
only requests whose `Host` and `Origin` are this computer, so a web page in your browser cannot use
it. Nothing is sent from the app, and it needs no network at all.

**A security problem** - for example a way for a web page, a file or another user on the computer
to read your files or run code through Signal Viewer: please report it privately through
[*Report a vulnerability*](https://github.com/DavidAlpert11/SignalViewer/security/advisories/new),
not as a public issue. You will get an answer within a week; the fix goes into the next release
with credit to you, if you wish.

Opening a file you do not trust: the readers only read data; a *reader* or a *Python operation* in
your `~/.signalviewer` folder is Python code and runs as you - install only ones you trust.

Supported: the latest release.
