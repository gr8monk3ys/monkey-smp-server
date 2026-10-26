# Promotion

How Monkey SMP finds players: free server lists, creators who play here, and clips from real event nights.
Nothing in here is posted, submitted or sent without an owner's OK. The accounts are the owners' own.

Three ground rules, everywhere:

- **Price and requirements up front.** Every listing says the server needs a paid pass ($5 a month or $14 for
  3 months) and Minecraft Java Edition on a PC with 16 GB of RAM. A player who finds out at the whitelist step
  feels tricked, and lists remove servers that hide a paywall.
- **Free placements only.** No paid list slots, auctions or vote buying. The pass and supporter tiers pay for
  the server (docs/RETENTION.md, "Budget"), not for ads.
- **Each place gets its own join address** (below), so we can see which one brought players in.

## The listing kit

Paste these as they are. Lists that have a field this kit doesn't cover get the website.

**Name:** `Monkey SMP | Modded Factions | Java 26.3`

**Short description** (under 150 characters, for lists that show one line):

> Modded factions on Java 26.3: factions of four, territory, PvP, Strength SMP, voice chat, weekly events. Paid pass, $5/mo.

**Long description:**

> Monkey SMP is a small modded factions server on Minecraft Java 26.3 (Fabric), for players who play evenings,
> Pacific time.
>
> - Factions of up to four, alliances, banner-marked territory nobody may grief. Everything outside it is
>   contested.
> - Strength SMP: win fights and your strength grows, lose them and it drains.
> - Tectonic, Terralith, Incendium and Nullscape terrain, with dungeons, taverns and capitals to raid.
> - Proximity voice chat, and a public 3D live map.
> - One event a week (Saturday, 6 pm Pacific): faction raids, arena nights, Dragon Night.
> - Up to 30 online, a pre-generated world on a dedicated CPU, 20 TPS.
>
> Access is a server pass: $5 a month or $14 for 3 months, the same for everyone. Supporter tiers are cosmetic
> only, and nothing sold gives an advantage or a place in line. You need Minecraft Java Edition on a PC
> (Windows, macOS or Linux) with 16 GB of RAM; the modpack installs in one click from the website. If it won't
> run in your first 48 hours, you get your money back.
>
> Website: https://monkeysmp.lscaturchio.xyz · Discord: https://discord.gg/C25hy9Ca9W

**Tags** (pick what each list offers): Factions, PvP, SMP, Modded, Survival, Whitelist, Teams, Voice chat,
Fabric, US West, English. Not Roleplay: the server has no roleplay rules, and a roleplay crowd
would be disappointed.

**Version:** Java 26.3. **Country:** United States. **Max players:** 30.

**Banner** (468 × 60, the size every list takes): `site/kit/server-list-468x60.png`, also served at
https://monkeysmp.lscaturchio.xyz/kit/server-list-468x60.png. **Icon** (64 × 64): `marketing/server-icon.png`.
The logo and the Discord banner are in `site/kit/` too.

**Links:** website https://monkeysmp.lscaturchio.xyz, Discord https://discord.gg/C25hy9Ca9W, map
https://map.monkeysmp.lscaturchio.xyz.

**Paid-server field:** where a list asks, say yes and link the pricing section,
https://monkeysmp.lscaturchio.xyz/#pricing. Lists that don't take whitelisted or paid servers are skipped.

### Where to list

All free to list on. Each needs an account the owner makes; the server address given is the one in the
"Address" column, so joins from lists can be counted.

| List | Address | Notes |
| --- | --- | --- |
| [Official Minecraft Server List](https://findmcserver.com) (findmcserver.com) | `find.monkeysmp.lscaturchio.xyz` | Run with Mojang; listed servers must follow the Usage Guidelines, which the one-price pass does. |
| [minecraft-server-list.com](https://minecraft-server-list.com) | `list.monkeysmp.lscaturchio.xyz` | |
| [minecraft-mp.com](https://minecraft-mp.com) | `list.monkeysmp.lscaturchio.xyz` | |
| [minecraftservers.org](https://minecraftservers.org) | `list.monkeysmp.lscaturchio.xyz` | |
| [topg.org](https://topg.org/minecraft-servers) | `list.monkeysmp.lscaturchio.xyz` | |
| [Planet Minecraft](https://www.planetminecraft.com/servers/) | `list.monkeysmp.lscaturchio.xyz` | Blocked our check (403); see whether it still takes server posts. |

The toplists share one address: each brings a few players at most, and one count for "the lists" is enough to
decide whether they are worth the votes. If one list turns out to bring most of them, give it its own.

Most toplists rank by votes and offer vote rewards through Votifier. Skip them: they hand out items for
something other than play, and would need one more mod. Ask players to vote in the Discord instead, if at all.

## Join addresses

A join address is a hostname that reaches the same server, one per place we promote it:
`yt.monkeysmp.lscaturchio.xyz` for YouTube, `tt.` for TikTok, `list.` for the toplists, `find.` for the
Official list, and one per creator on request (`<name>.monkeysmp.lscaturchio.xyz`). Players type it like the
main address.

### The DNS records

In Cloudflare, for each address, two records, both **DNS only** (grey cloud; Minecraft can't go through
Cloudflare's proxy):

| Type | Name | Content |
| --- | --- | --- |
| A | `yt.monkeysmp` | the VPS's IP, the same as the `play.monkeysmp` record |
| SRV | `_minecraft._tcp.yt.monkeysmp` | priority 0, weight 5, port 25565, target `yt.monkeysmp.lscaturchio.xyz` |

The same for `tt`, `list` and `find`. Leave every other record alone. The wildcard `*.lscaturchio.xyz` points
at Vercel, so a name without its own records reaches the website, not the server.

Why the SRV target is the address's own name and not `monkeysmp.lscaturchio.xyz`: a Minecraft client sends
the server the hostname it connected to *after* following the SRV record. An SRV that pointed at the main
name would make every address look like the main one, and nothing could be counted.

**On failover.** When the server fails over to playit (docs/LIVE.md), swap every join address's SRV record
to the playit address and port too, not just the main one, and swap them all back afterwards. A forgotten
one leaves its players on a dead address. Joins during a failover can't be counted by address.

### Counting joins per address

Vanilla Minecraft doesn't log the address a player used, so the server runs a small server-side mod that
does: [Hostname Catcher](https://modrinth.com/mod/hostname-catcher) (GPL-3.0). It's in the server pack, not
the client pack. Every join adds a line like this to the log:

```text
[20:15:02] [Server thread/INFO]: [STDOUT]: Player NAME connected via: yt.monkeysmp.lscaturchio.xyz
```

Modrinth lists it for 26.2 only; it was tested on 26.3 (docs/MAINTAINING.md, "Mods pinned by hand"). The mod
can also turn away players who come in through an address that isn't on its allow-list. The pack ships
`config/hostname-catcher.yml` with an empty list (`allowed-domains: []`), which lets every address in; keep it
that way. The mod's own default lists only `localhost`, `127.0.0.1` and `*.example.com`, so it would turn away
every real player with "Connection Throttled.".

Joins per address, on the VPS (`--since` counts from that day on, e.g. the start of a campaign):

```sh
python3 /srv/realms/repo/tools/join_addresses.py /srv/realms/TheRealms-Server/server/logs --since 2026-11-01
```

It prints, for each address, the joins, the different players, and the **new** players: those whose first
logged join came through it. The new column is the one that says which channel brought players in.

The count shows which address a player typed, not who bought: some buy and then switch to the main
address, and a player who joined on the free trial (docs/LIVE.md, "The store") counts before paying. Ask
new players in the Discord where they heard of the server too, and compare.

## Season I launch announcements

Drafts for Season I's launch, Saturday 21 November 2026 at 5 PM Pacific. When each one goes out, and where,
is in docs/LAUNCH.md, "Announcement schedule"; the founding roster post (T-14) and the moderator post are in
docs/LAUNCH.md too. Like everything here, nothing is posted until an owner says yes.

- **Lines marked [needs ...]** mention work that isn't merged yet. Each stays only if that work is in the
  release tagged by Friday 13 November (docs/LAUNCH.md, "Copy that depends on unmerged work"). Delete the
  marker before posting.
- **Lines marked [store]** or **[by hand]**: keep the one that is true on the day. The store's link goes on the
  site at 5 PM on launch day (docs/LAUNCH.md, "The store").
- **Addresses.** The lists use their join addresses from the table above. Reddit and the Discord have none of
  their own yet, so they use the main address. To count Reddit on its own, add `rd.monkeysmp` records (as in
  "The DNS records") before 14 November and use `rd.monkeysmp.lscaturchio.xyz` in the Reddit post.
- **Discord times** are written as Discord timestamps (`<t:1795309200:F>` is 21 November, 5 PM Pacific), so
  every reader sees their own time. Each Discord draft is under Discord's 2,000-character limit.
- **Line breaks.** The drafts are wrapped to fit this file. Reddit joins the lines of a paragraph by itself;
  Discord doesn't, so join each paragraph and list item into one line before pasting it there.

### The free lists

From Saturday 7 November until launch, swap the short description and put this line at the top of the long
one. Everything else in the listing kit stays.

**Short description** (under 150 characters):

> Modded factions on Java 26.3. Season I opens Sat 21 Nov, 5 PM PT. Factions of four, PvP, weekly events. Paid pass $5/mo.

**First line of the long description:**

> **Season I opens Saturday 21 November 2026 at 5 PM Pacific (8 PM Eastern).** Everyone gets in at the same
> moment: the first hour is peaceful, then PvP and the Nether open. Sign up for the founding roster in the
> Discord; it's free, and the order is first come, first served.

From Sunday 22 November, 9 AM, swap them for:

> Modded factions on Java 26.3. Season I is live until 6 Feb. Factions of four, PvP, weekly events. Paid pass $5/mo.

> **Season I is live**, from 21 November 2026 to 6 February 2027, with an event every Saturday at 6 PM Pacific.

### Reddit (r/mcservers)

We couldn't read r/mcservers' rules from here (the page didn't load), so read them and the flair list before
posting, and fit the title to the format they ask for. Server subreddits usually want the version and tags in
the title, the price stated, and no more than one post every so often. One post, on Saturday 14 November;
answer comments from the same account that day. Other subreddits only after reading their rules too.

**Title:**

> [Java 26.3] [Modded] [Factions] [Paid] Monkey SMP: Season I opens Saturday 21 November, 5 PM Pacific

**Body:**

> **Monkey SMP** is a small modded factions server on Minecraft Java 26.3 (Fabric), for people who play
> evenings, Pacific time. **Season I opens Saturday 21 November at 5 PM Pacific / 8 PM Eastern**, with
> everyone let in at the same moment, and runs to 6 February 2027.
>
> - Factions of up to four, alliances, and banner-marked territory nobody may grief. Everything outside it is
>   contested.
> - Strength SMP: win fights and your strength grows, lose them and it drains.
> - Tectonic, Terralith, Incendium and Nullscape terrain, with dungeons, taverns and capitals to raid.
> - An event every Saturday at 6 PM Pacific: faction raids, arena nights, Dragon Night. Launch weekend is a
>   Build Battle.
> - Weekly faction standings and a bounty board. [needs #42]
> - Weekly challenges. [needs weekly challenges]
> - Player shops in chests, priced in items. [needs shop chests]
> - Proximity voice chat and a public live map.
> - Up to 30 online, a pre-generated world, 20 TPS.
>
> **It's paid:** a server pass, $5 a month or $14 for 3 months, the same for everyone. Supporter tiers are
> cosmetic only, and nothing sold gives an advantage or a place in line. You need Minecraft Java Edition on a
> PC with 16 GB of RAM; the modpack installs in one click from the website. If it won't run in your first 48
> hours, you get your money back.
>
> **Founding roster:** the first 30 to sign up in the Discord are in on launch night, in the order they
> signed up. Signing up is free. Play launch weekend and you keep the Founder skin for good; it's never
> sold. [needs the Founder skin]
>
> - Website and modpack: https://monkeysmp.lscaturchio.xyz
> - Discord: https://discord.gg/C25hy9Ca9W
> - Address, from launch: `monkeysmp.lscaturchio.xyz`
> - Live map: https://map.monkeysmp.lscaturchio.xyz

### Discord

**T-14, Saturday 7 November:** the founding roster post in docs/LAUNCH.md.

**T-7, Saturday 14 November, 5 PM, `#announcements`:**

> **One week: Monkey SMP Season I opens <t:1795309200:F>** (<t:1795309200:R>)
>
> **Register your faction** from today in #smp-forum: one post with the faction's name, its members'
> Minecraft names (up to four), its banner, and a charter: a paragraph on who you are and what you're after
> this season. Solo? Say so in #smp-forum and staff will find you a faction.
>
> **Install the modpack now**, not on launch night: https://monkeysmp.lscaturchio.xyz/#join
> Start it once and get to the main menu. If it won't run, open a ticket and we'll sort it out this week.
>
> **Founding roster:** N of 30 places taken. Sign up in #founding-roster: free, first come, first served.
>
> **New this season**
> - The Build Battle: the wheel spins at 5 PM on launch night, judging Sunday at 6 PM.
> - Weekly faction standings and a bounty board. [needs #42]
> - Weekly challenges. [needs weekly challenges]
> - Shops in chests, priced in items. [needs shop chests]
> - Play launch weekend and keep the Founder skin for good. Never sold. [needs the Founder skin]
>
> A pass is $5 a month, the same for everyone. [store] The store opens at 5 PM on launch day. [by hand]
> Until the store opens, arrange yours in a ticket.

**T-1, Friday 20 November, 5 PM, `#announcements` and `#monkey-smp`:**

> **Tomorrow: Monkey SMP Season I opens <t:1795309200:F>** (<t:1795309200:R>)
>
> Tonight:
> 1. **Update the modpack** from https://monkeysmp.lscaturchio.xyz/#join, start it and get to the main menu.
>    Stuck? Open a ticket tonight, not at 5 tomorrow.
> 2. **Sort out your pass.** [store] The store opens at 5 PM tomorrow, on the website. [by hand] Arrange it in
>    a ticket by tonight.
> 3. **Hit "Interested"** on the launch event for a reminder.
>
> How launch works:
> - Everyone gets in at 5 PM. For the first hour there's no PvP and no Nether. PvP and the Nether open at
>   6 PM; the End stays closed until we announce it.
> - The Build Battle wheel spins at 5: three bonus blocks. Factions build on their plot next to spawn, and
>   judging is Sunday at 6 PM (<t:1795399200:F>).
> - No Netherite armor until we say so. The border starts at 2500 × 2500 and grows with the season.
> - Play launch weekend and keep the Founder skin. [needs the Founder skin]
> - New here? The monthly pass starts with 7 free days. [only if the trial is on]
> - The rules: https://monkeysmp.lscaturchio.xyz/#rules (the full rulebook is in #smp-rules).
>
> Address: `monkeysmp.lscaturchio.xyz`

**T-1h, Saturday 21 November, 4 PM, `#monkey-smp`:**

> **One hour.** Season I opens <t:1795309200:t> (<t:1795309200:R>).
>
> Start the modpack now and let it load; the first start takes a few minutes.
> Address: `monkeysmp.lscaturchio.xyz`
>
> The Build Battle wheel's seed is **S1 launch**, posted before the spin so nobody can pick the draw after
> seeing it.
>
> We're recording tonight for the server's clips. Don't want to be in them? Say so here or in chat and
> you'll be cut out. No voice chat is recorded.

**Launch, Saturday 21 November, 5 PM, `#announcements` and `#monkey-smp`:**

> @everyone **Season I is open.** `monkeysmp.lscaturchio.xyz`
>
> **The wheel:** BLOCK 1, BLOCK 2, BLOCK 3 (seed "S1 launch"). Each scores when at least 9 of it can be
> seen from your plot's edge.
>
> - No PvP and no Nether until <t:1795312800:t>.
> - Build Battle judging: <t:1795399200:F>.
> - The Founder skin is yours if you play before Sunday midnight Pacific (<t:1795420800:F>).
>   [needs the Founder skin]
> - [store] Get a pass: https://monkeysmp.lscaturchio.xyz/#pricing
> - Can't get in? Ask in #help or open a ticket.

## Creators

Who to ask: small Minecraft creators (roughly 500 to 20,000 subscribers) who post factions, SMP or
modded-survival videos, or who run roleplay or faction series and need a server for one. A creator who plays
here every week for a season is worth more than one big video. Not: channels aimed at young children, or
anyone whose recent videos are drama about other servers.

The terms are on https://monkeysmp.lscaturchio.xyz/creators.html: 20% of each 3-month pass bought with their
code, no discount for the buyer, and the #ad disclosure. Send them the page, don't restate it.

Message template (Discord DM, email from the channel's About page, or a reply on their Discord; one message,
no follow-up spam):

> Hi NAME, I'm Lorenzo, one of the two people running Monkey SMP, a small modded factions server on Java 26.3
> (factions of four, territory, Strength SMP, proximity voice, a weekly raid or arena night).
>
> I liked VIDEO. If you're looking for a server for a series, you'd be welcome to play here for free, and you
> can have a creator code that pays you 20% of each 3-month pass your viewers buy with it. The terms are
> here: https://monkeysmp.lscaturchio.xyz/creators.html
>
> No pressure either way. If it's not for you, no reply needed.

Fill in NAME and a real VIDEO of theirs (one you watched), and send from the owner's own account. A creator
who says yes gets a free pass (staff whitelist them by hand), a join address and a code in Tebex.

## Clips from real event nights

The trailer on the site is staged on a test server with stand-in players, and says so. Replace it with clips
from real Saturday events once there are three or four good ones.

- **Recording.** A staff account in spectator mode records the event with OBS at 1080p60. One camera account, so nobody plays and films at once.
- **Consent.** Announce in the event post and in chat before it starts that the event is recorded for the
  server's clips, and that anyone who doesn't want to be in them can say so and is cut out. Player names stay
  visible only for players who said yes; blur the rest.
- **Sound.** No players' voice chat in published clips (many players are under 18). Game sound and a music
  bed only (`marketing/music.py` synthesises one).
- **Cuts.** 15 to 30 seconds each, one moment per clip: a flag carried home, an arena last-man, the dragon
  going down. Export 9:16 (TikTok, Shorts, Reels) and 16:9 (the site, YouTube). Show the join address for the
  channel on screen for the last 3 seconds.
- **Storage.** Raw recordings in `D:\DevData\monkey-smp-marketing\footage\real\`, never in the repo.
- **The site.** When three or four real clips exist, cut a new trailer from them (`marketing/trailer.py`)
  and change the caption to say what it shows. The "staged" caption goes with the old trailer.

Posting a clip is an owner's call, every time.

## If there's money for ads later

None now. If the server is full on event nights and the waitlist is growing, a small boosted-post test
(one clip, a few dollars a day for a week, the `yt.` or `tt.` address on screen) shows whether paid reach
brings paying players. Count joins on that address before spending more.
