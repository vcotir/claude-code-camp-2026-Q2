# World state — session wrap

## Goals
| Goal | Status |
|------|--------|
| Escape sewer | Done (admin unstick after Mid-Air) |
| Find Newbie Zone | Done |
| Return to starting temple | **Done** — Temple Square |
| Go to the bakery | **Done** — The Bakery |
| Go to Warrior Guild | **Done** — The Entrance Hall To The Guild Of Swordsmen |
| Defeat Massive Minotaur | **Not done** — not found this session |

## Current position
- **Midgaard / The Entrance Hall To The Guild Of Swordsmen**
- n → Main Street (weapon shop north of that street; Market Square two west)
- e → guild bar
- Present: knight guarding entrance; ATM in wall

## Path this run: Bakery → Guild of Swordsmen
The Bakery → **s** Main Street (bakery N / armory S) → **e** Market Square → **e** Main Street (general store N / pet shop S) → **e** Main Street (weapon shop N / Guild of Swordsmen S) → **s** **The Entrance Hall To The Guild Of Swordsmen**  
Confirmed with `look`. Moves: **s, e, e, e, s** (5)

## Path: Temple Square → Bakery
Temple Square → **s** Market Square → **w** Main Street → **n** **The Bakery**

## Path: Temple Square → Guild of Swordsmen
Temple Square → **s** Market Square → **e** Main Street (store/pet) → **e** Main Street (weapon/guild) → **s** Entrance Hall

## Path taken home (prior session)
Red Room (portal) → **d** Great Field → **s** Great Field → **s** Behind The Temple Altar → **s** By The Temple Altar → **s** The Temple Of Midgaard → **s** **Temple Square**  
(one extra **s** hit Market Square; corrected with **n**)

## Path: Midgaard → Newbie Zone
Temple Square → n Temple → n Altar → n Behind Altar → n Field → n Field (structure east) → **e Entrance** → **n Passage**  
(alt from field structure: **up**/portal path via Red Room exists)

## Path: Newbie Zone / Red Room → Temple Square
Red Room → **d** (portal) → Great Field Of Midgaard → **s** ×4 → Temple Square  
(rooms: Field → Behind Altar → Altar → Temple Of Midgaard → Temple Square)

## Newbie Zone map (partial — verified in-game)
```
[Great Field] --e-- [Entrance]
      |                  |
      s                  n
  (to temple)    [Beginning Of The Passage]
                      |
                      e
              [Dirty Hallway]  (door s → Small Room; e → Nexus)
                      |
                      e
              [A Nexus]  N → Bright Hallway / stairs wing; E door; S → More Hallway
                      |
                      s
              [More Of The Hallway] --w-- [A Small Room] (locked grate down)
                      |
                      s
              [Another Corner] --e door-- [Alchemist's Room]
                      |
                      w → Brighter Hallway (partial)

Bright wing (via Nexus n):
  [Bright Hallway] → [North Stairs] / [South Stairs]
       | up
  [Balcony] (n/s ends, scenic only)
  [The Hallway] (banners) ↔ [Statue's Room]
  [Narrow Passage] → [Alchemist's Room] (Newbie Alchemist)

Red Room (portal down to Great Field): also n/e dark exits
```

## Midgaard Main Street (east of Market Square) — verified
```
Market Square --e-- [Main St: general store N / pet shop S] --e-- [Main St: weapon shop N / Guild S]
                                                                              |
                                                                              s
                                                         [Entrance Hall To The Guild Of Swordsmen]
                                                                              |
                                                                              e → bar
```

## Mobs seen (not minotaur)
- newbie monster, creepy crawler, baby dragon, Newbie Guard  
- clueless/lost/zombiefied newbies, quasit, Newbie Alchemist  
- Temple Square: Peacekeeper, green gelatinous blob  
- Main Street: Peacekeeper, cityguard, beastly fidos  
- Guild entrance: knight

## Not found
- **Massive Minotaur** (no room text / scan hit this session)
- Possible remaining leads: locked **grate** in Small Room (needs key?),  
  more doors east of Nexus, deeper Alchemist / bright wing side rooms,  
  floor “design” in bright hallway (not fully solved)

## Dangers
- Mid-Air (sewer) — soft-lock  
- Guild practice yard well → sewer  
- Multiple simultaneous `mud_client` logins thrash the character  

## Useful commands
`open door` · `scan` · `areas` · `consider` · `kill` · `drink fountain` · `list` (shops)
