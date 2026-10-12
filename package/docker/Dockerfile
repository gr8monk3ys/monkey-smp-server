# The Realms on Docker: a small Debian base that runs the release folder's own installer.
#
# The image holds no Minecraft, mod or Java files (docs/adr/0002): compose.yaml mounts the whole
# release folder at /realms, and realms/realms.sh downloads PowerShell, Java, Fabric and the mods
# into that folder on the first start, checking every hash, exactly as a native start does. So a
# Docker run and a native run of the same folder share one world, one Java and one install.
FROM debian:12-slim

# ca-certificates, curl, tar, gzip: what realms.sh needs to fetch the pinned PowerShell and Java.
# libicu72, libssl3, libgssapi-krb5-2: what PowerShell needs on Debian 12 (no ICU-less mode).
# fontconfig: what Java's AWT needs if a mod draws text (the eclipse-temurin images ship it too).
# tini: PID 1, passes docker stop's SIGTERM to the entrypoint and reaps orphans.
# tzdata: so TZ=Europe/Berlin and the like work for log and backup times.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates curl tar gzip tini tzdata fontconfig \
        libicu72 libssl3 libgssapi-krb5-2 \
    && rm -rf /var/lib/apt/lists/*

# HOME is outside /realms (PowerShell keeps caches there) and writable by whichever user the
# entrypoint runs as. C.UTF-8 so Java and PowerShell read non-ASCII file names correctly.
ENV LANG=C.UTF-8 \
    HOME=/home/realms \
    POWERSHELL_TELEMETRY_OPTOUT=1 \
    POWERSHELL_UPDATECHECK=Off \
    DOTNET_CLI_TELEMETRY_OPTOUT=1 \
    DOTNET_NOLOGO=1
RUN mkdir -m 1777 /home/realms

COPY entrypoint.sh /usr/local/bin/realms-entrypoint
# "realms <command>" for docker compose exec: runs realms.sh as the same user as the server.
RUN chmod 0755 /usr/local/bin/realms-entrypoint \
    && ln -s realms-entrypoint /usr/local/bin/realms

WORKDIR /realms
# 25565 game, 24454/udp Simple Voice Chat, 8100 BlueMap. RCON (25575) stays inside the container.
EXPOSE 25565/tcp 24454/udp 8100/tcp
STOPSIGNAL SIGTERM
ENTRYPOINT ["tini", "--", "realms-entrypoint"]
CMD ["server"]
