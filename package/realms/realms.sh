#!/bin/sh
# Runs realms.ps1 (the installer and launcher) on Linux and macOS:
#
#     sh realms/realms.sh <command> [options]      e.g.  sh realms/realms.sh install -AcceptEula -NonInteractive
#
# The commands and options are the ones realms.ps1 takes; start.sh, stop.sh and the other launchers
# next to the realms folder all come through here. realms.ps1 needs PowerShell 7.2 or newer:
#   - pwsh on the PATH is used when it is new enough (set REALMS_IGNORE_SYSTEM_PWSH=1 to skip it);
#   - otherwise the PowerShell pinned in pwsh.lock is downloaded once into pwsh/<platform>/ next to
#     the realms folder (beside java/<platform>/), checked against its sha256, and used from there.
#     One folder per platform, so a release folder shared by a Mac and a Linux container works for both.
# Server memory: REALMS_MEMORY_GB=8 sh start.sh (otherwise picked from the RAM or container limit).
# "start" installs first and then replaces this shell with the Java server process itself, so the
# server gets the console and the signals (Ctrl+C, docker stop, systemd) and saves the world on them.
#
# Plain POSIX sh: no bash features, LF line endings, plain ASCII.

here=$(cd "$(dirname "$0")" && pwd) || exit 1
root=$(dirname "$here")

fail() {
    printf 'The Realms: %s\n' "$*" >&2
    exit 1
}

# ---------------------------------------------------------------- platform

platform() {
    case "$(uname -s)" in
        Linux) os=linux ;;
        Darwin) os=mac ;;
        *) fail "this computer runs $(uname -s), but The Realms runs on Windows, Linux and macOS only." ;;
    esac
    case "$(uname -m)" in
        x86_64 | amd64) arch=x64 ;;
        aarch64 | arm64) arch=aarch64 ;;
        *) fail "this computer has a $(uname -m) processor, but The Realms needs a 64-bit Intel/AMD (x64) or ARM (aarch64) one." ;;
    esac
    # A Terminal running under Rosetta on an Apple Silicon Mac reports x86_64; use the native builds.
    if [ "$os" = mac ] && [ "$arch" = x64 ] && [ "$(sysctl -n sysctl.proc_translated 2>/dev/null)" = 1 ]; then
        arch=aarch64
    fi
    if [ "$os" = linux ] && ls /lib/ld-musl-* >/dev/null 2>&1; then
        fail "this Linux uses musl (Alpine?), but Java and PowerShell here need a glibc Linux such as Debian, Ubuntu or Fedora."
    fi
    echo "$os-$arch"
}

# ---------------------------------------------------------------- PowerShell

# True if $1 is a pwsh of version 7.2 or newer.
pwsh_ok() {
    v=$("$1" --version 2>/dev/null | sed -n 's/^PowerShell \([0-9][0-9]*\)\.\([0-9][0-9]*\).*/\1 \2/p')
    [ -n "$v" ] || return 1
    major=${v% *}
    minor=${v#* }
    [ "$major" -gt 7 ] || { [ "$major" -eq 7 ] && [ "$minor" -ge 2 ]; }
}

sha256_of() {
    if command -v sha256sum >/dev/null 2>&1; then
        sha256sum "$1" | cut -d' ' -f1
    elif command -v shasum >/dev/null 2>&1; then
        shasum -a 256 "$1" | cut -d' ' -f1
    else
        fail "can't check downloads: install sha256sum (coreutils) or shasum (perl)."
    fi
}

download() {
    if command -v curl >/dev/null 2>&1; then
        # -C - resumes a download that was cut off earlier.
        curl -fL --retry 3 --connect-timeout 30 -C - -o "$2" "$1"
    elif command -v wget >/dev/null 2>&1; then
        wget -c -O "$2" "$1"
    else
        fail "can't download PowerShell: install curl or wget (for example: sudo apt install curl)."
    fi
}

# Installs the pinned PowerShell for platform $1 under pwsh/$1/ (skipped when already installed and
# verified) and prints the path of its pwsh. The download only lands there after its sha256 matched.
pinned_pwsh() {
    runtime="$root/pwsh/$1"
    url=
    sha=
    while read -r p u s; do
        if [ "$p" = "$1" ]; then url=$u; sha=$(printf '%s' "$s" | tr -d '\r'); fi
    done < "$here/pwsh.lock"
    [ -n "$url" ] || fail "realms/pwsh.lock has no PowerShell for $1."
    name=$(basename "$url" .tar.gz)
    dest="$runtime/$name"
    if [ -x "$dest/pwsh" ] && [ "$(cat "$dest/.realms-sha256" 2>/dev/null)" = "$sha" ]; then
        echo "$dest/pwsh"
        return
    fi
    command -v tar >/dev/null 2>&1 || fail "can't unpack PowerShell: install tar (and gzip)."
    mkdir -p "$runtime" || fail "can't create $runtime."
    part="$runtime/$name.tar.gz.part"
    echo "==> Downloading PowerShell for $1 (about 75 MB, once): $url" >&2
    for try in 1 2; do
        download "$url" "$part" >&2 || fail "the PowerShell download failed. Check the internet connection and run this again."
        got=$(sha256_of "$part")
        [ "$got" = "$sha" ] && break
        rm -f "$part"
        [ "$try" = 2 ] && fail "the PowerShell download doesn't match pwsh.lock (sha256 $got, expected $sha)."
        echo "    The download was damaged; downloading it again..." >&2
    done
    rm -rf "$dest" "$dest.extract"
    mkdir -p "$dest.extract" || exit 1
    tar -xzf "$part" -C "$dest.extract" || fail "couldn't unpack $part (is gzip installed?)."
    chmod +x "$dest.extract/pwsh" || exit 1
    mv "$dest.extract" "$dest" || exit 1
    printf '%s\n' "$sha" > "$dest/.realms-sha256"
    rm -f "$part"
    # PowerShell versions from earlier releases (of this platform only).
    for old in "$runtime"/*; do
        [ "$old" = "$dest" ] || rm -rf "$old"
    done
    echo "    PowerShell ready." >&2
    echo "$dest/pwsh"
}

# ---------------------------------------------------------------- run

plat=$(platform) || exit 1
pwsh=
if [ "${REALMS_IGNORE_SYSTEM_PWSH:-}" != 1 ] && command -v pwsh >/dev/null 2>&1 && pwsh_ok pwsh; then
    pwsh=pwsh
else
    pwsh=$(pinned_pwsh "$plat") || exit 1
fi

# .NET needs ICU for culture data; minimal Linux images (Debian slim, many containers) don't ship it.
if [ "$plat" != "${plat#linux-}" ] && [ -z "${DOTNET_SYSTEM_GLOBALIZATION_INVARIANT:-}" ]; then
    icu=
    for f in /usr/lib/libicuuc.so* /usr/lib64/libicuuc.so* /usr/lib/*/libicuuc.so* /lib/*/libicuuc.so*; do
        [ -e "$f" ] && icu=yes
    done
    [ -n "$icu" ] || export DOTNET_SYSTEM_GLOBALIZATION_INVARIANT=1
fi
export POWERSHELL_TELEMETRY_OPTOUT=1
export POWERSHELL_UPDATECHECK=Off

if [ "${1:-}" = start ]; then
    # realms.ps1 installs, then writes the launch (folder, then java and its arguments, one per line).
    launch="$root/.realms-launch"
    rm -f "$launch"
    "$pwsh" -NoProfile -File "$here/realms.ps1" "$@" -LaunchFile "$launch"
    code=$?
    if [ "$code" -ne 0 ] || [ ! -s "$launch" ]; then
        rm -f "$launch"
        echo >&2
        echo "Something went wrong - see the message above. READ ME FIRST.txt has help." >&2
        [ "$code" -ne 0 ] || code=1
        exit "$code"
    fi
    {
        IFS= read -r dir
        set --
        while IFS= read -r arg; do set -- "$@" "$arg"; done
    } < "$launch"
    rm -f "$launch"
    cd "$dir" || exit 1
    exec "$@"
fi

"$pwsh" -NoProfile -File "$here/realms.ps1" "$@"
code=$?
if [ "$code" -ne 0 ]; then
    echo >&2
    echo "Something went wrong - see the message above. READ ME FIRST.txt has help." >&2
fi
exit "$code"
