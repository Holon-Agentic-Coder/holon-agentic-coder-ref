#!/usr/bin/env bash
set -euo pipefail

# Resolve the directory of this script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Help menu
show_help() {
  cat <<EOF
Usage: $(basename "$0") [options]

Builds all Docker images for the Holon agentic environments (base, agents, and orchestrator).

Options:
  -h, --help      Show this help message and exit
  --no-cache      Build Docker images without using the cache (forces fresh packages/dependencies)
  --output-log    Print all build logs to stdout with timestamps prepended
EOF
}

# Check command line arguments
NO_CACHE_FLAG=""
OUTPUT_LOG="false"

while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help)
      show_help
      exit 0
      ;;
    --no-cache)
      NO_CACHE_FLAG="--no-cache"
      shift
      ;;
    --output-log)
      OUTPUT_LOG="true"
      shift
      ;;
    *)
      echo "Unknown option: $1"
      show_help
      exit 1
      ;;
  esac
done

# Helper function to print log lines from stdin with timestamps in real-time
print_log_with_timestamps() {
  # Check if bash version supports built-in printf %(...)T (introduced in bash 4.2)
  if [[ "${BASH_VERSINFO[0]}" -gt 4 || ( "${BASH_VERSINFO[0]}" -eq 4 && "${BASH_VERSINFO[1]}" -ge 2 ) ]]; then
    while IFS= read -r line || [[ -n "$line" ]]; do
      printf "[%(%Y-%m-%d %H:%M:%S)T] %s\n" -1 "$line"
    done
  else
    while IFS= read -r line || [[ -n "$line" ]]; do
      echo "[$(date +'%Y-%m-%d %H:%M:%S')] $line"
    done
  fi
}

# Helper function to build a single Docker target image
build_image() {
  local target="$1"
  local image_tag="$2"
  shift 2
  local build_args=("$@")

  local log_file
  log_file=$(mktemp "/tmp/docker-build-${target}.XXXXXX")

  local build_cmd="docker build"
  local cache_opts=()

  if docker buildx version >/dev/null 2>&1; then
    build_cmd="docker buildx build"
    if [[ "${CI:-}" == "true" ]]; then
      cache_opts=(
        "--cache-from=type=gha,scope=${target}"
        "--cache-to=type=gha,mode=max,scope=${target}"
        "--load"
      )
    fi
  fi

  echo "Building $image_tag (target: $target)..."
  if ! $build_cmd $NO_CACHE_FLAG "${cache_opts[@]}" --target "$target" "${build_args[@]}" -t "$image_tag" "$SCRIPT_DIR" 2>&1 | print_log_with_timestamps > "$log_file"; then
    echo "ERROR: Failed to build $image_tag (target: $target)!"
    cat "$log_file"
    rm -f "$log_file"
    return 1
  fi

  echo "Successfully built $image_tag"
  if [[ "$OUTPUT_LOG" == "true" ]]; then
    echo "=== Build log for $image_tag (target: $target) ==="
    cat "$log_file"
    echo "=== End build log for $image_tag ==="
  fi
  rm -f "$log_file"
  return 0
}

# 1. Build and tag the shared base layer first
echo "Building shared base image (holon/base)..."
if ! build_image "holon-base" "holon/base"; then
  exit 1
fi

# 2. Build the agents and orchestrator inheriting from the pre-built base image in parallel
echo "Building agent images using pre-built base (concurrency limited to 3)..."

images=(
  "agent-claude|holon/agent-claude|--build-arg AGENT_BASE=holon/base"
  "agent-codex|holon/agent-codex|--build-arg AGENT_BASE=holon/base"
  "agent-gemini|holon/agent-gemini|--build-arg AGENT_BASE=holon/base"
  "agent-hermes|holon/agent-hermes|--build-arg AGENT_BASE=holon/base"
  "agent-opencode|holon/agent-opencode|--build-arg AGENT_BASE=holon/base"
  "agent-open-codex|holon/agent-open-codex|--build-arg AGENT_BASE=holon/base"
  "agent-pi|holon/agent-pi|--build-arg AGENT_BASE=holon/base"
  "agent-antigravity|holon/agent-antigravity|--build-arg AGENT_BASE=holon/base"
  "holon-orchestrator|holon/orchestrator|--build-arg AGENT_BASE=holon/base"
)

MAX_JOBS=3
pids=()

for item in "${images[@]}"; do
  # Parse item by delimiter
  IFS='|' read -r target tag extra_args <<< "$item"

  # Run build in background
  build_image "$target" "$tag" $extra_args &
  pids+=("$!")

  # Control concurrency: if we reached MAX_JOBS, wait for the oldest jobs to finish
  while [ ${#pids[@]} -ge $MAX_JOBS ]; do
    still_running=()
    for pid in "${pids[@]}"; do
      if kill -0 "$pid" 2>/dev/null; then
        still_running+=("$pid")
      fi
    done

    if [ ${#still_running[@]} -lt $MAX_JOBS ]; then
      pids=("${still_running[@]}")
      break
    fi
    sleep 0.5
  done
done

# Wait for all remaining background jobs and check status
exit_code=0
for pid in "${pids[@]}"; do
  if ! wait "$pid"; then
    exit_code=1
  fi
done

if [ $exit_code -ne 0 ]; then
  echo "Error: One or more Docker builds failed!"
  exit 1
fi

echo "All images built successfully!"
