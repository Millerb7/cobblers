#!/usr/bin/env python
"""Minimal RCON client so the server can be driven and stopped cleanly.

Needed because a background-launched server has no reachable stdin: without
RCON the only way to stop it is to kill the process, which skips the world
save. It is also the only way to run Distant Horizons' /dh pregen.

Enable in server.properties with enable-rcon=true, rcon.port=25575 and a
strong rcon.password, then put that password in a .rcon-password file next
to this script. Neither the password file nor server.properties is committed.
Bind RCON to localhost only; it is unauthenticated beyond the password.

  python rcon.py "dh pregen start overworld 4096 4096 256"
  python rcon.py stop
"""
import socket
import struct
import sys
from pathlib import Path

HOST, PORT = "127.0.0.1", 25575
LOGIN, COMMAND, RESPONSE = 3, 2, 0


def pack(req_id, kind, body):
    payload = struct.pack("<ii", req_id, kind) + body.encode("utf8") + b"\x00\x00"
    return struct.pack("<i", len(payload)) + payload


def read_exact(sock, n):
    buf = b""
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise EOFError("connection closed")
        buf += chunk
    return buf


def read_packet(sock):
    (length,) = struct.unpack("<i", read_exact(sock, 4))
    data = read_exact(sock, length)
    req_id, kind = struct.unpack("<ii", data[:8])
    return req_id, kind, data[8:-2].decode("utf8", "replace")


def run(commands, password, timeout=1800):
    with socket.create_connection((HOST, PORT), timeout=timeout) as s:
        s.sendall(pack(1, LOGIN, password))
        rid, _, _ = read_packet(s)
        if rid == -1:
            raise SystemExit("RCON auth failed")
        out = []
        for i, cmd in enumerate(commands, start=2):
            s.sendall(pack(i, COMMAND, cmd))
            _, _, body = read_packet(s)
            out.append(body)
        return out


if __name__ == "__main__":
    pw = Path(__file__).with_name(".rcon-password").read_text(encoding="utf8").strip()
    cmds = sys.argv[1:]
    if not cmds:
        raise SystemExit("usage: rcon.py <command> [command ...]")
    for reply in run(cmds, pw):
        print(reply if reply.strip() else "(no output)")
