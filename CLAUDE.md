# Monkey SMP server

Everything is named Monkey SMP / `monkey`: what players see and the code, folders, command, data pack namespace
and download names alike (see `GLOSSARY.md`). Don't bring back the old name; only `tools/migrate_names.py` (old
worlds and server folders) and the player installer's move of the old game folder still have to know it.

Server package for a Fabric 26.3 factions server (1.x releases were Paper 26.1.2) that runs natively on
Windows (`.bat`), Linux and macOS (`.sh` launchers + the `monkey/monkey.sh` PowerShell bootstrap) and in
Docker (`package/docker/`), with one PowerShell installer (ADR-0007), plus a "Prepare for Hosting" bundle for
panel hosts (ADR-0006). `package/` is exactly what ships in the release zip; `package/monkey/manifest.json`
pins every download (Java per platform) and `package/monkey/pwsh.lock` the portable PowerShell 7; `tools/`
are maintainer scripts (Python stdlib); `tests/smoke.ps1` boots the real server. See `README.md` and
`docs/MAINTAINING.md`.

- Checks: `python tools/checks.py` (ruff, pytest, validate.py, datapacks.py --check, dash -n, Pester 5, the site via bun); CI runs the same file.
  Before a PR leaves draft: `/code-review`, fix its findings (docs/MAINTAINING.md, "Review"). No Actions minutes? `python tools/local_ci.py <PR>`
- `package/monkey/*.ps1`/`*.psm1` must stay plain ASCII and run on both Windows PowerShell 5.1 and PowerShell 7
  on Linux/macOS (ADR-0003, ADR-0007): Windows-only calls go behind a platform check.
- `package/*.sh`, `package/monkey/monkey.sh` and `Start Server.command` are POSIX `sh` (no bash-isms), LF line endings.
- `site/` is the public website: Next.js built as a static export with bun; links, the address and the launch
  time live in `site/config.json`. See `site/README.md`.
- Domain terms: `GLOSSARY.md`. Decisions not to re-litigate: `docs/adr/`.
- Never commit worlds, jars, datapacks or a live `server.properties` (it holds the RCON password).

## Agent skills

### Issue tracker

Issues live in GitHub Issues for gr8monk3ys/monkey-smp-server (via `gh`). See `docs/agents/issue-tracker.md`.

### Triage labels

Default vocabulary: needs-triage, needs-info, ready-for-agent, ready-for-human, wontfix. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: root `GLOSSARY.md` + `docs/adr/` (created lazily). See `docs/agents/domain.md`.
