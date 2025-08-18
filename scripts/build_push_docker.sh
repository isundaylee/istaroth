#!/bin/bash
set -euo pipefail

# Generate timestamp tag
TIMESTAMP=$(date +"%Y%m%d-%H%M%S")
SHORT_SHA=$(git rev-parse --short HEAD)
TIMESTAMP_TAG="${TIMESTAMP}-${SHORT_SHA}"

docker buildx build \
  --platform linux/amd64 \
  -t isundaylee/istaroth:latest \
  -t isundaylee/istaroth:${TIMESTAMP_TAG} \
  --cache-from=type=registry,ref=isundaylee/istaroth:localbuildcache \
  --cache-to=type=registry,ref=isundaylee/istaroth:localbuildcache,mode=max \
  --push .

docker buildx build \
  --platform linux/amd64 \
  -t isundaylee/istaroth-frontend:latest \
  -t isundaylee/istaroth-frontend:${TIMESTAMP_TAG} \
  --cache-from=type=registry,ref=isundaylee/istaroth-frontend:localbuildcache \
  --cache-to=type=registry,ref=isundaylee/istaroth-frontend:localbuildcache,mode=max \
  --push ./frontend
