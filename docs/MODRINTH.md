# Monkey SMP on Modrinth

The client pack is published on [Modrinth](https://modrinth.com) as the modpack **Monkey SMP**
(`modrinth.com/modpack/monkeysmp`), and the server can have a Modrinth **server listing** that links to it.
Players then install the pack in one click in the Modrinth App, the app updates it before they join, and the
server shows up in Modrinth's server discovery.

| Project | Slug | Holds | Who keeps it current |
|---|---|---|---|
| modpack **Monkey SMP** | `monkeysmp` | every client-pack release as a version (the release's `.mrpack`) | `tools/modrinth.py`, after each release |
| server listing **Monkey SMP** | `monkeysmp-server` | the address, region, tags, and which modpack version players get | made once by hand; `tools/modrinth.py` moves its modpack version |

Status (2026-10-28): the modpack `monkeysmp` holds version 2.8.0 (2.9.0 left `client/` alone, so it uploaded
nothing) and was submitted for review on 2026-10-28, with the listing below. The server listing doesn't exist
yet: it waits for Modrinth's answer on paid access (below), and the owner hasn't sent that question yet.

## Before the first publish (the owner, once)

1. **Account.** Make a Modrinth account (signing in with GitHub works) and turn on two-factor auth.
2. **The modpack project.** On modrinth.com, create a **Project** (Modrinth's create dialog now offers only Project and Server;
   the uploaded `.mrpack` makes it a modpack): name `Monkey SMP`, URL `monkeysmp`. It starts as a private draft. Fill it in from [The modpack listing](#the-modpack-listing).
3. **A token.** Settings > Personal access tokens (modrinth.com/settings/pats) > Create a token: name
   `monkey-smp release`, scopes **Read projects, Write projects, Read versions, Create versions**, with an
   expiry. Keep it in your password manager. It never goes in the repo, an issue, a chat or a command line.
4. **The first version.** Run [Publishing a version](#publishing-a-version) for the current release. A draft
   project can hold versions, and Modrinth wants one before it accepts the project for review.
5. **Review.** Submit the project for review. Send Modrinth the paid-access question at the same time
   ([Review, and the paid-access rule](#review-and-the-paid-access-rule)); the answer decides step 6.
6. **The server listing.** Once that's settled, create it from [The server listing](#the-server-listing). The next
   `tools/modrinth.py` run points it at the newest version.

Then set `MODPACK_URL` in `site/config.js` to `https://modrinth.com/modpack/monkeysmp` once the project is
approved (a draft page is a 404 for everyone else).

## Publishing a version

After the GitHub release (docs/MAINTAINING.md, "Releasing"), from a clean checkout of the release tag:

```bash
git switch --detach vX.Y.Z
python tools/modrinth.py --dry-run     # builds the .mrpack and prints the upload; no token, no network
```

Then put the token in the environment for this one shell, and publish. PowerShell (5.1 or 7):

```powershell
$env:MODRINTH_TOKEN = [Net.NetworkCredential]::new('', (Read-Host 'Modrinth token' -AsSecureString)).Password
python tools/modrinth.py
Remove-Item Env:MODRINTH_TOKEN
```

bash:

```bash
read -rsp 'Modrinth token: ' MODRINTH_TOKEN && export MODRINTH_TOKEN
python tools/modrinth.py
unset MODRINTH_TOKEN
```

Typing the token at a hidden prompt keeps it out of shell history and out of the screen. The tool sends it
to `api.modrinth.com` only (it refuses any other host).

What it does, checking before each step so a re-run after a failure picks up where it stopped:

1. Builds `dist/TheRealms-Client-<version>.mrpack`, the same bytes as the GitHub release's file.
2. Uploads it as version `<version>` of `monkeysmp`, with the version's CHANGELOG section as its notes, unless
   Modrinth already has that version with the same file, or the newest version holds the same pack apart
   from its version number. A release that didn't touch `client/` asks nothing of players (the same rule as
   the live server's Discord message), so it uploads nothing; `--force` uploads it anyway.
3. Points the server listing at the newest version, so linked players update before they join. It skips this
   while the listing doesn't exist, and when the version it just published is older than the newest one.

It refuses to run from anything but a clean checkout of the `vX.Y.Z` tag that matches the manifest, because a
version's file can't be replaced once it's on Modrinth: to fix a pack, release a new patch version.
`--any-checkout` skips that check (for testing against a scratch project). `--project` and `--server` take
other slugs or ids; `--server ''` leaves the server listing alone.

## The modpack listing

Copy these into the project's settings. The description is drawn from the site and the README; when they
change, change it too.

| Field | Value |
|---|---|
| Name | Monkey SMP |
| URL | `monkeysmp` |
| Summary | The client pack for Monkey SMP, a small whitelisted factions server on Minecraft 26.3 (Fabric). It has the claims map, proximity voice, the new terrain mods and shaders. |
| Categories | Multiplayer (featured), Adventure, Combat |
| Environment | client-side only (the server runs its own package, not this pack) |
| License | MIT for the pack's own files (configs, settings, the Monkey SMP Wardrobe resource pack); every mod, resource pack and shader keeps its own license and is downloaded from its own Modrinth page |
| Icon | `marketing/logo/png/mark-512.png` |
| Links | Wiki `https://monkeysmp.lscaturchio.xyz` (Modrinth has no website field, and the site is the players' guide), Discord `https://discord.gg/C25hy9Ca9W`. No source or issues link: the repo is private, and Modrinth flags links it can't open. |
| Disclosures | **Paid features**, two entries: "Joining the server needs a paid server pass (the pack itself is free)" and "Supporter tiers unlock some Wardrobe cosmetic skins". Nothing else is on (the owners left AI-generated content off). |

### Description

```markdown
Monkey SMP is a small whitelisted factions server on Minecraft Java 26.3 (Fabric). Most of us play in the evenings, Pacific time. This is the pack you need to join, with the shaders, sounds and settings we actually play with.

## Joining

You need a server pass and your Minecraft name on the whitelist. You can get both at [monkeysmp.lscaturchio.xyz](https://monkeysmp.lscaturchio.xyz).

1. Install this pack in the [Modrinth App](https://modrinth.com/app). In the instance settings, under Java and memory, give it at least 6 GB.
2. Press Play, go to Multiplayer > Add Server, enter `monkeysmp.lscaturchio.xyz` and join.

The app updates the pack whenever the server moves to a new version. A PC with 16 GB of RAM and a mid-range graphics card runs it fine. If you get stuck, ask on [Discord](https://discord.gg/C25hy9Ca9W).

## What the server is like

- Factions of up to four players. You claim land on the map (2×2 chunks per player), allies share claims, and PvP is on everywhere outside spawn.
- Strength SMP rules: winning fights makes you stronger, and losing them drains it.
- Tectonic and Terralith terrain, with mountains past y 500. Incendium redoes the Nether, Endercon the End, and Dungeons and Taverns adds new structures.
- Proximity voice through Simple Voice Chat. There's a live BlueMap of the world on the website.
- Every season has a Build Battle, a Faction Raid and Arena Glory, and the factions play for the Season Cup.

## What's in the pack

- Performance: Sodium, Lithium, FerriteCore and ImmediatelyFast, plus Distant Horizons for long view distances.
- Visuals: Iris with Complementary, BSL and Photon (press O to switch shaders or turn them off), Fresh Animations, Continuity and 3D Skin Layers.
- Maps: Xaero's Minimap and World Map (you can claim chunks from the map), JEI and AppleSkin.
- Sound: Simple Voice Chat (press V) and the Enhanced Audio resource pack.
- Server content: Naturalist, Variants and Ventures, Goat Expansion and the other mods that add blocks, mobs and items. Don't turn these off, because the server needs them.
- The Monkey SMP Wardrobe resource pack, for the server's sword and helmet skins. You earn most of them by playing.

If your computer struggles, turn off Distant Horizons, the shaders and the visual and sound mods in the instance's Content tab, and leave the performance mods on. The FAQ on the website has more.

Run by Diego and Lorenzo Scaturchio.
```

### Gallery

From `site/img/` (in-game screenshots, the site's captions). The first is the banner image.

| File | Title | Description |
|---|---|---|
| `mountains-1600.webp` | The Painted Mountains | Above the clouds. Tectonic and Terralith push peaks past y 500. |
| `nether-castle-1600.webp` | A Forbidden Castle | In the Nether. It is guarded. |
| `end-citadel-1600.webp` | The Phantom Citadel | Out past the dragon's island. |
| `fortified-village-1600.webp` | A fortified village | On the coast. Someone will claim it. |
| `floating-island-1600.webp` | A floating island | A cabin, a long swim from anywhere. |
| `mage-tower-1600.webp` | A mage tower | In the shallows. |

Modrinth doesn't allow AI-made images on a project page; these are all screenshots from the game.

## The server listing

Create it once the paid-access question is answered (next section).

| Field | Value |
|---|---|
| Name | Monkey SMP |
| URL | `monkeysmp-server` (the tool's default `--server`; the unrelated "monkey smp" server owns `monkey-smp`) |
| Address | `monkeysmp.lscaturchio.xyz` (no port: its SRV record points at `play.monkeysmp.lscaturchio.xyz:25565`, and Modrinth looks SRV records up) |
| Content | Modded, the Modrinth modpack **Monkey SMP**, its newest version |
| Region | US West (the group plays evenings Pacific; US East only if the VPS is on the East Coast) |
| Language | English |
| Max players | 30 (`max-players` in `defaults/server.properties`) |
| Tags | Factions, PvP, Teams, Roleplay, SMP, Whitelisted, World Resets |
| Summary, description, icon, gallery, links | as the modpack's; the description can start at "What the server is like" |

A linked server listing doesn't follow new modpack versions on its own (other listings on Modrinth still link
old versions), which is why `tools/modrinth.py` moves it on each release. Discovery ranks servers by players
online and by verified plays, and drops a server that can't be pinged for a sustained time, so the server
has to stay up and reachable at that address.

## Review, and the paid-access rule

**Review can take about four weeks for a modpack.** Modrinth's page after submitting says it aims to review
within a week, but of the last 100 modpacks it approved (checked 2026-10-25) the median wait from submission to
approval was 29 days (most between 28 and 31). Server listings went faster: a median of 4 days. Editing the
project while it waits doesn't lose its place in the queue.

**Modrinth rejects servers that charge for access.** Since July 2026 its moderators' checklist has a rule for
server listings: Modrinth doesn't list servers that "require players to pay for access or donate to be able
to join". Monkey SMP's pass is exactly that. The public content rules don't spell it out, and the rule applies
to server listings only, not to modpacks, so:

- **The modpack went to review on 2026-10-28.** It is a normal client pack; the description says joining needs a pass.
- **The server listing waits for Modrinth's answer.** The owner asks Modrinth support first (the Help Center,
  support.modrinth.com, the chat bubble): can a paid-access, whitelisted server list, for instance if it has a
  free way in (a trial, free nights)? If not, the modpack alone still gives players one-click install and
  updates, and any free way in is the owners' call (pricing and the store, not this repo).

## What's in the pack, and may it be published

Checked 2026-10-25 against Modrinth's API (by sha512 hash, every file in `client/modrinth.index.json`):

- **All 213 files are on Modrinth** (176 mods, 22 resource packs, 15 shader packs) and download from
  `cdn.modrinth.com`. Modrinth's rule for modpacks is that a file hosted on Modrinth may be used in a pack
  whatever its license, so none of them needs extra permission.
- **The overrides are the pack's own**: configs, `options.txt`, the generated Monkey SMP Wardrobe resource pack
  (`tools/wardrobe.py` draws its pixel art), and a shader settings file. No jars or zips, which Modrinth flags
  in a pack's overrides.
- To tidy up, not blocking: two shader projects are archived by their authors (Aurora's Shaders, Pixel
  Perfect; their files still download), and Complementary Unbound is in the pack twice (r5.7.1 and
  r5.9.3).

## Updating this page

When Modrinth answers, or a project goes live, write the result and the date here, and remove what no longer
applies.
