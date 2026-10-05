# The Realms server

One-click Windows package for a Paper 26.1.2 factions server. `package/` is exactly what ships in the
release zip; `package/realms/manifest.json` pins every download; `tools/` are maintainer scripts
(Python stdlib); `tests/smoke.ps1` boots the real server. See `README.md` and `docs/MAINTAINING.md`.

- Checks: `python -m pytest -q && python -m ruff check tools tests && python tools/validate.py`, plus Pester 5: `Invoke-Pester tests/Realms.Tests.ps1`
- `package/realms/*.ps1`/`*.psm1` must stay plain ASCII and Windows PowerShell 5.1 compatible (ADR-0003).
- Domain terms: `GLOSSARY.md`. Decisions not to re-litigate: `docs/adr/`.
- Never commit worlds, jars, datapacks or a live `server.properties` (it holds the RCON password).

## Agent skills

### Issue tracker

Issues live in GitHub Issues for gr8monk3ys/the-realms-server (via `gh`). See `docs/agents/issue-tracker.md`.

### Triage labels

Default vocabulary: needs-triage, needs-info, ready-for-agent, ready-for-human, wontfix. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: root `GLOSSARY.md` + `docs/adr/` (created lazily). See `docs/agents/domain.md`.
