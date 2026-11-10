---
status: accepted
---
# Our own mods may be pinned from a GitHub release

Every plugin, mod and datapack is pinned from Modrinth, with one exception: a mod the owners wrote themselves
may be pinned from a release of its own GitHub repository. The repositories are listed by name in
`entries.GITHUB_PINS` (today only `gr8monk3ys/patina-and-chime`), and adding one is a change to this decision.

Patina & Chime is the reason. It has been waiting for Modrinth's moderation since October 2026, its project
page returns 404 until it passes, and a server that can't run its owner's own mod until a third party approves
it is the wrong way round. ADR-0002 still holds in full: the package carries no jar, the installer downloads
the file from upstream and checks the size and hash pinned in the manifest, and a download that doesn't match
is refused. Only the host is new, and for these mods the owners are the upstream.

The rule is kept narrow so that it can't become a second way to add mods:

- A GitHub pin is its own kind of entry (`github`, `tag`, no `project_id` or `version_id`). GitHub is not in
  the list of allowed hosts: the entry's `url` must be exactly the release download URL of its `file` in its
  `tag` of its repository, and the repository must be in `GITHUB_PINS`. Only a mod can be one.
- It needs a sha512, and the players' pack must contain the same file: same name, URL, size and sha512.
  A file in `client/modrinth.index.json` may come from somewhere other than Modrinth's CDN only when it is
  such a pin of the server manifest, and every such pin must be in the pack. These mods add blocks and items,
  so a player without the mod, or with another build of it, is refused at the door.
- Nothing moves the pin on its own. `check_updates.py` and `add.py` skip it, and a snapshot keeps it only while
  the jar on the server is still the pinned file, byte for byte. A new release is pinned by a maintainer with
  `python tools/pin_github.py <mod> <tag> <jar>`, which writes the server's entry and the pack's together.

A release asset on GitHub can be deleted and uploaded again under the same name, where a Modrinth version
file can't be replaced. The pinned hash covers that: a changed file fails the install and
`validate.py --online`, it is never installed. A deleted one breaks new installs until the pin moves, as a
version pulled from Modrinth does.

When Modrinth approves the mod, pin it from there (`add.py`, after taking the GitHub pin out) so that the
update check sees it again. This ADR then stays for the next mod of ours that is waiting.

## Considered Options

- Wait for Modrinth: no change to the rules, but no date either, and the mod was written for this server.
- Add `github.com` to the allowed hosts: one line, and from then on any jar from any repository validates.
  The Modrinth rule is what keeps the mod list reviewable, so the exception names the repositories instead.
- Ship the jar inside the package: breaks ADR-0002 (the package contains no third-party files, and the size
  of a release stays that of scripts and config), and the players' pack would still need a download URL.
- Host the jar on the server's own site: a second place to publish each release, with no version history,
  and Modrinth's modpack format only allows downloads from Modrinth, GitHub, raw.githubusercontent.com and
  GitLab, so the players' pack could not be published with it.
