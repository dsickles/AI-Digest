#!/usr/bin/env bash
# Home-worker polling loop (D-B5b): object-storage marker rendezvous →
# --only-pending-transcripts → git push → marker delete.
set -euo pipefail

POLL_INTERVAL="${WORKER_POLL_INTERVAL_SECONDS:-600}"
REPO_DIR="${REPO_DIR:-/repo}"
DATA_DIR="${REPO_DIR}/data"
MARKERS_PREFIX="markers"
DB_OBJECT="db/aidigest.db"
REMOTE="${B2_REMOTE_NAME:-b2}"
PYTHON="/app/.venv/bin/python"

log() {
  printf '[worker] %s\n' "$*" >&2
}

require_env() {
  local name="$1"
  if [ -z "${!name:-}" ]; then
    log "FATAL: required environment variable ${name} is not set."
    exit 1
  fi
}

materialize_rclone_conf() {
  require_env B2_KEY_ID
  require_env B2_APPLICATION_KEY
  require_env B2_BUCKET

  mkdir -p "${HOME}/.config/rclone"
  umask 077
  cat > "${HOME}/.config/rclone/rclone.conf" <<EOF
[${REMOTE}]
type = b2
account = ${B2_KEY_ID}
key = ${B2_APPLICATION_KEY}
hard_delete = false
EOF
  chmod 600 "${HOME}/.config/rclone/rclone.conf"
}

is_sunday_processing_window() {
  # UTC Sunday 09:00–14:00 — cron marker is expected in this band.
  local dow hour
  dow="$(date -u +%w)"
  hour="$(date -u +%H | sed 's/^0//')"
  hour="${hour:-0}"
  [ "${dow}" = "0" ] && [ "${hour}" -ge 9 ] && [ "${hour}" -lt 14 ]
}

resolve_week_id() {
  "${PYTHON}" -c 'from pipeline.week import active_digest_week_id; print(active_digest_week_id())'
}

marker_remote_path() {
  local week_id="$1"
  printf '%s:%s/%s/cron-complete-%s.json' "${REMOTE}" "${B2_BUCKET}" "${MARKERS_PREFIX}" "${week_id}"
}

marker_exists() {
  local week_id="$1"
  local marker_name="cron-complete-${week_id}.json"
  rclone ls "${REMOTE}:${B2_BUCKET}/${MARKERS_PREFIX}/" 2>/dev/null \
    | awk '{print $2}' \
    | grep -Fxq "${marker_name}"
}

validate_marker_week_id() {
  local week_id="$1"
  local tmp
  tmp="$(mktemp)"
  if ! rclone copyto "$(marker_remote_path "${week_id}")" "${tmp}"; then
    rm -f "${tmp}"
    return 1
  fi
  if ! "${PYTHON}" -c "
import json, sys
from pathlib import Path
data = json.loads(Path('${tmp}').read_text())
sys.exit(0 if data.get('week_id') == '${week_id}' else 1)
"; then
    rm -f "${tmp}"
    log "Marker JSON week_id mismatch — ignoring spoofed marker."
    return 1
  fi
  rm -f "${tmp}"
}

ensure_repo() {
  require_env GITHUB_TOKEN
  require_env GITHUB_REPO

  if [ ! -d "${REPO_DIR}/.git" ]; then
    log "Cloning ${GITHUB_REPO} into ${REPO_DIR}…"
    rm -rf "${REPO_DIR}"
    git clone --depth 1 \
      "https://x-access-token:${GITHUB_TOKEN}@github.com/${GITHUB_REPO}.git" \
      "${REPO_DIR}"
  else
    log "Pulling latest ${GITHUB_REPO}…"
    git -C "${REPO_DIR}" pull --ff-only
  fi

  mkdir -p "${DATA_DIR}"
}

pull_database() {
  if ! rclone copy "${REMOTE}:${B2_BUCKET}/${DB_OBJECT}" "${DATA_DIR}/" --no-traverse; then
    log "No database on object storage yet — aborting cycle."
    return 1
  fi
}

push_database() {
  rclone copy "${DATA_DIR}/aidigest.db" "${REMOTE}:${B2_BUCKET}/db/"
}

delete_marker() {
  local week_id="$1"
  rclone deletefile "$(marker_remote_path "${week_id}")"
}

run_catch_up() {
  local week_id="$1"
  (
    cd "${REPO_DIR}"
    export GEMINI_API_KEY
    "${PYTHON}" -m pipeline.run all --only-pending-transcripts --week "${week_id}"
  )
}

commit_and_push() {
  local week_id="$1"
  local author_name="${GITHUB_COMMIT_AUTHOR_NAME:-ai-digest-worker}"
  local author_email="${GITHUB_COMMIT_AUTHOR_EMAIL:-noreply@example.invalid}"

  git -C "${REPO_DIR}" config user.name "${author_name}"
  git -C "${REPO_DIR}" config user.email "${author_email}"
  git -C "${REPO_DIR}" add web/src/content/digests/ web/src/content/reports/

  if git -C "${REPO_DIR}" diff --cached --quiet; then
    log "No digest changes to commit for ${week_id}."
    return 0
  fi

  git -C "${REPO_DIR}" commit -m "chore(digest): home worker transcript catch-up ${week_id}"
  git -C "${REPO_DIR}" push \
    "https://x-access-token:${GITHUB_TOKEN}@github.com/${GITHUB_REPO}.git" HEAD
}

# Plan 05-06 wires full Healthchecks start/end pings (D-B7).
ping_worker_start() {
  if [ -n "${HEALTHCHECK_WORKER_URL:-}" ]; then
    curl -fsS -m 30 --retry 2 "${HEALTHCHECK_WORKER_URL}/start" || true
  fi
}

ping_worker_finish() {
  local week_id="$1"
  if [ -n "${HEALTHCHECK_WORKER_URL:-}" ]; then
    local spend
    spend="$("${PYTHON}" -c "
import json
from pathlib import Path
report = Path('${REPO_DIR}') / 'web/src/content/reports' / '${week_id}.json'
if report.is_file():
    data = json.loads(report.read_text())
    print(data.get('budget', {}).get('spent_usd', 0))
else:
    print(0)
")"
    curl -fsS -m 30 --retry 2 --data-raw "spent_usd=${spend}" "${HEALTHCHECK_WORKER_URL}" || true
  fi
}

ping_worker_fail() {
  if [ -n "${HEALTHCHECK_WORKER_URL:-}" ]; then
    curl -fsS -m 30 --retry 2 "${HEALTHCHECK_WORKER_URL}/fail" || true
  fi
}

process_marker() {
  local week_id="$1"
  local marker_path
  marker_path="$(marker_remote_path "${week_id}")"

  log "Marker found for ${week_id} — starting transcript catch-up."

  ping_worker_start

  if ! (
    ensure_repo
    pull_database
    run_catch_up "${week_id}"
    push_database
    commit_and_push "${week_id}"
    delete_marker "${week_id}"
    ping_worker_finish "${week_id}"
  ); then
    ping_worker_fail
    return 1
  fi

  log "Cycle complete for ${week_id}; marker deleted."
}

main() {
  require_env GEMINI_API_KEY
  materialize_rclone_conf

  log "Polling every ${POLL_INTERVAL}s (Sunday UTC 09:00–14:00 processing window)."

  while true; do
    if is_sunday_processing_window; then
      week_id="$(resolve_week_id)"
      if marker_exists "${week_id}" && validate_marker_week_id "${week_id}"; then
        if process_marker "${week_id}"; then
          log "Sleeping ${POLL_INTERVAL}s before next poll."
        else
          log "Cycle failed — will retry after ${POLL_INTERVAL}s."
        fi
      fi
    fi
    sleep "${POLL_INTERVAL}"
  done
}

main "$@"
