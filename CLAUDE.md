# The Realms server

One-click Windows package for a Paper 26.1.2 factions server. `package/` is exactly what ships in the
release zip; `package/realms/manifest.json` pins every download; `tools/` are maintainer scripts
(Python stdlib); `tests/smoke.ps1` boots the real server. See `README.md` and `docs/MAINTAINING.md`.

- Checks: `pytest -q && ruff check tools tests && python tools/validate.py`
- `package/realms/realms.ps1` must stay plain ASCII and Windows PowerShell 5.1 compatible.
- Never commit worlds, jars, datapacks or a live `server.properties` (it holds the RCON password).

## Agent skills

### Issue tracker

Issues live in GitHub Issues for gr8monk3ys/the-realms-server (via `gh`). See `docs/agents/issue-tracker.md`.

### Triage labels

Default vocabulary: needs-triage, needs-info, ready-for-agent, ready-for-human, wontfix. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: root `GLOSSARY.md` + `docs/adr/` (created lazily). See `docs/agents/domain.md`.
