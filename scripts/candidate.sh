#!/usr/bin/env bash
# Side-by-side (blue/green) release validation on the Pi.
#
#   just candidate [ref]      # start/refresh the candidate on :8001 (default ref: origin/master)
#   just candidate promote    # cut the live service over to the validated candidate
#   just candidate stop       # stop the candidate, keeping its checkout and DB copy
#   just candidate clean      # stop and remove the candidate checkout, DB copy and unit
#
# The candidate is a second git worktree (/home/galeb/meals-next) with its own .env, its own
# copy of the live database and its own port, so the live service is never touched until
# `promote`. Only one process may open a given SQLite file, and this script refuses to start
# the candidate unless its DATABASE_URL resolves to the copy. The live database is never
# promoted; `promote` backs it up and migrates it in place at cutover, because it may have
# changed since the copy was taken.
set -euo pipefail

LIVE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# Must match WorkingDirectory/EnvironmentFile in deploy/meals-next.service; only override
# this together with that unit (the default is the Pi's layout).
CANDIDATE_DIR="${CANDIDATE_DIR:-/home/galeb/meals-next}"
LIVE_SERVICE="meals"
CANDIDATE_SERVICE="meals-next"
LIVE_PORT="8000"
CANDIDATE_PORT="8001"
HEALTH_TIMEOUT="${HEALTH_TIMEOUT:-30}"

action="${1:-start}"
if [ "$#" -gt 0 ]; then
    shift
fi

die() {
    printf 'candidate: %s\n' "$*" >&2
    exit 1
}

usage() {
    printf 'usage: %s [start [ref] | stop | clean | promote]\n' "${BASH_SOURCE[0]}" >&2
}

wait_for_health() {
    local url="$1" timeout="${2:-$HEALTH_TIMEOUT}" i
    for i in $(seq 1 "$timeout"); do
        if curl -fsS --max-time 2 "$url" >/dev/null 2>&1; then
            return 0
        fi
        sleep 1
    done
    return 1
}

# Print the filesystem path behind DATABASE_URL for a checkout.
db_path() {
    local dir="$1"
    ( cd "$dir" && uv run --frozen --no-sync --env-file .env python -c \
        'from sqlalchemy.engine import make_url; from meals.settings import database_url; print(make_url(database_url()).database)' )
}

require_host() {
    [ "$(id -u)" -ne 0 ] || die "run as the service user (galeb), not root"
    systemctl cat "$LIVE_SERVICE" >/dev/null 2>&1 || die "no '$LIVE_SERVICE' unit; run this on the Pi"
    for cmd in git uv curl sudo cmp seq realpath; do
        command -v "$cmd" >/dev/null 2>&1 || die "$cmd not found"
    done
}

require_clean() {
    local dir="$1" what="$2"
    [ -z "$(git -C "$dir" status --porcelain --untracked-files=no)" ] || die "$what has modified tracked files; commit or stash first"
}

# Resolve the live data directory and the candidate copy; sets LIVE_DB, DATA_DIR,
# CANDIDATE_DB and candidate_data_dir.
resolve_paths() {
    [ -f "$LIVE_DIR/.env" ] || die "missing $LIVE_DIR/.env"
    LIVE_DB="$(db_path "$LIVE_DIR")" || die "could not resolve DATABASE_URL from $LIVE_DIR/.env"
    [ -n "$LIVE_DB" ] && [ "$LIVE_DB" != "None" ] && [ "$LIVE_DB" != ":memory:" ] \
        || die "DATABASE_URL is not a persistent file database"
    case "$LIVE_DB" in
        /*) : ;;
        *) die "DATABASE_URL must be an absolute path (got '$LIVE_DB')" ;;
    esac
    DATA_DIR="$(dirname "$LIVE_DB")"
    [ "$DATA_DIR" != "/" ] || die "refusing to treat / as the data directory"
    CANDIDATE_DB="${CANDIDATE_DB:-$DATA_DIR/candidate/meals.db}"
    candidate_data_dir="$(dirname "$CANDIDATE_DB")"
    [ "$(realpath -m "$CANDIDATE_DB")" != "$(realpath -m "$LIVE_DB")" ] || die "the candidate database would be the live database"
}

start() {
    local ref="${1:-origin/master}"
    require_host
    require_clean "$LIVE_DIR" "the live checkout"
    resolve_paths
    git -C "$LIVE_DIR" rev-parse --verify --quiet "$ref" >/dev/null || die "unknown ref: $ref"
    sudo -v

    printf '==> stopping any running candidate\n'
    sudo systemctl stop "$CANDIDATE_SERVICE" >/dev/null 2>&1 || true

    printf '==> preparing %s at %s\n' "$CANDIDATE_DIR" "$ref"
    git -C "$LIVE_DIR" fetch --prune origin
    git -C "$LIVE_DIR" worktree prune
    if [ -f "$CANDIDATE_DIR/.git" ]; then
        git -C "$CANDIDATE_DIR" switch --detach --force "$ref"
    elif [ -e "$CANDIDATE_DIR" ]; then
        die "$CANDIDATE_DIR exists but is not a git worktree; move it away first"
    else
        git -C "$LIVE_DIR" worktree add --detach "$CANDIDATE_DIR" "$ref"
    fi
    local candidate_commit
    candidate_commit="$(git -C "$CANDIDATE_DIR" rev-parse --short HEAD)"
    printf 'candidate release: %s\n' "$candidate_commit"

    local unit_src="$CANDIDATE_DIR/deploy/meals-next.service"
    [ -f "$unit_src" ] || die "$ref does not contain deploy/meals-next.service"

    printf '\n==> copying the live database (the live service keeps running)\n'
    mkdir -p "$candidate_data_dir"
    rm -f "$CANDIDATE_DB" "$CANDIDATE_DB-wal" "$CANDIDATE_DB-shm"
    ( cd "$LIVE_DIR" && uv run --frozen --no-sync --env-file .env python scripts/backup_db.py --to "$CANDIDATE_DB" )

    printf '\n==> writing %s/.env\n' "$CANDIDATE_DIR"
    local candidate_url="sqlite+aiosqlite:///$CANDIDATE_DB"
    umask 077
    if grep -q '^DATABASE_URL=' "$LIVE_DIR/.env"; then
        sed "s|^DATABASE_URL=.*|DATABASE_URL=$candidate_url|" "$LIVE_DIR/.env" > "$CANDIDATE_DIR/.env"
    else
        { cat "$LIVE_DIR/.env"; printf 'DATABASE_URL=%s\n' "$candidate_url"; } > "$CANDIDATE_DIR/.env"
    fi
    umask 022

    printf '\n==> syncing candidate dependencies\n'
    ( cd "$CANDIDATE_DIR" && uv sync --frozen )

    local resolved
    resolved="$(db_path "$CANDIDATE_DIR")" || die "could not resolve the candidate DATABASE_URL"
    [ -n "$resolved" ] || die "the candidate DATABASE_URL is not a file database"
    [ "$(realpath -m "$resolved")" = "$(realpath -m "$CANDIDATE_DB")" ] \
        || die "candidate DATABASE_URL ($resolved) is not the database copy ($CANDIDATE_DB)"

    printf '\n==> migrating the database copy\n'
    ( cd "$CANDIDATE_DIR" && uv run --frozen --env-file .env alembic upgrade head )

    if ! cmp -s "$unit_src" "/etc/systemd/system/$CANDIDATE_SERVICE.service"; then
        printf '\n==> installing %s.service\n' "$CANDIDATE_SERVICE"
        sudo install -m 0644 "$unit_src" "/etc/systemd/system/$CANDIDATE_SERVICE.service"
        sudo systemctl daemon-reload
    fi

    printf '\n==> starting %s on :%s\n' "$CANDIDATE_SERVICE" "$CANDIDATE_PORT"
    sudo systemctl restart "$CANDIDATE_SERVICE"
    if ! wait_for_health "http://127.0.0.1:$CANDIDATE_PORT/health"; then
        sudo systemctl status "$CANDIDATE_SERVICE" --no-pager >&2 || true
        sudo journalctl -u "$CANDIDATE_SERVICE" -n 40 --no-pager >&2 || true
        die "candidate did not become healthy on :$CANDIDATE_PORT; the live service was not touched"
    fi

    local candidate_host
    candidate_host="$(tailscale ip -4 2>/dev/null | head -n1 || true)"
    [ -n "$candidate_host" ] || candidate_host="$(hostname)"
    printf '\ncandidate %s is healthy:\n' "$candidate_commit"
    printf '  URL: http://%s:%s  (Tailscale/LAN)\n' "$candidate_host" "$CANDIDATE_PORT"
    printf '  DB:  %s  (a copy; the live DB is %s)\n' "$CANDIDATE_DB" "$LIVE_DB"
    printf '\nexercise the changed flows, then:\n'
    printf '  just candidate promote   # back up the live DB, cut over and health-check\n'
    printf '  just candidate stop      # free :%s, keep the checkout\n' "$CANDIDATE_PORT"
}

stop() {
    require_host
    sudo -v
    sudo systemctl stop "$CANDIDATE_SERVICE" >/dev/null 2>&1 || true
    printf 'candidate stopped; :%s is free (checkout and database copy kept)\n' "$CANDIDATE_PORT"
}

clean() {
    require_host
    resolve_paths
    sudo -v
    sudo systemctl stop "$CANDIDATE_SERVICE" >/dev/null 2>&1 || true
    if [ -f "$CANDIDATE_DIR/.git" ]; then
        git -C "$LIVE_DIR" worktree remove --force "$CANDIDATE_DIR"
    elif [ -e "$CANDIDATE_DIR" ]; then
        printf 'candidate: %s exists but is not a worktree; leaving it alone\n' "$CANDIDATE_DIR" >&2
    fi
    git -C "$LIVE_DIR" worktree prune
    [ "$candidate_data_dir" != "$DATA_DIR" ] || die "refusing to delete the live data directory"
    [ "$candidate_data_dir" != "/" ] || die "refusing to delete /"
    rm -rf "$candidate_data_dir"
    if [ -f "/etc/systemd/system/$CANDIDATE_SERVICE.service" ]; then
        sudo rm -f "/etc/systemd/system/$CANDIDATE_SERVICE.service"
        sudo systemctl daemon-reload
    fi
    printf 'candidate removed: checkout, database copy and unit\n'
}

# Print why the cutover failed and how to undo it, without touching anything automatically.
promote_failure() {
    local reason="$1" prev="$2" backup="$3"
    printf '\npromote: %s\n' "$reason" >&2
    printf '%s\n' '---- systemctl status ----' >&2
    sudo systemctl status "$LIVE_SERVICE" --no-pager >&2 || true
    printf '%s\n' '---- recent logs ----' >&2
    sudo journalctl -u "$LIVE_SERVICE" -n 40 --no-pager >&2 || true
    cat >&2 <<EOF

---- rollback ----
The candidate is still running on :$CANDIDATE_PORT for comparison.
  sudo systemctl stop $LIVE_SERVICE
  # roll the code back:
  git -C $LIVE_DIR reset --hard $prev
  ( cd $LIVE_DIR && uv sync --frozen )
  # restore the database only if the migration was not backward-compatible:
  #   cp $backup $LIVE_DB
  #   rm -f $LIVE_DB-wal $LIVE_DB-shm
  sudo systemctl start $LIVE_SERVICE
  curl -fsS http://127.0.0.1:$LIVE_PORT/health
EOF
    exit 1
}

promote() {
    require_host
    require_clean "$LIVE_DIR" "the live checkout"
    [ -f "$CANDIDATE_DIR/.git" ] || die "no candidate worktree; run 'just candidate' first"
    require_clean "$CANDIDATE_DIR" "the candidate checkout"
    resolve_paths
    curl -fsS --max-time 2 "http://127.0.0.1:$CANDIDATE_PORT/health" >/dev/null 2>&1 \
        || die "candidate is not healthy on :$CANDIDATE_PORT; run 'just candidate' first"
    sudo -v

    local candidate_sha prev backup
    candidate_sha="$(git -C "$CANDIDATE_DIR" rev-parse HEAD)"
    prev="$(git -C "$LIVE_DIR" rev-parse --short HEAD)"
    backup="$DATA_DIR/backups/pre-promote-$(date +%Y%m%d-%H%M%S).db"

    printf '==> backing up the live database\n'
    mkdir -p "$DATA_DIR/backups"
    ( cd "$LIVE_DIR" && uv run --frozen --no-sync --env-file .env python scripts/backup_db.py --to "$backup" )

    printf '\n==> fast-forwarding the live checkout to %s\n' "$(git -C "$LIVE_DIR" rev-parse --short "$candidate_sha")"
    git -C "$LIVE_DIR" merge --ff-only "$candidate_sha" \
        || die "the live branch cannot fast-forward to the candidate; the live service was not restarted"
    ( cd "$LIVE_DIR" && uv sync --frozen ) \
        || die "uv sync failed; the live service is still on the old process — do not restart until it is fixed"

    if ! cmp -s "$LIVE_DIR/deploy/meals.service" "/etc/systemd/system/$LIVE_SERVICE.service"; then
        printf '\n==> installing %s.service\n' "$LIVE_SERVICE"
        sudo install -m 0644 "$LIVE_DIR/deploy/meals.service" "/etc/systemd/system/$LIVE_SERVICE.service"
        sudo systemctl daemon-reload
    fi

    printf '\n==> restarting %s (runs alembic upgrade head)\n' "$LIVE_SERVICE"
    sudo systemctl restart "$LIVE_SERVICE" || promote_failure "restart failed" "$prev" "$backup"

    printf '==> waiting for http://127.0.0.1:%s/health\n' "$LIVE_PORT"
    wait_for_health "http://127.0.0.1:$LIVE_PORT/health" \
        || promote_failure "health check failed after ${HEALTH_TIMEOUT}s" "$prev" "$backup"

    sudo systemctl stop "$CANDIDATE_SERVICE" >/dev/null 2>&1 || true
    printf '\npromoted %s (previous %s); candidate stopped\n' \
        "$(git -C "$LIVE_DIR" rev-parse --short HEAD)" "$prev"
    printf 'backup before the cutover: %s\n' "$backup"
    printf 'rollback: git -C %s reset --hard %s (then restore that backup if the migration was not backward-compatible)\n' \
        "$LIVE_DIR" "$prev"
}

case "$action" in
    start) start "$@" ;;
    stop) stop ;;
    clean) clean ;;
    promote) promote ;;
    -h | --help | help) usage ;;
    *)
        usage
        exit 2
        ;;
esac
