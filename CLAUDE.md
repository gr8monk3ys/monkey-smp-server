# Monkey SMP server

Everything is named Monkey SMP / `monkey`: what players see and the code, folders, command, data pack namespace
and download names alike (see `GLOSSARY.md`). Don't bring back the old name; only `tools/migrate_names.py` (old
worlds and server folders) and the player installer's move of the old game folder still have to know it.

Server package for a Fabric 26.2 factions server (1.x releases were Paper 26.1.2) that runs natively on
Windows (`.bat`), Linux and macOS (`.sh` launchers + the `monkey/monkey.sh` PowerShell bootstrap) and in
Docker (`package/docker/`), with one PowerShell installer (ADR-0007), plus a "Prepare for Hosting" bundle for
panel hosts (ADR-0006). `package/` is exactly what ships in the release zip; `package/monkey/manifest.json`
pins every download (Java per platform) and `package/monkey/pwsh.lock` the portable PowerShell 7; `tools/`
are maintainer scripts (Python stdlib); `tests/smoke.ps1` boots the real server. See `README.md` and
`docs/MAINTAINING.md`.

- Checks: `make check` (= `python tools/checks.py`; ruff, pytest, validate.py, datapacks.py --check, dash -n, Pester 5, the site via bun); CI runs the same file.
  Before a PR leaves draft: `/code-review`, fix its findings (docs/MAINTAINING.md, "Review"). No Actions minutes? `python tools/local_ci.py <PR>`
- `package/monkey/*.ps1`/`*.psm1` must stay plain ASCII and run on both Windows PowerShell 5.1 and PowerShell 7
  on Linux/macOS (ADR-0003, ADR-0007): Windows-only calls go behind a platform check.
- `package/*.sh`, `package/monkey/monkey.sh` and `Start Server.command` are POSIX `sh` (no bash-isms), LF line endings.
- `site/` is the public website: Next.js built as a static export with bun; links, the address and the launch
  time live in `site/config.json`. See `site/README.md`.
- Domain terms: `GLOSSARY.md`. Decisions not to re-litigate: `docs/adr/`.
- Never commit worlds, jars, datapacks or a live `server.properties` (it holds the RCON password).

## Working agreements

- Feature freeze for the rest of Season I: fixes, monitoring and simplification only. New gameplay packs and new
  staff page features wait for Season II.
- Keep a PR under about 800 changed lines, generated output (builds, fixtures, lock files) aside.
- No two live releases within 48 hours unless the second fixes something broken live.
- A release needs CI's boot tests green and the Clean install workflow passing (docs/MAINTAINING.md, "Releasing").
- When something breaks on the live server, start with `docs/RUNBOOK.md`.

## Agent skills

### Issue tracker

GitHub Issues on `gr8monk3ys/monkey-smp-server`, via the `gh` CLI. See `docs/agents/issue-tracker.md`.

### Triage labels

The five canonical roles, label string equal to role name. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: `GLOSSARY.md` + `docs/adr/` at the repo root. See `docs/agents/domain.md`.
