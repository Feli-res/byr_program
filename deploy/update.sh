#!/usr/bin/env bash
set -euo pipefail
BASE=/home/sunxiang/youzhihui
TAG=${1:?Usage: sudo update.sh RELEASE_FOLDER_NAME}
[[ "$TAG" =~ ^[a-zA-Z0-9][a-zA-Z0-9._-]{0,63}$ ]] || { echo 'Invalid release name'; exit 1; }
TARGET=$(realpath "$BASE/releases/$TAG")
[[ "$TARGET" == "$BASE/releases/$TAG" && -f "$TARGET/deploy/compose.prod.yaml" ]] || { echo 'Release missing or outside releases'; exit 1; }
# Build first: no interruption to the current application.
export RELEASE_TAG="$TAG"
dc() { docker compose --env-file "$BASE/shared/.env.prod" -f "$TARGET/deploy/compose.prod.yaml" "$@"; }
dc build
"$BASE/shared/backup.sh"
exec 9>"$BASE/shared/operations.lock"
flock -n 9 || { echo 'Another operation is running'; exit 1; }
readlink -f "$BASE/current" > "$BASE/shared/previous-release.txt"
dc stop api web
dc run --rm api --migrate
dc up -d
for i in $(seq 1 60); do
 if curl -fsS http://127.0.0.1:18082/health/ready >/dev/null && curl -fsS http://127.0.0.1:18083/ >/dev/null; then
  ln -sfn "$TARGET" "$BASE/current"
  echo "Updated to $TAG; check the public URL before inviting users."
  exit 0
 fi
 sleep 2
done
echo 'Startup failed: keep backup and previous release; inspect logs before restoring data.' >&2
exit 1
