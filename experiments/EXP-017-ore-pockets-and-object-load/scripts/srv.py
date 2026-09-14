#!/usr/bin/env python
"""EXP-017: drive the local test server over RCON. The password is read from the server's
.rcon-password file and never printed or logged.

  python srv.py wait-ready <console.log> [timeout_s]
  python srv.py cmd <log.jsonl> "command" ...
  python srv.py wait-exit [timeout_s]

Environment: COBBLERS_SERVER (default C:\\Users\\wnd\\Documents\\github\\cobblers-server).
"""
import datetime
import json
import os
import socket
import sys
import time
from pathlib import Path

SRV = Path(os.environ.get("COBBLERS_SERVER", r"C:\Users\wnd\Documents\github\cobblers-server"))
sys.path.insert(0, str(SRV))
import rcon  # noqa: E402  (the server's own helper)


def password():
    return (SRV / ".rcon-password").read_text(encoding="utf8").strip()


def port_open():
    try:
        with socket.create_connection(("127.0.0.1", 25575), timeout=2):
            return True
    except OSError:
        return False


def run(cmds, log=None):
    """Run commands over one RCON connection; append {t, cmd, resp} lines to log; return replies."""
    replies = rcon.run(cmds, password(), timeout=600)
    if log:
        with Path(log).open("a", encoding="utf8") as fh:
            t = datetime.datetime.now().isoformat(timespec="seconds")
            for c, r in zip(cmds, replies):
                fh.write(json.dumps({"t": t, "cmd": c, "resp": r}) + "\n")
    return replies


if __name__ == "__main__":
    mode = sys.argv[1]
    if mode == "wait-ready":
        log, timeout = Path(sys.argv[2]), float(sys.argv[3]) if len(sys.argv) > 3 else 900
        t0 = time.time()
        while time.time() - t0 < timeout:
            text = log.read_text(encoding="utf8", errors="replace") if log.exists() else ""
            if "Done (" in text and port_open():
                print("ready after %.0f s" % (time.time() - t0))
                sys.exit(0)
            for bad in ("Exception in server tick loop", "Failed to start the minecraft server",
                        "Crash report saved", "Stopping server"):
                if bad in text:
                    print("FAILED: %s" % bad)
                    sys.exit(1)
            time.sleep(3)
        print("TIMEOUT")
        sys.exit(2)
    elif mode == "cmd":
        for c, r in zip(sys.argv[3:], run(sys.argv[3:], sys.argv[2])):
            print("> %s\n  %s" % (c, r.strip() or "(no output)"))
    elif mode == "wait-exit":
        timeout, t0 = float(sys.argv[2]) if len(sys.argv) > 2 else 300, time.time()
        while time.time() - t0 < timeout:
            if not port_open():
                print("rcon closed after %.0f s" % (time.time() - t0))
                sys.exit(0)
            time.sleep(2)
        print("TIMEOUT")
        sys.exit(2)
