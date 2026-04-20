#!/bin/bash

# Dev stack runner — same flag pattern as tests/run.sh, adapted for an
# always-on environment instead of a one-shot test cycle.
#
# No args is "start everything and show me the URLs". --down stops the
# stack without wiping data; --reset nukes volumes when you want a clean
# MariaDB / Redis / Mailpit. --logs tails everything; --rebuild rebuilds
# images then restarts.
#
# Every step logs its full output under test-results/dev-{step}.log so a
# failing build or a stuck service leaves a post-mortem on disk.
#
# Usage:
#   v84-docs/scripts/dev/run.sh                start the stack (default)
#   v84-docs/scripts/dev/run.sh --up           same, explicitly
#   v84-docs/scripts/dev/run.sh --down         stop the stack, keep data
#   v84-docs/scripts/dev/run.sh --reset        stop + wipe db/redis/mail volumes
#   v84-docs/scripts/dev/run.sh --rebuild      rebuild images, then start
#   v84-docs/scripts/dev/run.sh --logs         follow container logs (Ctrl-C to stop)
#   v84-docs/scripts/dev/run.sh --status       ps-style service status

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
COMPOSE_FILE="${REPO_ROOT}/docker/dev/docker-compose.yml"
RESULTS="${REPO_ROOT}/test-results"

DO_UP=false
DO_DOWN=false
DO_RESET=false
DO_REBUILD=false
DO_LOGS=false
DO_STATUS=false

if [ $# -eq 0 ]; then
  DO_UP=true
else
  for arg in "$@"; do
    case "$arg" in
      --up) DO_UP=true ;;
      --down) DO_DOWN=true ;;
      --reset) DO_RESET=true ;;
      --rebuild) DO_REBUILD=true ;;
      --logs) DO_LOGS=true ;;
      --status) DO_STATUS=true ;;
      -h|--help)
        sed -n '3,20p' "$0"
        exit 0
        ;;
      *)
        echo "Unknown option: $arg" >&2
        echo "Run '$0 --help' for usage." >&2
        exit 2
        ;;
    esac
  done
fi

mkdir -p "$RESULTS"

log_cmd() {
  local label="$1" logfile="$2"
  shift 2
  echo ""
  echo "=== ${label} ==="
  echo "    logs → ${RESULTS}/${logfile}"
  "$@" 2>&1 | tee "${RESULTS}/${logfile}"
  return "${PIPESTATUS[0]}"
}

# Compose brings the dev stack up with --wait so the healthchecks that api/db/
# redis/mailpit declare get respected. If anything is unhealthy the script
# exits non-zero and the container logs are already in test-results/.
do_up() {
  log_cmd "Dev stack up" "dev-up.log" \
    docker compose -f "$COMPOSE_FILE" up -d --build --wait
  rc=$?
  if [ $rc -eq 0 ]; then
    cat <<'URLS'

Dev URLs (add to /etc/hosts or rely on *.localhost resolving to 127.0.0.1):
  Web app          http://web.localhost
  API + Swagger    http://api.localhost/api/docs
  Storybook        http://storybook.localhost
  Mail catcher     http://mail.localhost
  DB admin         http://adminer.localhost
  Traefik dashboard http://traefik.localhost

Tail logs:  v84-docs/scripts/dev/run.sh --logs
Stop:       v84-docs/scripts/dev/run.sh --down
URLS
  fi
  return $rc
}

if $DO_REBUILD; then
  log_cmd "Dev rebuild" "dev-rebuild.log" \
    docker compose -f "$COMPOSE_FILE" build
  DO_UP=true
fi

if $DO_UP; then
  do_up
  exit $?
fi

if $DO_DOWN; then
  log_cmd "Dev stack down" "dev-down.log" \
    docker compose -f "$COMPOSE_FILE" down
  exit $?
fi

if $DO_RESET; then
  log_cmd "Dev stack reset" "dev-reset.log" \
    docker compose -f "$COMPOSE_FILE" down -v
  exit $?
fi

if $DO_LOGS; then
  docker compose -f "$COMPOSE_FILE" logs -f
  exit $?
fi

if $DO_STATUS; then
  docker compose -f "$COMPOSE_FILE" ps
  exit $?
fi
