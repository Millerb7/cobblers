# Morning report: launch night, 2026-10-14/15

Branch `build/2026-10-14-launch` (worktree `.claude/worktrees/mods-182`). Updated as the night goes; the last section
is the current state.

## Calls you made last night (recorded, not re-asked)
- Eight Challenge leaders with a new ace: fine. The 77 route/junior Challenge fights: not redesigned tonight.
- No cap on the Trading Post (about $3,800 an hour per pasture): fine. Kitchen and pharmacy goods SELL (built: 40 goods).
- The Trading Post's one-page 14-option dialogue: fine. Fossick and Northlight squares: built, with posts.
- Oak's rules pages rewritten; the battle guide's raw balance notes hidden; no wild Larvesta (Gible takes the South East
  Dunes' rare); voucher re-measured: unchanged at $23,748 (its grant is still not built).
- Hosting from this PC; a tunnel (playit.gg) recommended: `docs/launch/HOSTING.md`.

## Done before you went to bed
- #137 and #138 merged to main (f4268bcb). Launch work on `build/2026-10-14-launch`.
- Job D (rips that open and close at random): 80 candidates, the scheduler, the independent audit (15 generator
  mutations caught); its pause-survives-reload defect fixed; its pool-change-while-open defect recorded (close every
  rip, `function cobblers:rips/close_all`, before installing a pack that changes the candidate list).
- The server's mods swapped to the Cobblemon 1.8.2 set (101 jars); the old set kept in
  `cobblers-server-retired/mods-1.8.0-20261014`. A throwaway boot reached "Done" in 6.9 s.
- 1.8.2 fallout fixed as prepare found it: the bank file (CobbleDollars Beta-6.1 reads `default_bank.json`, a bare list
  with string prices: the real bank goes in that way), the install's hard-coded 1.8.0 jar name, Zamega's stones moved
  into Mega Showdown (three Z-A stones have no recipe; the Cutters still trade them), Tom's Storage's storage terminal
  (no longer locked with the crafting terminal), Showdown data zipped inside the 1.8.2 jar, the Tera-only Stellar type,
  the rip pool's siting notes read as places, and two rips re-sited clear of Fungal Isle's build.

## Overnight log
(each step below with its result)
- prepare stopped at coldwater_station_audit: the audit predated Kyogre's cave (R18KC) and the dialogue compiler's probes; fixed (0 problems, its known red test green)
- prepare stopped at nuzlocke_zones: stale after the Larvesta/Gible spawn change; regenerated (three zones' counts)
- prepare stopped at spawn_tiers_audit: the Great Crater had one rare without Larvesta; Carkol added as its second rare (Rolycoly's line, unused elsewhere); 92 areas pass
- prepare stopped at legendary_sweep_audit: rip_fungal_isle_3 was 20 blocks from the Newmoon Island legendary site; removed, Fungal Isle keeps 3 rip sites (no spot clears everything); rip_fungal_isle and _2 were moved earlier for Fungal Isle's own build
- prepare stopped at ambient_idle: the new Northlight square and Redbrow post collided with idle Pokemon scenes and the field hand's spot; the field hand moved mid-edge, two scenes allowed on the walkway, Redbrow's post re-sited (4833, 162, 5691)
- prepare's whole-build check: the 40 kitchen/pharmacy single-good sell functions were called by nothing (no menu line); sell/all now names them as operator entry points
- **PREPARE COMPLETE: all 242 jobs** on head b0547586 (full run, 2746 s; every function pack covered; 58 packs)
- staging install: every pack and config installed and current; the REAL bank (economy v2, 15 kinds) is the server's default_bank.json; 4 mod configs recorded (Cobbreeding's new alphaChances 0.05 accepted: a bred egg can hatch an alpha 5% of the time, your call)
