# Monkey SMP server

Players see the name Monkey SMP (formerly The Realms); internal names keep `realms` (see `GLOSSARY.md`).

Server package for a Fabric 26.3 factions server (1.x releases were Paper 26.1.2) that runs natively on
Windows (`.bat`), Linux and macOS (`.sh` launchers + the `realms/realms.sh` PowerShell bootstrap) and in
Docker (`package/docker/`), with one PowerShell installer (ADR-0007), plus a "Prepare for Hosting" bundle for
panel hosts (ADR-0006). `package/` is exactly what ships in the release zip; `package/realms/manifest.json`
pins every download (Java per platform) and `package/realms/pwsh.lock` the portable PowerShell 7; `tools/`
are maintainer scripts (Python stdlib); `tests/smoke.ps1` boots the real server. See `README.md` and
`docs/MAINTAINING.md`.

- Checks: `python -m pytest -q && python -m ruff check tools tests && python tools/validate.py`, plus Pester 5: `Invoke-Pester tests/Realms.Tests.ps1`
- `package/realms/*.ps1`/`*.psm1` must stay plain ASCII and run on both Windows PowerShell 5.1 and PowerShell 7
  on Linux/macOS (ADR-0003, ADR-0007): Windows-only calls go behind a platform check.
- `package/*.sh`, `package/realms/realms.sh` and `Start Server.command` are POSIX `sh` (no bash-isms), LF line endings.
- Domain terms: `GLOSSARY.md`. Decisions not to re-litigate: `docs/adr/`.
- Never commit worlds, jars, datapacks or a live `server.properties` (it holds the RCON password).

## Agent skills

### Issue tracker

Issues live in GitHub Issues for gr8monk3ys/monkey-smp-server (via `gh`). See `docs/agents/issue-tracker.md`.

### Triage labels

Default vocabulary: needs-triage, needs-info, ready-for-agent, ready-for-human, wontfix. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: root `GLOSSARY.md` + `docs/adr/` (created lazily). See `docs/agents/domain.md`.
