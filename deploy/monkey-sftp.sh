#!/bin/sh
# SFTP logins for staff: an owner's step, as root (docs/LIVE.md, "The staff page", "SFTP"). A login made here can
# use SFTP and nothing else (no shell, no forwarding, no tty), logs in with a key only, and sees one folder: the
# server's (LIVE_DIR/server), through a chroot. The staff page shows the host, the port and the user names
# (STAFF_DIR/sftp.json, no secrets); it can't make or remove a login itself.
#
#   sudo sh monkey-staff.sh --add-sftp-user NAME KEYFILE    adds NAME (or gives NAME a new key): KEYFILE is NAME's
#                                                           public key, one line (ssh-ed25519 AAAA... is best)
#   sudo sh monkey-staff.sh --remove-sftp-user NAME         takes NAME out again; the server's files stay
#
# (monkey-staff.sh hands both to this script.) What --add-sftp-user does:
#   - the group monkey-sftp, and NAME in it: no home, nologin as the shell, no password (a key only)
#   - /etc/ssh/monkey-sftp-keys/NAME: the public key (root's, 644)
#   - /srv/monkey-sftp/NAME (root's, 755, as sshd wants a chroot) with server/ in it: a bind mount of LIVE_DIR/server,
#     also a line in /etc/fstab so it is back after a reboot
#   - ACLs on LIVE_DIR/server: NAME may read and write there, and what NAME makes stays the server user's to change
#   - /etc/ssh/sshd_config.d/monkey-sftp.conf: Match Group monkey-sftp (chroot, internal-sftp, key only, no forwarding),
#     ended by Match all. `sshd -t`, and `sshd -T` for NAME and for root, are checked before sshd is reloaded; if any
#     fails the old drop-in is put back and nothing is reloaded
#   - STAFF_DIR/sftp.json: the host (SFTP_HOST from the env file, else hostname -f), the port and the user names
#
# Reads LIVE_DIR, STAFF_DIR and SFTP_HOST from /etc/monkey-deploy.env (or MONKEY_DEPLOY_ENV). Needs setfacl (acl).
#
# Plain POSIX sh, LF line endings, plain ASCII.
set -eu

LOG_NAME=monkey-sftp
. "$(dirname -- "$0")/lib.sh"

usage() {
    echo "usage: sudo sh monkey-staff.sh --add-sftp-user NAME KEYFILE | --remove-sftp-user NAME" >&2
    echo "  NAME: a lowercase letter, then up to 30 lowercase letters, digits, - and _" >&2
    exit 2
}

MODE=${1:-}
NAME=${2:-}
KEY=${3:-}
case $MODE in
    --add-sftp-user) [ -n "$KEY" ] || usage ;;
    --remove-sftp-user) [ -z "$KEY" ] || usage ;;
    *) usage ;;
esac
case $NAME in
    [a-z]*) ;;
    *) usage ;;
esac
case $NAME in *[!a-z0-9_-]*) usage ;; esac
[ ${#NAME} -le 31 ] || usage

ENV_FILE=${MONKEY_DEPLOY_ENV:-/etc/monkey-deploy.env}
LIVE_DIR=${LIVE_DIR:-$(setting LIVE_DIR /srv/monkey/MonkeySMP-Server)}
STAFF_DIR=${STAFF_DIR:-$(setting STAFF_DIR /srv/monkey/staff)}
SFTP_HOST=${SFTP_HOST:-$(setting SFTP_HOST '')}
GROUP=monkey-sftp
# Root-owned and outside /srv/monkey (the monkey user owns that): sshd needs every component of a chroot path to be
# root's and not group/other-writable. An older version used /srv/monkey/sftp; it is left alone if it is there.
CHROOTS=/srv/monkey-sftp
KEYS=/etc/ssh/monkey-sftp-keys
DROPIN=/etc/ssh/sshd_config.d/monkey-sftp.conf
SERVER=$LIVE_DIR/server
JAIL=$CHROOTS/$NAME
MOUNT=$JAIL/server
FSTAB_LINE="$SERVER $MOUNT none bind 0 0"

[ "$(id -u)" = 0 ] || die 'run as root: it adds a system user and changes sshd'
SSHD=$(command -v sshd 2>/dev/null || echo /usr/sbin/sshd)
[ -x "$SSHD" ] || die 'sshd is missing'
command -v setfacl >/dev/null 2>&1 || die 'setfacl is missing: sudo apt install acl'
[ -d "$SERVER" ] || die "no $SERVER: is the server installed?"
case $SERVER in *[!A-Za-z0-9/._-]*) die "LIVE_DIR has characters /etc/fstab can't hold: $LIVE_DIR" ;; esac
grep -Eq '^[[:space:]]*Include[[:space:]]+/etc/ssh/sshd_config\.d/\*\.conf' /etc/ssh/sshd_config ||
    die '/etc/ssh/sshd_config does not Include /etc/ssh/sshd_config.d/*.conf: add that line at its top first'
SERVER_USER=$(stat -c %U "$LIVE_DIR")

# True when NAME is an account in the monkey-sftp group (its primary group).
is_ours() {
    o_gid=$(getent group "$GROUP" | cut -d: -f3)
    [ -n "$o_gid" ] && [ "$(id -g "$1" 2>/dev/null || true)" = "$o_gid" ]
}

# "dropin FILE": the sshd drop-in. Match all at the end, so nothing after it in sshd_config applies only to the group.
dropin() {
    cat >"$1" <<EOF
# Staff SFTP logins (deploy/monkey-sftp.sh, docs/LIVE.md): SFTP only, a key only, inside their own folder.
Match Group $GROUP
    ChrootDirectory $CHROOTS/%u
    ForceCommand internal-sftp -d /server -u 0002
    AuthorizedKeysFile $KEYS/%u
    PubkeyAuthentication yes
    PasswordAuthentication no
    KbdInteractiveAuthentication no
    AllowTcpForwarding no
    AllowStreamLocalForwarding no
    AllowAgentForwarding no
    X11Forwarding no
    PermitTunnel no
    PermitTTY no
Match all
EOF
}

# "effective USER": sshd's settings for a login by USER from this machine.
effective() { "$SSHD" -T -C "user=$1,host=localhost,addr=127.0.0.1" 2>/dev/null; }

# Whether sshd, with the drop-in, sends NAME to internal-sftp in its chroot, and root to neither.
sshd_right() {
    "$SSHD" -t || return 1
    s_name=$(effective "$NAME") || return 1
    s_root=$(effective root) || return 1
    printf '%s\n' "$s_name" | grep -q '^forcecommand internal-sftp' || return 1
    printf '%s\n' "$s_name" | grep -q "^chrootdirectory $CHROOTS/" || return 1
    printf '%s\n' "$s_name" | grep -qx 'passwordauthentication no' || return 1
    ! printf '%s\n' "$s_root" | grep -q '^forcecommand internal-sftp'
}

reload_sshd() { systemctl reload ssh 2>/dev/null || systemctl reload sshd; }

# STAFF_DIR/sftp.json for the page: the host, the port and every user in the group. No secrets.
write_card() {
    w_gid=$(getent group "$GROUP" 2>/dev/null | cut -d: -f3)
    w_users=''
    if [ -n "$w_gid" ]; then
        w_users=$(getent passwd | awk -F: -v g="$w_gid" '$4 == g { printf "%s\"%s\"", (n++ ? "," : ""), $1 }')
    fi
    w_host=${SFTP_HOST:-$(hostname -f 2>/dev/null || hostname)}
    case $w_host in *[!A-Za-z0-9.:-]* | '') w_host=$(hostname) ;; esac
    w_port=$(effective root | sed -n 's/^port //p' | head -n 1)
    case $w_port in '' | *[!0-9]*) w_port=22 ;; esac
    [ -d "$STAFF_DIR" ] || { log "no $STAFF_DIR: the page's SFTP card waits for sudo sh monkey-staff.sh --install"; return 0; }
    w_tmp=$(mktemp "$STAFF_DIR/.sftp.XXXXXX")
    printf '{"host":"%s","port":%s,"users":[%s]}\n' "$w_host" "$w_port" "$w_users" >"$w_tmp"
    chmod 644 "$w_tmp"
    mv -f "$w_tmp" "$STAFF_DIR/sftp.json"
    SFTP_SHOWN_HOST=$w_host
    SFTP_SHOWN_PORT=$w_port
}

if [ "$MODE" = --add-sftp-user ]; then
    [ -f "$KEY" ] && [ ! -L "$KEY" ] || die "$KEY is not a file"
    ! grep -q 'PRIVATE KEY' "$KEY" || die "$KEY is a private key: give the public one (the .pub file), and keep the private one secret"
    [ "$(grep -c . "$KEY")" = 1 ] || die "$KEY must be one public key on one line"
    case $(cut -d' ' -f1 "$KEY") in
        ssh-ed25519 | ssh-rsa | ecdsa-sha2-nistp256 | ecdsa-sha2-nistp384 | ecdsa-sha2-nistp521 | \
            sk-ssh-ed25519@openssh.com | sk-ecdsa-sha2-nistp256@openssh.com) ;;
        *) die "$KEY does not start with a key type (ssh-ed25519, ssh-rsa, ecdsa-...)" ;;
    esac
    ssh-keygen -l -f "$KEY" >/dev/null 2>&1 || die "$KEY is not a public key ssh-keygen can read"

    getent group "$GROUP" >/dev/null 2>&1 || { groupadd --system "$GROUP"; log "added the group $GROUP"; }
    if id "$NAME" >/dev/null 2>&1; then
        is_ours "$NAME" || die "$NAME is an account on this machine already, and not an SFTP login made here"
        log "$NAME is an SFTP login already: giving it this key"
    else
        useradd --system --no-create-home --home-dir / --shell /usr/sbin/nologin --gid "$GROUP" "$NAME"
        # '*' rather than a locked '!': no password works, and sshd still takes the key.
        usermod -p '*' "$NAME"
        log "added the user $NAME"
    fi
    install -d -m 755 -o root -g root "$KEYS"
    install -m 644 -o root -g root "$KEY" "$KEYS/$NAME"
    install -d -m 755 -o root -g root "$CHROOTS" "$JAIL" "$MOUNT"
    if ! grep -qxF "$FSTAB_LINE" /etc/fstab; then
        cp -p /etc/fstab "/etc/fstab.before-monkey-sftp-$(date -u +%Y%m%dT%H%M%SZ)"
        printf '%s\n' "$FSTAB_LINE" >>/etc/fstab
        log "added the bind mount to /etc/fstab: $MOUNT"
    fi
    mountpoint -q "$MOUNT" || mount "$MOUNT"
    # NAME reads and writes the server folder; what NAME makes stays readable and writable by the server's user.
    setfacl -R -m "u:$NAME:rwX,d:u:$NAME:rwX,d:u:$SERVER_USER:rwX" "$SERVER"
    log "gave $NAME read and write on $SERVER (ACLs)"

    old=$(mktemp)
    had=''
    if [ -f "$DROPIN" ]; then cp -p "$DROPIN" "$old"; had=1; fi
    new=$(mktemp)
    dropin "$new"
    install -m 644 -o root -g root "$new" "$DROPIN"
    rm -f "$new"
    if ! sshd_right; then
        if [ -n "$had" ]; then install -m 644 -o root -g root "$old" "$DROPIN"; else rm -f "$DROPIN"; fi
        rm -f "$old"
        die "sshd did not take the drop-in as it should (sshd -t, or sshd -T for $NAME and root): it is as it was, and sshd was not reloaded"
    fi
    rm -f "$old"
    reload_sshd
    log 'sshd reloaded with the drop-in'
    write_card
    printf '\nSFTP login for %s:\n\n  host: %s\n  port: %s\n  user: %s\n  try:  sftp -P %s %s@%s\n\n' "$NAME" \
        "${SFTP_SHOWN_HOST:-this machine}" "${SFTP_SHOWN_PORT:-22}" "$NAME" "${SFTP_SHOWN_PORT:-22}" "$NAME" \
        "${SFTP_SHOWN_HOST:-HOST}"
    exit 0
fi

# --remove-sftp-user
is_ours "$NAME" || die "$NAME is not an SFTP login made here"
pkill -KILL -u "$NAME" 2>/dev/null || :
if mountpoint -q "$MOUNT"; then umount "$MOUNT"; fi
if grep -qxF "$FSTAB_LINE" /etc/fstab; then
    cp -p /etc/fstab "/etc/fstab.before-monkey-sftp-$(date -u +%Y%m%dT%H%M%SZ)"
    f_tmp=$(mktemp)
    grep -vxF "$FSTAB_LINE" /etc/fstab >"$f_tmp" || :
    cat "$f_tmp" >/etc/fstab
    rm -f "$f_tmp"
fi

# A login made by an older version sits under /srv/monkey/sftp: unmount and drop that one too.
OLD_MOUNT=/srv/monkey/sftp/$NAME/server
OLD_LINE="$SERVER $OLD_MOUNT none bind 0 0"
if mountpoint -q "$OLD_MOUNT" 2>/dev/null; then umount "$OLD_MOUNT"; fi
if grep -qxF "$OLD_LINE" /etc/fstab; then
    cp -p /etc/fstab "/etc/fstab.before-monkey-sftp-$(date -u +%Y%m%dT%H%M%SZ)"
    f_tmp=$(mktemp)
    grep -vxF "$OLD_LINE" /etc/fstab >"$f_tmp" || :
    cat "$f_tmp" >/etc/fstab
    rm -f "$f_tmp"
fi
rmdir "$OLD_MOUNT" "/srv/monkey/sftp/$NAME" 2>/dev/null || :

setfacl -R -x "u:$NAME,d:u:$NAME" "$SERVER" 2>/dev/null || :
userdel "$NAME"
rm -f "$KEYS/$NAME"
# rmdir, never rm -r: the mount point is empty once unmounted, and anything else in it is left alone.
rmdir "$MOUNT" 2>/dev/null || :
rmdir "$JAIL" 2>/dev/null || :
write_card
log "removed the SFTP login $NAME; the server's files are as they were"
