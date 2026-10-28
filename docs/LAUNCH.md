# Season I launch

The run sheet for opening Season I: **Saturday 21 November 2026 at 5 PM Pacific** (8 PM Eastern, 01:00 UTC
on Sunday 22 November), with everyone let in at once. It runs from T-26 (Monday 26 October, when this was
written) to T+7 (Saturday 28 November, the first weekly event). Every date below is Pacific time.

Every Discord, Reddit and server-list text here and in docs/PROMOTION.md is a **draft**. Nothing is posted,
pinned, submitted or sent until an owner has read it and said yes.

The launch time lives in one place, `LAUNCH_AT` in `site/config.js`. `python tools/site_links.py` writes it
into the site (the hero, the "Season I launch" rule, and the description that link previews show), and the
front page adds the visitor's own time and a countdown, then says "Season I is live" once it has passed. To
move the launch: change `LAUNCH_AT`, run the tool, and change the dates in this file, in the Season I
calendar (docs/SEASONS.md) and in the drafts (docs/PROMOTION.md, "Season I launch announcements").

## The dates

| Day | T | What |
| --- | --- | --- |
| Mon 26 Oct | T-26 | This kit. Start the store. |
| Tue 27 Oct | T-25 | Moderator recruitment post (below). |
| Fri 30 Oct | T-22 | Store submitted to Tebex for review. |
| Mon 2 Nov | T-19 | Check Chunky has finished. |
| Sat 7 Nov | T-14 | Launch-date announcement and the founding roster opens. Server-list descriptions get the date. |
| Sun 8 Nov | T-13 | Moderator applications close. Off-site backups and Uptime Kuma alerts working. |
| Thu 12 Nov | T-9 | Moderators picked and given the rank. |
| Fri 13 Nov | T-8 | **Last release tagged.** Everything for launch is in it. |
| Sat 14 Nov | T-7 | The last release deploys at 4-5 AM; the freeze starts. T-7 announcement; faction registration opens; Reddit post. |
| Sun 15 Nov | T-6 | Load test on the VPS; restore drill and launch rehearsal on the home PC. |
| Wed 18 Nov | T-3 | Trial decided. Build Battle plots built. Moderators onboarded. |
| Thu 19 Nov | T-2 | 5 PM: founding roster closes. Over 30: the waitlist gets its first calls. |
| Fri 20 Nov | T-1 | T-1 announcement. 5 PM: the roster is final. |
| Sat 21 Nov | T-0 | 4 PM the last call; **5 PM launch**, the launch hour and the Build Battle wheel; 6 PM PvP and the Nether open. Recorded. |
| Sun 22 Nov | T+1 | Day-1 check. 6 PM Build Battle judging. Launch weekend ends at midnight. |
| Mon 23 Nov | T+2 | The freeze ends. Day-1 retention. |
| Sat 28 Nov | T+7 | Day-7 check. 6 PM Faction Raid I, recorded. |

## Before launch

### The store (Tebex)

docs/LIVE.md, "Payments and Discord" and "The store", has the packages, prices and commands. This is the
order and the dates.

- [ ] **Mon 26 Oct to Thu 29 Oct: build the storefront** at `monkeysmp.tebex.io`. The packages exactly as in
  the table in docs/LIVE.md (prices can't change on a subscription once sold, docs/adr/0008). Commands from
  docs/RETENTION.md. The Discord integration for the paid role. Link the payout wallet (Link Wallet).
- [ ] **Connect the server:** the Tebex jar in `server/mods` (docs/LIVE.md gives the URL), then
  `tebex secret <key>` in the console. The key is a secret: type it into the console, never into a file in
  this repo or a chat.
- [ ] **Test purchase** of the $5 pass on a staff account. Check that `whitelist add` ran, `rw.months` went up
  by one, and the Discord role arrived. Then refund it in the panel (if the package has refund commands,
  check they ran), and leave only staff on the whitelist.
- [ ] **Fri 30 Oct: Submit for Review.** Tebex doesn't say how long review takes. If the store isn't
  approved by **Fri 13 Nov**, launch with passes by hand (below); the site already says that while
  `STORE_URL` is empty.
- [ ] **Once approved: open the `STORE_URL` pull request** (the one-line change in `site/config.js`, then
  `python tools/site_links.py`) and leave it unmerged. It merges **at 5 PM on launch day** (launch day,
  below), or on Sunday 22 November if the founding roster is over 30. Until it merges the site says passes are
  arranged in the Discord, which stays true. Site-only pull requests are fine during the release freeze.
- [ ] **Keep the storefront's address to staff until it merges.** A pass bought there goes on the whitelist
  within a minute, and that player could walk into the world before everyone else. Staff check the whitelist
  daily from T-7 (below).

### The 7-day trial

docs/LIVE.md, "The store", explains the trial and what is unknown about it. Test it once with real money
before turning it on for everyone.

- [ ] **Once the store is approved (aim for Tue 10 Nov):** turn the 7-day trial on for the monthly pass, buy
  it with a real card on a staff alt, and check: the whitelist command ran when the trial started, the
  Discord role arrived, and `rw.months` didn't move yet.
- [ ] **The same day, cancel the trial** on Tebex's payment history page and check `whitelist remove` ran.
  No money changes hands if it's cancelled inside the 7 days.
- [ ] **Wed 18 Nov: decide.** Trials go on only if all three checks passed. Then add the FAQ answer from
  docs/LIVE.md to `site/index.html` in its own small pull request, and add the trial line to the T-1 and
  launch announcements (docs/PROMOTION.md). If the whitelist waited for the first charge, leave trials off
  and plan an open-house evening in December instead (docs/LIVE.md).
- [ ] If the store isn't approved in time, there is no trial at launch. Say nothing about one.

### Release freeze: 7 days

**N = 7.** The last release is tagged by **Friday 13 November** and goes live in the 4-5 AM window on
**Saturday 14 November**. Nothing new deploys until **Monday 23 November**, after launch weekend.

Why seven days: one full week of the world on the exact release players will launch on, with a load test,
a restore drill and a rehearsal against it (Sunday 15 November), and time to roll back or patch a bad
release before the T-1 announcement. A shorter freeze puts a fresh, untested release under launch night.

How:

- **Hold the tag.** The VPS deploys only the newest `vX.Y.Z` tag (`TRACK=tags`), so no tag means no deploy.
  This is the freeze. Merging to `main` is fine; tagging is not.
- **Stop the deploy timer as a backstop**, once the last release is live (check with
  `sh /srv/realms/repo/deploy/realms-deploy.sh --status` on Saturday 14 November after 5 AM):
  `sudo systemctl stop realms-deploy.timer`. An accidental tag then waits. The timer is still enabled, so a
  reboot of the VPS starts it again: after any reboot, `systemctl is-active realms-deploy.timer` and stop it
  again.
- **`DEPLOY_WINDOW` stays 04:00-05:00.** It can't express a date range, so it isn't the freeze, but it keeps
  any deploy far from the evening.
- **What still runs:** the daily restart at 4:30 AM, the hourly off-site backup, the Monday update check.
  Leave them.
- **Exception:** a crash, a dupe or a security hole. Both owners agree, tag a patch release, and deploy it
  with `--now` at a quiet hour after a backup. Nothing else.
- **Mon 23 Nov:** `sudo systemctl start realms-deploy.timer`. Tagging is open again.

Weekly faction standings and the bounty board, weekly challenges and the Founder skin all shipped in 2.6.0
(item-priced shop chests too, but the owners shelved them on 26 October, so they aren't at launch). Anything new
after that makes launch only if it is in the Friday 13 November release; whatever misses it waits until Monday
23 November at the earliest, and its lines come out of the announcements ("Copy that depends on unmerged work",
below).

### Ops readiness

- [x] **The 2.8.0 world.** Done 2026-10-27: 2.8.0 went live on a new world (docs/LIVE.md, "A new world for
  Season I (2.8.0)"), and Chunky started pre-generating it. Do the load test and the rehearsal on this world.
- [ ] **Mon 2 Nov: Chunky.** `realms rcon "chunky progress"` (as `realms`, in
  `/srv/realms/TheRealms-Server/docker`; `realms rcon` is short for `docker compose exec realms realms rcon`).
  It should report no running task for the overworld or the Nether. If one is still running, let it finish:
  the load test refuses to run before it does.
- [ ] **By Sun 8 Nov: off-site backups.** Set up R2 as in docs/LIVE.md, "Set up the off-site copy (once)", and
  check `sh /srv/realms/repo/deploy/realms-backup.sh --restic snapshots` lists hourly snapshots. The keys go
  in the password manager and `/etc/realms-deploy.env`, nowhere else.
- [ ] **Sun 15 Nov: verified with a restore.** Run the monthly restore drill (docs/LIVE.md, "Monthly restore
  drill") with the newest snapshot of the launch release, and see the world load. A backup nobody has
  restored isn't a backup yet. Without working off-site backups by launch day, copy a backup off the VPS by
  hand that morning, and tell the other owner.
- [ ] **By Sun 8 Nov: uptime alerts.** Uptime Kuma on the home PC (fleet repo, `services/uptime-kuma.md`)
  with the Minecraft ping and the map check from docs/LIVE.md, "Monitoring". Use the notification's Test
  button and check the message arrives in the staff channel.
- [ ] **Sun 15 Nov: load test** after the last release, as in docs/LIVE.md, "Load test" (as root, at a quiet
  hour, not near 4 PM Pacific, which is midnight UTC). Add its row to the table there in a docs pull request.
  Over about 40 ms median at 25 players: follow the decision rule there before launch.
- [ ] **By Sat 14 Nov: the 2.6.0 one-time steps.** Each is done once 2.6.0 is live; check none is still to
  do: `sh /srv/realms/repo/deploy/realms-week.sh --check` (the week timer runs) and
  `sudo sh /srv/realms/repo/deploy/install-standings.sh --check` (the standings timers). Anything left:
  docs/LIVE.md, "The weekly challenges' timer" and "The weekly standings". Without the week timer the
  challenge week never turns over and Founder's Circlet's window doesn't close at midnight on Sunday.
- [ ] **By Sat 14 Nov: the 2.7.0 one-time steps**, once 2.7.0 is live: `sh /srv/realms/repo/deploy/realms-drops.sh
  --check` says the drops timer runs, and the Guide and the Town Crier stand at spawn. Anything left:
  docs/LIVE.md, "The supply drops' timer" and "The spawn NPCs". Without the timer there are no weeknight drops;
  a release places no NPCs by itself.
- [ ] **Sun 15 Nov: rehearse on the drill copy**, never the live world: `function realms:rules/launch`,
  watch PvP and the Nether close and open again an hour later, then `python tools/block_wheel.py "rehearsal"`
  and paste its `tellraw`. Shut the copy down afterwards (it uses BlueMap's port 8100). On the live world a
  launch before 5 PM on the day would open Founder's Circlet's window early and spend the one-time wipe of
  test play's challenges, and the real launch wouldn't open the window again.
- [ ] **Daily from Sat 14 Nov: the whitelist.** `realms rcon "whitelist list"`. Before launch it holds staff
  only. Anyone else: `whitelist remove NAME`, note the name, and add it back at 5 PM on launch day.

### Passes and the whitelist by hand

Until the store's link is live, a pass is arranged in a Discord ticket, as the site says (decided 26
October). Only an owner takes the payment, directly with the player and never in a public channel; record
each one in the roster sheet (below). Nobody goes on the whitelist before
launch: at 5 PM on launch day, staff add every founding-roster member with a pass in one go.

```sh
cd /srv/realms/TheRealms-Server/docker
for n in Name1 Name2 Name3; do docker compose exec -T realms realms add-player "$n"; done
```

Prepare that line on Friday from the roster sheet, so on the day it is one paste. After launch, a pass
arranged by hand is added the same way, the same day (docs/LIVE.md, "Let a player in by hand"). If the
Discord bridge is on, a moderator can then link the name to its member with `/smp adopt`
(gr8monk3ys/discord-server).

### Build Battle

The rules are in docs/SEASONS.md, "Build Battle"; the staff commands in docs/ADMIN.md, "Events".

- [ ] **By Wed 18 Nov:** the showcase area next to spawn, outside the no-PvP spawn claim: equal 32 x 32 plots,
  one per registered faction plus a few spare, built in creative under the spawn rules. Each plot claimed
  for its faction when registration closes (Friday), and the area marked no-PvP while the event runs.
- [ ] **Fri 20 Nov:** the judges: both owners plus one guest judge, who agrees to be on at 6 PM on Sunday.
- [ ] **The seed for the wheel is "S1 launch".** It goes in the T-1h announcement, before the spin, so anyone
  can check the draw.

## Announcement schedule

The texts are in docs/PROMOTION.md, "Season I launch announcements", except the founding roster post, which
is below. Times are Pacific. Each Discord draft writes the time as a Discord timestamp, so every reader sees
it in their own time zone.

| When | Where | What |
| --- | --- | --- |
| Tue 27 Oct | `#announcements`, `#monkey-smp` | Moderator recruitment (below) |
| Sat 7 Nov, 5 PM (T-14) | `#announcements` | The date, and the founding roster opens (below) |
| Sat 7 Nov to Sat 14 Nov | the free lists | The launch line in each list's description (docs/PROMOTION.md) |
| Sat 14 Nov, 5 PM (T-7) | `#announcements` | One week; faction registration opens; install the pack now |
| Sat 14 Nov | r/mcservers | One post, after reading the subreddit's current rules |
| Fri 20 Nov, 5 PM (T-1) | `#announcements`, `#monkey-smp` | Tomorrow: the checklist |
| Sat 21 Nov, 4 PM (T-1h) | `#monkey-smp` | One hour: open the game now; the wheel's seed |
| Sat 21 Nov, 5 PM (launch) | `#announcements`, `#monkey-smp` | Open; the wheel's blocks |
| Sun 22 Nov, 9 AM | the free lists | Swap the launch line for the "Season I is live" one |

Use Front Desk's `/gamenight` for the launch, the Build Battle judging and Faction Raid I, so "Interested" is
the RSVP and the bot reminds people 15 minutes before (docs/SEASONS.md, "A weekly rhythm"). Mention
`@everyone` only on the T-14 and launch posts.

## Launch day: Saturday 21 November

| Time | Who | Step |
| --- | --- | --- |
| 9 AM | an owner | `realms-deploy.sh --status`: the release from 13 November is live and nothing is waiting. `whitelist list`: staff only. Uptime Kuma green. |
| 3 PM | staff | In Discord voice. Each staff member logs in, checks their rank (`lp user NAME info`) and `vanish` works. |
| 4 PM | an owner | Post the T-1h announcement. |
| 4:30 PM | staff | Last whitelist check. The add-player line ready to paste. The `STORE_URL` pull request approved and ready to merge. |
| 4:45 PM | the camera | Recording starts (below). |
| 5:00 PM | an owner | Paste the whitelist line. In the console: `function realms:rules/launch`. Merge the `STORE_URL` pull request (if the roster is 30 or under and the store is approved). Post the launch announcement. |
| 5:00 PM | an owner | `python tools/block_wheel.py "S1 launch"` on the maintainer's computer; paste its `tellraw` into the console and the three blocks into `#monkey-smp`. |
| 5:00 to 6 PM | moderators | The launch hour (rule 23): PvP and the Nether are closed, the End stays closed. Answer install questions in `#help` and tickets. The hourly backup runs at 5:00 and takes a minute or two; a short stutter then is that. |
| 5:10 PM | an owner | `spark tps` in the console: under 50 ms a tick holds 20 TPS. Then every half hour. |
| 6:00 PM | — | PvP and the Nether open by themselves. Say so in chat and `#monkey-smp`. |
| 7 PM | the camera | Stop recording (or carry on while something is happening). |
| 10 PM | an owner | Post the first night's notes in the staff channel: online peak, problems, who couldn't join. |

If the server won't start or falls over at launch: say so in `#announcements` straight away with a new time,
fix it, and run `function realms:rules/launch` only once everyone can join. The launch hour's timer is kept
with the world, so run it once.

## Launch weekend: Sunday 22 November

- [ ] **9 AM: day-1 check** (below).
- [ ] **6 PM: Build Battle judging.** Owners and the guest judge score look (10) and idea (10), plus 5 a
  visible wheel block (docs/SEASONS.md). Players' Discord vote breaks ties. Then
  `/function realms:events/cup/add {id:"...",points:30,why:"Build Battle, 1st"}` and so on, `begin` and
  `attend` for everyone who built (docs/ADMIN.md, "Attendance"), and the result in `#monkey-smp`.
- [ ] **Midnight:** launch weekend ends, and with it Founder's Circlet's window: `realms-week.timer` closes it
  at 12:00:30 AM. Then `realms rcon "scoreboard players get #founder.open rw.day"` should say 0; if it says
  1, `realms rcon "function realms:wardrobe/founder/close"`.
- [ ] **Roster over 30:** merge the `STORE_URL` pull request in the morning, after the waitlist has had its
  message the night before (founding roster, below).

## Recording real footage

docs/PROMOTION.md, "Clips from real event nights", has the rules: consent, no player voices, storage. The
recording setup is the `demo` scenario in the obs-config repo (gr8monk3ys/obs-config; don't change it from
here). Two nights: **launch night** (Saturday 21 November, 4:45 to 7 PM, the gathering at spawn, 5 PM and
PvP opening at 6) and **the first Saturday event**, Faction Raid I (Saturday 28 November, 6 PM).

- [ ] The camera is one staff account in spectator mode that doesn't play that night, on the home PC.
- [ ] `python scripts/obsconf.py launch demo` in the obs-config folder: OBS on the Demo profile, Screen scene,
  1440p60 with a 60-second replay buffer.
- [ ] In Simple Voice Chat, deafen the camera account, so no player's voice reaches the recording. The
  Demo profile records the desktop sound alone on track 3: use that track.
- [ ] Ctrl+Alt+F9 starts and stops the recording, Ctrl+Alt+F6 drops a chapter marker at a good moment, and
  Ctrl+Alt+F11 saves the last 60 seconds when something happens that wasn't being recorded.
- [ ] The event post and a chat message before the start say the night is recorded for the server's clips,
  and that anyone who doesn't want to be in them can say so.
- [ ] Afterwards, move the files from `D:\Videos\OBS\Demo` to `D:\DevData\monkey-smp-marketing\footage\real\`,
  never into this repo, and note who asked to be left out.

## After launch: day 1 and day 7

The VPS's `.env` sets `TZ=America/Los_Angeles` (docs/LIVE.md, "Set up (once)", step 5), so log days are
Pacific days.
Retention groups players by the week they first joined, starting Monday: launch night's players are the
week of `2026-11-16`.

**Day 1, Sunday 22 November, 9 AM**

- [ ] `python3 /srv/realms/repo/tools/retention.py /srv/realms/TheRealms-Server/server/logs`: how many new
  players joined. D1 is only complete on Monday, once Sunday is over.
- [ ] Who has a pass but never joined. With the store: export the payments (Payments, Export as CSV), copy
  them to the VPS and run
  `python3 /srv/realms/repo/tools/funnel.py ~/payments.csv /srv/realms/TheRealms-Server/server/logs --log-tz America/Los_Angeles`,
  then delete the CSV (it holds emails; never commit it). Without the store: compare the roster sheet with
  the joins. Either way, send everyone who never joined the install help (docs/SHARING.md) that day.
- [ ] **Monday 23 November:** run retention again for the launch cohort's D1.

**Day 7, Saturday 28 November, before the event**

- [ ] Retention again: D1 for the launch cohort, and how many different players the week of `2026-11-23`
  has had so far. D7 for launch night's players is complete once Saturday is over; run it again on Sunday 29 November.
- [ ] The funnel again (with the store): joined, played 30 minutes, came back.
- [ ] What to do with it: docs/RETENTION.md, "Reading the numbers". D7 under about 30% means the first days
  aren't landing; fix onboarding before anything else.
- [ ] Write the numbers in the staff channel with one line on what changes because of them.

## Founding roster

The founding roster is the list of players who are in on launch night. Signing up is free and costs nothing
later: it is not a pass and doesn't replace one. Everyone pays the same for a pass, and nobody can pay to be
higher on the roster.

- **One price.** Mojang's usage guidelines ask for one price for access, so there are no priority slots,
  reserved places, early access or "founder packs" for sale (docs/LIVE.md, "The store"). The Founder skin is
  earned by playing launch weekend and is never sold.
- **First come, first served.** The order is the time of the sign-up message, which Discord records. The
  first 30 are the roster; everyone after is on the waitlist, in order.
- **Up to 30, because 30 is the server's slot count** (`max-players=30`). If 30 or fewer sign up, there is no
  waitlist and the store opens to everyone at 5 PM.

### The announcement (draft, T-14, Saturday 7 November, `#announcements`)

> **Monkey SMP Season I opens Saturday 21 November, 5 PM Pacific / 8 PM Eastern** (<t:1795309200:F>, that's
> <t:1795309200:R>)
>
> Everyone gets in at the same moment. The first hour is peaceful: no PvP, no Nether. Then it's on. The
> first Build Battle starts the second the server opens.
>
> **Sign up for the founding roster in #founding-roster.** Post one message with your Minecraft Java name,
> and your faction's name if you have one. That's it.
>
> - The roster is the first 30 sign-ups, in the order you post. After 30 there's a waitlist, also in order.
>   If someone on the roster drops out, the next person on the waitlist moves up.
> - Signing up is free. You still need a server pass to play: $5 a month, the same for everyone. Nobody can
>   pay to be higher on the list, and there are no reserved slots for sale.
> - Play launch weekend and you keep the Founder skin for good. It's never sold.
> - Factions of up to four register from Saturday 14 November in #smp-forum.
>
> Website and modpack: https://monkeysmp.lscaturchio.xyz

The Founder line depends on the Founder-skin work shipping; see "Copy that depends on unmerged work".

### Sign-up: a channel

A text channel, `#founding-roster`, next to `#monkey-smp`. A channel rather than a reaction: a message
carries the Minecraft name and a time anyone can see, while the order of reactions isn't shown reliably.

Staff steps:

1. **Before Sat 7 Nov:** create `#founding-roster` (if the Discord's channels are managed by the
   discord-server repo's layout script, add it there, so a later sync doesn't remove it). Everyone can read
   and post; slow mode 6 hours; no threads. Pin a short copy of the rules above.
2. **Post the announcement** at 5 PM on Saturday 7 November, after an owner's yes.
3. **Each sign-up:** check the Minecraft name is a real Java name, add a row to the roster sheet, and react
   with ✅. The sheet lives in the staff channel or a private spreadsheet and holds only: number, sign-up time
   (from the message), Discord name, Minecraft name, faction, pass (none / by hand / store), and a note.
   A name that isn't a Java account gets a reply asking for the right one; the place in line is kept.
4. **One sign-up each.** A second message from the same person is deleted; the first one counts. Someone who
   deletes their message and posts again goes to the back.
5. **Leaving:** a member who says they can't make it is taken off, and the next on the waitlist moves up and
   is told.
6. **Thu 19 Nov, 5 PM: the roster closes.** Post the count in `#founding-roster`. Later sign-ups go to the
   waitlist, or, under 30, simply get a pass and join on the night.
7. **Over 30 only:** members without a pass arranged by Thursday 5 PM get a message: arrange one by Friday
   5 PM or the place passes on. On Friday at 5 PM, each empty place goes to the next on the waitlist, who
   gets a message the same evening. Fill places only while the next person can still arrange a pass in time.
8. **Fri 20 Nov, 5 PM: the roster is final.** Write the add-player line from it (above).
9. **Over 30, Saturday night:** message the waitlist that the store opens Sunday morning, and merge the
   `STORE_URL` pull request on Sunday. From then on the slots are first come, first served on the server
   itself, as on any night.

## Moderator recruitment

Two or three moderators, so that every evening has someone on besides the owners. Owners pick; nobody
applies their way in by being first.

### The post (draft, Tuesday 27 October, `#announcements` and `#monkey-smp`)

> **Monkey SMP is looking for 2 or 3 moderators for Season I** (opens <t:1795309200:F>)
>
> **What moderators do**
> - Answer questions and tickets, and help new players get the modpack running.
> - Watch for rule breaks, check reports with the server's tools, and warn, mute or ban with a reason when
>   the rules say so. Owners handle appeals and anything unclear.
> - Help run the Saturday events (6 PM Pacific): set up, count who came, keep things fair.
>
> **What we ask**
> - About 3 hours a week, mostly evenings Pacific time, and at least one Saturday event a month.
> - Launch weekend, Saturday 21 and Sunday 22 November, if you can.
> - Answers to tickets within a day, and knowing the rules well.
> - Being 16 or older.
>
> **What you get:** it's a volunteer role. No pay, and no items, Strength or advantages in the game, but your
> server pass is free while you moderate. Moderators play under the same rules as everyone, and a moderator
> who breaks them loses the rank.
>
> **How to apply:** open a ticket titled "Moderator application" by Sunday 8 November, with your Minecraft
> name, your time zone and the evenings you're usually free, any moderating you've done before, and what
> you'd do here: two players argue in chat over a kill and one starts calling the other names. We'll reply
> to everyone by Thursday 12 November.

Decided 26 October: moderators must be 16 or older, and a moderator's own pass is free for as long as they
moderate (whitelisted by hand, like staff; it ends with the rank). It's the same pass everyone has, so no one
gets anything in the game for it.

### Picking (by Thu 12 Nov)

- Read every ticket, answer every one, and talk to the likely ones in voice.
- Prefer people who have played with the owners before, are on in the evening, and answered the example
  calmly.
- Give the rank and the Discord Moderator role, then onboard them (below) by Wednesday 18 November.

### Onboarding checklist

The tools are documented once; this list points at them.

- [ ] **The rank:** `lp user NAME parent set moderator` (docs/ADMIN.md, "Ranks (LuckPerms)"). It lists what the
  rank can and can't do.
- [ ] **Read the rules:** docs/RULES.md in full, the rule numbers included, and "Community and payments" for
  the enforcement steps (warning, temporary ban, ban) and what skips straight to a ban.
- [ ] **Punishments, BanHammer:** `warn`, `tempmute`, `tempban`, `ban`, always with a reason, `-s` to keep it
  out of public chat (docs/ADMIN.md, "Moderation"). Check a player's history before acting.
- [ ] **Vanish and InvView:** `vanish`, `view inv NAME`, `view echest NAME` (look only), same section.
- [ ] **Getting somewhere, and what goes to an owner:** a moderator reaches a spot with `ledger tp` or a
  clicked position in Ledger's results. Whitelisting, game modes and teleporting to a player need op, which
  moderators don't get, so they ask an owner (docs/ADMIN.md, "What needs op" under "Ranks").
- [ ] **X-ray alerts (MinerTrack) and Ledger:** alerts at VL 2, 4 and 5, `mtrack check NAME`, and the diamond
  query; a lucky miner sets it off too, so check before acting (docs/ADMIN.md, "Moderation" and
  "Griefing").
- [ ] **Tickets and appeals:** reports and payment problems come in Front Desk tickets. Appeals are
  reviewed by a different admin within 7 days (docs/RULES.md, "Community and payments").
  Anything about money goes to an owner.
- [ ] **Events:** `begin` and `attend` for attendance, and the arena commands (docs/ADMIN.md, "Events").
- [ ] **Discord:** the Moderator role, two-factor authentication on (Discord can require it for moderation),
  and the staff channel.
- [ ] **One shadowed evening** with an owner before launch weekend, from Sunday 15 November.

## Copy that depends on unmerged work

These appear in the drafts. The first three shipped together in 2.6.0, so their lines stay; the shop chests'
lines are already cut. The table is for a later release that takes one out again: then cut its line before
posting.

| Work | Where it is mentioned | If it misses the release |
| --- | --- | --- |
| Founder skin for playing launch weekend (Sat 21 Nov 5 PM to Sun 22 Nov midnight Pacific) | the roster post, T-7, T-1, launch, Reddit | Cut the line. (Founder's Edge, for anyone who plays in Season I, is already in the wardrobe.) |
| Weekly faction standings and the bounty board (pull request #42) | T-7, Reddit, the long list description | Cut "weekly standings" and "bounty board" |
| Weekly challenges | T-7, Reddit | Cut the line |
| Item-priced shop chests | T-7, Reddit | Cut: shelved on 26 October 2026 |
