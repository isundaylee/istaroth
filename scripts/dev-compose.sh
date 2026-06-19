#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
COMPOSE_DIR="$REPO_ROOT/docker-compose/web"
ENV_FILE="$REPO_ROOT/.dev-stack.env"

_resolve_identity() {
  if [[ -n "${CONDUCTOR_WORKSPACE_NAME:-}" ]]; then
    WORKSPACE_NAME="$CONDUCTOR_WORKSPACE_NAME"
    COMPOSE_PROJECT_NAME="conductor-${WORKSPACE_NAME}"
  else
    WORKSPACE_NAME="$(basename "$(git -C "$REPO_ROOT" rev-parse --show-toplevel)")"
    COMPOSE_PROJECT_NAME="cursor-${WORKSPACE_NAME}"
  fi
  if [[ -z "$WORKSPACE_NAME" || -z "$COMPOSE_PROJECT_NAME" ]]; then
    echo "dev-compose.sh: could not resolve docker compose project name" >&2
    exit 1
  fi
}

_resolve_main_root() {
  if [[ -n "${CONDUCTOR_ROOT_PATH:-}" ]]; then
    MAIN_ROOT="$CONDUCTOR_ROOT_PATH"
  else
    MAIN_ROOT="$(git -C "$REPO_ROOT" worktree list --porcelain | awk '/^worktree/ {print $2; exit}')"
  fi
}

_export_ports() {
  _resolve_identity
  if [[ -z "${CONDUCTOR_PORT:-}" ]]; then
    OFFSET=$(( $(echo -n "$WORKSPACE_NAME" | cksum | awk '{print $1}') % 50 * 10 ))
    export CONDUCTOR_PORT=$((5173 + OFFSET))
  fi
  export COMPOSE_PROJECT_NAME
  export CONDUCTOR_BACKEND_METRICS_HOST_PORT=$((CONDUCTOR_PORT + 1))
  export CONDUCTOR_RETRIEVAL_METRICS_HOST_PORT=$((CONDUCTOR_PORT + 2))
  export CONDUCTOR_JAEGER_UI_HOST_PORT=$((CONDUCTOR_PORT + 3))
  export CONDUCTOR_JAEGER_OTLP_HOST_PORT=$((CONDUCTOR_PORT + 4))
}

_write_env_file() {
  cat >"$ENV_FILE" <<EOF
COMPOSE_PROJECT_NAME=$COMPOSE_PROJECT_NAME
WORKSPACE_NAME=$WORKSPACE_NAME
CONDUCTOR_PORT=$CONDUCTOR_PORT
CONDUCTOR_BACKEND_METRICS_HOST_PORT=$CONDUCTOR_BACKEND_METRICS_HOST_PORT
CONDUCTOR_RETRIEVAL_METRICS_HOST_PORT=$CONDUCTOR_RETRIEVAL_METRICS_HOST_PORT
CONDUCTOR_JAEGER_UI_HOST_PORT=$CONDUCTOR_JAEGER_UI_HOST_PORT
CONDUCTOR_JAEGER_OTLP_HOST_PORT=$CONDUCTOR_JAEGER_OTLP_HOST_PORT
EOF
}

_load_env() {
  _export_ports
  _write_env_file
}

cmd_setup() {
  _resolve_main_root
  for name in .env.common .env.mcp .env.web tmp; do
    target="$REPO_ROOT/$name"
    [[ -e "$target" ]] || ln -s "$MAIN_ROOT/$name" "$target"
  done
}

cmd_up() {
  local detach=-d
  if [[ "${1:-}" == "--foreground" ]]; then
    detach=""
    shift
  fi
  cmd_setup
  _load_env
  cd "$COMPOSE_DIR"
  # shellcheck disable=SC2086
  docker compose up $detach "$@"
}

cmd_down() {
  _load_env
  cd "$COMPOSE_DIR"
  docker compose down --volumes --remove-orphans
}

cmd_urls() {
  if [[ -f "$ENV_FILE" ]]; then
    # shellcheck disable=SC1090
    source "$ENV_FILE"
  else
    _load_env
  fi
  if [[ -z "${COMPOSE_PROJECT_NAME:-}" ]]; then
    echo "dev-compose.sh: COMPOSE_PROJECT_NAME is empty" >&2
    exit 1
  fi
  echo "COMPOSE_PROJECT_NAME=$COMPOSE_PROJECT_NAME"
  echo "Web UI:            http://localhost:$CONDUCTOR_PORT"
  echo "Backend metrics:   http://localhost:$CONDUCTOR_BACKEND_METRICS_HOST_PORT"
  echo "Retrieval metrics: http://localhost:$CONDUCTOR_RETRIEVAL_METRICS_HOST_PORT"
  echo "Jaeger UI:         http://localhost:$CONDUCTOR_JAEGER_UI_HOST_PORT"
}

usage() {
  echo "Usage: $(basename "$0") {setup|up|down|urls} [--foreground]" >&2
  exit 1
}

[[ $# -ge 1 ]] || usage
case "$1" in
  setup) cmd_setup ;;
  up) shift; cmd_up "$@" ;;
  down) cmd_down ;;
  urls) cmd_urls ;;
  *) usage ;;
esac
