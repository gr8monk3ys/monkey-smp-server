# Maintaining the pack

Tools are plain Python 3.11+ with no dependencies (tests use `pytest`, lint uses `ruff`).

## Where things live

| Path | What | Edited by |
|---|---|---|
| `package/realms/manifest.json` | pinned Java, Paper, plugins, datapacks | `tools/snapshot.py`, `tools/check_updates.py --apply`, or by hand |
| `package/realms/defaults/` | first-run configs, copied only if missing | by hand |
| `package/realms/patches/<slug>/` | files replaced inside a downloaded datapack | `tools/snapshot.py` |
| `client/` | the player modpack (`modrinth.index.json` + `overrides/`) | `tools/snapshot.py client` |

## Updating plugins and Paper

```bash
python tools/check_updates.py            # what's newer (same Minecraft version, stable only)
python tools/check_updates.py --apply    # pin them
python tools/validate.py --online        # download + hash-check everything
```

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

Every file must be on Modrinth (matched by SHA-1). A datapack you edited in place is matched against
`datapack-originals/<same file name>` in the server folder, and the changed files become a patch.
Config defaults are curated by hand: copy changed configs into `package/realms/defaults/` yourself, and
never copy files containing secrets (`server.properties` from a live server has the RCON password).

## Releasing

1. Bump `version` in `package/realms/manifest.json` (semver: patch = plugin bumps, minor = new content,
   major = new Minecraft version or a world reset).
2. Add a `## [x.y.z]` section to `CHANGELOG.md`.
3. Merge to `main`, then tag: `git tag vX.Y.Z && git push origin vX.Y.Z`.

The release workflow re-runs CI, refuses to publish if the tag and manifest version differ, and attaches
`TheRealms-Server-X.Y.Z.zip` and `TheRealms-Client-X.Y.Z.mrpack`.

## Changing Minecraft version

All 20 plugins and 24 datapacks need builds for the new version. `check_updates.py` only looks within the
pinned version, so change `minecraft` in the manifest, run `snapshot.py` against a server you've upgraded
by hand, and expect world-gen datapack changes to affect new chunks only.
