#!/usr/bin/env bash
set -euo pipefail
BASE="${YOUZHIHUI_BASE:-$(cd -- "$(dirname -- "$0")/.." && pwd -P)}"
export RELEASE_TAG="$(basename "$(readlink -f "$BASE/current")")"
dc() { docker compose --env-file "$BASE/shared/.env.prod" -f "$BASE/current/deploy/compose.prod.yaml" "$@"; }
case "${1:-status}" in
 status) dc ps ;;
 start) dc up -d ;;
 stop) dc stop ;;
 restart) dc restart api web ;;
 logs) dc logs --tail 100 "${2:-api}" ;;
 backup) exec "$BASE/shared/backup.sh" ;;
 admin) dc exec api youzhihui-api --init-admin ;;
 *) echo 'Usage: sudo ./manage.sh status|start|stop|restart|logs [api|web|mysql|redis]|backup|admin'; exit 2 ;;
esac
