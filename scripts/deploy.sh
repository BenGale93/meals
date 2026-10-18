#!/usr/bin/env bash
# Deploy this checkout on the Pi: verified backup, fast-forward pull, sync, restart, health check.
#
#   just deploy             # real deploy (asks for sudo once)
#   DRY_RUN=1 just deploy   # print what would happen, change nothing
#
# Run it on the Pi from /home/galeb/meals. It refuses to run on a dirty tracked tree and
# never rolls back automatically: on failure it prints the status, recent logs, and the
# rollback steps (also documented in deploy/README.md).
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_DIR"

SERVICE="${SERVICE:-meals}"
UNIT_SRC="deploy/meals.service"
UNIT_DST="/etc/systemd/system/${SERVICE}.service"
HEALTH_URL="${HEALTH_URL:-http://127.0.0.1:8000/health}"
HEALTH_TIMEOUT="${HEALTH_TIMEOUT:-30}"
DRY_RUN="${DRY_RUN:-0}"

if [ "${1:-}" = "--dry-run" ]; then
    DRY_RUN=1
elif [ "$#" -gt 0 ]; then
    printf 'usage: %s [--dry-run]\n' "$0" >&2
    exit 2
fi

die() {
    printf 'deploy: %s\n' "$*" >&2
    exit 1
}

[ "$(id -u)" -ne 0 ] || die "run as the service user (galeb), not root"
[ -f .env ] || die "missing .env; copy .env.example and set DATABASE_URL"
[ -z "$(git status --porcelain --untracked-files=no)" ] || die "tracked files are modified; commit or stash first"
systemctl cat "$SERVICE" >/dev/null 2>&1 || die "no '$SERVICE' systemd unit; run this on the Pi"
for cmd in git uv curl sudo cmp seq; do
    command -v "$cmd" >/dev/null 2>&1 || die "$cmd not found"
done

prev="$(git rev-parse --short HEAD)"
printf 'current release: %s\n' "$prev"

if [ "$DRY_RUN" = 1 ]; then
    if cmp -s "$UNIT_SRC" "$UNIT_DST"; then
        unit_state="unchanged"
    else
        unit_state="changed (would reinstall)"
    fi
    printf 'systemd unit: %s\n' "$unit_state"
    printf 'dry run: would back up the database, git pull --ff-only, uv sync --frozen,\n'
    printf '         restart %s (applying migrations), then poll %s for %ss\n' \
        "$SERVICE" "$HEALTH_URL" "$HEALTH_TIMEOUT"
    exit 0
fi

sudo -v || die "sudo is required to restart $SERVICE"

printf '\n==> backing up the database\n'
# --no-sync: back up with the environment that is already proven, before touching the venv.
uv run --frozen --no-sync --env-file .env python scripts/backup_db.py

printf '\n==> pulling the release\n'
git pull --ff-only
release="$(git rev-parse --short HEAD)"
printf 'release to deploy: %s\n' "$release"

printf '\n==> syncing dependencies\n'
uv sync --frozen || die "uv sync failed; do not restart until the environment is fixed"

if ! cmp -s "$UNIT_SRC" "$UNIT_DST"; then
    printf '\n==> installing updated systemd unit\n'
    sudo install -m 0644 "$UNIT_SRC" "$UNIT_DST"
    sudo systemctl daemon-reload
fi

sudo systemctl enable "$SERVICE" >/dev/null

rollback() {
    printf '\ndeploy: %s\n' "$1" >&2
    printf '%s\n' '---- systemctl status ----' >&2
    sudo systemctl status "$SERVICE" --no-pager >&2 || true
    printf '%s\n' '---- recent logs ----' >&2
    sudo journalctl -u "$SERVICE" -n 40 --no-pager >&2 || true
    cat >&2 <<EOF

---- rollback ----
The verified backup printed above is the database state before this deploy.
  sudo systemctl stop $SERVICE
  # restore that backup if the migration is not backward-compatible (see deploy/README.md)
  git switch --detach $prev
  uv sync --frozen
  sudo systemctl start $SERVICE
  curl -fsS $HEALTH_URL
Return to the branch later with: git switch master
EOF
    exit 1
}

printf '\n==> restarting %s (runs alembic upgrade head)\n' "$SERVICE"
sudo systemctl restart "$SERVICE" || rollback "restart failed"

printf '==> waiting for %s\n' "$HEALTH_URL"
for _ in $(seq 1 "$HEALTH_TIMEOUT"); do
    if curl -fsS --max-time 2 "$HEALTH_URL" >/dev/null 2>&1; then
        printf '\ndeployed %s (previous %s); health OK\n' "$release" "$prev"
        exit 0
    fi
    sleep 1
done

rollback "health check failed after ${HEALTH_TIMEOUT}s"
