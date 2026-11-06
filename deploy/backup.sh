#!/usr/bin/env bash
set -euo pipefail
umask 077
BASE=/home/sunxiang/youzhihui
exec 9>"$BASE/shared/operations.lock"
flock -n 9 || { echo "Another backup/update is running" >&2; exit 1; }
export RELEASE_TAG="$(basename "$(readlink -f "$BASE/current")")"
dc() { docker compose --env-file "$BASE/shared/.env.prod" -f "$BASE/current/deploy/compose.prod.yaml" "$@"; }
DEST="$BASE/backups/$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$DEST"
trap 'dc start api web >/dev/null' EXIT
dc stop web api >/dev/null
dc exec -T mysql sh -c 'MYSQL_PWD="$MYSQL_PASSWORD" exec mysqldump -u "$MYSQL_USER" --single-transaction --no-tablespaces "$MYSQL_DATABASE"' > "$DEST/database.sql"
docker run --rm --network none --user 0 --entrypoint tar -v youzhihui-trial_uploads:/data:ro "$(dc images -q api | head -n 1)" -czf - -C /data . > "$DEST/uploads.tar.gz"
cp "$BASE/shared/.env.prod" "$DEST/server.env"
readlink -f "$BASE/current" > "$DEST/release.txt"
python3 "$(dirname "$0")/backup_inventory.py" "$DEST" "$(dc ps -q mysql)"
(cd "$DEST" && sha256sum database.sql uploads.tar.gz server.env release.txt inventory.json > SHA256SUMS)
dc start api web >/dev/null
trap - EXIT
# Keep the newest 14 successful snapshots; no volume or live upload removal.
python3 - "$BASE/backups" <<'PY'
from pathlib import Path
import shutil,sys
root=Path(sys.argv[1]).resolve()
snapshots=sorted((p for p in root.iterdir() if p.is_dir() and not p.is_symlink() and (p/'SHA256SUMS').is_file()), reverse=True)
for p in snapshots[14:]:
    if p.resolve().parent != root: raise SystemExit('Unsafe backup path')
    shutil.rmtree(p)
PY
echo "Backup completed: $DEST"
