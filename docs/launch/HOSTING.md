# Hosting from this PC: how friends reach the server

Written 2026-10-14 for launch. Nothing here was changed on the router or tested from outside: these are the steps,
not a report of them.

The server listens on **TCP 25565** on this PC. Friends need a route from the internet to that port. Two ways:

## Option A: a tunnel (playit.gg). RECOMMENDED for launch night

A small agent runs on this PC and gives you a public address (something like `name.playit.gg` or an IP and port).
Friends type that into Minecraft. The router is not touched.

- **Why for launch:** no router change; it works even if your ISP puts you behind carrier-grade NAT (where port
  forwarding cannot work at all); your home IP is not handed out.
- **Cost:** traffic goes through their relay, so a little more latency than a direct connection. For a co-op
  Pokemon server with a handful of players this is usually fine.
- **Steps:** create a free account at playit.gg, install the Windows agent on this PC, add a "Minecraft Java" tunnel
  pointing at `127.0.0.1:25565`, start the server, and give friends the address the agent shows. Keep the agent
  running while the server runs.

## Option B: port forwarding (direct)

- In the router's admin page, forward **TCP 25565** to this PC's LAN IP (find it with `ipconfig`: the IPv4 address
  of the active adapter). Give the PC a fixed LAN IP (a DHCP reservation) or the forward breaks when it changes.
- Allow Java through Windows Defender Firewall (inbound, TCP 25565, Private and Public as needed).
- Check you are not behind CGNAT: if the router's WAN IP differs from what a "what is my IP" site shows, forwarding
  will not work; use Option A.
- Friends connect to your public IP (or a free dynamic-DNS name, since home IPs change).
- **Cost:** your home IP is visible to anyone you give it to; the port is open to the whole internet, so the
  whitelist below matters.

## Either way

- Keep `online-mode=true` (the default) so only real Minecraft accounts join.
- **Whitelist:** turn it on and add each friend by their exact Minecraft username, from the server console:
  `whitelist on`, then `whitelist add <name>` for each. This was NOT done tonight: the friends' names are not in the
  repo, and `whitelist.json` must never be committed.
- The server runs at a 12G play heap (`-Xmx12G`). With your own client open on the same PC, close other heavy apps:
  a 16G server once died of a native memory error with the client open (memory: start-staging-in-terminal-panel).

## Later, not tonight

A VPS would free this PC and stay up when it sleeps. It needs roughly **24-32 GB of RAM** (24G for an apply, 12G to
play, plus the OS), and the tooling (PowerShell scripts, Windows paths in the tools) would need moving to Linux.
