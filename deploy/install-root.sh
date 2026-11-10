#!/bin/sh
# Installs what root runs: root-owned copies of the root scripts, and the systemd units, from root's own clone of the
# repo on GitHub, for a release that passed the release gate. docs/LIVE.md, "Root's own copies".
#
# Why: the backup, the staff helper and the restore drill run as root. They used to run from the checkout in
# /srv/monkey/repo, which the monkey user (and so the staff page, and anyone who gets in as monkey) can write: a
# changed script there ran as root on the next hour. Now root runs only these copies.
#
#   sh /opt/monkey/deploy/install-root.sh                 as root: the newest release tag
#   sh /opt/monkey/deploy/install-root.sh --tag=vX.Y.Z    as root: that release (to go back to an older one)
#   sh /opt/monkey/deploy/install-root.sh --check         any user: what an install would change, changing nothing
#
# The first time, root clones the repo and runs this from the clone (docs/LIVE.md gives the commands):
#   git clone https://github.com/gr8monk3ys/monkey-smp-server.git /opt/monkey/src
#   sh /opt/monkey/src/deploy/install-root.sh
#
# What an install does:
#   1. git fetch in ROOT_SRC (/opt/monkey/src, root's clone over https, never the monkey checkout) and picks the tag
#   2. asks the release gate (tools/release_gate.py, root's copy): a published release on GitHub that is this commit,
#      and green CI. Not yet: nothing is installed
#   3. checks out the tag and copies the root files (ROOT_FILES in lib.sh) to ROOT_DEST (/opt/monkey/deploy and
#      /opt/monkey/tools), owned by root and writable by root only; each copy is a new file moved into place, so a
#      script that is running keeps the copy it started with
#   4. copies the monkey-* units that changed into /etc/systemd/system, and the new ones (ROOT_NEW_UNITS), then
#      daemon-reload; restarts the timers and path units that changed (that never runs their service), and starts
#      monkey-logs.timer. It never enables the restore drill's timer: that waits for a first pass by hand.
#   5. writes ROOT_DEST/INSTALLED: the tag and commit
# It never touches the live folder, the world, the backups, the checkout or a setting.
#
# Plain POSIX sh, LF line endings, plain ASCII.
set -eu

LOG_NAME=install-root
. "$(dirname -- "$0")/lib.sh"

HERE=$(cd "$(dirname -- "$0")" && pwd)
ENV_FILE=${MONKEY_DEPLOY_ENV:-/etc/monkey-deploy.env}
REPO_DIR=${REPO_DIR:-$(setting REPO_DIR /srv/monkey/repo)}
SRC=${ROOT_SRC:-/opt/monkey/src}
ROOT_DEST=${ROOT_DEST:-/opt/monkey}
UNIT_DIR=${UNIT_DIR:-/etc/systemd/system}
REMOTE=https://github.com/gr8monk3ys/monkey-smp-server.git
RELEASE_GATE=$(setting RELEASE_GATE on)

mode=install
tag=''
for arg in "$@"; do
    case $arg in
        --check) mode=check ;;
        --tag=*) tag=${arg#--tag=} ;;
        *) echo "usage: sh $0 [--tag=vX.Y.Z | --check]" >&2; exit 2 ;;
    esac
done
if [ -n "$tag" ]; then
    case $tag in v[0-9]*.[0-9]*.[0-9]*) ;; *) die "--tag takes a release tag, vX.Y.Z, not '$tag'" ;; esac
    case ${tag#v} in *[!0-9.]* | *..* | *.) die "--tag takes a release tag, vX.Y.Z, not '$tag'" ;; esac
fi

if [ "$mode" = check ]; then
    # Against the deployed checkout: what this release would change for root.
    stale=$(root_stale "$REPO_DIR")
    if [ -z "$stale" ]; then
        log "root's copies and the units match $REPO_DIR"
    else
        log "root's copies or units that differ from $REPO_DIR (sudo sh $ROOT_DEST/deploy/install-root.sh installs them):"
        printf '%s\n' "$stale" | while IFS= read -r line; do log "  $line"; done
    fi
    exit 0
fi

[ "$(id -u)" = 0 ] || die 'run this as root: it installs what root runs'
cd /

# "root_only PATH": PATH (links resolved) is owned by root and nobody else may write to it, nor to a folder above it.
root_only() {
    p=$(realpath -e "$1") || die "there is no $1"
    while :; do
        perms=$(stat -c '%u %A' "$p") || die "can't read $p"
        case $perms in
            '0 '?????w???? | '0 '????????w?) die "$p is writable by others than root: chmod go-w $p" ;;
            '0 '*) ;;
            *) die "$p is not owned by root: chown root:root $p" ;;
        esac
        up=$(dirname -- "$p")
        [ "$up" != "$p" ] || break   # / (realpath gives a full path, so the walk ends there)
        p=$up
    done
}

# ---------------------------------------------------------------- 1. root's clone

if [ ! -d "$SRC/.git" ]; then
    mkdir -p "$(dirname -- "$SRC")"
    root_only "$(dirname -- "$SRC")"
    log "cloning $REMOTE into $SRC"
    git clone --quiet --no-checkout "$REMOTE" "$SRC"
fi
root_only "$SRC"
[ "$(git -C "$SRC" remote get-url origin)" = "$REMOTE" ] || die "$SRC's origin is not $REMOTE"
git -C "$SRC" fetch --quiet --tags --prune --force origin
if [ -z "$tag" ]; then
    tag=$(git -C "$SRC" tag -l 'v[0-9]*.[0-9]*.[0-9]*' --sort=-v:refname | head -n 1)
    [ -n "$tag" ] || die "no release tag (vX.Y.Z) in $SRC"
fi
commit=$(git -C "$SRC" rev-parse --verify --quiet "refs/tags/$tag^{commit}") || die "there is no tag $tag on GitHub"

# ---------------------------------------------------------------- 2. the release gate

# Root's installed copy of the gate when there is one, else the one beside this script (the first install, from the
# clone): both are root's.
if [ -f "$ROOT_DEST/tools/release_gate.py" ]; then GATE_TOOLS=$ROOT_DEST/tools; else GATE_TOOLS=$HERE/../tools; fi
release_gate "$commit" "$tag" || die "$tag was not installed: ${GATE_SAYS#release gate: }"

# ---------------------------------------------------------------- 3. root's copies

git -C "$SRC" -c advice.detachedHead=false checkout --quiet --force --detach "$commit"
for f in $ROOT_FILES; do
    [ -f "$SRC/$f" ] || die "$tag has no $f: it is older than root's copies (install-root.sh came with them)"
done
for d in "$ROOT_DEST" "$ROOT_DEST/deploy" "$ROOT_DEST/tools"; do
    install -d -m 755 -o root -g root "$d"
done
root_only "$ROOT_DEST/deploy"
root_only "$ROOT_DEST/tools"
copied=0
for f in $ROOT_FILES; do
    if ! cmp -s "$SRC/$f" "$ROOT_DEST/$f"; then
        install -m 644 -o root -g root "$SRC/$f" "$ROOT_DEST/$f.new"
        mv -f "$ROOT_DEST/$f.new" "$ROOT_DEST/$f"
        log "installed $ROOT_DEST/$f"
        copied=$((copied + 1))
    fi
done

# ---------------------------------------------------------------- 4. the units

changed=''
for u in "$SRC"/deploy/monkey-*.service "$SRC"/deploy/monkey-*.timer "$SRC"/deploy/monkey-*.path; do
    [ -f "$u" ] || continue
    n=${u##*/}
    if [ -f "$UNIT_DIR/$n" ]; then
        cmp -s "$u" "$UNIT_DIR/$n" && continue
    else
        case " $(printf '%s' "$ROOT_NEW_UNITS" | tr '\n' ' ') " in *" $n "*) ;; *) continue ;; esac
    fi
    install -m 644 -o root -g root "$u" "$UNIT_DIR/$n"
    log "installed $UNIT_DIR/$n"
    changed="$changed $n"
done
if [ -n "$changed" ]; then
    systemctl daemon-reload
    for n in $changed; do
        case $n in
            # A changed schedule or watch takes effect on restart; try-restart leaves a stopped one stopped.
            *.timer | *.path) systemctl try-restart "$n" ;;
        esac
    done
fi
# The alert and log units run as monkey from the deployed checkout: start them only once it has their scripts.
if [ -f "$REPO_DIR/deploy/monkey-logs.sh" ] && [ -f "$REPO_DIR/deploy/monkey-alert.sh" ]; then
    systemctl enable --now monkey-logs.timer >/dev/null 2>&1 || log 'WARNING: could not start monkey-logs.timer'
else
    log "NOTE: $REPO_DIR has no monkey-logs.sh or monkey-alert.sh yet (the deploy hasn't brought $tag): run this again once it is live, to start monkey-logs.timer"
fi
printf '%s %s\n' "$tag" "$commit" >"$ROOT_DEST/INSTALLED.new"
mv -f "$ROOT_DEST/INSTALLED.new" "$ROOT_DEST/INSTALLED"
log "done: root's copies are $tag ($copied file(s) changed), units changed:${changed:- none}"
[ "$RELEASE_GATE" != off ] || log 'NOTE: RELEASE_GATE=off in the settings: put it back to on'
