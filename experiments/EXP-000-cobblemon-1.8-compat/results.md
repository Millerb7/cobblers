# EXP-000 results

One row per boot attempt. `mod set hash` is the 12-char value printed by
`server/scripts/boot-test.ps1` (sha256 of the sorted jar list, also in
`runs/<timestamp>/mods.txt`). `outcome` is the script verdict:
BOOTED / CRASH / EXITED / TIMEOUT / pre-flight refused.

| # | date | run dir | mod set hash | cobblemon | loader | outcome | errors (short) | action taken |
|---|------|---------|--------------|-----------|--------|---------|----------------|--------------|
| 0 | | | | 1.7.3 | | | baseline, not yet run | |
| 1 | | | | 1.8.0 | | | Cobblemon swapped only, not yet run | |
| 2 | | | | 1.8.0 | | | overlay applied, not yet run | |

## Smoke tests (fill after a BOOTED row)

| test | date | players | result | notes |
|------|------|---------|--------|-------|
| server boots | | | | |
| client connects | | | | |
| /pokespawn | | | | |
| wild battle + catch | | | | |
| RCT trainer spawns and battles | | 2 | | |
| Mega evolution | | | | |
| TM machine | | | | |
| PC | | | | |
| Cobblenav / raid den / breeding | | | | |
| second client sees battle | | 2 | | |

## Environment (record once)

- Machine / OS:
- Java: (dev machine has Temurin 21.0.9)
- Fabric loader:
- Fabric API:
