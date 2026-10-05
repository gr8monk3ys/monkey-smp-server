# Maintaining the pack

Tools are plain Python 3.11+ with no dependencies (tests use `pytest`, lint uses `ruff`).

## Where things live

| Path | What | Edited by |
|---|---|---|
| `package/realms/manifest.json` | pinned Java, Paper, plugins, datapacks | `tools/snapshot.py`, `tools/add.py`, `tools/check_updates.py --apply` |
| `package/realms/defaults/` | first-run configs, copied only if missing | by hand |
| `package/realms/patches/<slug>/` | files replaced inside a downloaded datapack | `tools/snapshot.py` |
| `client/` | the player modpack (`modrinth.index.json` + `overrides/`) | `tools/snapshot.py client` |
| `tests/fixtures/upstream/` | API responses the unit tests replay | `tests/fixtures/record.py` |

The command-line tools (`snapshot`, `check_updates`, `validate`, `build`) are thin; the knowledge
lives in a few modules they share:

| Module | Owns |
|---|---|
| `tools/entries.py` | the manifest entry shape, the `file` naming rule, entry validation, hash choice |
| `tools/patches.py` | making, storing, applying and checking patches |
| `tools/upstream.py` | the Upstream catalog (Modrinth, PaperMC, Adoptium) behind a swappable HTTP adapter |
| `tools/defaults.py` | the `{{TOKEN}}` placeholders the installer fills into `defaults/server.properties` |
| `tools/repo.py` | where things live in the repo (tools take a `Repo`, so tests can use a temp copy) |

## Updating plugins and Paper

```bash
python tools/check_updates.py            # what's newer (same Minecraft version, stable only)
python tools/check_updates.py --apply    # pin them
python tools/add.py datapack <slug>...    # add new Modrinth projects at their newest stable build
python tools/validate.py --online        # download + hash-check everything
```

An update has to be a stable release with a different file, published after the pinned version, so a
re-listed file (same jar, new version id) or a newer pre-release pin is never "updated" backwards.

Patched datapacks are the exception: `check_updates.py` lists a newer release of a patched pack as
"patched - re-snapshot needed" and `--apply` leaves its pin alone, because the patch was made against
the old file and may not fit the new one (see `docs/adr/0004-patched-datapacks-are-not-auto-updated.md`).
To take it, put the new upstream zip in the server's `datapack-originals/` and (edited) in its
datapacks folder, then snapshot the server as below; that re-makes the patch against the new file.

Then boot it locally on spare ports (doesn't disturb a server already on 25565):

```powershell
python tools/build.py
Expand-Archive dist\TheRealms-Server-*.zip $env:TEMP\realms-test -Force
.\tests\smoke.ps1 -Root $env:TEMP\realms-test\TheRealms-Server -Port 25566 -RconPort 25576
```

Open a PR. CI runs the same smoke test on a clean Windows runner.

## Capturing changes from a live server

If you add or update plugins/datapacks on a running server by hand, snapshot it back into the manifest:

```bash
python tools/snapshot.py server C:/MCServer/factions
python tools/snapshot.py client "C:/Games/PrismLauncher/instances/Factions Client/minecraft"
```

Every file must be on Modrinth (matched by SHA-1). Datapacks are read from the world folder named by
`level-name` in the server's `server.properties`. A datapack you edited in place is matched against
`datapack-originals/<same file name>` in the server folder, and the changed files become a patch:
`package/realms/patches/<slug>/` plus `"patch": {"path": "patches/<slug>", "base_sha512": ...}` on
the entry, pinned to the original's hash. A patch may only replace files that exist in the upstream
zip (adding or removing files fails the snapshot), and patch folders no datapack uses are deleted.
`validate.py` checks that every patch matches its entry's pinned hash, and `--online` applies each
patch to the real download to prove it still fits.

Datapacks and plugins keep the file name they have on the server. On `check_updates.py --apply`,
plugins take the new upstream file name, but datapacks keep theirs, because the world refers to
datapacks by file name (the rule is written down once, in `tools/entries.py`).
Config defaults are curated by hand: copy changed configs into `package/realms/defaults/` yourself, and
never copy files containing secrets (`server.properties` from a live server has the RCON password).

## Tests

```bash
pip install pytest ruff
python -m pytest -q && python -m ruff check tools tests && python tools/validate.py
```

The unit tests never touch the network or the real checkout: tools take an `Upstream` catalog and
a `Repo`, and tests pass a `RecordedHttp` adapter (replaying `tests/fixtures/upstream/*.json`, or
responses built in the test) and a temporary copy of the repo. A request with no recorded response
fails loudly. If an upstream API changes shape, or a test needs a new request, re-record the
fixtures from the live APIs (responses are trimmed to the fields the tools read):

```bash
python tests/fixtures/record.py
```

## Releasing

1. Bump `version` in `package/realms/manifest.json` (semver: patch = plugin bumps, minor = new content,
   major = new Minecraft version or a world reset).
2. Add a `## [x.y.z]` section to `CHANGELOG.md`.
3. Merge to `main`, then tag: `git tag vX.Y.Z && git push origin vX.Y.Z`.

The release workflow re-runs CI, refuses to publish if the tag and manifest version differ, and attaches
`TheRealms-Server-X.Y.Z.zip` and `TheRealms-Client-X.Y.Z.mrpack`.

## Changing Minecraft version

Every plugin and datapack needs a build for the new version. `check_updates.py` only looks within the
pinned version, so change `minecraft` in the manifest, run `snapshot.py` against a server you've upgraded
by hand, and expect world-gen datapack changes to affect new chunks only.
