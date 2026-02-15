#!/bin/bash

set -euo pipefail

WORKING_DIR=$(PWD)
TEXT_PATH=$1
CHECKPOINT_PATH=$2

if [[ -z "$TEXT_PATH" || -z "$CHECKPOINT_PATH" ]]; then
  echo "Usage: $0 <text_path> <checkpoint_path>"
  exit 1
fi

if [[ -z "${REMOTE_HOST:-}" || -z "${REMOTE_PORT:-}" ]]; then
  POD_LINE=$(runpodctl get pod --allfields | grep "istaroth-checkpoint-builder" | grep "RUNNING" | head -1 || true)
  if [[ -z "$POD_LINE" ]]; then
    echo "No running pod named istaroth-checkpoint-builder found. Run runpodctl get pod to list pods."
    exit 1
  fi
  _re='([0-9]+\.[0-9]+\.[0-9]+\.[0-9]+):([0-9]+)->22'
  if [[ "$POD_LINE" =~ $_re ]]; then
    export REMOTE_HOST="${BASH_REMATCH[1]}"
    export REMOTE_PORT="${BASH_REMATCH[2]}"
  else
    echo "Pod found but no SSH port (22/tcp) exposed. Create pod with --ports 22/tcp."
    exit 1
  fi
fi

# istaroth+venv on disk (/dev/shm has noexec); text+checkpoint on ram-disk for fast I/O
WORK_ROOT=/root/checkpoint-build
DATA_ROOT=/dev/shm/checkpoint-build
ssh -p $REMOTE_PORT root@$REMOTE_HOST "mkdir -p $WORK_ROOT $DATA_ROOT && ([[ -d $WORK_ROOT/istaroth ]] || (cd $WORK_ROOT && git clone https://github.com/isundaylee/istaroth.git istaroth))"
ssh -p $REMOTE_PORT root@$REMOTE_HOST "cd $WORK_ROOT/istaroth && git fetch origin main && git reset --hard origin/main"
ssh -p $REMOTE_PORT root@$REMOTE_HOST "cd $WORK_ROOT/istaroth && ([[ -d env ]] || python3 -m venv env) && env/bin/pip install -r requirements.txt"
ssh -p $REMOTE_PORT root@$REMOTE_HOST "rm -rf $DATA_ROOT/text $DATA_ROOT/checkpoint"

# Compress the folder $TEXT_PATH into a tar.gz file locally
(cd $TEXT_PATH && COPYFILE_DISABLE=1 tar --exclude='**/._*' --no-xattrs --exclude 'text.tar.gz' -czf "text.tar.gz" .)
ssh -p $REMOTE_PORT root@$REMOTE_HOST "mkdir -p $DATA_ROOT/text"
scp -P $REMOTE_PORT $TEXT_PATH/text.tar.gz root@$REMOTE_HOST:$DATA_ROOT/text/
ssh -p $REMOTE_PORT root@$REMOTE_HOST "cd $DATA_ROOT/text && tar -xzf text.tar.gz && rm text.tar.gz"

# Build the checkpoint (text+checkpoint on ram-disk)
ssh -p $REMOTE_PORT root@$REMOTE_HOST "cd $WORK_ROOT/istaroth && env/bin/python3 scripts/rag_tools.py build $DATA_ROOT/text $DATA_ROOT/checkpoint"

rm -rf $CHECKPOINT_PATH
scp -P $REMOTE_PORT -r root@$REMOTE_HOST:$DATA_ROOT/checkpoint/ $CHECKPOINT_PATH
cp -r $TEXT_PATH $CHECKPOINT_PATH/text
(cd $TEXT_PATH && git rev-parse HEAD > $WORKING_DIR/$CHECKPOINT_PATH/text.git_commit)
(cd $TEXT_PATH && git diff HEAD > $WORKING_DIR/$CHECKPOINT_PATH/text.git_diff)
(cd $CHECKPOINT_PATH && COPYFILE_DISABLE=1 tar --exclude='**/._*' -czf "../$(basename $CHECKPOINT_PATH).tar.gz" .)

echo "Checkpoint built successfully at $CHECKPOINT_PATH & $CHECKPOINT_PATH.tar.gz"
