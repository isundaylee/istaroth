#!/bin/bash

# Enable strict mode
set -euo pipefail

TEXT_PATH=$1
CHECKPOINT_PATH=$2

if [[ -z "$TEXT_PATH" || -z "$CHECKPOINT_PATH" ]]; then
  echo "Usage: $0 <text_path> <checkpoint_path>"
  exit 1
fi

# Clone git repo if it doesn't exist
ssh -p $REMOTE_PORT root@$REMOTE_HOST "[[ -e istorath ]] || git clone https://github.com/isundaylee/istorath.git"
ssh -p $REMOTE_PORT root@$REMOTE_HOST "cd istorath && ([[ -e env ]] || python3 -m venv env)"
ssh -p $REMOTE_PORT root@$REMOTE_HOST "cd istorath && env/bin/pip install -r requirements.txt"

# Compress the folder $TEXT_PATH into a tar.gz file locally
(cd $TEXT_PATH && COPYFILE_DISABLE=1 tar --exclude='**/._*' --exclude 'text.tar.gz' -czf "text.tar.gz" .)
ssh -p $REMOTE_PORT root@$REMOTE_HOST "rm -rf text && mkdir text"
scp -P $REMOTE_PORT $TEXT_PATH/text.tar.gz root@$REMOTE_HOST:text/text.tar.gz
ssh -p $REMOTE_PORT root@$REMOTE_HOST "cd text && tar -xzf text.tar.gz && rm text.tar.gz"

# Build the checkpoint
ssh -p $REMOTE_PORT root@$REMOTE_HOST "cd istorath && \
    rm -rf ../checkpoint && \
    ISTORATH_DOCUMENT_STORE=../checkpoint env/bin/python3 scripts/rag_tools.py add-documents ../text"

rm -rf $CHECKPOINT_PATH
scp -P $REMOTE_PORT -r root@$REMOTE_HOST:checkpoint/ $CHECKPOINT_PATH
cp -r $TEXT_PATH $CHECKPOINT_PATH/text
(cd $CHECKPOINT_PATH && COPYFILE_DISABLE=1 tar --exclude='**/._*' -czf "../$(basename $CHECKPOINT_PATH).tar.gz" .)
