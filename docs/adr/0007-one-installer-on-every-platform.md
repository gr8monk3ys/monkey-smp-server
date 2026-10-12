---
status: accepted (extends ADR-0003, amends ADR-0006)
---
# One PowerShell installer on every platform, bootstrapped by sh on macOS and Linux

From 2.3 the server package runs natively on Windows, Linux (x64, arm64) and macOS (Intel, Apple Silicon), and in Docker, with one installer: `realms.ps1` and `Realms.psm1`. It runs on Windows PowerShell 5.1 as before, so Windows hosts still install nothing, and on PowerShell 7 everywhere else. On macOS and Linux, POSIX `sh` launchers call `realms/realms.sh`, which uses `pwsh` if it is installed and otherwise downloads a portable PowerShell 7 from Microsoft's GitHub releases into the server folder, pinned by URL and hash in `realms/pwsh.lock` and checked like every other download. It needs only `curl` or `wget`, `tar` and `sha256sum` or `shasum`, which every Mac and nearly every Linux has. The manifest pins a Java build for each platform. The Docker setup's image holds only an operating system and those tools: it mounts the release folder and runs the same installer in it, so nothing third-party is redistributed (ADR-0002) and one folder can move between a native and a Docker run.

The costs: a first start on macOS or Linux without PowerShell 7 downloads about 70 MB more; the installer must keep working on both PowerShell 5.1 and 7, so Windows-only calls (CIM, robocopy, `\` paths, `.exe` names) sit behind a platform check, and ADR-0003's plain-ASCII rule now covers code that runs on all three systems; and macOS is only booted in CI on releases and manual runs, because macOS runners are slow and scarce, so a macOS-only break can reach `main` and is caught at release time at the latest. Prepare for Hosting (ADR-0006) now works on every platform, and a Linux VPS no longer needs the hosting bundle; it stays for panel hosts that only accept a finished server.

## Considered Options

- A second installer in `sh` or Python for macOS and Linux: two copies of the install, patch, hash and RCON logic to keep in step, and Python isn't on a Mac until the developer tools are installed.
- Ask macOS and Linux hosts to install PowerShell 7 themselves: one more manual step (with `sudo` on Linux) for hosts who aren't technical.
- Ship PowerShell 7 inside the release zip: about 70 MB per platform in a download that is otherwise about 100 KB.
- PowerShell 7 on Windows too: Windows hosts would have to install it, which ADR-0003 rules out.
- A published Docker image with the server inside: redistributes All-Rights-Reserved mods, as ADR-0006 already rejected.
