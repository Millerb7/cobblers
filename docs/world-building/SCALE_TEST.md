# EXP-009 scale playtest

## Launch and setup

1. In `experiments/EXP-000-cobblemon-1.8-compat/runtime/server/server.properties`,
   confirm `level-name=exp009-hex-prototype`.
2. From that server directory, run:
   `& 'C:\Program Files\Eclipse Adoptium\jdk-21.0.9.10-hotspot\bin\java.exe' -Xms3072M -Xmx6144M -jar fabric-server-launch.jar -nogui`.
3. Join with the matching complete-overlay client, then run:
   `/gamemode creative @s`, `/gamerule doDaylightCycle false`, `/time set day`,
   and `/tp @s 520 100 560`. Descend into Brookstep; its generated surface is
   near Y 78.
4. Obtain the two land controls with `/pokegive mudsdale level=50` and
   `/pokegive rapidash level=50`. If direct giving is inconvenient, use
   `/pokespawn mudsdale level=50` and `/pokespawn rapidash level=50`, then catch
   them in Creative. The running server reports `/pokegive <properties>` and
   `/pokespawn <properties>` for these commands.
5. Send out each Pokémon and use Cobblemon's normal mount interaction. No
   riding gamerule or extra permission command is required. Operator permission
   is required only for the setup commands above.

Do not infer travel time from distance. Record each route manually on foot,
Mudsdale, and Rapidash, then classify the 1,250-block scale as **too condensed**,
**promising**, or **too empty**.

## Measured routes

Coordinates use the deterministic terrain surface Y. Distances are straight-line
horizontal distances between the stated endpoints.

| Route | Start | End | Distance | Intended terrain/path character |
| --- | --- | --- | ---: | --- |
| A. Town → nearest medium event | Brookstep `(520, 78, 560)` | Disposable D4 meadow marker `(930, 80, 790)` | 470.1 blocks | Open meadow road becoming a lightly rolling approach to a placeholder fenced arena. This measures scale; it is not the authored trial. |
| B. Town → adjacent hex center | Brookstep `(520, 78, 560)` | D5 center `(1875, 93, 625)` | 1,356.6 blocks | Main eastbound dirt path, river crossing reservation, then forest-edge travel. |
| C. Opposite sides of one hex | D4 west `(25, 82, 625)` | D4 east `(1225, 59, 625)` | 1,200.0 blocks | Broad lowland traverse through town influence toward the river bank. |
| D. Longest useful prototype route | D4 berry grove `(280, 90, 1040)` | E5 cavern `(2150, 166, 1840)` | 2,033.9 blocks | Diagonal journey from meadow edge through river valley into steep rocky foothills. |

## Sightline observations

- **Town reveal:** stand at `(900, 75, 600)` and look west. Check whether the
  town becomes legible at a useful approach distance without exposing every lot.
- **Forest threshold:** stand at `(1350, 71, 500)` and travel east to
  `(1900, 90, 500)`. Check whether the forest gains enough depth and concealment.
- **Ridge occlusion:** compare the west flank `(1500, 120, 1800)` with the far
  side `(2200, 155, 1800)`. Check whether the ridge hides the opposite region
  before the crest and reveals it deliberately afterward.
- **Macro seam:** inspect around `(1250, 85, 1250)`. Check whether river,
  foothill, and forest transitions read as natural geography rather than four
  tiled cells.
- **Town panorama:** stand at the generated landmark `(750, 73, 720)` and scan
  back toward Brookstep and east toward the route. Check town framing and whether
  the neighboring macro-region appears too early.

Inspect the Pokémon Center, Poké Mart, six settlement pieces, plaza, landmark,
road, foundations, doors, and functional blocks. WorldEdit remains uninstalled;
decide whether it is useful as a development-only tool after this playtest.
