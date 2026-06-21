#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
COMPOSE_DIR="$REPO_ROOT/docker-compose/web"
ENV_FILE="$REPO_ROOT/.dev-stack.env"

_resolve_identity() {
  if [[ -n "${CONDUCTOR_WORKSPACE_NAME:-}" ]]; then
    WORKSPACE_NAME="$CONDUCTOR_WORKSPACE_NAME"
    COMPOSE_PROJECT_NAME="conductor-${WORKSPACE_NAME}"
  elif [[ -n "${PASEO_BRANCH_NAME:-}" ]]; then
    WORKSPACE_NAME="$PASEO_BRANCH_NAME"
    COMPOSE_PROJECT_NAME="paseo-${WORKSPACE_NAME}"
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
  elif [[ -n "${PASEO_SOURCE_CHECKOUT_PATH:-}" ]]; then
    MAIN_ROOT="$PASEO_SOURCE_CHECKOUT_PATH"
  else
    MAIN_ROOT="$(git -C "$REPO_ROOT" worktree list --porcelain | awk '/^worktree/ {print $2; exit}')"
  fi
}

_rebase_onto_upstream() {
  local upstream remote
  if upstream="$(git -C "$REPO_ROOT" rev-parse --abbrev-ref --symbolic-full-name '@{upstream}' 2>/dev/null)"; then
    :
  else
    upstream="origin/main"
    echo "dev-compose.sh: no upstream configured for current branch, using $upstream" >&2
  fi
  remote="${upstream%%/*}"
  # Worktrees share refs/remotes, so concurrent stack startups can race on the
  # remote-tracking ref lock ("cannot lock ref ... unable to update local ref").
  # The failure is transient — the ref is already moving to its new value — so
  # retry a few times with a short backoff before giving up.
  local attempt
  for attempt in 1 2 3 4 5; do
    if git -C "$REPO_ROOT" fetch "$remote"; then
      break
    elif [[ "$attempt" -eq 5 ]]; then
      echo "dev-compose.sh: git fetch $remote failed after $attempt attempts" >&2
      return 1
    else
      echo "dev-compose.sh: git fetch $remote failed (attempt $attempt), retrying..." >&2
      sleep "$attempt"
    fi
  done
  git -C "$REPO_ROOT" rebase --autostash "$upstream"
}

_export_ports() {
  _resolve_identity
  if [[ -z "${CONDUCTOR_PORT:-}" ]]; then
    if [[ -n "${PASEO_WORKTREE_PORT:-}" ]]; then
      export CONDUCTOR_PORT="$PASEO_WORKTREE_PORT"
    else
      OFFSET=$(( $(echo -n "$WORKSPACE_NAME" | cksum | awk '{print $1}') % 50 * 10 ))
      export CONDUCTOR_PORT=$((5173 + OFFSET))
    fi
  fi
  export COMPOSE_PROJECT_NAME
  export CONDUCTOR_BACKEND_METRICS_HOST_PORT=$((CONDUCTOR_PORT + 1))
  export CONDUCTOR_RETRIEVAL_METRICS_HOST_PORT=$((CONDUCTOR_PORT + 2))
  export CONDUCTOR_JAEGER_UI_HOST_PORT=$((CONDUCTOR_PORT + 3))
  export CONDUCTOR_JAEGER_OTLP_HOST_PORT=$((CONDUCTOR_PORT + 4))
}

# Clone the shared checkpoints into a per-worktree directory so each stack gets
# an isolated, writable copy (Chroma opens its SQLite read-write even for
# queries, so concurrent stacks must not share one on-disk database). Uses
# copy-on-write (APFS clonefile / reflink) where the filesystem supports it so
# the clone is instant and near-zero disk; otherwise it degrades to a full copy.
# Clones only when the destination doesn't already exist.
_clone_checkpoints() {
  local src="$MAIN_ROOT/tmp/checkpoints"
  local dest="$COMPOSE_DIR/checkpoints"
  if [[ ! -d "$src" ]]; then
    echo "dev-compose.sh: checkpoint source $src not found — skipping clone" >&2
    return
  fi
  if [[ -e "$dest" ]]; then
    echo "dev-compose.sh: docker-compose/web/checkpoints already exists, skipping clone."
    return
  fi
  echo "dev-compose.sh: cloning checkpoints -> docker-compose/web/checkpoints ..."
  local how=""
  if [[ "$(uname)" == "Darwin" ]]; then
    cp -cR "$src" "$dest" 2>/dev/null && how="copy-on-write clone"
  else
    cp -R --reflink=auto "$src" "$dest" 2>/dev/null && how="reflink/copy"
  fi
  if [[ -z "$how" ]]; then
    cp -R "$src" "$dest"
    how="full copy (copy-on-write unavailable)"
  fi
  echo "dev-compose.sh: checkpoint clone done ($how)."
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
VITE_PUBLIC_HOST=$(hostname -f 2>/dev/null || hostname)
EOF
}

_load_env() {
  if [[ ! -f "$ENV_FILE" ]]; then
    echo "dev-compose.sh: $ENV_FILE not found — run 'scripts/dev-compose.sh setup' first" >&2
    exit 1
  fi
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  export COMPOSE_PROJECT_NAME CONDUCTOR_PORT \
    CONDUCTOR_BACKEND_METRICS_HOST_PORT CONDUCTOR_RETRIEVAL_METRICS_HOST_PORT \
    CONDUCTOR_JAEGER_UI_HOST_PORT CONDUCTOR_JAEGER_OTLP_HOST_PORT VITE_PUBLIC_HOST
}

_refresh_paseo_port() {
  local paseo_port=""
  local paseo_port_helper=""
  if paseo_port_helper="$(command -v paseo-port 2>/dev/null)"; then
    :
  elif [[ -x "$REPO_ROOT/paseo-port" ]]; then
    paseo_port_helper="$REPO_ROOT/paseo-port"
  fi
  if [[ -n "$paseo_port_helper" ]]; then
    if ! paseo_port="$("$paseo_port_helper" 2>/dev/null)"; then
      echo "dev-compose.sh: paseo-port failed; keeping CONDUCTOR_PORT=$CONDUCTOR_PORT" >&2
      return
    fi
  elif [[ -r "$REPO_ROOT/paseo-port" ]]; then
    paseo_port="$(<"$REPO_ROOT/paseo-port")"
  elif [[ -n "${PASEO_PORT:-}" ]]; then
    paseo_port="$PASEO_PORT"
  fi
  [[ -n "$paseo_port" ]] || return
  if [[ ! "$paseo_port" =~ ^[0-9]+$ ]]; then
    echo "dev-compose.sh: paseo-port returned non-numeric port '$paseo_port'; keeping CONDUCTOR_PORT=$CONDUCTOR_PORT" >&2
    return
  fi
  export CONDUCTOR_PORT="$paseo_port"
  _export_ports
  _write_env_file
}

cmd_setup() {
  _rebase_onto_upstream
  _resolve_main_root
  for name in .env.common .env.mcp .env.web tmp; do
    target="$REPO_ROOT/$name"
    [[ -e "$target" ]] || ln -s "$MAIN_ROOT/$name" "$target"
  done
  _clone_checkpoints
  _resolve_identity
  _export_ports
  _write_env_file
}

cmd_up() {
  local detach=""
  while [[ "${1:-}" == -* ]]; do
    case "$1" in
      --detach | -d | --background) detach=-d; shift ;;
      *) break ;;
    esac
  done
  _load_env
  _refresh_paseo_port
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
  _load_env
  echo "COMPOSE_PROJECT_NAME=$COMPOSE_PROJECT_NAME"
  echo "Web UI:            http://$VITE_PUBLIC_HOST:$CONDUCTOR_PORT"
  echo "Backend metrics:   http://$VITE_PUBLIC_HOST:$CONDUCTOR_BACKEND_METRICS_HOST_PORT"
  echo "Retrieval metrics: http://$VITE_PUBLIC_HOST:$CONDUCTOR_RETRIEVAL_METRICS_HOST_PORT"
  echo "Jaeger UI:         http://$VITE_PUBLIC_HOST:$CONDUCTOR_JAEGER_UI_HOST_PORT"
}

usage() {
  echo "Usage: $(basename "$0") {setup|up|down|urls} [--detach|-d]" >&2
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
