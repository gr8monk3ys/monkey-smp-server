# Monkey SMP: player growth plan (written 2026-11-08)

Not committed. Nothing in here is posted, paid for or sent. Each post, listing, DM and ad is the
owner's call, one item at a time. The older kit in `docs/PROMOTION.md` still holds; this file ranks the channels
and replaces the drafts that are now out of date.

## Read this first: the server can't take a flood yet

- On launch night, 12 players used all of the VPS's CPU. The server holds 30 at most.
- v3.2.0 has the performance work. It installs on 11-09 at 4 AM. Nobody knows yet how many players it can
  carry.
- A paid pass is a sale. If we sell 25 passes and the server lags, we owe refunds and get bad reviews.
- **So grow in two waves.**
  - **Wave 1 (now):** low-volume channels. These are referrals, server lists and Discord directories. They bring
    a few players a week.
  - **Wave 2 (after a check):** Reddit, clips and creators. These can bring 10 to 30 players in a day. Start
    them only when `spark tps` stays at 19 or more with 15 or more players on 3.2.0.
- **The other way out is a bigger VPS.** Reizor Dallas with 3 threads cost $67.50 a month on 11-04 (my
  last reading; prices and stock change). That is $22.50 a month more. It pays for itself at about 5 more
  $5 passes. The owner decides this, after the 3.2.0 numbers.

## The ranking

"Joins" here means new **paying** players. There is no free trial, so nobody joins without a pass. All the
numbers are **my guess** for a small paid modded server. Nothing here is measured yet. Use
`tools/join_addresses.py` after two weeks to replace the guesses with real counts.

| # | Channel | Owner time | New players (guess) | Joins per hour | Wave |
| --- | --- | --- | --- | --- | --- |
| 1 | Bring-your-faction push to current players | 30 min | 3 to 8 | ~10 | 1 |
| 2 | Server lists (Official list, Planet Minecraft, 4 toplists) | 2 h once, then 10 min a week | 2 to 6 a month | ~2 | 1 |
| 3 | Reddit (r/mcservers, one post) | 1.5 h (post + answer comments) | 2 to 8 | ~3 | 2 |
| 4 | Short clips (TikTok, YouTube Shorts) | 1 to 2 h per clip | 0 to 20 per clip (mostly 0 to 2) | ~1, big upside | 2 |
| 5 | Creator collabs | 15 min per DM, ~10 DMs | 0 to 20 per "yes" | ~1, big upside | 2 |
| 6 | Discord directories (Disboard and others) | 5 min a day | 0 to 2 a month | <0.5 | 1 |
| 7 | Modrinth modpack page | 1 h to update | 0 to 2 a month | <0.5 | later |
| 8 | Paid ads | money + 2 h | unknown | n/a | not now |

**Top 3 by joins per hour of owner effort:** (1) the bring-your-faction push, (3) Reddit and (2) server lists.
Clips and creators come next. They have the biggest upside but the most variance. They also need the
capacity check first.

**When doing nothing is better:** if 3.2.0 still has no headroom at 12 players, stop after wave 1 until the
VPS question is settled. More buyers on a lagging server cost more than they bring.

---

## 1. Bring-your-faction push (current players)

**Why it is first:** factions hold four players. Each current player has friends who already trust them. A
friend who comes in with a faction stays longer than a stranger from a list (my guess, based on how factions
servers usually work).

**Steps**
1. Post the draft below in `#announcements` and `#monkey-smp`. Pin it in `#monkey-smp`.
2. Answer questions in the thread for a day.
3. Count new passes in Tebex over the next week.

**Rules risk (checked in the docs: Minecraft Usage Guidelines, minecraft.net, read 2026-11-08).**
"The cost to access the server is the same for everyone". So there are no friend discounts, no
"buy 4 get 1", and no free pass for recruiting. A cosmetic thank-you is fine. The guidelines allow selling
cosmetics, and a free cosmetic is a softer case of that. **Before promising a cosmetic, check it's live:**
Diego turned off the wardrobe data pack on 11-06, and the owner kept it off. If no cosmetic works today, post
the version without the reward line.

**Draft (Discord, `#announcements`). Join each paragraph into one line before pasting:**

> **Got friends who'd survive a raid? Bring them.** 🐒
>
> Factions here go up to four. If yours is short, now's the time: Season I runs until 23 January, and the
> border hasn't even started growing yet.
>
> Send them https://monkeysmp.lscaturchio.xyz. The pass is $5 a month or $8 for 2 months, the same price for
> everyone. They'll need Minecraft Java on a PC with 16 GB of RAM. The modpack installs in one click from the
> site.
>
> Tell us in #monkey-smp who you brought, so we know where new monkeys come from.

Add this line only if a cosmetic reward really works in game today:

> Bring a friend who buys a pass and you both get [COSMETIC]. Cosmetic only, like everything we hand out.

---

## 2. Server lists

**Steps (about 2 hours the first time).** The fields are in `docs/PROMOTION.md`, "The listing kit". Use the
updated texts below.
1. **Official Minecraft Server List** (findmcserver.com). Run by GamerSafer with Mojang. Address
   `find.monkeysmp.lscaturchio.xyz`. It needs a public contact email: use lorenzosca7@protonmail.ch.
2. **Planet Minecraft** (planetminecraft.com/servers). It's still active: 6,255 servers listed on 11-08, and
   it sorts by "Updated" by default. Edit the post once a week (new season news) to stay near the top.
   Address `list.monkeysmp.lscaturchio.xyz`.
3. **minecraft-server-list.com, minecraftservers.org, minecraft-mp.com, topg.org**, all on
   `list.monkeysmp.lscaturchio.xyz`. Use the free listing only. topg and minecraft-mp sell paid boosts:
   skip them, because `docs/PROMOTION.md` says free placements only.
4. Don't add vote rewards. They need Votifier, and minecraftservers.org bans vote-swapping.

**Rules risk and how sure I am**
- **Official list:** checked in its Code of Conduct (findmcserver.com/rules, effective 10 July 2023, read
  2026-11-08). You must follow the EULA and the Usage Guidelines. Descriptions must "accurately represent the
  actual gameplay experience". If you break this, they can take the server off the list.
  **Main risk: overclaiming.** The old kit advertises weekly events and standings. 15 of the 17 data packs
  are off since 11-06 (rules, standings, events, drops, wardrobe and others). The drafts below leave those out.
  Add them back only when they're on again.
- **Mojang disclaimer:** checked in the Usage Guidelines. They say to put "NOT AN OFFICIAL MINECRAFT
  [PRODUCT/SERVICE]. NOT APPROVED BY OR ASSOCIATED WITH MOJANG OR MICROSOFT" on the listing and description too,
  not only on the site. The site footer already has it. The drafts below add it.
- **Contact:** checked. The Usage Guidelines say chat and forum links are not acceptable contact methods. Give
  the email.
- **Price before joining:** checked. The Usage Guidelines want all content and pricing shown "before a person
  joins". The drafts say the price first.
- **minecraftservers.org:** checked in its terms (last updated September 2025). It allows one listing per
  server. Tags must be accurate. It bans cracked servers (we're not one).
- **topg.org:** checked in its terms (2014). They say little: no fake votes and no bots.
- **minecraft-server-list.com and the Planet Minecraft posting rules:** not checked. Both blocked automated
  reads. Read their rules on the form before submitting.

**Updated short description (under 150 characters):**

> Modded factions on Java 26.2. Season I live to 23 Jan. Factions of four, Strength SMP, ships, voice chat. Pass $5/mo.

**Updated long description:**

> **Monkey SMP** is a small modded factions server on Minecraft Java 26.2 (Fabric), for players who play
> evenings, Pacific time. **Season I is live until 23 January 2027.**
>
> - Factions of up to four, alliances, and claimed land nobody may grief. Everything outside it is contested.
> - Strength SMP: win fights and your strength grows, lose them and it drains.
> - Ships you can build and sail, a remade Nether, rebuilt villages, bigger dungeons and new structures.
> - Maces are capped at three on the whole server.
> - Proximity voice chat and a public 3D live map.
> - A pre-generated world on a dedicated CPU, up to 30 online.
>
> **Access is a server pass:** $5 a month or $8 for 2 months, the same for everyone. Supporter tiers are
> cosmetic only. Nothing sold gives an advantage. You need Minecraft Java Edition on a PC (Windows, macOS or
> Linux) with 16 GB of RAM. The modpack installs in one click from the website. If it won't run in your first
> 48 hours, you get your money back.
>
> Website: https://monkeysmp.lscaturchio.xyz · Discord: https://discord.gg/C25hy9Ca9W ·
> Contact: lorenzosca7@protonmail.ch
>
> Not an official Minecraft server. Not approved by or associated with Mojang or Microsoft.

Check before pasting: are the 48-hour refunds still workable? On 11-02 Tebex refused refunds until sales
settle (about 14 days). The owner honours the promise by hand, so keep the line only while that's true.

---

## 3. Reddit (wave 2)

**Steps**
1. Add DNS records for `rd.monkeysmp` (A + SRV, as in `docs/PROMOTION.md`, "The DNS records"). This lets
   us count Reddit players separately. It's a Cloudflare change, so it's the owner's step.
2. Read r/mcservers' sidebar rules and flair list on the day you post. Fit the title to their format.
3. Post once, on a weekday evening Pacific (my guess for when the most US players are online). Answer every
   comment from the same account that day.
4. Other subreddits only after reading their rules. r/feedthebeast and r/admincraft are probably no-server-ad
   subs (my guess, not verified).

**Rules risk and how sure I am: NOT verified.** Reddit blocks every automated read from this PC, so I could
not read r/mcservers' rules. Server subs usually limit posts to one every few days or a week, want the version
and tags in the title, and remove posts that hide a paywall (my guess). Reddit's sitewide rules also frown on
accounts that only self-promote. Post from an account with some normal history. **Main risk:** comments
calling out "paid server". Answer plainly: one price, cosmetics only, the pass pays for a dedicated CPU.

**Title:**

> [Java 26.2] [Modded] [Factions] [Paid] Monkey SMP: Season I is live, factions of four, Strength SMP, ships

**Body:**

> **Monkey SMP** is a small modded factions server on Minecraft Java 26.2 (Fabric), for people who play
> evenings, Pacific time. Season I started on 7 November and runs to 23 January 2027.
>
> - Factions of up to four, alliances, and claimed land nobody may grief. Everything outside it is contested.
> - Strength SMP: win fights and your strength grows, lose them and it drains.
> - Build and sail ships, a remade Nether, rebuilt villages, bigger dungeons and new structures.
> - Maces capped at three for the whole server.
> - Proximity voice chat and a public live map: https://map.monkeysmp.lscaturchio.xyz
>
> **It's paid, and here's why:** a pass is $5 a month or $8 for 2 months, the same for everyone. It pays for
> a dedicated server. Supporter tiers are cosmetic only, and nothing sold gives an advantage. You need
> Minecraft Java on a PC with 16 GB of RAM. The modpack installs in one click from the site. If it won't run
> in your first 48 hours, you get your money back.
>
> - Website and modpack: https://monkeysmp.lscaturchio.xyz
> - Discord: https://discord.gg/C25hy9Ca9W
> - Address: `rd.monkeysmp.lscaturchio.xyz`
>
> Not an official Minecraft server. Not approved by or associated with Mojang or Microsoft.

---

## 4. Short clips: TikTok and YouTube Shorts (wave 2)

**Steps**
1. Find out whether launch night was recorded (the streaming#1 plan). If not, record the next big moment
   from a staff spectator account at 1080p60.
2. Cut 15 to 30 seconds, one moment per clip, 9:16. Use game sound and a music bed, never players' voice chat.
   Players' names stay visible only for players who said yes. Show `tt.` or `yt.monkeysmp.lscaturchio.xyz`
   on screen for the last 3 seconds.
3. Post from the server's own accounts. On TikTok, turn on the content disclosure setting ("Your brand").
4. Post 2 or 3 clips a week for 3 weeks. Then count `tt.` and `yt.` joins and decide whether to keep going.

**Rules risk and how sure I am**
- **TikTok:** checked in its Community Guidelines (effective 24 Sep 2026). Commercial content must use "TikTok's
  content disclosure setting". It bans buying fake engagement. The setting's exact name ("Your brand") is
  **my guess**: the support page didn't load.
- **YouTube:** checked in the help page on paid promotion. The "paid promotion" box is for sponsorships and
  similar deals. Whether it applies to promoting your own server isn't stated. Ticking it costs nothing, so
  tick it.
- **Mojang (checked):** gameplay videos are fine if they are free to view and add your own content. Put title
  cards and callouts outside the game footage. Keep everything suitable for all ages.
- **Age (my understanding):** TikTok, YouTube and Discord all need users to be 13 or older. Many players are
  under 18. That's why there's no voice chat in clips, and why you blur anyone who didn't agree.

**Three clip ideas (caption drafts):**

> 1. *A ship raid:* "they sailed a ship to our base. it did not go well for them 🐒⚓ Monkey SMP · modded
>    factions · Java 26.2 · link in bio #minecraft #minecraftsmp #factions"
> 2. *Strength SMP fight:* "won 3 fights, strength went up. lost the 4th. this is strength smp on a factions
>    server 💪 #minecraft #strengthsmp #minecraftpvp"
> 3. *Mace cap:* "there are only 3 maces on the whole server. this is what people do to get one #minecraft
>    #mace #minecraftsmp"

Change each caption to match what the footage really shows.

---

## 5. Creator collabs (wave 2)

**Steps**
1. Make a list of 10 small creators (500 to 20,000 subscribers) who post factions, SMP or modded-survival
   videos. Skip channels aimed at young kids and channels that make drama about other servers.
2. Watch one real video of each. Send **one** message each, from the owner's own account. Don't follow up.
3. A creator who says yes gets a free pass (whitelisted by hand), their own join address, and a Tebex code.
   The terms are on https://monkeysmp.lscaturchio.xyz/creators.
4. Before a creator with more than ~5,000 viewers plays, check the capacity rule above. A good video can
   bring 30 players in one evening.

**Rules risk (checked in the Usage Guidelines):** you must "require any social influencers ... to disclose
their relationship with you" and follow the FTC rules. The creators page already asks for #ad. The free pass
plus 20% code counts as a relationship.

**DM draft:**

> Hi NAME, I'm Lorenzo, one of the two people running Monkey SMP, a small modded factions server on Java 26.2.
> It has factions of four, Strength SMP, ships and proximity voice.
>
> I liked VIDEO. If you're looking for a server for a series, you're welcome to play here free, with your
> own creator code that pays you 20% of each 2-month pass bought with it. Terms:
> https://monkeysmp.lscaturchio.xyz/creators
>
> No pressure. If it's not for you, no reply needed.

---

## 6. Discord directories (Disboard, discord.me, Discadia, top.gg)

**Steps**
1. Check whether the 10-29 note's listings exist (`Code\reports\discord-posts-2026-10-29.md`, section 4).
2. On each listing, put the short description first, mention the paid pass, and set the age to "all ages".
3. Bump on Disboard when someone is in the server anyway. Don't make it a chore: it brings Discord members,
   not pass buyers.

**Rules risk: NOT verified.** Disboard's guideline pages returned 404, and top.gg blocked the read. I believe
Disboard lets you bump every 2 hours and bans NSFW and server-advert spam, but that's **my guess**. The Discord
is "Lorenzo's Server", not SMP-only, so say clearly that the SMP is one part of it.

**Description draft:**

> Lorenzo's Server: home of **Monkey SMP**, a modded factions Minecraft server (Java 26.2, $5/month pass,
> Season I live). Factions of four, Strength SMP, ships, voice chat. Plus game nights and chat.

---

## 7. Modrinth (later)

- The modpack page "monkeysmp" was sent for review on 10-28 with **version 2.8.0 (26.3)**. That's the wrong game
  version for today's 3.1.1 (26.2) server. If it goes public as it is, people get a pack that can't join.
- **Rules risk (checked: Modrinth Content Rules, last changed 13 Aug 2026).** Rule 6.1 requires the "Contains
  AI-generated content" label when the description "relies on generative AI". The description was AI-written,
  and the label was left off at the owner's word. Rule 6.2 says no AI-made icon or gallery images; use real
  screenshots. Projects "primarily" made of AI output can't be public. Modrinth also has an unpublished rule
  that rejects server listings that need payment to join (seen 2026-07, per the 10-25 notes).
- **Recommendation:** upload the current client pack, turn the AI label on, and use real screenshots. Expect
  few players from it. The modpack page gets you discovered while browsing, but the paywall turns most of
  those people away.

## 8. Paid ads

Not now. `docs/PROMOTION.md` says no paid list slots or vote buying. Revisit only when the server is full on
event nights and capacity is solved. Then run one boosted clip at a few dollars a day for a week, and count
`tt.` or `yt.` joins before spending more. Any spend needs the owner's yes.

---

## Owner checklist (each one is a separate yes)

1. Post the bring-your-faction message (with or without the cosmetic line).
2. Submit the six server lists with the updated text.
3. After 3.2.0's numbers: VPS upgrade, yes or no.
4. Add the `rd.monkeysmp` DNS records, then post on Reddit.
5. Post clips (each clip is its own yes).
6. Send creator DMs (each one is its own yes).
7. Modrinth: upload the current pack and turn the AI label on.

Also fix `docs/PROMOTION.md` in a PR later. Its long description has no Mojang disclaimer and no contact
email, and it still lists features whose data packs are off. That's a repo change, so it needs the owner's
OK to commit.
