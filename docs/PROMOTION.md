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

Vanilla Minecraft doesn't log the address a player used. A small server-side mod does:
[Hostname Catcher](https://modrinth.com/mod/hostname-catcher) (GPL-3.0) logs
`Player NAME connected via: <address>`. It isn't in the pack yet: it was built for 26.2, so it needs a test
on 26.3 first, and its default config blocks every address except its examples, so it must ship with an empty
allow-list (`allowed-domains: []`). Once it's in, joins per address over a week are:

```sh
zgrep -h "connected via:" logs/*.log.gz logs/latest.log | sed 's/.*connected via: //' | sort | uniq -c
```

The count shows which address a player typed, not who bought: some buy and then switch to the main
address, and a player who joined on the free trial (docs/LIVE.md, "The store") counts before paying. Ask
new players in the Discord where they heard of the server too, and compare.

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
