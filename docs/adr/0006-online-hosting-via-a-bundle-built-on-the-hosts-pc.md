# Online hosting uses a bundle the host builds on their own PC

To run The Realms on an online service, the host runs "Prepare for Hosting" on their Windows PC: the normal install downloads and verifies every artifact from its upstream, applies patches and defaults, and packs the finished server into one zip with a `start.sh`, a `docker-compose.yml` and plain-language hosting steps. That one zip works on panel-based Minecraft hosts (upload, pick the jar and Java version) and on a Linux VPS (Docker or plain Java). We don't publish a ready-made server pack or Docker image because some artifacts are All-Rights-Reserved and two of them are patched; building the bundle from upstream on the host's machine keeps ADR-0002 intact. The cost is that preparing a bundle needs a Windows PC; a Linux-native installer can come later if a host without Windows needs one.

## Considered Options

- A server `.mrpack` for hosts with Modrinth-pack installers: can't carry the patched mods, so Strength SMP would be broken.
- A published Docker image or full server zip: redistributes All-Rights-Reserved files.
- A second installer in Python or PowerShell 7 for Linux: double the host-side code to maintain for a case no host needs yet.
