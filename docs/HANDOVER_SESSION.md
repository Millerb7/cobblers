# Handover: session deb65fc9, ended 2026-10-21 evening

A cold session reads CLAUDE.md, `docs/STATE.md` and this file, and nothing else, before it starts.

## 1. Branch
`build/2026-10-21-challenge` (worktree `.claude/worktrees/mods-182`, holds `derived/`, `build/`, kits), off main
9a92ee38 (PR #156 merged). Pushed; NO PR yet. Commits: the Viltri berry stall, rips near players, the voucher in cash,
the 77 Challenge fights (rules), the generator field (`c5be914c`), STATE. Re-read the head with `git fetch --prune`.

## 2. Where it stopped
- Built and checked offline: `generate_trainers.py --check-active` ok, `income_model.py --check` current,
  `challenge_voucher.py --check` current, `validate_data` 0 errors; rip scheduler tests 290 passed, progression tests
  pass, contracts pass. Known failures NOT from this branch: 3 plaza tests (`displaced_city` missing from
  `data/plaza_centres.json` on main), 2 `test_challenge_mode_audit` mutation tests (fail at af3ce5c9 too).
- **Next:** at the owner's chosen time, `python tools/reapply.py prepare` on this branch (about an hour), then the
  install sequence (STATE "PREPARED, NOT INSTALLED" lists what goes in). After install: run `loot_fix.rcon.txt`
  section by section, swap the 4 legendary gate barrels to Lootr barrels (Zapdos (895,68,5582) s2, Articuno
  (682,311,379) s4, Moltres (6266,168,5361) s6, Crown Spire (5363,131,493) s5:
  `lootr:lootr_barrel{LootTable:"cobblers:chests/<stage>/legendary_adopted_<site>"}`), `run --only R17M,R13` for the
  berry stall, kill tag `cobblers_temp_berry_grower`, verify, strip, the owner restarts at 16G.
- **Session-owned, die with this session:** the bean sweep RCON loop (`nobeans_loop.py`, needed until the no-beans
  pack is installed: restart it if the server is up and the pack is not in), and the coordination lock held under
  owner `claude-loot-prepare-2026-10-21` (release it if no session is using the server).
- The server runs from the owner's own PowerShell window; never restart while players are on without the owner's yes.

## 3. Waiting on the owner
- The install time.
- Whether the Greenhollow Berry Specialist becomes a real stall (needs a seventh slot in a large square).
- Open from earlier: Nuzlocke page styling, Trading Post sub-menus, the coastal fishing-gap sweep, showing tree birds
  or hearts on the site, mint seeds in loot.

## 4. Do not rediscover
- An RCON command over about 1,400 bytes closes the connection: a merchant's shop must be summoned small and filled by
  `data modify`.
- A CobbleDollars merchant stores its shop as `CobbleDollars.Shop.shop[].{name, offers[].{item, price}}`, not the summon
  shape `CobbleMerchantShop`; set `CobbleDollars.Bank` to `{type:"registry",bank:"cobbledollars:default"}`.
- `forceload add` then a fixed 3 s wait is not enough: wait until the entity test passes.
- Selector arguments need an @-selector (`@a[name=X,...]`, never `X[...]`). TMCraft TMs are `tmcraft:tm_<move>`;
  `consumeMoveItemOnUse` is true (single use).
- The voucher was a written plan only (Oak's $4,000 built); the owner chose cash for every step.
- `docs/mechanics/CHALLENGE_ROUTES.md` lists the designer's open items: shared dialogue names members Challenge no
  longer has (Route 3 tells Challenge players to catch Ground types), Kingdra ASSUMED, learnsets unchecked.

## 5. Cost
`python tools/session_cost.py`: 891 turns, context 259k at the end, weighted 48.8M. Agents: the berry stall builder,
the Challenge designer (Opus), the generator builder.
