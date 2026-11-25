# Season 1 (relaunch): the plan

Ten weeks, from the launch on **Saturday 6 February 2027** to the finale on **Saturday 10 April 2027**,
then an off-week and Season 2 on **Saturday 17 April**. Every season after follows the same shape in 8 to
10 weeks. Times are Pacific; Saturday events start at **6 PM Pacific (9 PM Eastern)**. US clocks go
forward on Sunday 14 March, which moves nothing in Pacific time.

`tools/season_calendar.py` has these dates as `RELAUNCH`, `RELAUNCH_FINALE` and `RELAUNCH_NEXT`. Its `SEASON`
stays on the modded Season I, which the live server's timers read, until the release that switches the tools to
Paper after that season's finale on 23 January 2027. The tool counts the launch weekend as week 0, so its week N
is week N+1 in the table below.

## The calendar

| Week | Saturday | Event | Also |
| --- | --- | --- | --- |
| 1 | 6 Feb | **Launch, 5 PM.** Spawn and the market open. The world border is 6,000 wide; the End is closed. | Everyone starts with 10 hearts and 3 hours of newbie protection. |
| 2 | 13 Feb | **King of the Hill I.** Hold the hill outside spawn for the most time over an hour. | |
| 3 | 20 Feb | **The border opens** to 8,000 at 6 PM. | |
| 4 | 27 Feb | **Revival Night I** at 6 PM, then **Dragon Night**: the End opens at 7 PM. | Late-joiner catch-up turns on (below). |
| 5 | 6 Mar | **Base of the Week**: staff tour and judge claimed bases. No PvP stakes. | |
| 6 | 13 Mar | **The border opens** to 10,000, and **the Edgewalker** rises at the new edge. | Clocks go forward Sunday. |
| 7 | 20 Mar | **Revival Night II**, then **King of the Hill II**. Season 2's date is announced, 4 weeks ahead. | Last revival by staff this season. |
| 8 | 27 Mar | **Supply Drop**: a guarded chest at an announced spot, with Crafted Hearts inside. | Easter is Sunday 28 March. |
| 9 | 3 Apr | **The closing.** The finale's details are posted, and over the week the border shrinks from 10,000 to 3,000. | Revive Beacons and the 24-hour return still work; staff revive no one. |
| 10 | 10 Apr | **The finale** (below). The world locks after it. | |
| | 11 to 16 Apr | **Off-week**: the world download goes up, the finale video goes out, the Season 2 vote, a creative night. | |
| | 17 Apr | **Season 2 opens.** | |

- **Say the end date on day one:** Season 1 ends with the finale on Saturday 10 April 2027. It's in the
  launch announcement, the welcome message and the website from the start, so nobody is surprised by a reset
  and creators can plan a story around it.
- **Event rewards** are Crafted Hearts (they only work below 15, so they can't crown anyone) and
  cosmetics. Money prizes are the economy's call.
- **King of the Hill:** a small capture area outside the safe zone; the player with the most time on it
  wins. Hearts are at stake as everywhere.

## The finale

1. **6 PM:** staff announce it. The border starts shrinking from 3,000 to 256 around the finale monument,
   over 45 minutes. Players outside take border damage.
2. **6:45 PM:** the last hour. The border holds at 256. Every second, each team scores a point for each of its
   members standing at the monument. Kills still move hearts; eliminated players stay out.
3. **7:45 PM:** the team with the most points wins (a solo player is a team of one). A tie goes to the team
   with the most hearts between its members still in, which staff check.
4. The champion gets the season's champion title and cosmetic, which carry into Season 2.

- **It's filmed.** A staff member records the finale in spectator mode from above the ring, and the brand
  team cuts a recap video for the off-week. Players are told in the finale announcement that it's being filmed.
- **Nobody comes back during it.** Revive Beacons and the 24-hour return stop at 6 PM; eliminated players stay
  out until Season 2.
- **The world download:** once the world is locked, staff publish it (spawn, the market and the finale ring,
  with player bases as they stood) for anyone to explore. Nothing in it identifies players beyond their builds
  and signs.

### Porting the finale and the boss to Paper

The modded season's finale and border boss (`tools/finale.py`, `tools/boss.py`) are datapacks, which Paper
still runs, but both score by faction (`st.faction`, the Open Parties and Claims party), and there are no
factions on Paper. Before week 6 they need:

- **Scoring per team** in place of per faction: the finale already scores each faction's member-time at the
  monument, so it keeps that, reading team numbers, with hearts as the tiebreak staff check. The boss's kill
  announcement names the player, and their team if they have one.
- **Teams only for the finale:** players register a team of up to 4 by ticket before week 9, and staff give
  its members the same team number; everyone else is a team of one. No team plugin.
- The border acts above in `ACTS` (`tools/border.py`): 8,000 in week 3 and 10,000 in week 6, with the
  week 9 shrink and the finale's 256. Vanilla `/worldborder` works on Paper over RCON as before.

That port, and the 24-hour return timer, are a follow-up PR for the tools; this one sets the plan and the dates.

## Late joiners

- **From week 4:** newbie protection rises from 3 to 8 hours. Staff set `Newbie Protection.Time` to `28800`
  in `PvPManager/config.yml` and run `/pvpmanager reload`.
- **A starter kit on first join**, from week 4: iron armor and tools, 32 cooked beef, 32 torches and a bed.
  From week 7, also diamond pickaxe and sword. (An EssentialsX first-join kit, set up by the platform.)
- **Hearts don't change**: a late joiner starts with 10 like everyone. Crafted Hearts and Revival Nights
  are the catch-up for hearts.
- Claim blocks build up with play time as for everyone; staff don't hand them out.

## What resets and what carries over

| Resets every season | Carries over |
| --- | --- |
| The world and the border | Cosmetics: titles, tags, the season badge, the champion cosmetic |
| Hearts, heart items, revives | Permanent bans |
| Items, money, shops | |
| Claims and claim blocks | |
| Warnings and temporary bans | |

What paid ranks keep between seasons is set by the store's terms, not here.

## Running the week

- **Monday:** post the week's event in game and on the Discord.
- **Saturday, 30 minutes before:** remind in game; check spark for lag before the event starts.
- **Revival Nights:** `staff-guide.md`, "Revival Night".
- **Border changes:** announce 24 hours ahead and again at the moment it moves.
