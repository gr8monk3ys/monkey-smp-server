# Staff guide

For moderators and admins of the relaunched Monkey SMP. The rules and the punishment ladder are in
`rules.md`; how hearts and claims work is in `lifesteal.md`. When this guide and the rules disagree, the
rules win, and the guide gets fixed.

## How we moderate

- **Be boring and consistent.** Same rule, same step on the ladder, whoever the player is. Look up their
  record before you choose the step.
- **Evidence first.** Act on what you saw, a recording, Grim's alerts, or the block log, not on a report
  alone. Keep screenshots or clips with the punishment note.
- **Don't moderate your own fights.** If you, your team or someone you're feuding with is involved, hand it
  to another staff member.
- **Tell the player what and why:** the rule number and the length, in the punishment reason.
- **Write it down.** Every warning, mute, kick and ban goes in the punishment log (who, what, rule, step,
  evidence, staff member). Appeals are judged from it.

## Staff playing on the server

- Staff play by the same rules on their own accounts, and get no heart bypass, fly, god mode, items or
  claim blocks there.
- Moderation powers (vanish, `/ignoreclaims`, teleporting to players, inventory views) are for
  investigations only, and never to help yourself or friends in a fight, a raid or a trade.
- Don't share what you saw while investigating: base locations, stashes, who is eliminated and where.

## Tools

Moderators (LuckPerms group `moderator`) have everything below except the rows marked admin; admins have
all of it. Neither group gets a heart bypass, combat-tag or anti-cheat exemption, or the PvP toggle.
Builders (`builder`) get WorldEdit, creative and fly for building spawn, the market and event areas, and
only while they're building them.

| Need | Command |
| --- | --- |
| Warn | A chat message naming the rule, then a line in the punishment log |
| Mute | `/mute <player> <time> <reason>` |
| Kick | `/kick <player> <reason>` |
| Temporary ban | `/tempban <player> <time> <reason>` |
| Permanent ban | `/ban <player> <reason>`, plus `/banip` for ban evasion |
| Who's flagged for cheats | Grim's alerts (staff see them in chat) |
| Who's in combat | `/pvpinfo <player>` |
| A player's hearts | `/lifestealz hearts get <player>` |
| Fix hearts (admin) | `/lifestealz hearts add|remove|set <player> <n>` (log why) |
| Revive (admin) | `/revive <player>`, or `/revive *` on Revival Night |
| Look inside claims | `/ignoreclaims` (toggle it off when you're done) |
| A player's claims | `/claimslist <player>`; `/deleteclaim` while standing in one (admin) |
| Server lag | `/spark tps` and `/spark healthreport`; `/spark profiler` (admin) |

**Rollbacks need a block log.** The stack has no block logger yet. Until one is added (CoreProtect is the
usual choice), staff can't see who broke what, and "griefing is rolled back" can only mean restoring by hand.

## Common cases

- **Cheating flag from Grim.** Watch the player in vanish before acting; one alert is not proof. Ping and
  Bedrock can trigger some checks. Ban when what you see matches the alerts, and remove what they gained.
- **Kill farming or alt hearts.** Check `/lifestealz hearts get`, the kill-abuse kick in the console, and
  whether the accounts share an address. Remove the hearts gained, then apply rule 14 or 17.
- **Death from a bug or a server lag spike.** If spark or the console shows the server stalled, or the
  death was a plugin bug, give the heart back and log it. A player's own lag is not a bug.
- **Combat logging by a crash.** The game can't tell a crash from quitting. Give the heart back only once,
  if the console shows the server or their connection timed out rather than a normal leave.
- **Griefing or theft in a claim.** That should be impossible; find how it happened, fix or report the
  hole, and treat using it as rule 4.
- **"My base outside a claim was raided."** Not against the rules (rule 7). Point them to claiming.
- **Elimination while banned.** A ban doesn't touch hearts. An eliminated player who is also banned stays
  out until both are over.

## Before launch

In the new world, once, as an admin:

1. Turn off the modded season's Netherite ban, which the relaunch doesn't have:
   `datapack disable "file/monkey-no-netherite-armor"`. The world remembers it.
2. Turn on the late joiners' kit: `function monkey:catchup/on` (it only gives the kit from week 4).
3. At the launch time, run `function monkey:rules/launch`. The End stays closed until Dragon Night, when you
   run `function monkey:rules/open_end`.

## Revival Night

On the Saturdays in `season-1.md`, at the start of the event, an admin:

1. Announce it in game and on the Discord 30 minutes ahead.
2. Run `/revive *` from the console. Everyone eliminated can join again with 3 hearts.
3. Banned players are revived too, and that's fine: a revive doesn't lift a ban, and a ban never costs
   hearts, so they come back with 3 when the ban ends.

## Appeals

- Read the appeal, the punishment log entry and the evidence. You can't review your own punishment.
- Answer within 7 days: upheld (undo it and give back what can be given back), shortened, or denied, with a
  sentence on why.
- Lying in an appeal, or appealing from an alt, is a denial.
