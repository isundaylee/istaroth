#!/bin/bash
set -euo pipefail

docker buildx build \
  --platform linux/amd64 \
  -t isundaylee/istaroth:latest \
  --cache-from=type=registry,ref=isundaylee/istaroth:localbuildcache \
  --cache-to=type=registry,ref=isundaylee/istaroth:localbuildcache,mode=max \
  --push .

docker buildx build \
  --platform linux/amd64 \
  -t isundaylee/istaroth-frontend:latest \
  --cache-from=type=registry,ref=isundaylee/istaroth-frontend:localbuildcache \
  --cache-to=type=registry,ref=isundaylee/istaroth-frontend:localbuildcache,mode=max \
  --push ./frontend
