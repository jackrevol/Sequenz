#!/usr/bin/env bash
set -euo pipefail

ECR_REGISTRY="${ECR_REGISTRY:-775145693936.dkr.ecr.ap-northeast-2.amazonaws.com}"
IMAGE_REPOSITORY="${IMAGE_REPOSITORY:-samsincr/squenz}"
AWS_REGION="${AWS_REGION:-ap-northeast-2}"
IMAGE_TAG="${IMAGE_TAG:-latest}"
NETWORK="${NETWORK:-navi}"
NPM_CONTAINER="${NPM_CONTAINER:-ec2-user-nginx-proxy-manager-1}"
APP_PORT="${APP_PORT:-8000}"
HEALTH_PATH="${HEALTH_PATH:-/healthz/}"
HEALTH_HOST_HEADER="${HEALTH_HOST_HEADER:-localhost}"
STARTUP_DELAY_SECONDS="${STARTUP_DELAY_SECONDS:-20}"
HEALTH_RETRIES="${HEALTH_RETRIES:-30}"
HEALTH_INTERVAL_SECONDS="${HEALTH_INTERVAL_SECONDS:-2}"
GRACE_SECONDS="${GRACE_SECONDS:-10}"
CURL_IMAGE="${CURL_IMAGE:-curlimages/curl:8.10.1}"
RESTART_POLICY="${RESTART_POLICY:-unless-stopped}"
ENV_FILE="${ENV_FILE:-.env}"
DATA_VOLUME="${DATA_VOLUME:-sequenz_data}"
DEPLOY_WORKER="${DEPLOY_WORKER:-true}"
PREFIX="${PREFIX:-sequenz}"
LEGACY_CONTAINER="${LEGACY_CONTAINER:-sequenz}"
SKIP_ECR_LOGIN="false"
DEPLOYMENT_SWITCHED="false"
CANDIDATE_CONTAINER=""

usage() {
  cat <<'USAGE'
Usage: ./update_sequenz.sh [options]

Options:
  --tag TAG              Deploy a specific ECR image tag (default: latest)
  --skip-ecr-login       Skip ECR docker login before pulling the image
  -h, --help             Show this help

Environment overrides:
  ECR_REGISTRY           ECR registry hostname
  IMAGE_REPOSITORY       ECR repository name (default: samsincr/squenz)
  AWS_REGION             AWS region for ECR login (default: ap-northeast-2)
  IMAGE_TAG              Image tag (default: latest)
  NETWORK                Docker network shared with NPM (default: navi)
  NPM_CONTAINER          Nginx Proxy Manager container name
  APP_PORT               Application container port (default: 8000)
  HEALTH_PATH            Health endpoint path (default: /healthz/)
  HEALTH_HOST_HEADER     Host header used for health checks (default: localhost)
  STARTUP_DELAY_SECONDS  Seconds to wait before health checks (default: 20)
  HEALTH_RETRIES         Health check retry count (default: 30)
  HEALTH_INTERVAL_SECONDS Health check interval seconds (default: 2)
  GRACE_SECONDS          Seconds to keep the previous slot (default: 10)
  ENV_FILE               Production env file path (default: .env)
  DATA_VOLUME            Persistent /data volume (default: sequenz_data)
  DEPLOY_WORKER          Also replace payment-expirer: true/false (default: true)
  RESTART_POLICY         Docker restart policy (default: unless-stopped)

NPM Proxy Host target:
  sequenz-active:8000
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --tag)
      if [[ $# -lt 2 || -z "$2" ]]; then
        echo "--tag requires a value." >&2
        exit 2
      fi
      IMAGE_TAG="$2"
      shift 2
      ;;
    --skip-ecr-login)
      SKIP_ECR_LOGIN="true"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

IMAGE="${ECR_REGISTRY}/${IMAGE_REPOSITORY}:${IMAGE_TAG}"
BLUE="${PREFIX}-blue"
GREEN="${PREFIX}-green"
ACTIVE_ALIAS="${PREFIX}-active"
WORKER="${PREFIX}-payment-expirer"

log() {
  printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*"
}

die() {
  log "$*"
  exit 1
}

container_exists() {
  docker inspect "$1" >/dev/null 2>&1
}

container_running() {
  [[ "$(docker inspect --format '{{.State.Running}}' "$1" 2>/dev/null)" == "true" ]]
}

network_exists() {
  docker network inspect "$1" >/dev/null 2>&1
}

container_has_alias() {
  local container="$1"
  local alias="$2"

  container_exists "$container" || return 1
  docker inspect --format '{{range $name, $net := .NetworkSettings.Networks}}{{range $net.Aliases}}{{println .}}{{end}}{{end}}' "$container" \
    | grep -Fxq "$alias"
}

current_slot() {
  if container_has_alias "$BLUE" "$ACTIVE_ALIAS"; then
    printf '%s\n' "$BLUE"
    return 0
  fi

  if container_has_alias "$GREEN" "$ACTIVE_ALIAS"; then
    printf '%s\n' "$GREEN"
    return 0
  fi

  return 1
}

remove_container_if_exists() {
  local container="$1"

  if container_exists "$container"; then
    docker rm -f "$container" >/dev/null
  fi
}

cleanup_failed_candidate() {
  local exit_code=$?

  if [[ "$exit_code" -ne 0 && "$DEPLOYMENT_SWITCHED" != "true" && -n "$CANDIDATE_CONTAINER" ]]; then
    log "Removing unpromoted deployment candidate: $CANDIDATE_CONTAINER"
    remove_container_if_exists "$CANDIDATE_CONTAINER"
  fi
}

trap cleanup_failed_candidate EXIT

reload_npm() {
  container_exists "$NPM_CONTAINER" || die "NPM container not found: $NPM_CONTAINER"
  docker exec "$NPM_CONTAINER" nginx -s reload
}

ecr_login() {
  log "Logging in to ECR registry: $ECR_REGISTRY"
  aws ecr get-login-password --region "$AWS_REGION" \
    | docker login --username AWS --password-stdin "$ECR_REGISTRY"
}

wait_for_health() {
  local container="$1"
  local url="http://${container}:${APP_PORT}${HEALTH_PATH}"

  for ((attempt = 1; attempt <= HEALTH_RETRIES; attempt++)); do
    if ! container_running "$container"; then
      log "Container exited before passing its health check: $container"
      docker logs "$container" --tail 100 || true
      return 1
    fi

    if docker run --rm --network "$NETWORK" "$CURL_IMAGE" \
      -fsS --max-time 3 -H "Host: ${HEALTH_HOST_HEADER}" "$url" >/dev/null; then
      log "Health check passed: $url"
      return 0
    fi

    log "Health check waiting (${attempt}/${HEALTH_RETRIES}): $url"
    sleep "$HEALTH_INTERVAL_SECONDS"
  done

  log "Health check failed: $url"
  docker logs "$container" --tail 100 || true
  return 1
}

deploy_worker() {
  local next_worker="${WORKER}-next"

  log "Replacing background worker: $WORKER"
  remove_container_if_exists "$next_worker"
  docker run -d \
    --name "$next_worker" \
    --network "$NETWORK" \
    --env-file "$ENV_FILE" \
    --mount "type=volume,source=${DATA_VOLUME},target=/data" \
    --restart "$RESTART_POLICY" \
    "$IMAGE" \
    sh -c 'while true; do python manage.py expire_payment_pending_orders; sleep 60; done' >/dev/null

  sleep 2
  if [[ "$(docker inspect --format '{{.State.Running}}' "$next_worker")" != "true" ]]; then
    docker logs "$next_worker" --tail 100 || true
    remove_container_if_exists "$next_worker"
    die "Background worker failed to start: $next_worker"
  fi

  remove_container_if_exists "$WORKER"
  docker rename "$next_worker" "$WORKER"
  log "Background worker is running: $WORKER"
}

command -v docker >/dev/null 2>&1 || die "docker command not found."
[[ -f "$ENV_FILE" ]] || die "Environment file not found: $ENV_FILE"
network_exists "$NETWORK" || die "Docker network not found: $NETWORK"
container_running "$NPM_CONTAINER" || die "NPM container is not running: $NPM_CONTAINER"

if [[ "$SKIP_ECR_LOGIN" != "true" ]]; then
  command -v aws >/dev/null 2>&1 || die "aws command not found."
  ecr_login
else
  log "Skipping ECR login."
fi

CURRENT="$(current_slot || true)"
if [[ -z "$CURRENT" ]]; then
  NEXT="$BLUE"
  log "No active blue/green slot found. Bootstrapping $NEXT with alias $ACTIVE_ALIAS."
  if container_exists "$LEGACY_CONTAINER"; then
    log "Legacy container will be left running during first migration: $LEGACY_CONTAINER"
  fi
elif [[ "$CURRENT" == "$BLUE" ]]; then
  NEXT="$GREEN"
else
  NEXT="$BLUE"
fi

log "Image: $IMAGE"
log "Environment file: $ENV_FILE"
log "Persistent volume: $DATA_VOLUME"
log "Current slot: ${CURRENT:-none}"
log "Next slot: $NEXT"

docker pull "$IMAGE"
docker volume inspect "$DATA_VOLUME" >/dev/null 2>&1 || docker volume create "$DATA_VOLUME" >/dev/null
remove_container_if_exists "$NEXT"

docker run -d \
  --name "$NEXT" \
  --network "$NETWORK" \
  --network-alias "$ACTIVE_ALIAS" \
  --env-file "$ENV_FILE" \
  --mount "type=volume,source=${DATA_VOLUME},target=/data" \
  --restart "$RESTART_POLICY" \
  "$IMAGE" >/dev/null
CANDIDATE_CONTAINER="$NEXT"

if [[ "$STARTUP_DELAY_SECONDS" -gt 0 ]]; then
  log "Waiting ${STARTUP_DELAY_SECONDS}s before health checks."
  sleep "$STARTUP_DELAY_SECONDS"
fi

if ! wait_for_health "$NEXT"; then
  log "Deployment failed before traffic switch. Removing failed container: $NEXT"
  remove_container_if_exists "$NEXT"
  CANDIDATE_CONTAINER=""
  exit 1
fi

log "Reloading NPM with active alias: $ACTIVE_ALIAS"
reload_npm
DEPLOYMENT_SWITCHED="true"

if [[ -n "$CURRENT" ]]; then
  log "Keeping previous slot for ${GRACE_SECONDS}s before removal: $CURRENT"
  sleep "$GRACE_SECONDS"
  remove_container_if_exists "$CURRENT"
  log "Reloading NPM after removing previous slot: $CURRENT"
  reload_npm
else
  log "Bootstrap complete. Set the NPM Forward Hostname/IP to $ACTIVE_ALIAS."
  if container_exists "$LEGACY_CONTAINER"; then
    log "Legacy container was not removed: $LEGACY_CONTAINER"
  fi
fi

if [[ "$DEPLOY_WORKER" == "true" ]]; then
  deploy_worker
else
  log "Skipping background worker deployment."
fi

log "Deployment complete. Active slot: $NEXT"
