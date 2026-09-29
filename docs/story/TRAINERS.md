# Trainer roster generation

**Status:** Normal and Challenge source data is generated for all eight gyms and Routes 1–8. Normal remains the runtime-compatible top-level payload. The mode selector, revised gym installation, and AI behavior are not runtime-proven.

The complete battle design is in [TRAINER_MODE_DESIGN.md](TRAINER_MODE_DESIGN.md). The editable source is `TRAINER_RULES.json`; `data/trainers.json` must not be hand-edited.

```text
python docs/story/generate_trainers.py --write-active
python docs/story/generate_trainers.py --check-active
```

The active command rebuilds all boss records and Routes 1–8, then preserves Victory Road's blocked records. Full generation remains intentionally red until the obsolete surface-route pins are reconciled with the built ten-fight cave network.

## Generated contract

| Rule | Value |
| --- | --- |
| Modes | `normal`, `challenge` |
| Gym ace curve | `20/25/30/35/40/45/50/55` in both modes |
| Level inflation | None; both modes use cap offset `0` |
| Normal gym sizes | `3/3/4/4/5/5/5/6` |
| Challenge gym sizes | `4/4/4/5/6/6/6/6` |
| Route density | 49 required trainers plus 1 optional Lake Viltri shore trainer; unchanged between modes |
| Route mode delta | Sharper AI, one modest held item, and one extra member only for strategist/final-rehearsal roles |
| Compatibility | Top-level `team` and `rct` mirror Normal; full variants live under `modes` |
| Mode selection | Intended as one server-wide campaign setting; not implemented |

`maxSelectMargin` stays positive because RCT treats it as a random bound. RCT calls the requested stat/status preference `statusMoveBias`; `statMoveBias` is not a valid field.

## Gym identities

| Gym | Theme | Normal | Challenge delta |
| ---: | --- | --- | --- |
| 1 Brock | Fault Line | Rock Tomb speed tax; Sturdy Onix gets one action. | Adds Cranidos; Weakness Policy Onix asks for a preserved second answer. |
| 2 Misty | Lake Tempo | Five-turn rain into speed control and recovery. | Adds Lightning Rod Goldeen; Grass remains untouched. |
| 3 Surge | Closed Circuit | Paralysis and mixed Electric pressure; no Ground coverage on Raichu. | Adds Light Screen and a one-hit Air Balloon delay; no Grass Knot. |
| 4 Erika | Glasshouse Sun | One sun engine, two beneficiaries, one Coba Berry check. | Adds Tangrowth and Heat Rock; no sleep/hazard/Sash pile. |
| 5 Koga | Venom Clock | Direct poison into Venoshock; Drapion checks Psychic. | Adds Dragalge; no Toxic Spikes, Tailwind, or Quiver Dance stack. |
| 6 Sabrina | Wrong Clock | Slow Trick Room phase, then fast Alakazam closer. | Adds Reuniclus; no terrain, doubles, or extra anti-Dark coverage. |
| 7 Blaine | Pressure Front | Sun changes Water math; Rock and Ground remain clean. | Adds Magmortar and one Shell Smash threat; no Solar Beam surprise. |
| 8 Giovanni | Fault Command | Sand, tempo interruption, physical anchor, visible Rock Polish ace. | Same six with Smooth Rock, Taunt, and one Rindo Berry; singles until doubles is proven. |

## Route identities

| Leg | Theme | Teaching purpose |
| --- | --- | --- |
| Route 1 | First Ascent | Roles, switching, speed loss, and preserving two Rock answers. |
| Route 2 | Lake Tempo | Denial, recovery pressure, and independent Electric/Grass plans. |
| Route 3 | Mountain Circuit | Ground immunity, resistance, priority, and paralysis recovery. |
| Route 4 | Alpine Sunbreak | Ice/Flying answers, then one setter-to-beneficiary weather sequence. |
| Route 5 | Venom Clock | Poison pressure and why Psychic needs a second line. |
| Route 6 | Wrong Clock | Trick Room, priority, bulk, and Dark immunity. |
| Route 7 | Weather Front | Contest sun with Water, Ground, Rock, or replacement weather. |
| Route 8 | Fault Lines | Water/Grass offense, Ground immunity, Fighting, and priority into Ground teams. |
| Victory Road | League Examination | One known lesson per cave fight; topology still blocked. |

Routes 4–8 now use explicit species teams so their generated battles demonstrate the lesson named in the data. Routes 1–3 retain their authored dialogue and exact seats. All route placements remain at the current route coordinates; this pass does not place or move entities.

## Elite Four and Champion

The existing five six-member rosters are preserved. They currently receive identical Normal and Challenge payloads so the schema is complete, but their separate Challenge deltas are deferred. Their ceilings remain Elite Four `60` and Champion `62`.

## Validation boundary

The generator checks deterministic output, the exact gym ace curve, one ace per concrete mode, team size, level bounds, move count, IV/EV bounds, exact RCT AI keys, positive selection margins, ordered route pins, and route-polyline anchors.

The `--write-active` boundary is explicit: bosses and Routes 1–8 are rebuilt; Victory Road is preserved because its source still describes obsolete surface placements. This prevents an unrelated topology defect from silently rewriting the active campaign data.

Format validity does not prove behavior. Weather/support move choice, Sturdy plus Weakness Policy, Air Balloon, Coba/Rindo berries, poison-aware Venoshock selection, Trick Room sequencing, items, switching, multiplayer isolation, and runtime mode selection still require Minecraft tests.
