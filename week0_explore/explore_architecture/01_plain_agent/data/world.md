# World state — explored by dummy character

## Current state
- Zone: **Sewer, Second Level**
- Position: dark room with exits n/e/s (east = "Mid-Air" = death pit)
- HP: 24/24 (no damage taken yet this session but depleted from prior sessions)
- Mana: 100/100
- Movement: 5/85 (near zero — sleep didn't restore much; possibly AFK-blocked)
- Hunger: hungry + thirsty
- Inventory: empty
- Equipment: none

## What we've learned about The Bakery
- **Not found yet.** The bakery is almost certainly in Midgaard proper (zone 19)
  but the dummy character is trapped in the Sewer, Second Level with no light,
  no items, no way to leave.

## Surroundings (mapped from this position)
- dark: exit n, e (Mid-Air — kills), s
- s → dark room: exit n, s
- s, s → dark room: exit n
- n from start → dead end

## Blockers to finding the Bakery
1. **No light** — every room description is "It is pitch black..."
2. **No food/water** — character is starving; eventually dies
3. **No equipment** — can't fight sewer mobs for drops
4. **Low movement** — out of move points; can't explore far
5. **East is Mid-Air** — instant death fall

## What the dummy needs (in priority order)
1. A light source (torch/lantern) to see room names
2. Food + drink
3. Equipment / weapons to survive mobs
4. A path out of the sewer (probably up, but `u` from current room = closed rock)

## Useful MUD commands discovered
- `where` — shows current zone
- `score` — full HP/mana/moves stats
- `exits` — works in dark rooms ("Too dark to tell")
- `inventory` / `equipment` — what's carried/worn
- `wake` / `stand` / `sleep` — rest cycle
- `afk` — toggle AFK (sending twice turns it off)
- `flee` — escape combat
- `recall` — not a player command here